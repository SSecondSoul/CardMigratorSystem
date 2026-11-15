"""Frozen pass is not manual acceptance; AST audit must select exported parent."""

import json
import unittest

from migration_pipeline.analyze_formal_30_v4_semantic_closure_v4 import ROOT, lifecycle_audit


class SemanticClosureV4AnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        snapshot = ROOT / 'data/experiments/snapshots/formal_30_v4_semantic_closure_v4_results_20261103_204227'
        state = json.loads((snapshot / 'repair_reports/complex/MonitoringDashboard_repair_history.json').read_text(encoding='utf-8'))['state']
        cls.vue = (snapshot / 'protocol/frozen/data/datasets/components/03_complex/MonitoringDashboard/vue/MonitoringDashboard.vue').read_text(encoding='utf-8')
        cls.final = state['final_code']
        cls.first = state['repair_history'][0]['repair_result']['repaired_code']

    def test_frozen_final_has_two_initializer_calls_despite_recorded_static_pass(self):
        result = lifecycle_audit(self.vue, self.final)
        self.assertTrue(result['duplicated_startup'])
        self.assertEqual(result['source_initializer_calls'], 1)
        self.assertEqual(result['target_initializer_calls'], 2)
        self.assertTrue(result['source_notification_permission_method_exists'])
        self.assertFalse(result['target_notification_permission_method_exists'])

    def test_first_repair_has_only_the_early_call_not_a_duplicate(self):
        result = lifecycle_audit(self.vue, self.first)
        self.assertFalse(result['duplicated_startup'])
        self.assertEqual(result['target_initializer_calls'], 1)
        self.assertEqual(result['target']['inited'][-1]['method'], 'initDataImpl')
        self.assertNotIn('initDataImpl', [r['method'] for r in result['target']['attached']])

    def test_inline_child_and_comments_are_not_counted_as_parent_initializer_calls(self):
        source = '<script>export default {mounted(){this.initData();},methods:{initData(){}}}</script>'
        code = '''<script>const child = san.defineComponent({inited(){this.initDataImpl();}});
module.exports = san.defineComponent({
  inited(){/* this.initDataImpl(); */},
  attached(){this.initDataImpl();}, initDataImpl(){}
});</script>'''
        result = lifecycle_audit(source, code)
        self.assertEqual(result['target_initializer_calls'], 1)
        self.assertFalse(result['duplicated_startup'])
        self.assertEqual(result['target']['inited'], [])


if __name__ == '__main__':
    unittest.main()
