"""Read-only audit must not label changed helpers as pre-existing findings."""

import json
import unittest
from pathlib import Path

from migration_pipeline.analyze_formal_30_v4_semantic_closure_v3 import ROOT, visibility_audit


SNAPSHOT = ROOT / 'data/experiments/snapshots/formal_30_v4_semantic_closure_v3_results_20261103_175401'


class SourcePhaseV3AnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        state = json.loads((SNAPSHOT / 'repair_reports/complex/MonitoringDashboard_repair_history.json').read_text(encoding='utf-8'))['state']
        cls.before = state['generated_code']
        cls.after = state['repair_history'][0]['repair_result']['repaired_code']
        cls.introduced = state['repair_history'][0]['repair_regression_gate']['introduced_semantic_findings']

    def test_real_four_findings_are_rediscovered_in_unchanged_baseline_helpers(self):
        audit = visibility_audit(self.before, self.after, self.introduced)
        self.assertEqual(audit['explained_findings'], 4)
        self.assertEqual(len(audit['proofs']), 2)
        self.assertTrue(all(p['diagnosed_render_expressions_equal'] for p in audit['proofs']))

    def test_changed_helper_body_cannot_be_explained_as_identical(self):
        changed = self.after.replace('return (index * 800) / data.length + 2;',
                                     'return (index * 800) / data.length + 3;')
        self.assertNotEqual(changed, self.after)
        with self.assertRaisesRegex(RuntimeError, 'Method changed'):
            visibility_audit(self.before, changed, self.introduced)

    def test_changed_render_call_or_extra_gate_finding_is_not_silently_explained(self):
        changed = self.after.replace('cx="{{getX(idx)}}"', 'cx="{{getX(idx, width)}}"')
        self.assertNotEqual(changed, self.after)
        with self.assertRaisesRegex(RuntimeError, 'render expressions changed'):
            visibility_audit(self.before, changed, self.introduced)
        with self.assertRaisesRegex(RuntimeError, 'does not explain all'):
            visibility_audit(self.before, self.after, self.introduced + [{
                'code': 'hidden_template_reactive_dependency', 'location': 'new', 'message': 'different', 'count': 1}])


if __name__ == '__main__':
    unittest.main()
