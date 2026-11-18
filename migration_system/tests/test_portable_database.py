"""Real temporary SQLite transfers; native MySQL roundtrips remain a live gate."""
from dataclasses import replace
from pathlib import Path
import sys
import tempfile
import unittest

from sqlalchemy import JSON, MetaData, select, text

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'src'))
from card_migration_system.config import load_settings
from card_migration_system.persistence.database import _upgrade, engine_for, transaction
from card_migration_system.persistence.portable_database import copy_business_rows, snapshot_to_sqlite


class PortableDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        base = load_settings(project_root=PROJECT, config_file='configs/multi_user.toml', environ={})
        self.settings = replace(base, runtime_dir=self.root / 'source', artifact_dir=self.root / 'artifacts')
        self.settings.runtime_dir.mkdir()
        _upgrade(self.settings)
        target = replace(self.settings, runtime_dir=self.root / 'target')
        target.runtime_dir.mkdir();_upgrade(target)
        self.source = engine_for(self.settings.business_database)
        self.target = engine_for(target.business_database)
        self.addCleanup(self.source.dispose);self.addCleanup(self.target.dispose)
        self.metadata = MetaData();self.metadata.reflect(bind=self.source)

    def populate(self, *, long_name=False, bad_json=False):
        tables = self.metadata.tables
        with self.source.begin() as connection:
            connection.execute(tables['users'].insert(), dict(
                id='u' * 32, username='x' * (65 if long_name else 5), username_normalized='admin',
                display_name='迁移测试 🧪', password_hash='fake-test-hash-never-a-real-password',
                role='admin', is_active=True, must_change_password=False,
                created_at=1794995830.1234567, password_changed_at=1794995830.2345678))
            connection.execute(tables['source_inputs'].insert(), dict(
                id='s' * 32, filename='测试.vue', relative_path='inputs/test.vue', sha256='0' * 64))
            connection.execute(tables['tasks'].insert(), dict(id='t' * 32, input_id='s' * 32, name='数据迁移'))
            connection.execute(tables['runs'].insert(), dict(
                id='r' * 32, task_id='t' * 32, idempotency_key='key', request_sha256='1' * 64,
                request={'unicode': '中文', 'nested': [True, None, {'v': float('nan') if bad_json else 1.5}]},
                binding={'fixture': 'explicit-test'}, status='completed', outcome='passed',
                final_revision_id=None, cancel_requested=False, stop_reason='fixture', created_at=1794995830.3456788))
            # Lexical ID ordering deliberately puts the child BEFORE its parent.
            connection.execute(tables['artifact_revisions'].insert(), dict(
                id='z-parent', run_id='r' * 32, parent_id=None, relative_path='parent.san',
                sha256='2' * 64, source_kind='fixture', fixture_assertions={}))
            connection.execute(tables['artifact_revisions'].insert(), dict(
                id='a-child', run_id='r' * 32, parent_id='z-parent', relative_path='child.san',
                sha256='3' * 64, source_kind='fixture', fixture_assertions={}))
            connection.execute(tables['run_events'].insert(), dict(
                run_id='r' * 32, event_key='event-1', kind='fixture', details={'flag': False}))

    def copy(self, **kwargs):
        with self.source.connect() as source, self.target.begin() as destination:
            return copy_business_rows(source, destination, PROJECT, **kwargs)

    def target_rows(self, table):
        with self.target.connect() as connection:
            return list(connection.execute(select(self.metadata.tables[table])).mappings())

    def test_roundtrip_all_34_tables_json_unicode_time_boolean_and_self_fk(self):
        self.populate()
        result = self.copy()
        self.assertEqual(len(result['tables']), 33)
        self.assertEqual(result['rows'], 7)
        self.assertEqual(self.target_rows('users')[0]['display_name'], '迁移测试 🧪')
        self.assertEqual(self.target_rows('users')[0]['created_at'], 1794995830.1234567)
        self.assertEqual(self.target_rows('runs')[0]['request'], {'unicode': '中文', 'nested': [True, None, {'v': 1.5}]})
        self.assertEqual(len(self.target_rows('artifact_revisions')), 2)
        self.assertEqual(self.target_rows('run_events')[0]['id'], 1)
        self.assertEqual(self.target_rows('alembic_version')[0]['version_num'], '0008_multi_user')
        with self.target.connect() as connection:
            self.assertEqual(connection.exec_driver_sql('PRAGMA foreign_key_check').all(), [])

    def test_nonempty_destination_is_rejected_without_overwrite(self):
        self.populate();self.copy()
        before = self.target_rows('users')
        with self.assertRaisesRegex(ValueError, 'destination_not_empty'):
            self.copy()
        self.assertEqual(self.target_rows('users'), before)

    def test_value_too_long_is_not_truncated_and_partial_rows_roll_back(self):
        self.populate(long_name=True)
        with self.assertRaisesRegex(ValueError, 'string_does_not_fit'):
            self.copy()
        self.assertEqual(self.target_rows('users'), [])
        self.assertEqual(self.target_rows('source_inputs'), [])

    def test_nonstandard_json_is_rejected_before_committing_destination(self):
        self.populate(bad_json=True)
        with self.assertRaisesRegex(ValueError, 'not_serializable'):
            self.copy()
        self.assertEqual(self.target_rows('users'), [])
        self.assertEqual(self.target_rows('runs'), [])

    def test_transfer_bounds_roll_back_all_destination_rows(self):
        self.populate()
        for limits in ({'max_rows': 2}, {'max_bytes': 32}):
            with self.assertRaisesRegex(ValueError, 'transfer_limit'):
                self.copy(**limits)
            self.assertEqual(self.target_rows('users'), [])

    def test_real_trigger_mutation_is_detected_by_readback_hash(self):
        self.populate()
        with self.target.begin() as connection:
            connection.exec_driver_sql("CREATE TRIGGER tamper AFTER INSERT ON users BEGIN UPDATE users SET display_name='changed' WHERE id=NEW.id; END")
        with self.assertRaisesRegex(ValueError, 'roundtrip_mismatch'):
            self.copy()
        self.assertEqual(self.target_rows('users'), [])

    def test_unexpected_table_prevents_copy(self):
        self.populate()
        with self.target.begin() as connection:
            connection.exec_driver_sql('CREATE TABLE unexpected (id INTEGER PRIMARY KEY)')
        with self.assertRaisesRegex(ValueError, 'table_inventory'):
            self.copy()
        self.assertEqual(self.target_rows('users'), [])

    def test_sql_null_and_json_null_are_not_conflated(self):
        self.populate()
        table = self.metadata.tables['attempts']
        with self.source.begin() as connection:
            values = dict(id='json-null', run_id='r' * 32, kind='fixture', status='done',
                          request_sha256='a' * 64, result=JSON.NULL, started_at=1.0, model_tokens=None)
            connection.execute(table.insert(), values)
            connection.execute(text('INSERT INTO attempts (id,run_id,kind,status,request_sha256,result,started_at,model_tokens) VALUES (:id,:run_id,:kind,:status,:hash,NULL,1,NULL)'),
                               dict(id='sql-null', run_id='r' * 32, kind='fixture', status='done', hash='b' * 64))
            # Non-null SQL JSON columns can legitimately contain the JSON null document.
            connection.execute(self.metadata.tables['runs'].update().values(binding=JSON.NULL))
        self.copy()
        for engine in (self.source, self.target):
            with engine.connect() as connection:
                self.assertEqual(connection.execute(text('SELECT id,result IS NULL FROM attempts ORDER BY id')).all(), [('json-null', 0), ('sql-null', 1)])
                self.assertEqual(connection.execute(text('SELECT binding IS NULL FROM runs')).scalar(), 0)

    def test_snapshot_to_sqlite_preserves_format_and_refuses_overwrite(self):
        self.populate()
        destination = self.root / 'archive/db/business.sqlite3'
        with transaction(self.source) as session:
            result = snapshot_to_sqlite(self.settings, session, destination)
        self.assertEqual(result['rows'], 7)
        saved = destination.read_bytes()
        with transaction(self.source) as session:
            with self.assertRaisesRegex(ValueError, 'destination_exists'):
                snapshot_to_sqlite(self.settings, session, destination)
        self.assertEqual(destination.read_bytes(), saved)


if __name__ == '__main__':
    unittest.main()
