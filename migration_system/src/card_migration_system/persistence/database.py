"""Short SQLite transactions, explicit Alembic initialization, no import-time DB."""
from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session
from .runtime_lock import execution_guard


HEAD = "0008_multi_user"


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


@contextmanager
def transaction(engine):
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
