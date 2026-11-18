"""Exercise cloud backup/restore branches with explicit local SQLite engines.

These are filesystem/row-transfer integration tests, NOT native MySQL tests.
No cloud credentials, model calls, or existing runtime data are used.
"""
from dataclasses import replace
from pathlib import Path
import json
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sqlalchemy import select, text

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'src'))
from test_scaffold import copy_fixture
from card_migration_system.config import load_settings
from card_migration_system.application.service import Service, ServiceError
from card_migration_system.application.accounts import AccountService
from card_migration_system.persistence.accounts import AuthSession, User
from card_migration_system.persistence.database import initialize, engine_for, transaction
from card_migration_system.persistence import backup, database


class MySQLArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.project = copy_fixture(Path(self.temp.name))
        shutil.copyfile(PROJECT / 'requirements.lock', self.project / 'requirements.lock')
        shutil.copytree(PROJECT / 'migrations', self.project / 'migrations', ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copytree(PROJECT / 'docs/deployment/mysql_handoff_v2', self.project / 'docs/deployment/mysql_handoff_v2')
        self.settings = replace(load_settings(project_root=self.project, environ={}), auth_mode='multi_user')
        initialize(self.settings)
        self.service = Service(self.settings);self.addCleanup(self.service.close)
        self.user = AccountService(self.service).create_user({'username': 'tester', 'password': 'Temporary-fixture-password-123'}, bootstrap=True)
        self.input = self.service.create_input({'filename': 'Example.vue', 'source': '<template><p>中文</p></template>'}, owner_id=self.user['id'])
        with transaction(self.service.engine) as session:
            session.add(AuthSession(id='a' * 32, user_id=self.user['id'], token_sha256='b' * 64,
                                    origin='http://127.0.0.1:8790', created_at=1.0, expires_at=9999999999.0, revoked_at=None))
        self.cloud = replace(self.settings, database_backend='mysql')

    def archive(self):
        original = Service
        simulated = SimpleNamespace(engine=self.service.engine, storage=self.service.storage,
                                    HEALTH_SECONDS=self.service.HEALTH_SECONDS, close=lambda: None,
                                    implementation_binding=self.service.implementation_binding)
        def service(settings):
            return simulated if settings.database_backend == 'mysql' else original(settings)
        with patch.object(backup, 'Service', side_effect=service):
            return backup.create_backup(self.cloud, backup_id='simulated-cloud-backup')

    def target(self):
        local = replace(self.settings, runtime_dir=self.project / 'var/cloud-db-test',
                        artifact_dir=self.project / 'var/artifacts/cloud-db-test')
        initialize(local)
        engine = engine_for(local.business_database);self.addCleanup(engine.dispose)
        destination = replace(self.cloud, runtime_dir=self.project / 'var/restored-cloud-client',
                              artifact_dir=self.project / 'var/artifacts/restored-cloud-client')
        return engine, destination

    def test_cloud_snapshot_keeps_registered_files_and_can_be_verified_offline(self):
        result = self.archive()
        self.assertEqual(result['status'], 'backup_created')
        self.assertEqual(backup.verify_backup(self.cloud, result['backup_id'])['status'], 'backup_verified')
        folder = self.project / 'var/backups' / result['backup_id']
        manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['source_database_backend'], 'mysql')
        self.assertIn('db/business.sqlite3', manifest['files'])
        self.assertTrue(any(path.startswith('artifacts/') for path in manifest['files']))
        self.assertFalse((folder / '.incomplete').exists())

    def test_restore_into_empty_target_preserves_account_and_files_but_revokes_sessions(self):
        archived = self.archive();engine, destination = self.target()
        with patch.object(database, 'engine_for_settings', return_value=engine):
            result = backup.restore_backup(destination, archived['backup_id'])
        self.assertEqual(result['database_backend'], 'mysql')
        self.assertTrue(result['sessions_revoked'])
        with transaction(engine) as session:
            self.assertEqual(session.get(User, self.user['id']).username, 'tester')
            self.assertIsNotNone(session.get(AuthSession, 'a' * 32).revoked_at)
            relative, fingerprint = session.execute(text('SELECT relative_path, sha256 FROM source_inputs')).one()
        from card_migration_system.application.storage import Storage
        self.assertIn('中文'.encode(), Storage(destination.artifact_dir).read(relative, fingerprint))
        self.assertFalse((destination.runtime_dir / '.restore-in-progress').exists())
        self.assertFalse((destination.runtime_dir / 'business.sqlite3').exists())
        with transaction(self.service.engine) as session:
            self.assertIsNone(session.get(AuthSession, 'a' * 32).revoked_at)

    def test_nonempty_cloud_target_is_not_overwritten_or_installed(self):
        archived = self.archive();engine, destination = self.target()
        with engine.begin() as connection:
            connection.execute(text('INSERT INTO source_inputs (id,filename,relative_path,sha256) VALUES (:id,:name,:path,:hash)'),
                               dict(id='existing', name='Keep.vue', path='keep.vue', hash='0' * 64))
        with patch.object(database, 'engine_for_settings', return_value=engine):
            with self.assertRaisesRegex(ServiceError, 'destination_not_empty'):
                backup.restore_backup(destination, archived['backup_id'])
        with engine.connect() as connection:
            self.assertEqual(connection.execute(text('SELECT id FROM source_inputs')).scalars().all(), ['existing'])
        self.assertFalse(destination.runtime_dir.exists());self.assertFalse(destination.artifact_dir.exists())

    def test_failed_transfer_keeps_marker_and_rolls_back_target(self):
        archived = self.archive();engine, destination = self.target()
        with patch.object(database, 'engine_for_settings', return_value=engine), \
             patch('card_migration_system.persistence.portable_database.copy_business_rows', side_effect=ValueError('injected-transfer-failure')):
            with self.assertRaisesRegex(ValueError, 'injected-transfer-failure'):
                backup.restore_backup(destination, archived['backup_id'])
        self.assertTrue((destination.runtime_dir / '.restore-in-progress').exists())
        with engine.connect() as connection:
            self.assertEqual(connection.execute(text('SELECT count(*) FROM users')).scalar(), 0)


if __name__ == '__main__':
    unittest.main()
