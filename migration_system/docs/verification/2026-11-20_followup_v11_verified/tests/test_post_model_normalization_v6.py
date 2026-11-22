"""Actual persistent graph/ledger, explicit model/check doubles, no cloud calls."""
import unittest
from test_modular_system import ModularFixture, SAN, FakeBrowser


def checks(_, action, **value):
    code=value['code']
    if action=='validate':
        errors=[{'code':'bad_target','message':'initial error'}] if 'BAD' in code else (
            [{'code':'missing_prop_defaults','message':'model dropped a default'}] if 'MISSING' in code else [])
        return {'validation_passed':not errors,'validation_errors':errors}
    if action=='rules':return {'code':code.replace('MISSING','Hello'),'changes':['fixture_default_restored'] if 'MISSING' in code else []}
    if action=='repair_prompt':return {'prompt':'Repair the target'}
    raise AssertionError(action)


class PostModelNormalizationTests(ModularFixture, unittest.TestCase):
    def test_raw_response_is_preserved_and_rules_finish_within_same_model_round(self):
        self.service.checks=checks
        self.model.codes=[SAN.replace('Hello','BAD'),SAN.replace('Hello','MISSING')]
        key=self.enqueue(max_repair_rounds=1);report=self.run_graph(key)
        self.assertEqual(report['status'],'finished')
        self.assertEqual(self.model.calls,2)
        self.assertEqual(report['actual_cloud_model_calls'],0)
        revision=self.service.cached(key,'revisions/1.json')
        self.assertEqual(revision['origin'],'model_repair')
        self.assertIn('Hello',revision['code']);self.assertNotIn('MISSING',revision['code'])
        raw=self.service.read_file(key,revision['raw_model_output']['relative_path']).decode()
        self.assertIn('MISSING',raw)
        self.assertNotEqual(revision['file']['sha256'],revision['raw_model_output']['sha256'])
        trace=self.service.cached(key,'normalizations/1.json')
        self.assertEqual(trace['model_calls'],0)
        self.assertEqual(trace['stop'],'fixed_point')
        self.assertIn('fixture_default_restored',trace['changes'])

    def test_postprocessing_does_not_bypass_final_runtime_regression_gate(self):
        class Browser(FakeBrowser):
            def evaluate(self,source,code,props,actions):
                result=super().evaluate(source,code,props,actions)
                if 'RUNTIME_BROKEN' in code:result['san']['errors']=['real candidate defect fixture']
                return result
        self.service.browser=Browser();self.service.checks=checks
        self.model.codes=[SAN.replace('Hello','BAD'),SAN.replace('Hello','MISSING RUNTIME_BROKEN')]
        key=self.enqueue(max_repair_rounds=1);report=self.run_graph(key)
        self.assertEqual(report['status'],'failed')
        self.assertFalse(report['state']['decisions'][0]['accepted'])
        self.assertEqual(report['state']['decisions'][0]['reason'],'candidate_regression')
        self.assertEqual(report['final_artifact']['sha256'],self.service.cached(key,'revisions/0.json')['file']['sha256'])
        self.assertEqual(self.model.calls,2)


if __name__=='__main__':unittest.main()
