"""Offline/fake-MySQL preflight tests. Never connect to a real DB or call a model."""
from contextlib import redirect_stdout
from dataclasses import replace
import importlib.util
import io
import json
from pathlib import Path
import re
import ssl
import struct
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch

PROJECT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('mysql_check',PROJECT/'src/card_migration_system/persistence/mysql_connection.py')
check=importlib.util.module_from_spec(spec);sys.modules[spec.name]=check;spec.loader.exec_module(check)
SNAPSHOT=json.loads(check.SCHEMA.read_text(encoding='utf-8'))
SECRET='secret-sentinel-password-never-print'


class FakeCursor:
    def __init__(self,config):
        self.config=config;self.statements=[];self.rows=[];self.version='8.4.7';self.cipher='TLS_AES_256_GCM_SHA384';self.modes='STRICT_TRANS_TABLES';self.nonempty=set()
        self.tables=[];self.columns=[];self.keys=[];self.checks=[];self.rules=[]
        for table in SNAPSHOT['tables']:
            name=table['name'];self.tables.append((name,'InnoDB','utf8mb4_0900_bin'))
            for c in table['columns']:
                kind={'BOOLEAN':'tinyint(1)','INTEGER':'int'}.get(c['mysql_type'],c['mysql_type'].lower())
                self.columns.append((name,c['name'],kind,'YES' if c['nullable'] else 'NO',None,'auto_increment' if c['autoincrement'] else '', 'utf8mb4_0900_bin' if kind.startswith('varchar') else None))
            for c in table['primary_key']:self.keys.append((name,'PRIMARY KEY','PRIMARY',c,None,None,None))
            for i,unique in enumerate(table['unique']):
                for c in unique:self.keys.append((name,'UNIQUE',f'uq_{i}',c,None,None,None))
            for i,fk in enumerate(table['foreign_keys']):
                for col,parent in zip(fk['columns'],fk['target_columns']):self.keys.append((name,'FOREIGN KEY',f'fk_{i}',col,config.name,fk['target_table'],parent))
                self.rules.append((name,'RESTRICT','RESTRICT'))
            for clause in table['checks']:self.checks.append((name,'('+clause+')','YES'))
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def execute(self,sql,params=None):
        self.statements.append(sql)
        if sql.startswith('SET SESSION TRANSACTION READ ONLY'):self.rows=[]
        elif sql.startswith('SELECT VERSION()'):self.rows=[(self.version,self.config.name,self.modes)]
        elif sql.startswith('SHOW SESSION'):self.rows=[('Ssl_cipher',self.cipher)]
        elif 'FROM information_schema.TABLES ' in sql:self.rows=self.tables
        elif 'FROM information_schema.COLUMNS ' in sql:self.rows=self.columns
        elif 'KEY_COLUMN_USAGE' in sql:self.rows=self.keys
        elif 'CHECK_CONSTRAINTS' in sql:self.rows=self.checks
        elif 'REFERENTIAL_CONSTRAINTS' in sql:self.rows=self.rules
        elif sql.startswith('SELECT 1 FROM '):self.rows=[(1,)] if sql.split('`')[3] in self.nonempty else []
        else:raise AssertionError('Unexpected SQL')
    def fetchone(self):return self.rows[0] if self.rows else None
    def fetchall(self):return self.rows


class FakeConnection:
    def __init__(self,config):self.reader=FakeCursor(config);self.rollback_called=False;self.closed=False
    def cursor(self):return self.reader
    def rollback(self):self.rollback_called=True
    def close(self):self.closed=True
    def commit(self):raise AssertionError('Inspection must not commit')


class MySQLConnectionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'connection.toml'
        self.template=(PROJECT/'configs/mysql_connection.example.toml').read_text(encoding='utf-8')
        self.path.write_text(self.template.replace('host = ""','host = "192.168.1.10"').replace('username = ""','username = "cardmig_app"'),encoding='utf-8')
        self.config=check.load_config(self.path)
    def test_offline_and_missing_config_never_connect(self):
        output=io.StringIO()
        with patch.dict('os.environ',{},clear=True),patch('socket.socket',side_effect=AssertionError('No network')),redirect_stdout(output):
            self.assertEqual(check.main(['--config',str(self.path)]),0)
        data=json.loads(output.getvalue());self.assertIn('mysql_password_missing',data['pending']);self.assertFalse(data['network_connected'])
        self.assertEqual(data['active_business_backend'],'not_inspected')
    def test_config_rejects_password_or_url_and_does_not_echo_values(self):
        for key in ('password','url'):
            self.path.write_text(self.template.replace('[database]',f'[database]\n{key} = "{SECRET}"'),encoding='utf-8')
            with self.assertRaises(check.CheckError) as caught:check.load_config(self.path)
            self.assertNotIn(SECRET,str(caught.exception))
    def test_config_rejects_invalid_ports_hosts_and_timeouts(self):
        for old,new in [('port = 3306','port = true'),('port = 3306','port = 65536'),('host = ""','host = "https://db.example/a"'),('connect_timeout = 5','connect_timeout = 0')]:
            self.path.write_text(self.template.replace(old,new),encoding='utf-8')
            with self.assertRaises(check.CheckError):check.load_config(self.path)
    def test_tls_identity_and_timeouts_are_explicit(self):
        options=check.connect_options(self.config,SECRET)
        self.assertTrue(options['ssl'].check_hostname);self.assertEqual(options['ssl'].verify_mode,ssl.CERT_REQUIRED)
        self.assertFalse(options['local_infile']);self.assertFalse(options['autocommit'])
        self.assertEqual(options['read_timeout'],10);self.assertEqual(options['password'],SECRET)
    def test_verify_ca_is_explicit_and_keeps_required_certificate_validation(self):
        config=replace(self.config,tls_mode='verify_ca',ca_file='configs/test-ca.pem')
        context=ssl.create_default_context()
        with patch.object(check.ssl,'create_default_context',return_value=context):
            options=check.connect_options(config,SECRET)
        self.assertEqual(options['ssl'].verify_mode,ssl.CERT_REQUIRED)
        self.assertFalse(options['ssl'].check_hostname)
        self.assertNotIn('ssl_disabled',options)
        with self.assertRaisesRegex(check.CheckError,'explicit_ca'):
            check.connect_options(replace(config,ca_file=''),SECRET)
        text=self.template.replace('mode = "verify_identity"','mode = "verify_ca"')
        self.path.write_text(text,encoding='utf-8')
        with self.assertRaises(check.CheckError):check.load_config(self.path)
    def test_no_tls_requires_explicit_private_ip_scope(self):
        config=replace(self.config,tls_mode='disabled')
        with patch('importlib.util.find_spec',return_value=True):
            self.assertIn('mysql_insecure_lan_not_explicitly_allowed',check.pending(config,{config.password_env:SECRET}))
            self.assertNotIn('mysql_insecure_lan_not_explicitly_allowed',check.pending(config,{config.password_env:SECRET},True))
            for host in ('8.8.8.8','db.example','192.0.2.1'):
                self.assertIn('mysql_insecure_lan_not_explicitly_allowed',check.pending(replace(config,host=host),{config.password_env:SECRET},True))
    def test_check_grammar_handles_mysql_representation_but_not_real_changes(self):
        self.assertEqual(check.check_expression("role IN ('admin','user')"),check.check_expression("((`role` in (_utf8mb4'user',_utf8mb4'admin')))"))
        self.assertEqual(check.check_expression('a >= 0 AND b >= 0'),check.check_expression('((`b` >= 0) and (`a` >= 0))'))
        self.assertNotEqual(check.check_expression("role IN ('admin','user')"),check.check_expression("role IN ('Admin','user')"))
        for sql in ('role IS NULL OR 1=1','some_function(role) = 1','role IN (SELECT role FROM users)'):
            with self.assertRaises(ValueError):check.check_expression(sql)

    def test_escaped_metadata_literal_delimiters_are_not_real_value_changes(self):
        for layers in (1,2):
            quote='\\'*layers+"'"
            actual='(`role` in (_utf8mb4'+quote+'admin'+quote+',_utf8mb4'+quote+'user'+quote+'))'
            self.assertEqual(check.check_expression("role IN ('admin','user')"),check.check_expression(actual,metadata=True))
            with self.assertRaises(ValueError):check.check_expression(actual)
            changed=actual.replace('admin','Admin')
            self.assertNotEqual(check.check_expression("role IN ('admin','user')"),check.check_expression(changed,metadata=True))
            with self.assertRaises(ValueError):check.check_expression(actual+' OR 1=1',metadata=True)

    def test_all_escaped_check_metadata_is_compared_without_skipping_constraints(self):
        for layers in (1,2):
            connection=FakeConnection(self.config)
            quote='\\'*layers+"'"
            connection.reader.checks=[(name,re.sub(r"'([A-Za-z0-9_]+)'",lambda m:'_utf8mb4'+quote+m.group(1)+quote,clause),enforced)
                                      for name,clause,enforced in connection.reader.checks]
            result=check.connect_check(self.config,SECRET,SNAPSHOT,lambda **kwargs:connection)
            self.assertEqual(result['schema']['differences'],[])
            self.assertEqual(result['status'],'mysql_prepared_schema_verified')
            # Disabling or changing a check still blocks with this representation.
            connection.reader.checks[0]=(connection.reader.checks[0][0],connection.reader.checks[0][1],'NO')
            result=check.connect_check(self.config,SECRET,SNAPSHOT,lambda **kwargs:connection)
            self.assertEqual(result['status'],'mysql_schema_review_required')

    def test_actual_frozen_cloud_report_has_only_equivalent_check_representations(self):
        path=PROJECT/'docs/verification/2026-11-18_mysql_cloud_integration/schema_inspection_before_quote_normalization.json'
        report=json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(report['schema']['actual_tables'],34)
        self.assertEqual(report['schema']['differences_total'],12)
        for difference in report['schema']['differences']:
            self.assertEqual(difference['kind'],'check_constraint_mismatch_or_unsupported')
            self.assertTrue(all(c['enforced']=='YES' for c in difference['actual']))
            expected={check.check_expression(c) for c in difference['expected']}
            actual={check.check_expression(c['clause'],metadata=True) for c in difference['actual']}
            self.assertEqual(expected,actual,difference['table'])
    def test_all_34_table_inspection_is_read_only_and_does_not_switch_runtime(self):
        connection=FakeConnection(self.config);connector=Mock(return_value=connection)
        result=check.connect_check(self.config,SECRET,SNAPSHOT,connector)
        self.assertEqual(result['status'],'mysql_prepared_schema_verified');self.assertEqual(result['schema']['actual_tables'],34)
        self.assertEqual(result['schema']['differences'],[]);self.assertFalse(result['runtime_switch_performed'])
        self.assertTrue(connection.rollback_called and connection.closed);connector.assert_called_once()
        self.assertTrue(all(sql.startswith(('SELECT','SHOW','SET SESSION TRANSACTION READ ONLY')) for sql in connection.reader.statements))
    def test_wrong_fk_target_or_unenforced_check_is_not_accepted(self):
        for kind in ('fk','check','extra_column','type','action'):
            connection=FakeConnection(self.config);reader=connection.reader
            if kind=='fk':
                index=next(i for i,row in enumerate(reader.keys) if row[1]=='FOREIGN KEY');row=list(reader.keys[index]);row[4]='other_database';reader.keys[index]=tuple(row)
            elif kind=='check':reader.checks[0]=(*reader.checks[0][:2],'NO')
            elif kind=='extra_column':reader.columns.append(('users','unexpected','int','NO',None,'',None))
            elif kind=='type':row=list(reader.columns[0]);row[2]='text';reader.columns[0]=tuple(row)
            else:reader.rules[0]=(reader.rules[0][0],'CASCADE','CASCADE')
            result=check.connect_check(self.config,SECRET,SNAPSHOT,lambda **kwargs:connection)
            self.assertEqual(result['status'],'mysql_schema_review_required',kind)
    def test_nonempty_database_is_reported_not_erased_or_stamped(self):
        connection=FakeConnection(self.config);connection.reader.nonempty={'alembic_version','users'}
        result=check.connect_check(self.config,SECRET,SNAPSHOT,lambda **kwargs:connection)
        self.assertEqual(result['status'],'mysql_schema_review_required');self.assertEqual(result['schema']['nonempty_tables'],['alembic_version','users'])
    def test_version_tls_and_strict_mode_fail_closed_and_close_connection(self):
        for field,value in (('version','8.0.15'),('version','10.11.8-MariaDB'),('version','9.0.1'),('cipher',''),('modes','')):
            connection=FakeConnection(self.config);setattr(connection.reader,field,value)
            with self.assertRaises(check.CheckError):check.connect_check(self.config,SECRET,SNAPSHOT,lambda **kwargs:connection)
            self.assertTrue(connection.closed and connection.rollback_called)
    def test_mysql_8_0_41_can_be_inspected_without_claiming_runtime_compatibility(self):
        connection=FakeConnection(self.config);connection.reader.version='8.0.41'
        result=check.connect_check(self.config,SECRET,SNAPSHOT,lambda **kwargs:connection)
        self.assertEqual(result['status'],'mysql_prepared_schema_verified')
        self.assertEqual(result['version_warnings'],['mysql_8_0_differs_from_handoff_target_8_4'])
        self.assertEqual(result['application_compatibility_status'],'not_validated')
        self.assertFalse(result['runtime_switch_performed'])
    def test_driver_errors_are_redacted_and_never_retried(self):
        output=io.StringIO();connector=Mock(side_effect=Exception(2003,'mysql://user:'+SECRET+'@db'))
        with patch.dict('os.environ',{'CARDMIG_MYSQL_PASSWORD':SECRET},clear=True),patch.object(check,'pending',return_value=[]),patch.dict(sys.modules,{'pymysql':Mock(connect=connector)}),redirect_stdout(output):
            self.assertEqual(check.main(['--config',str(self.path),'--connect']),2)
        self.assertNotIn(SECRET,output.getvalue());self.assertNotIn('mysql://',output.getvalue());connector.assert_called_once()
        self.assertEqual(json.loads(output.getvalue())['driver_error_code'],2003)

    def test_hidden_prompt_saves_schema_differences_without_saving_password(self):
        output=io.StringIO();connection=FakeConnection(self.config)
        row=list(connection.reader.columns[0]);row[2]='text';connection.reader.columns[0]=tuple(row)
        connector=Mock(return_value=connection)
        with patch.dict('os.environ',{},clear=True),patch.object(check,'PROJECT',Path(self.temp.name)), \
             patch.object(check,'pending',return_value=['mysql_password_missing']), \
             patch.object(check.sys.stdin,'isatty',return_value=True), \
             patch.object(check.getpass,'getpass',return_value=SECRET), \
             patch.dict(sys.modules,{'pymysql':Mock(connect=connector)}),redirect_stdout(output):
            self.assertEqual(check.main(['--config',str(self.path),'--connect','--password-prompt','--save-report']),2)
            self.assertNotIn('CARDMIG_MYSQL_PASSWORD',check.os.environ)
        result=json.loads(output.getvalue())
        saved=Path(result['report_file']).read_text(encoding='utf-8')
        self.assertNotIn(SECRET,output.getvalue()+saved)
        difference=next(d for d in result['schema']['differences'] if d['kind']=='column_definition_mismatch')
        self.assertIn('expected',difference);self.assertEqual(difference['actual']['type'],'text')
        self.assertTrue(result['read_only']);self.assertTrue(connection.closed and connection.rollback_called)
        self.assertTrue(all(sql.startswith(('SELECT','SHOW','SET SESSION TRANSACTION READ ONLY')) for sql in connection.reader.statements))
        connector.assert_called_once()

    def test_hidden_prompt_requires_a_terminal_and_never_uses_echoing_fallback(self):
        output=io.StringIO();connector=Mock()
        with patch.object(check,'pending',return_value=['mysql_password_missing']), \
             patch.object(check.sys.stdin,'isatty',return_value=False), \
             patch.object(check.getpass,'getpass') as prompt, \
             patch.dict(sys.modules,{'pymysql':Mock(connect=connector)}),redirect_stdout(output):
            self.assertEqual(check.main(['--config',str(self.path),'--connect','--password-prompt']),2)
        self.assertEqual(json.loads(output.getvalue())['error'],'mysql_password_requires_interactive_terminal')
        prompt.assert_not_called();connector.assert_not_called()
    def test_installed_driver_accepts_options_without_network(self):
        if importlib.util.find_spec('pymysql') is None:self.skipTest('Optional driver not installed')
        import pymysql
        with patch('socket.socket',side_effect=AssertionError('No network')):
            client=pymysql.connect(defer_connect=True,**check.connect_options(self.config,SECRET))
            self.assertEqual(client.charset,'utf8mb4')
            self.assertTrue(client._ssl_required)

    def greeting(self, ssl_enabled):
        packet = (b'\x0a8.0.30\0' + b'\x01\0\0\0' + b'12345678\0'
                  + (0x8a00 if ssl_enabled else 0x8200).to_bytes(2, 'little')
                  + b'\x2d\x02\0\0\0' + b'\0' * 20)
        return len(packet).to_bytes(3, 'little') + b'\0' + packet

    def probe_socket(self, ssl_enabled):
        stream = Mock();stream.__enter__=Mock(return_value=stream);stream.__exit__=Mock(return_value=False)
        data = bytearray(self.greeting(ssl_enabled))
        def receive(count):
            result=bytes(data[:count]);del data[:count];return result
        stream.recv.side_effect=receive
        return stream

    def test_probe_never_authenticates_when_server_has_no_tls(self):
        stream=self.probe_socket(False)
        with patch.object(check.socket,'create_connection',return_value=stream):
            result=check.probe_endpoint(self.config)
        self.assertEqual(result['status'],'mysql_tls_configuration_required')
        self.assertFalse(result['authentication_attempted']);stream.sendall.assert_not_called()

    def test_probe_sends_only_32_byte_ssl_request_not_credentials(self):
        stream=self.probe_socket(True)
        context=Mock();secured=Mock()
        secured.__enter__=Mock(return_value=secured);secured.__exit__=Mock(return_value=False)
        secured.version.return_value='TLSv1.3';context.wrap_socket.return_value=secured
        with patch.object(check.socket,'create_connection',return_value=stream), patch.object(check,'connect_options',return_value={'ssl':context}):
            result=check.probe_endpoint(self.config)
        wire=stream.sendall.call_args.args[0]
        self.assertEqual(len(wire),36);self.assertEqual(wire[:4],b'\x20\0\0\x01')
        self.assertNotIn(self.config.username.encode(),wire)
        self.assertTrue(result['tls_verified']);self.assertFalse(result['sql_executed'])

    def test_probe_reports_certificate_failure_without_downgrade_or_auth(self):
        stream=self.probe_socket(True);context=Mock()
        context.wrap_socket.side_effect=ssl.SSLCertVerificationError('untrusted')
        with patch.object(check.socket,'create_connection',return_value=stream), patch.object(check,'connect_options',return_value={'ssl':context}):
            result=check.probe_endpoint(self.config)
        self.assertEqual(result['status'],'mysql_tls_ca_or_identity_review_required')
        self.assertFalse(result['authentication_attempted']);self.assertEqual(stream.sendall.call_count,1)

    def test_probe_reports_safe_hostname_error_without_raw_exception_text(self):
        stream=self.probe_socket(True);context=Mock()
        error=ssl.SSLCertVerificationError(1,SECRET)
        error.verify_code=62;error.verify_message='Hostname mismatch; '+SECRET
        context.wrap_socket.side_effect=error
        with patch.object(check.socket,'create_connection',return_value=stream), patch.object(check,'connect_options',return_value={'ssl':context}):
            result=check.probe_endpoint(self.config)
        self.assertEqual(result['tls_verify_code'],62)
        self.assertEqual(result['tls_verification_reason'],'hostname_mismatch')
        self.assertNotIn(SECRET,json.dumps(result))
        self.assertFalse(result['tls_verified']);self.assertFalse(result['authentication_attempted'])
    def test_probe_ca_mode_does_not_claim_hostname_identity_verified(self):
        config=replace(self.config,tls_mode='verify_ca',ca_file='configs/test-ca.pem')
        stream=self.probe_socket(True);context=Mock();secured=Mock()
        secured.__enter__=Mock(return_value=secured);secured.__exit__=Mock(return_value=False)
        secured.version.return_value='TLSv1.3';context.wrap_socket.return_value=secured
        with patch.object(check.socket,'create_connection',return_value=stream),patch.object(check,'connect_options',return_value={'ssl':context}):
            result=check.probe_endpoint(config)
        self.assertTrue(result['tls_verified']);self.assertFalse(result['tls_identity_verified'])
        self.assertEqual(result['tls_verification_mode'],'verify_ca')
        self.assertFalse(result['authentication_attempted'])


if __name__=='__main__':unittest.main()
