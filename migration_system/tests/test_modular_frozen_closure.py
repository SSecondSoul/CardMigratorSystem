"""Recorded generation -> real rule graph and browser. No network model client."""
import json
from pathlib import Path
import unittest

from test_modular_system import ModularFixture,FakeModel,PROJECT
from card_migration_system.adapters.browser import BrowserEvaluator
from card_migration_system.adapters.legacy_checks import legacy_stage
from card_migration_system.config import load_settings
from card_migration_system.runtime import profile


class FrozenClosureTests(ModularFixture,unittest.TestCase):
    @unittest.skipUnless((PROJECT.parent/'data/experiments/evaluator_calibration/2026-11-17_modular_expense_tracker_syntax_closure_v1/frozen/source.vue').is_file(), 'Historical experiment corpus is not part of the standalone distribution')
    def test_recorded_initial_generation_passes_rule_graph_within_original_three_round_budget(self):
        frozen=PROJECT.parent/'data/experiments/evaluator_calibration/2026-11-17_modular_expense_tracker_syntax_closure_v1/frozen'
        source=(frozen/'source.vue').read_text(encoding='utf-8')
        initial=(frozen/'revisions/0.san').read_text(encoding='utf-8')
        ssm=json.loads((frozen/'ssm.json').read_bytes())
        class RecordedExtractor:
            def extract(self,*args):return ssm
        self.source=self.base.create_input({'filename':'ExpenseTracker.vue','source':source})
        self.service.extractor=RecordedExtractor()
        self.model.codes=[initial]
        settings=load_settings(project_root=PROJECT,environ={})
        self.service.browser=BrowserEvaluator(settings,profile(settings))
        self.service.checks=lambda repository,action,**kwargs:legacy_stage(PROJECT/'engine',action,**kwargs)
        actions=json.loads((PROJECT/'configs/diagnostics/expense-tracker-actions.json').read_bytes())
        key=self.enqueue(max_repair_rounds=3,actions=actions)
        result=self.run_graph(key)
        self.assertEqual(result['status'],'finished',{'stop_reason':result['stop_reason'],
            'round':result.get('state',{}).get('round'),
            'diagnostics':[(d['code'],d.get('message','')) for d in result.get('assessment',{}).get('diagnostics',[])]})
        self.assertEqual(self.model.calls,1,'A recorded initial response must not require model repair')
        self.assertEqual(result['actual_cloud_model_calls'],0)
        self.assertEqual(result['final_artifact']['sha256'],result['assessment']['revision_sha256'])
        self.assertLessEqual(result['state']['round'],3)
        self.assertEqual(result['assessment']['dimensions']['interaction'],'pass')
        self.assertEqual(len(result['assessment']['interaction']),15)
        self.assertTrue(all(item['passed'] for item in result['assessment']['interaction']))
        for number in range(1,result['state']['round']+1):
            self.assertEqual(self.service.cached(key,f'revisions/{number}.json')['origin'],'rule_repair')
            self.assertIsNone(self.service.cached(key,f'calls/{number}/request.json'))


if __name__=='__main__':unittest.main()
