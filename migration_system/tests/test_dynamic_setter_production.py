"""Dynamic setters enter the original MODEL pipeline, not a source compiler.

Real source parsing/recognition/SSM; explicit model and quality doubles test
routing, accounting and repair gates, NOT complex-component migration quality.
All mutable state belongs to temporary databases; no cloud model calls.
"""
from dataclasses import replace
from hashlib import sha256
import unittest

from test_modular_system import ModularFixture,PROJECT,FakeBrowser,FakeExtractor,SAN,checks
from card_migration_system.adapters.browser import BrowserEvaluator,SourceContractError
from card_migration_system.adapters.ssm import SSMExtractor
from card_migration_system.application.service import ServiceError
from card_migration_system.runtime import profile
from card_migration_system.workers.migration import work_once

SOURCE=(PROJECT/'tests/fixtures/CapacityPlanningBoard.vue').read_text(encoding='utf-8')


class AdmissionBrowser(FakeBrowser):
    def __init__(self,settings):
        super().__init__()
        self.parser=BrowserEvaluator(settings,profile(settings))

    def preflight(self,source):return self.parser.preflight(source)
    def source_contracts(self,source):return self.parser.source_contracts(source)


class DynamicSetterModelTests(ModularFixture,unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.service.settings=replace(self.settings,project_root=PROJECT,repository_root=PROJECT/'engine')
        self.service.browser=AdmissionBrowser(self.service.settings)
        self.service.extractor=FakeExtractor()
        self.source=self.base.create_input({'filename':'CapacityPlanningBoard.vue','source':SOURCE})

    def enqueue(self,**kwargs):
        return super().enqueue(confirm_model_calls=True,**kwargs)

    def test_original_complex_source_enters_actual_prompt_and_model_ledger(self):
        self.service.extractor=SSMExtractor(PROJECT/'engine')
        captured=[]
        exchange=self.model.exchange
        def record(messages):
            captured.append(messages)
            return exchange(messages)
        self.model.exchange=record
        validated=[]
        def observe(repository,action,**kwargs):
            if action=='validate':validated.append(kwargs)
            return checks(repository,action,**kwargs)
        self.service.checks=observe
        key=self.enqueue(max_repair_rounds=0)
        result=work_once(self.base,service=self.service)
        # The recorded Hello target is NOT equivalent to the complex source.
        # Real SSM structure checks must fail, even though admission succeeded.
        self.assertEqual(result['status'],'failed',result['stop_reason'])
        self.assertEqual(result['assessment']['dimensions']['structure'],'fail')
        self.assertEqual(result['model_calls_started'],1)
        self.assertEqual(result['generation_origin'],'generation')
        self.assertEqual(self.model.calls,1)
        self.assertEqual(result['actual_cloud_model_calls'],0)  # recorded double
        self.assertEqual(result['usage']['known_total_tokens'],30)
        self.assertEqual(self.service.source(key),SOURCE)
        self.assertEqual(result['request']['source_sha256'],sha256(SOURCE.encode()).hexdigest())
        self.assertEqual(len(captured),1)
        self.assertIn('CapacityPlanningBoard',str(captured[0]))
        self.assertIn('setValue',str(captured[0]))
        self.assertIn('this[key]',str(captured[0]))
        self.assertIsNotNone(self.service.cached(key,'ssm.json'))
        self.assertEqual(validated[0]['source'],SOURCE)
        self.assertEqual(validated[0]['code'],SAN)
        self.assertEqual(validated[0]['ssm'],self.service.cached(key,'ssm.json')['ssm'])
        self.assertIsNone(self.service.cached(key,'business-plan.json'))
        self.assertIsNone(self.service.cached(key,'revisions/0.business.json'))
        self.assertNotIn('route',self.service.cached(key,'revisions/0.json'))
        self.assertNotIn('deterministic_compiler_route',result['assessment'])
        self.assertEqual(result['assessment']['dimensions']['interaction'],'not_run')

    def test_leftover_plan_cannot_select_deleted_compiler_route(self):
        key=self.enqueue()
        self.service.put_json(key,'business-plan.json','source_capability',{'code':'MUST_NOT_USE'})
        result=work_once(self.base,service=self.service)
        self.assertEqual(result['generation_origin'],'generation')
        self.assertEqual(self.service.cached(key,'revisions/0.json')['code'],SAN)
        self.assertEqual(self.model.calls,1)

    def test_failed_model_output_uses_existing_repair_and_candidate_gate(self):
        self.model.codes=[SAN.replace('Hello','BAD'),SAN]
        key=self.enqueue(max_repair_rounds=1)
        result=work_once(self.base,service=self.service)
        self.assertEqual(result['status'],'finished',result['stop_reason'])
        self.assertEqual(self.model.calls,2)
        self.assertEqual(result['model_calls_started'],2)
        self.assertEqual(result['generation_origin'],'model_repair')
        self.assertTrue(result['state']['decisions'][0]['accepted'])
        self.assertEqual(self.service.cached(key,'evaluations/0.json')['dimensions']['static'],'fail')

    def test_persistent_failure_exhausts_repair_budget_not_rule_stop(self):
        self.model.codes=[SAN.replace('Hello','BAD')]
        key=self.enqueue(max_repair_rounds=1)
        result=work_once(self.base,service=self.service)
        self.assertEqual(result['status'],'failed')
        self.assertEqual(result['stop_reason'],'repair_budget_exhausted')
        self.assertEqual(self.model.calls,2)
        self.assertFalse(result['state']['decisions'][0]['accepted'])

    def test_ablation_strategies_also_admit_dynamic_setter_to_model(self):
        for strategy in ('direct','ssm_no_repair'):
            key=self.service.create({'input_id':self.source['input_id'],'trusted_source':True,
                'confirm_model_calls':True,'strategy':strategy},'admission-'+strategy)['migration_id']
            result=work_once(self.base,service=self.service)
            self.assertEqual(result['status'],'finished',result['stop_reason'])
            self.assertEqual(result['model_calls_started'],1)
            self.assertEqual(result['generation_origin'],'generation')

    def test_other_contract_error_is_not_swallowed(self):
        def other_contract(source):
            raise SourceContractError('some_other_contract',source,[])
        self.service.browser.source_contracts=other_contract
        key=self.enqueue()
        result=work_once(self.base,service=self.service)
        self.assertEqual(result['stop_reason'],'some_other_contract')
        self.assertEqual(self.model.calls,0)

    def test_source_syntax_error_still_blocks_before_model(self):
        self.source=self.base.create_input({'filename':'Broken.vue',
            'source':SOURCE.replace('<header>', '<header><span>',1)})
        key=self.enqueue()
        result=work_once(self.base,service=self.service)
        self.assertEqual(result['stop_reason'],'source_template_syntax_error')
        self.assertEqual(self.model.calls,0)


if __name__=='__main__':unittest.main()
