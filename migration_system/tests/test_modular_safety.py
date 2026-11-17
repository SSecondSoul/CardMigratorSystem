"""Budget, isolation, trace disclosure, source preflight and rollback boundaries."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch,MagicMock

PROJECT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(PROJECT/'src'))
from test_modular_system import ModularFixture,SAN,FakeModel,FakeBrowser
from card_migration_system.application.service import ServiceError
from card_migration_system.application.migrations import MigrationService
from card_migration_system.prompts.migration import examples
from card_migration_system.runtime import profile
from card_migration_system.observability.traces import Tracer
from card_migration_system.reporting.identity import digest
from card_migration_system.application.storage import Storage
from card_migration_system.persistence.backup import create_backup,verify_backup


class SafetyTests(ModularFixture,unittest.TestCase):
    def test_unknown_usage_blocks_second_call(self):
        model=FakeModel([SAN.replace('Hello','BAD'),SAN]);original=model.exchange
        def exchange(messages):
            result=original(messages);data=json.loads(result.body);data.pop('usage');result.body=json.dumps(data).encode();return result
        model.exchange=exchange;self.service.model=model
        key=self.enqueue();result=self.run_graph(key)
        self.assertEqual(result['stop_reason'],'model_usage_unknown_requires_review');self.assertEqual(model.calls,1)
        self.assertFalse(result['usage']['complete'])
    def test_repair_budget_zero_does_not_call_model_again(self):
        self.model.codes=[SAN.replace('Hello','BAD')];key=self.enqueue(max_repair_rounds=0);result=self.run_graph(key)
        self.assertEqual(result['status'],'failed');self.assertEqual(self.model.calls,1)
    def test_preflight_failure_never_calls_generator(self):
        class Broken(FakeBrowser):
            def preflight(self,source):raise ServiceError('source_dependencies_not_supported')
        self.service.browser=Broken();key=self.enqueue();result=self.run_graph(key)
        self.assertEqual(self.model.calls,0);self.assertEqual(result['stop_reason'],'source_dependencies_not_supported')
    def test_profile_rejects_embedded_secrets(self):
        path=self.project/'configs/system.toml';path.write_text(path.read_text(encoding='utf-8').replace('[model]','[model]\napi_key = "SECRET_SENTINEL"'),encoding='utf-8')
        with self.assertRaises(ServiceError) as error:profile(self.settings)
        self.assertNotIn('SECRET_SENTINEL',str(error.exception))
    def test_terminal_report_and_real_job_files_enter_backup(self):
        key=self.enqueue();result=self.run_graph(key)
        self.assertTrue(any(r['kind']=='report' for r in result['files']))
        created=create_backup(self.settings,backup_id='modular-test')
        self.assertEqual(created['status'],'backup_created')
        self.assertEqual(verify_backup(self.settings,backup_id='modular-test')['status'],'backup_verified')
    def test_few_shot_exact_source_and_group_are_excluded(self):
        conf=profile(self.settings);conf['learning']['few_shot_count']=1;conf['learning']['few_shot_manifest']='configs/shots.json'
        item={'id':'one','group':'same-group','split':'train','source_sha256':'a'*64,'ssm':{},'san':SAN}
        from hashlib import sha256
        item.update(ssm_sha256=digest({}),san_sha256=sha256(SAN.encode()).hexdigest())
        (self.project/'configs/shots.json').write_text(json.dumps({'schema_version':1,'examples':[item]}),encoding='utf-8')
        with self.assertRaises(ServiceError):examples(self.settings,conf,'a'*64,'different')
        with self.assertRaises(ServiceError):examples(self.settings,conf,'b'*64,'same-group')
        self.assertEqual(len(examples(self.settings,conf,'b'*64,'different')),1)
    def test_ambient_langsmith_key_does_not_enable_upload(self):
        conf=profile(self.settings)
        with patch.dict('os.environ',{'LANGSMITH_API_KEY':'SENTINEL'}),patch('langsmith.Client') as client:
            tracer=Tracer(conf,'a'*32);tracer.stage('test','hash',lambda:{'prompt':'do not upload'})
            result=tracer.finish({'status':'test'});client.assert_not_called();self.assertFalse(result['uploaded'])
            self.assertNotIn('do not upload',json.dumps(result))

    def test_multiple_manual_confirmations_do_not_inflate_denominator(self):
        from card_migration_system.reporting.statistics import statistics
        key=self.enqueue();report=self.run_graph(key)
        payload={'revision_sha256':report['final_artifact']['sha256'],'passed':True,'changed_lines':0,'notes':'first'}
        self.service.feedback(key,payload);self.service.feedback(key,{**payload,'passed':False,'notes':'latest'})
        result=statistics(self.service)
        self.assertEqual(result['configured'],1);self.assertEqual(result['manual_confirmations'],1);self.assertEqual(result['manual_small_edits'],0)

    def test_enabled_langsmith_uses_real_sdk_boundary_with_summary_only(self):
        conf=profile(self.settings);conf['tracing']['enabled']=True
        with patch.dict('os.environ',{'LANGSMITH_API_KEY':'TEST_KEY_NOT_FOR_NETWORK'}),patch('langsmith.Client') as client:
            tracer=Tracer(conf,'a'*32)
            tracer.stage('model','sha',lambda:{'secret_source':'NEVER_UPLOAD'},'llm',summarize=lambda _: {'usage':{'total_tokens':30}})
            result=tracer.finish({'status':'finished'})
            self.assertTrue(result['uploaded']);self.assertEqual(client.return_value.create_run.call_count,2)
            self.assertTrue(client.return_value.update_run.called)
            calls=str(client.return_value.create_run.call_args_list)
            self.assertIn('total_tokens',calls);self.assertNotIn('NEVER_UPLOAD',calls)

    def test_trace_failure_does_not_change_business_callback_result(self):
        conf=profile(self.settings);conf['tracing']['enabled']=True
        with patch.dict('os.environ',{'LANGSMITH_API_KEY':'TEST_KEY_NOT_FOR_NETWORK'}),patch('langsmith.Client',side_effect=RuntimeError('no service')):
            tracer=Tracer(conf,'b'*32)
            self.assertEqual(tracer.stage('test','hash',lambda:17),17)
            self.assertEqual(tracer.finish({'status':'test'})['export_error'],'langsmith_export_failed')

    def test_network_enabled_creation_requires_explicit_billing_policy_confirmation(self):
        path=self.project/'configs/system.toml';path.write_text(path.read_text(encoding='utf-8').replace('network_enabled = false','network_enabled = true'),encoding='utf-8')
        with self.assertRaisesRegex(ServiceError,'explicit_model_call_and_soft_budget_confirmation_required'):self.enqueue()
        key=self.enqueue(confirm_model_calls=True)
        self.assertEqual(self.service.report(key)['model_calls_started'],0)

    def test_rejected_rule_falls_back_to_model_and_rule_round_does_not_spend_call_slot(self):
        from test_modular_system import checks
        path=self.project/'configs/system.toml';path.write_text(path.read_text(encoding='utf-8').replace('max_calls = 4','max_calls = 2'),encoding='utf-8')
        self.model.codes=[SAN.replace('Hello','BAD'),SAN]
        def repeated_rule(repository,action,**kwargs):
            if action=='rules':return {'code':kwargs['code']+'\n<!-- ineffective rule -->','changes':[['rule','test']]}
            return checks(repository,action,**kwargs)
        self.service.checks=repeated_rule;key=self.enqueue();result=self.run_graph(key)
        self.assertEqual(result['status'],'finished');self.assertEqual(self.model.calls,2)
        self.assertEqual([d['accepted'] for d in result['state']['decisions']],[False,True])

    def test_overbudget_response_cannot_be_reenabled_by_receipt_replay(self):
        original=self.model.exchange
        def oversized(messages):
            exchange=original(messages);value=json.loads(exchange.body)
            value['usage']={'prompt_tokens':10,'completion_tokens':9000,'total_tokens':9010}
            exchange.body=json.dumps(value).encode();return exchange
        self.model.exchange=oversized;key=self.enqueue();result=self.run_graph(key)
        self.assertEqual(result['stop_reason'],'provider_output_budget_exceeded')
        self.assertEqual(result['usage']['known_total_tokens'],9010)
        with self.assertRaisesRegex(ServiceError,'provider_output_budget_exceeded'):
            self.service.invoke(key,0,[{'role':'user','content':'test'}])
        self.assertEqual(self.model.calls,1)

if __name__=='__main__':unittest.main()
