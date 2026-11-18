"""CurrentUser DPAPI tests with fake passwords only; no user credentials read."""
from dataclasses import replace
from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT/'src'))
from card_migration_system.persistence import mysql_connection as mysql
from card_migration_system.persistence import protected_password as store

SECRET='fake-application-password-test-123'
BINDING={'host':'db.example.test','port':25926,'database':'test_db','username':'cardmig_app'}


class PasswordStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.path=self.root/'var/secrets/app.dpapi'

    @unittest.skipUnless(os.name=='nt','DPAPI requires Windows')
    def test_real_current_user_encryption_roundtrip_and_endpoint_binding(self):
        store.save_password(self.path,SECRET,BINDING)
        self.assertNotIn(SECRET.encode(),self.path.read_bytes())
        self.assertEqual(store.load_password(self.path,BINDING),SECRET)
        with self.assertRaisesRegex(store.SecretError,'binding_mismatch'):
            store.load_password(self.path,{**BINDING,'host':'other.example.test'})
        before=self.path.read_bytes()
        with self.assertRaises(FileExistsError):store.save_password(self.path,'replacement',BINDING)
        self.assertEqual(self.path.read_bytes(),before)

    def test_root_is_never_persisted(self):
        with self.assertRaisesRegex(store.SecretError,'root_password_must_not_be_saved'):
            store.save_password(self.path,SECRET,{**BINDING,'username':'root'})
        self.assertFalse(self.path.exists())

    def test_plaintext_or_invalid_file_is_not_loaded(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_bytes(SECRET.encode())
        with self.assertRaisesRegex(store.SecretError,'file_invalid'):store.load_password(self.path,BINDING)

    def test_environment_password_keeps_priority_and_does_not_read_store(self):
        config=mysql.ConnectionConfig('db.example.test',25926,'test_db','cardmig_app','CARDMIG_MYSQL_APP_PASSWORD',5,10,'verify_identity','', 'var/secrets/app.dpapi')
        with patch.object(store,'load_password') as load:
            self.assertEqual(mysql.password_for(config,{config.password_env:SECRET}),SECRET)
        load.assert_not_called()

    @unittest.skipUnless(os.name=='nt','DPAPI requires Windows')
    def test_configured_protected_password_is_used_without_environment_variable(self):
        store.save_password(self.path,SECRET,BINDING)
        config=mysql.ConnectionConfig('db.example.test',25926,'test_db','cardmig_app','CARDMIG_MYSQL_APP_PASSWORD',5,10,'verify_identity','', 'var/secrets/app.dpapi')
        with patch.object(mysql,'PROJECT',self.root):
            self.assertEqual(mysql.password_for(config,{}),SECRET)
            self.assertNotIn('mysql_password_missing',mysql.pending(config,{}))
            with self.assertRaisesRegex(mysql.CheckError,'path_invalid'):
                mysql.secret_path(replace(config,password_file='../outside-secret'))


if __name__=='__main__':unittest.main()
