"""Offline native-probe protocol/credential-boundary tests; never use live secrets."""
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('mysql_bootstrap_cli', PROJECT / 'scripts/bootstrap_cloud_mysql.py')
bootstrap = importlib.util.module_from_spec(spec);spec.loader.exec_module(bootstrap)
SECRET = 'bootstrap-test-secret-never-log'


class NativeCursor:
    def __init__(self, *, other=False, reject_check=True, fk_error=1452,valid_fk_error=None):
        self.other=other;self.reject_check=reject_check;self.rows=[];self.sql=[];self.lock_acquires=0;self.inserted=False;self.rolled=False
        self.fk_error=fk_error;self.valid_fk_error=valid_fk_error;self.task_inserted=False
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def execute(self, sql, params=()):
        self.sql.append(sql)
        if sql.startswith('SELECT GET_LOCK'):
            self.lock_acquires+=1;self.rows=[(0 if self.other and self.lock_acquires==1 else 1,)]
        elif sql.startswith('SELECT RELEASE_LOCK'):self.rows=[(1,)]
        elif sql.startswith('SELECT JSON_TYPE'):self.rows=[('NULL',params[1],params[2])]
        elif sql.startswith('INSERT INTO source_inputs'):
            if self.inserted and not self.rolled:raise Exception(1062,'duplicate')
            self.inserted=True;self.rolled=False
        elif sql.startswith('SELECT COUNT'):
            self.rows=[(int((self.task_inserted if 'FROM tasks' in sql else self.inserted) and not self.rolled),)]
        elif sql.startswith('INSERT INTO tasks'):
            if self.inserted and not self.rolled:
                if self.valid_fk_error:raise Exception(self.valid_fk_error,'valid insert blocked')
                self.task_inserted=True
            elif self.fk_error is not None:raise Exception(self.fk_error,'fk')
        elif sql.startswith('INSERT INTO users'):
            if self.reject_check:raise Exception(3819,'check')
        else:raise AssertionError('Unexpected SQL')
    def fetchone(self):return self.rows[0]


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.config=self.root/'mysql.toml'
        self.config.write_text((PROJECT/'configs/mysql_connection.example.toml').read_text(encoding='utf-8'),encoding='utf-8')
        project_patch=patch.object(bootstrap,'PROJECT',self.root)
        project_patch.start();self.addCleanup(project_patch.stop)
    def test_plan_is_offline_does_not_prompt_or_create_reports(self):
        output=io.StringIO()
        with patch.object(bootstrap,'execute') as execute,patch.object(bootstrap.getpass,'getpass') as prompt,redirect_stdout(output):
            self.assertEqual(bootstrap.main(['--config',str(self.config)]),0)
        execute.assert_not_called();prompt.assert_not_called()
        self.assertFalse((self.root/'var').exists())
        self.assertEqual(json.loads(output.getvalue())['status'],'offline_bootstrap_plan_only')
    def test_noninteractive_execution_never_prompts_or_sends_a_password(self):
        output=io.StringIO()
        with patch.object(bootstrap.sys.stdin,'isatty',return_value=False),patch.object(bootstrap.getpass,'getpass') as prompt,redirect_stdout(output):
            self.assertEqual(bootstrap.main(['--config',str(self.config),'--execute']),2)
        prompt.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())['error'],'mysql_password_requires_interactive_terminal')
    def test_password_is_hidden_and_success_report_has_no_secret(self):
        output=io.StringIO()
        with patch.object(bootstrap,'PROJECT',self.root),patch.object(bootstrap.sys.stdin,'isatty',return_value=True), \
             patch.object(bootstrap.getpass,'getpass',return_value=SECRET) as prompt, \
             patch.object(bootstrap,'execute',return_value={'status':'test-success','runtime_switch_performed':False}) as execute,redirect_stdout(output):
            self.assertEqual(bootstrap.main(['--config',str(self.config),'--execute']),0)
        prompt.assert_called_once();execute.assert_called_once_with(self.config,SECRET)
        self.assertNotIn(SECRET,output.getvalue())
        report=Path(json.loads(output.getvalue())['report_file'])
        self.assertNotIn(SECRET,report.read_text(encoding='utf-8'))
    def test_driver_exception_text_cannot_leak_password(self):
        output=io.StringIO()
        with patch.object(bootstrap.sys.stdin,'isatty',return_value=True),patch.object(bootstrap.getpass,'getpass',return_value=SECRET), \
             patch.object(bootstrap,'execute',side_effect=Exception(1045,SECRET)),redirect_stdout(output):
            self.assertEqual(bootstrap.main(['--config',str(self.config),'--execute']),2)
        self.assertNotIn(SECRET,output.getvalue());self.assertEqual(json.loads(output.getvalue())['driver_error_code'],1045)
        result=json.loads(output.getvalue())
        saved=Path(result['report_file']).read_text(encoding='utf-8')
        self.assertNotIn(SECRET,saved);self.assertEqual(json.loads(saved)['status'],'blocked')

    def test_schema_failure_is_saved_with_metadata_for_direct_agent_review(self):
        output=io.StringIO()
        review={'differences_total':1,'differences':[{'table':'users','kind':'check_constraint_mismatch_or_unsupported'}]}
        with patch.object(bootstrap.sys.stdin,'isatty',return_value=True),patch.object(bootstrap.getpass,'getpass',return_value=SECRET), \
             patch.object(bootstrap,'execute',side_effect=bootstrap.SchemaReviewError(review)),redirect_stdout(output):
            self.assertEqual(bootstrap.main(['--config',str(self.config),'--execute']),2)
        result=json.loads(output.getvalue())
        self.assertEqual(result['error'],'mysql_schema_requires_manual_review')
        saved=json.loads(Path(result['report_file']).read_text(encoding='utf-8'))
        self.assertEqual(saved['schema'],review)
        self.assertNotIn(SECRET,json.dumps(saved))
    def test_native_probes_rollback_and_do_not_create_accounts_or_drop_tables(self):
        first=NativeCursor();second=NativeCursor(other=True)
        one=Mock(cursor=lambda:first,rollback=lambda:setattr(first,'rolled',True));two=Mock(cursor=lambda:second)
        result=bootstrap.native_checks(one,two)
        self.assertTrue(all(result.values()))
        self.assertTrue(first.rolled)
        self.assertTrue(all(not sql.startswith(('CREATE','DROP','DELETE','GRANT','COMMIT')) for sql in first.sql+second.sql))
        one.commit.assert_not_called();two.commit.assert_not_called()
    def test_unenforced_check_is_a_failure_and_still_rolls_back(self):
        first=NativeCursor(reject_check=False);second=NativeCursor(other=True)
        one=Mock(cursor=lambda:first,rollback=lambda:setattr(first,'rolled',True));two=Mock(cursor=lambda:second)
        with self.assertRaisesRegex(bootstrap.CheckError,'not_enforced'):
            bootstrap.native_checks(one,two)
        self.assertTrue(first.rolled);one.commit.assert_not_called()

    def test_missing_parent_fk_codes_are_both_valid_but_other_errors_are_not(self):
        for number in (1216,1452,1142,1048,1364,None):
            with self.subTest(number=number):
                first=NativeCursor(fk_error=number);second=NativeCursor(other=True)
                one=Mock(cursor=lambda:first,rollback=lambda:setattr(first,'rolled',True));two=Mock(cursor=lambda:second)
                if number in (1216,1452):
                    result=bootstrap.native_checks(one,two)
                    self.assertTrue(result['foreign_key_valid_insert_and_rollback'])
                else:
                    with self.assertRaises(bootstrap.CheckError) as caught:bootstrap.native_checks(one,two)
                    if number is not None:self.assertEqual(caught.exception.driver_error_code,number)
                self.assertTrue(first.rolled);one.commit.assert_not_called()

    def test_valid_parent_insert_must_work_and_is_rolled_back(self):
        first=NativeCursor(valid_fk_error=1142);second=NativeCursor(other=True)
        one=Mock(cursor=lambda:first,rollback=lambda:setattr(first,'rolled',True));two=Mock(cursor=lambda:second)
        with self.assertRaises(Exception):bootstrap.native_checks(one,two)
        self.assertTrue(first.rolled);one.commit.assert_not_called()


if __name__=='__main__':unittest.main()
