"""Offline runtime boundaries; these do not certify a live cloud connection."""
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import json
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'src'))
from card_migration_system.config import load_settings, ConfigurationError
from card_migration_system.persistence import database, mysql_connection

SECRET = 'mysql-test-secret-not-logged'


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'configs').mkdir()
        self.path = self.root / 'configs/system.toml'
        self.path.write_text((PROJECT / 'configs/mysql_multi_user.example.toml').read_text(encoding='utf-8'), encoding='utf-8')
        self.settings = load_settings(project_root=self.root, config_file=self.path, environ={})
        self.config = mysql_connection.ConnectionConfig('db.example.test', 25926, 'cardmig', 'cardmig_app',
                                                       'CARDMIG_MYSQL_PASSWORD', 5, 10, 'verify_identity', '')

    def test_opt_in_mysql_does_not_create_or_switch_sqlite_files(self):
        self.assertEqual(self.settings.database_backend, 'mysql')
        self.assertFalse((self.root / 'var').exists())
        self.assertIn('credentials redacted', self.settings.public_summary()['business_database'])

    def test_sqlite_defaults_still_work(self):
        self.path.write_text((PROJECT / 'configs/development.toml').read_text(encoding='utf-8'), encoding='utf-8')
        settings = load_settings(project_root=self.root, config_file=self.path, environ={})
        self.assertEqual(settings.database_backend, 'sqlite')
        self.assertIsNone(settings.mysql_connection_file)

    def test_rejects_mysql_file_escape_and_unexpected_fields(self):
        original = self.path.read_text(encoding='utf-8')
        for content in (original.replace('configs/mysql_connection.local.toml', '../outside.toml'),
                        original + '\npassword = "' + SECRET + '"\n',
                        original.replace('auth_mode = "multi_user"', 'auth_mode = "local"')):
            self.path.write_text(content, encoding='utf-8')
            with self.assertRaises(ConfigurationError) as caught:
                load_settings(project_root=self.root, config_file=self.path, environ={})
            self.assertNotIn(SECRET, str(caught.exception))

    def test_runtime_rejects_root_and_unverified_tls_before_network(self):
        for config, code in ((replace(self.config, username='root'), 'application_account'),
                             (replace(self.config, tls_mode='disabled'), 'verified_tls')):
            with patch.object(mysql_connection, 'load_config', return_value=config), patch.object(database, 'create_engine') as connect:
                with self.assertRaisesRegex(ValueError, code):
                    database.engine_for_settings(self.settings)
                connect.assert_not_called()

    def test_mysql_engine_uses_password_env_and_redacts_parameters(self):
        engine = SimpleNamespace()
        with patch.object(mysql_connection, 'load_config', return_value=self.config), \
             patch.object(mysql_connection, 'pending', return_value=[]), \
             patch.dict('os.environ', {self.config.password_env: SECRET}), \
             patch.object(database, 'create_engine', return_value=engine) as build, \
             patch.object(database.event, 'listens_for', return_value=lambda fn: fn):
            self.assertIs(database.engine_for_settings(self.settings), engine)
        url = build.call_args.args[0]
        self.assertEqual(url.drivername, 'mysql+pymysql')
        self.assertEqual(url.password, SECRET)
        self.assertNotIn(SECRET, str(url))
        self.assertTrue(build.call_args.kwargs['hide_parameters'])
        self.assertNotIn('check_same_thread', build.call_args.kwargs['connect_args'])
        self.assertTrue(build.call_args.kwargs['connect_args']['ssl'].check_hostname)
        self.assertLessEqual(len(engine._cardmig_mysql_lock), 64)

    def test_mysql_engine_accepts_explicit_ca_mode_without_claiming_hostname_verification(self):
        config=replace(self.config,tls_mode='verify_ca',ca_file='configs/test-ca.pem')
        import ssl
        context=ssl.create_default_context()
        with patch.object(mysql_connection,'load_config',return_value=config), \
             patch.object(mysql_connection,'pending',return_value=[]), \
             patch.object(mysql_connection.ssl,'create_default_context',return_value=context), \
             patch.dict('os.environ',{config.password_env:SECRET}), \
             patch.object(database,'create_engine',return_value=SimpleNamespace()) as build, \
             patch.object(database.event,'listens_for',return_value=lambda fn:fn):
            database.engine_for_settings(self.settings)
        tls=build.call_args.kwargs['connect_args']['ssl']
        self.assertFalse(tls.check_hostname);self.assertEqual(tls.verify_mode,ssl.CERT_REQUIRED)

    def test_missing_password_does_not_connect(self):
        with patch.object(mysql_connection, 'load_config', return_value=self.config), \
             patch.object(mysql_connection, 'pending', return_value=['mysql_password_missing']), \
             patch.object(database, 'create_engine') as connect:
            with self.assertRaisesRegex(ValueError, 'mysql_password_missing'):
                database.engine_for_settings(self.settings)
            connect.assert_not_called()

    def run_transaction(self, *, acquired=1, released=1, body_error=False):
        connection = Mock()
        connection.execute.side_effect = [Mock(scalar=lambda: acquired), Mock(scalar=lambda: released)]
        engine = SimpleNamespace(dialect=SimpleNamespace(name='mysql'), _cardmig_mysql_lock='test-lock',
                                 connect=Mock(return_value=connection))
        connection.__enter__ = Mock(return_value=connection)
        connection.__exit__ = Mock(return_value=False)
        session = Mock()
        session.__enter__ = Mock(return_value=session)
        session.__exit__ = Mock(return_value=False)
        @contextmanager
        def begin():
            yield
        session.begin = begin
        try:
            with patch.object(database, 'Session', return_value=session):
                with database.transaction(engine) as value:
                    self.assertIs(value, session)
                    if body_error:
                        raise RuntimeError('body failure')
        except Exception as error:
            return connection, error
        return connection, None

    def test_mysql_transaction_lock_is_released_after_success_and_body_failure(self):
        for fail in (False, True):
            connection, error = self.run_transaction(body_error=fail)
            self.assertEqual(connection.execute.call_count, 2)
            self.assertIn('RELEASE_LOCK', str(connection.execute.call_args.args[0]))
            connection.invalidate.assert_not_called()
            self.assertEqual(isinstance(error, RuntimeError), fail)

    def test_lock_unavailable_never_runs_or_releases_someone_elses_lock(self):
        connection, error = self.run_transaction(acquired=0)
        self.assertIn('lock_unavailable', str(error))
        self.assertEqual(connection.execute.call_count, 1)

    def test_lock_release_failure_discards_connection(self):
        connection, error = self.run_transaction(released=0)
        self.assertIn('release_failed', str(error))
        connection.invalidate.assert_called_once()

    def test_mysql_initialization_is_explicit_not_legacy_alembic(self):
        with patch.object(database, '_initialize_mysql') as bootstrap, patch.object(database, 'engine_for') as sqlite:
            database._upgrade(self.settings)
            bootstrap.assert_called_once_with(self.settings)
            sqlite.assert_not_called()

    def test_sqlite_engine_still_commits_and_rolls_back(self):
        engine = database.engine_for(self.root / 'test.sqlite3')
        self.addCleanup(engine.dispose)
        with engine.begin() as connection:
            connection.exec_driver_sql('CREATE TABLE x (id INTEGER PRIMARY KEY)')
        with database.transaction(engine) as session:
            session.execute(database.text('INSERT INTO x VALUES (1)'))
        with self.assertRaises(RuntimeError):
            with database.transaction(engine) as session:
                session.execute(database.text('INSERT INTO x VALUES (2)'))
                raise RuntimeError('rollback')
        with engine.connect() as connection:
            self.assertEqual(connection.execute(database.text('SELECT id FROM x')).scalars().all(), [1])

    def bootstrap(self, *, tables=None, versions=None, nonempty=(), partial=False):
        from test_mysql_connection import FakeCursor
        reader = FakeCursor(self.config)
        reader.nonempty = set(nonempty)
        if partial:
            reader.tables = [row for row in reader.tables if row[0] == 'users']
        connection = Mock()
        connection.__enter__ = Mock(return_value=connection)
        connection.__exit__ = Mock(return_value=False)
        connection.connection.driver_connection.cursor.return_value = reader
        connection.execute.return_value.scalars.return_value.all.return_value = versions or []
        engine = Mock();engine.connect.return_value = connection
        session = Mock();session.execute.return_value.first.return_value = None
        @contextmanager
        def serialized(_engine):
            yield session
        error = None
        settings = replace(self.settings, project_root=PROJECT)
        with patch.object(database, 'engine_for_settings', return_value=engine), \
             patch.object(mysql_connection, 'load_config', return_value=self.config), \
             patch.object(database, 'inspect', return_value=SimpleNamespace(get_table_names=lambda: tables or [])), \
             patch.object(database, 'transaction', serialized), patch.object(database, 'require_schema'):
            try:
                database._initialize_mysql(settings)
            except ValueError as caught:
                error = caught
        return connection, session, error

    def test_empty_mysql_initialization_creates_only_reviewed_34_tables_and_stamps(self):
        connection, session, error = self.bootstrap()
        self.assertIsNone(error)
        statements = [call.args[0] for call in connection.exec_driver_sql.call_args_list]
        self.assertEqual(len(statements), 34)
        self.assertTrue(all(sql.startswith('CREATE TABLE `') for sql in statements))
        self.assertFalse(any('DROP TABLE' in sql or 'CREATE DATABASE' in sql for sql in statements))
        writes = [str(call.args[0]) for call in session.execute.call_args_list if str(call.args[0]).startswith('INSERT')]
        self.assertEqual(len(writes), 1)
        self.assertIn('alembic_version', writes[0])

    def test_prepared_empty_mysql_tables_are_not_recreated(self):
        connection, session, error = self.bootstrap(tables=['already_created'])
        self.assertIsNone(error);connection.exec_driver_sql.assert_not_called()
        self.assertTrue(any(str(call.args[0]).startswith('INSERT') for call in session.execute.call_args_list))

    def test_initialized_mysql_does_not_rewrite_versions_or_business_rows(self):
        connection, session, error = self.bootstrap(tables=['already_created'], versions=[database.HEAD], nonempty=('alembic_version', 'users'))
        self.assertIsNone(error);connection.exec_driver_sql.assert_not_called();session.execute.assert_not_called()

    def test_partial_mysql_schema_is_not_repaired_or_stamped_silently(self):
        connection, session, error = self.bootstrap(tables=['users'], partial=True)
        self.assertIn('manual_review', str(error))
        connection.exec_driver_sql.assert_not_called();session.execute.assert_not_called()

    def test_unknown_or_nonempty_mysql_is_not_stamped(self):
        for versions, nonempty in ((['other_version'], ()), ([], ('users',))):
            connection, session, error = self.bootstrap(tables=['already_created'], versions=versions, nonempty=nonempty)
            self.assertIn('refuse_stamp', str(error))
            connection.exec_driver_sql.assert_not_called();session.execute.assert_not_called()


if __name__ == '__main__':
    unittest.main()
