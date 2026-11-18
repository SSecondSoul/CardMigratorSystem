"""Offline account-provisioning boundary tests. No live credentials or SQL."""
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT/'src'))
from card_migration_system.persistence import mysql_connection as mysql
from card_migration_system.interfaces import accounts_cli
import pymysql

spec=importlib.util.spec_from_file_location('mysql_app_provision',PROJECT/'scripts/provision_mysql_app.py')
script=importlib.util.module_from_spec(spec);spec.loader.exec_module(script)
FAKE_PASSWORD='fake-database-application-password-never-print'
ROOT_PASSWORD='fake-root-password-never-save'


class RootCursor:
    def __init__(self,*,existing=False):self.rows=[];self.queries=[];self.existing=existing
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def execute(self,sql,params=()):
        self.queries.append((sql,params))
        if sql.startswith('SELECT VERSION'):self.rows=[('8.0.30-cynos-test','root@192.0.2.1',0)]
        elif sql.startswith('SELECT version_num'):self.rows=[('0008_multi_user',)]
        elif sql.startswith('SHOW GRANTS'):
            if not self.existing and not any(q.startswith('CREATE USER') for q,p in self.queries):
                raise pymysql.err.OperationalError(1141,'no such grant')
            self.rows=[('GRANT USAGE ON *.* TO `cardmig_app`@`192.0.2.1`',),
                       ('GRANT SELECT, INSERT, UPDATE, DELETE ON `cardmig`.* TO `cardmig_app`@`192.0.2.1`',)]
        elif sql.startswith(('CREATE USER','GRANT ')):self.rows=[]
        else:raise AssertionError('Unexpected SQL')
    def fetchone(self):return self.rows[0]
    def fetchall(self):return self.rows


class ProvisionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        (self.root/'configs').mkdir()
        schema=self.root/'docs/deployment/mysql_handoff_v2/schema_multi_user.json'
        schema.parent.mkdir(parents=True);schema.write_text('{}',encoding='utf-8')
        (self.root/'configs/mysql_multi_user.example.toml').write_text(
            (PROJECT/'configs/mysql_multi_user.example.toml').read_text(encoding='utf-8'),encoding='utf-8')
        self.config=mysql.ConnectionConfig('db.example.test',25926,'cardmig','root','ROOT_PASSWORD',5,10,'verify_ca','ca.pem')
        self.cursor=RootCursor()
        self.root_connection=Mock(cursor=Mock(return_value=self.cursor))
        app_cursor=Mock();app_cursor.__enter__=Mock(return_value=app_cursor);app_cursor.__exit__=Mock(return_value=False)
        def app_execute(sql,params=()):
            if sql.startswith('SELECT CURRENT_USER'):app_cursor.fetchone.return_value=('cardmig_app@192.0.2.1','cardmig')
            elif sql.startswith('SELECT @@GLOBAL.partial_revokes'):app_cursor.fetchone.return_value=(0,)
            elif sql.startswith('SHOW GRANTS'):
                app_cursor.fetchall.return_value=[('GRANT SELECT, INSERT, UPDATE, DELETE ON `cardmig`.* TO `cardmig_app`@`192.0.2.1`',)]
            elif sql.startswith('SELECT version_num'):app_cursor.fetchall.return_value=[('0008_multi_user',)]
            else:raise AssertionError('Unexpected application SQL')
        app_cursor.execute.side_effect=app_execute
        self.application_connection=Mock(cursor=Mock(return_value=app_cursor))
        self.connect=Mock(side_effect=[self.root_connection,self.application_connection,Mock()])
        self.structure={'differences_total':0,'nonempty_tables':['alembic_version']}
        self.saved=[]
        def save(path,password,binding):
            self.saved.append((path,password,binding))
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'fake-encrypted-blob')
        patches=[patch.object(script,'PROJECT',self.root),patch.object(mysql,'PROJECT',self.root),
                 patch.object(script,'load_config',return_value=self.config),
                 patch.object(script,'inspect_schema',return_value=self.structure),
                 patch.object(script,'connect_options',side_effect=lambda config,pw:{'user':config.username,'password':pw}),
                 patch.object(script,'save_password',side_effect=save),
                 patch.object(script,'password_for',return_value=FAKE_PASSWORD),
                 patch.object(script.secrets,'token_urlsafe',return_value=FAKE_PASSWORD),
                 patch.object(pymysql,'connect',self.connect),
                 patch.dict(sys.modules,{'bootstrap_cloud_mysql':SimpleNamespace(native_checks=lambda one,two:{'rollback':True})})]
        for item in patches:item.start();self.addCleanup(item.stop)

    def run_provision(self):
        progress={'application_account_created':False,'secret_saved_encrypted':False}
        script.provision(self.root/'config.toml','cardmig_app',ROOT_PASSWORD,progress)
        return progress

    @unittest.skipUnless(sys.platform=='win32','local provisioning uses Windows DPAPI')
    def test_minimal_account_tls_source_and_independent_configs(self):
        progress=self.run_provision()
        self.assertEqual(progress['status'],'mysql_application_account_and_native_checks_passed')
        sql='\n'.join(q for q,p in self.cursor.queries)
        self.assertIn('REQUIRE SSL',sql)
        self.assertNotIn('DROP',sql);self.assertNotIn('TRUNCATE',sql);self.assertNotIn('ALL PRIVILEGES',sql)
        create=next(p for q,p in self.cursor.queries if q.startswith('CREATE USER'))
        self.assertEqual(create,('cardmig_app','192.0.2.1',FAKE_PASSWORD))
        runtime=(self.root/'configs/mysql_multi_user.local.toml').read_text(encoding='utf-8')
        self.assertIn('configs/mysql_app.local.toml',runtime)
        self.assertNotIn('configs/mysql_connection.local.toml',runtime)
        config=(self.root/'configs/mysql_app.local.toml').read_text(encoding='utf-8')
        self.assertIn('password_file',config)
        for content in (config,runtime,json.dumps(progress)):
            self.assertNotIn(FAKE_PASSWORD,content);self.assertNotIn(ROOT_PASSWORD,content)
        self.assertFalse((self.root/'var/multi_user').exists())

    @unittest.skipUnless(sys.platform=='win32','Windows-specific provisioning')
    def test_existing_local_config_stops_before_network(self):
        (self.root/'configs/mysql_app.local.toml').write_text('keep',encoding='utf-8')
        with self.assertRaisesRegex(mysql.CheckError,'files_exist'):self.run_provision()
        self.connect.assert_not_called();self.assertFalse(self.saved)

    @unittest.skipUnless(sys.platform=='win32','Windows-specific provisioning')
    def test_existing_account_is_never_reset(self):
        self.cursor.existing=True
        with self.assertRaisesRegex(mysql.CheckError,'account_already_exists'):self.run_provision()
        self.assertFalse(self.saved)
        self.assertFalse(any(q.startswith(('CREATE USER','GRANT ')) for q,p in self.cursor.queries))

    @unittest.skipUnless(sys.platform=='win32','Windows-specific provisioning')
    def test_nonempty_business_database_rejected(self):
        self.structure['nonempty_tables'].append('users')
        with self.assertRaisesRegex(mysql.CheckError,'fresh_database_expected'):self.run_provision()
        self.assertFalse(self.saved)

    @unittest.skipUnless(sys.platform=='win32','Windows-specific provisioning')
    def test_partial_failure_records_existing_account_without_configs(self):
        self.connect.side_effect=[self.root_connection,pymysql.err.OperationalError(1045,FAKE_PASSWORD)]
        progress={}
        with self.assertRaises(pymysql.MySQLError):
            script.provision(self.root/'config.toml','cardmig_app',ROOT_PASSWORD,progress)
        self.assertTrue(progress['application_account_created']);self.assertTrue(progress['secret_saved_encrypted'])
        self.assertNotIn(FAKE_PASSWORD,json.dumps(progress))
        self.assertFalse((self.root/'configs/mysql_app.local.toml').exists())

    def test_grants_reject_global_extra_missing_and_roles(self):
        good='GRANT SELECT, INSERT, UPDATE, DELETE ON `cardmig`.* TO `app`@`192.0.2.1`'
        script.check_grants([good],'cardmig')
        for bad in (good.replace('`cardmig`.*','*.*'),good+' WITH GRANT OPTION',
                    good.replace('DELETE','CREATE'),good.replace(', DELETE',''),
                    good.replace('`cardmig`.*','`another`.*'),'GRANT `some_role`@`%` TO `app`@`host`'):
            with self.subTest(bad=bad),self.assertRaises(mysql.CheckError):script.check_grants([bad],'cardmig')

    def test_database_underscores_never_expand_grant_scope(self):
        prefix='GRANT SELECT, INSERT, UPDATE, DELETE ON '
        suffix=' TO `app`@`192.0.2.1`'
        self.assertEqual(script.grant_resource('test_db'),r'`test\_db`.*')
        script.check_grants([prefix+r'`test\_db`.*'+suffix],'test_db')
        with self.assertRaises(mysql.CheckError):script.check_grants([prefix+'`test_db`.*'+suffix],'test_db')
        script.check_grants([prefix+'`test_db`.*'+suffix],'test_db',partial_revokes=True)
        with self.assertRaises(mysql.CheckError):
            script.check_grants([prefix+r'`test\_db`.*'+suffix],'test_db',partial_revokes=True)

    def test_default_plan_does_not_prompt_or_connect(self):
        output=io.StringIO()
        with patch.object(script.getpass,'getpass') as prompt,redirect_stdout(output):
            code=script.main(['--init-admin'])
        self.assertEqual(code,0);prompt.assert_not_called();self.connect.assert_not_called()
        self.assertTrue(json.loads(output.getvalue())['initialize_administrator'])

    def test_admin_reuses_existing_cli_and_failure_has_recovery_report(self):
        for admin_code in (0,2):
            output=io.StringIO()
            def prepared(config,user,password,progress):
                progress.update(status='mysql_application_account_and_native_checks_passed',stage='application_config_ready',
                                application_account_created=True,secret_saved_encrypted=True)
            with patch.object(script.sys.stdin,'isatty',return_value=True), \
                 patch.object(script.getpass,'getpass',return_value=ROOT_PASSWORD), \
                 patch.object(script,'provision',side_effect=prepared), \
                 patch.object(accounts_cli,'main',return_value=admin_code) as admin,redirect_stdout(output):
                code=script.main(['--execute','--init-admin'])
            result=json.loads(output.getvalue());report=json.loads(Path(result['report_file']).read_text(encoding='utf-8'))
            self.assertEqual(code,0 if admin_code==0 else 2)
            self.assertEqual(report['administrator_initialized'],admin_code==0)
            self.assertIn('init-admin',admin.call_args.args[0])
            self.assertNotIn(ROOT_PASSWORD,json.dumps(report));self.assertFalse(report['runtime_switch_performed'])
            self.assertTrue(report['application_account_created'])
            if admin_code:self.assertEqual(report['status'],'blocked')

    def resume_report(self,**changes):
        report={'status':'blocked','stage':'minimal_grants_verified','application_account_created':True,
                'secret_saved_encrypted':True,'administrator_initialized':False,'runtime_switch_performed':False,
                'error':'mysql_native_foreign_key_check_failed','application_username':'cardmig_app','allowed_source':'192.0.2.1',**changes}
        path=self.root/'var/mysql-provision-reports/prior.json'
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(report),encoding='utf-8')
        secret=self.root/'var/secrets/mysql-app.dpapi';secret.parent.mkdir(parents=True,exist_ok=True);secret.write_bytes(b'fake-encrypted')
        return path

    def test_resume_verifies_existing_identity_schema_and_grants_without_root_or_ddl(self):
        path=self.resume_report()
        self.connect.side_effect=[self.application_connection,Mock()]
        progress={}
        script.resume_provision(self.root/'config.toml',path,progress)
        self.assertEqual(progress['status'],'mysql_application_account_and_native_checks_passed')
        self.assertFalse(progress['account_ddl_executed']);self.assertFalse(self.saved)
        self.assertFalse(self.cursor.queries)
        self.assertTrue(all(call.kwargs['user']=='cardmig_app' for call in self.connect.call_args_list))
        self.assertEqual((self.root/'var/secrets/mysql-app.dpapi').read_bytes(),b'fake-encrypted')

    def test_resume_rejects_wrong_stage_or_unrelated_report_before_network(self):
        for changes in ({'stage':'encrypted_secret_saved'},{'application_username':'root'},
                        {'application_account_created':False},{'runtime_switch_performed':True}):
            path=self.resume_report(**changes)
            with self.assertRaises(mysql.CheckError):script.resume_provision(self.root/'config.toml',path,{})
        with self.assertRaisesRegex(mysql.CheckError,'path_invalid'):
            script.resume_provision(self.root/'config.toml',self.root/'outside.json',{})
        self.connect.assert_not_called()


if __name__=='__main__':unittest.main()
