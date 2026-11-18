"""Explicit SQLite/MySQL engines, short serialized transactions and initialization."""
from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session
from .runtime_lock import execution_guard


HEAD = "0008_multi_user"


class SchemaReviewError(ValueError):
    """Carry schema metadata differences, never credentials or business rows."""
    def __init__(self, review):
        super().__init__('mysql_schema_requires_manual_review')
        self.review = review


def engine_for(path):
    engine = create_engine(URL.create("sqlite", database=str(Path(path))),
                           connect_args={"check_same_thread": False, "timeout": 5})

    @event.listens_for(engine, "connect")
    def configure(connection, _):
        connection.isolation_level = None
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")

    @event.listens_for(engine, "begin")
    def begin(connection):
        # Serial short transactions for the deliberately single-worker slice.
        connection.exec_driver_sql("BEGIN IMMEDIATE")
    return engine


def engine_for_settings(settings, *, allow_admin=False):
    if settings.database_backend == 'sqlite':
        return engine_for(settings.business_database)
    from .mysql_connection import load_config, pending, connect_options, version_review, password_for
    config = load_config(settings.mysql_connection_file)
    if config.tls_mode not in ('verify_identity', 'verify_ca'):
        raise ValueError('mysql_runtime_requires_verified_tls')
    if config.username.lower() == 'root' and not allow_admin:
        raise ValueError('mysql_runtime_requires_application_account')
    missing = pending(config, os.environ)
    if missing:
        raise ValueError('mysql_configuration_pending:' + ','.join(missing))
    options = connect_options(config, password_for(config, os.environ))
    url = URL.create('mysql+pymysql', username=options.pop('user'),
                     password=options.pop('password'), host=options.pop('host'),
                     port=options.pop('port'), database=options.pop('database'))
    engine = create_engine(url, connect_args=options, pool_pre_ping=True,
                           pool_recycle=300, isolation_level='READ COMMITTED',
                           hide_parameters=True)
    engine._cardmig_mysql_lock = 'cardmig:' + sha256(config.name.encode()).hexdigest()[:48]

    @event.listens_for(engine, 'connect')
    def configure_mysql(connection, _):
        with connection.cursor() as cursor:
            cursor.execute('SELECT VERSION(), @@SESSION.sql_mode')
            version, modes = cursor.fetchone()
            version_review(version)
            if not {'STRICT_TRANS_TABLES', 'STRICT_ALL_TABLES'} & set(modes.split(',')):
                raise ValueError('mysql_strict_mode_required')
            cursor.execute("SHOW SESSION STATUS LIKE 'Ssl_cipher'")
            cipher = cursor.fetchone()
            if not cipher or not cipher[1]:
                raise ValueError('mysql_tls_not_negotiated')
    return engine


@contextmanager
def transaction(engine):
    if engine.dialect.name == 'mysql':
        # Preserve SQLite's short-transaction serialization across API/Worker
        # processes. A server-side, connection-scoped lock avoids quota races;
        # never retry an outcome-unknown write automatically.
        with engine.connect() as connection:
            name = engine._cardmig_mysql_lock
            acquired = connection.execute(text('SELECT GET_LOCK(:name, 5)'), {'name': name}).scalar()
            connection.commit()
            if acquired != 1:
                raise ValueError('mysql_transaction_lock_unavailable')
            try:
                with Session(connection, expire_on_commit=False) as session:
                    with session.begin():
                        yield session
            finally:
                try:
                    connection.rollback()
                    released = connection.execute(text('SELECT RELEASE_LOCK(:name)'), {'name': name}).scalar()
                    connection.commit()
                    if released != 1:
                        raise ValueError('mysql_transaction_lock_release_failed')
                except Exception:
                    connection.invalidate()  # Never pool a connection retaining our lock.
                    raise
        return
    with Session(engine, expire_on_commit=False) as session:
        with session.begin():
            yield session


def require_schema(engine):
    with engine.connect() as connection:
        if "alembic_version" not in inspect(connection).get_table_names():
            raise ValueError("database_not_initialized")
        if connection.execute(text("SELECT version_num FROM alembic_version")).scalar() != HEAD:
            raise ValueError("database_schema_mismatch")


def initialize(settings):
    settings.runtime_dir.mkdir(parents=True, exist_ok=True)
    with execution_guard(settings.runtime_dir):
        if (settings.runtime_dir / ".restore-in-progress").exists():
            raise ValueError("restore_incomplete_requires_review")
        _upgrade(settings)


def _upgrade(settings):
    if settings.database_backend == 'mysql':
        return _initialize_mysql(settings)
    engine = engine_for(settings.business_database)
    try:
        with engine.begin() as connection:
            tables = inspect(connection).get_table_names()
            if tables and "alembic_version" not in tables:
                raise ValueError("refuse_unknown_existing_database")
            config = Config()
            config.set_main_option("script_location", str(settings.project_root / "migrations"))
            config.attributes["connection"] = connection
            command.upgrade(config, HEAD)
        require_schema(engine)
    finally:
        engine.dispose()


def _initialize_mysql(settings):
    """Only explicit init-db may bootstrap/stamp the reviewed empty schema.

    Do not replay SQLite-specific historical migrations against MySQL, and do
    not run destructive/drop/repair DDL on a partially initialized database.
    """
    from .mysql_connection import inspect_schema
    root = settings.project_root / 'docs/deployment/mysql_handoff_v2'
    snapshot = json.loads((root / 'schema_multi_user.json').read_text(encoding='utf-8'))
    sql = (root / 'schema_multi_user.sql').read_text(encoding='utf-8')
    if (snapshot['schema_basis'] != HEAD or snapshot['table_count'] != 34
            or sha256(sql.encode()).hexdigest() != snapshot['schema_sql_sha256']):
        raise ValueError('mysql_bootstrap_artifact_drift')
    engine = engine_for_settings(settings, allow_admin=True)
    try:
        from .mysql_connection import load_config
        config = load_config(settings.mysql_connection_file)
        with engine.connect() as connection:
            tables = inspect(connection).get_table_names()
            connection.rollback()
            if not tables:
                # The database itself must already exist; use only CREATE TABLE.
                statements = sql.split(';')[2:]
                for statement in statements:
                    statement = statement.strip()
                    if not statement:
                        continue
                    if not statement.startswith('CREATE TABLE `'):
                        raise ValueError('mysql_bootstrap_unexpected_statement')
                    connection.exec_driver_sql(statement)
                connection.commit()  # MySQL DDL is not an atomic migration.
            reader = connection.connection.driver_connection
            with reader.cursor() as cursor:
                result = inspect_schema(cursor, config, snapshot)
            connection.rollback()
            if result['differences_total']:
                raise SchemaReviewError(result)
            versions = connection.execute(text('SELECT version_num FROM alembic_version')).scalars().all()
            connection.rollback()
            if versions == [HEAD]:
                return
            if versions or not result['prepared_empty_database']:
                raise ValueError('mysql_refuse_stamp_nonempty_or_unknown_database')
        with transaction(engine) as session:
            # Recheck emptiness under the same DB transaction mutex before stamping.
            for table in sorted(snapshot['tables'], key=lambda t: t['name']):
                if session.execute(text(f"SELECT 1 FROM `{table['name']}` LIMIT 1")).first():
                    raise ValueError('mysql_refuse_stamp_nonempty_or_unknown_database')
            session.execute(text('INSERT INTO alembic_version (version_num) VALUES (:head)'), {'head': HEAD})
        require_schema(engine)
    finally:
        engine.dispose()
