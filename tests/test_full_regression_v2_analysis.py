"""Read-only outcome accounting and narrow gate/alias audit counterexamples."""
import unittest

from migration_pipeline.analyze_formal_30_v4_full_regression_v2 import ROOT, audit, clone_audit, default_fields

SAN = '''<script>module.exports=san.defineComponent({simulateDataUpdate(){
const kpiData=this.data.get('kpiData').map(k=>({...k}));
kpiData[0].value=1;this.data.set('kpiData',kpiData);
}});</script>'''


class FullRegressionV2AnalysisTests(unittest.TestCase):
    def test_frozen_accounting_keeps_raw_scores_and_discloses_reviews(self):
        data = audit(ROOT / 'data/experiments/snapshots/formal_30_v4_full_regression_v2_results_20261104_214821')
        self.assertEqual(data['verified_files'], 457)
        self.assertEqual((data['aggregate']['passed'], data['aggregate']['failed'], data['aggregate']['execution_errors']), (24, 6, 0))
        self.assertEqual(data['aggregate']['total_tokens'], 1821544)
        self.assertEqual(data['transition_counts']['v4'], {'kept_pass': 21, 'improved_to_pass': 3, 'regressed_to_fail': 4, 'still_not_pass': 2})
        self.assertEqual(data['rule_builder_gate_review']['after_missing_defaults'], ['initialGroups'])
        self.assertTrue(data['monitoring_review']['clone_audit']['local_scalar_writes_are_on_cloned_records'])
        self.assertFalse(data['original_score_modified'])

    def test_shrinking_group_is_not_a_new_field_but_still_an_error(self):
        issue = lambda text: [{'code': 'missing_prop_defaults', 'message': f'以下带默认值的 Vue props 未在 San initData 中落地：{text}。'}]
        before, after = default_fields(issue('title, initialGroups')), default_fields(issue('initialGroups'))
        self.assertTrue(after < before)
        self.assertTrue(after)
        with self.assertRaises(ValueError):
            default_fields([{'code': 'missing_prop_defaults', 'message': 'unknown grouped diagnostic'}])

    def test_fresh_record_clone_with_scalar_write_and_commit_is_recognized(self):
        self.assertTrue(clone_audit(SAN)['local_scalar_writes_are_on_cloned_records'])

    def test_array_map_identity_is_not_a_record_clone(self):
        self.assertFalse(clone_audit(SAN.replace('k=>({...k})', 'k=>k'))['local_scalar_writes_are_on_cloned_records'])

    def test_deeper_mutation_is_not_proven_safe_by_a_shallow_record_copy(self):
        self.assertFalse(clone_audit(SAN.replace('kpiData[0].value=1', 'kpiData[0].nested.value=1'))['local_scalar_writes_are_on_cloned_records'])

    def test_commit_must_exist_and_follow_the_local_writes(self):
        for candidate in (SAN.replace("this.data.set('kpiData',kpiData);", ''),
                          SAN.replace("kpiData[0].value=1;this.data.set('kpiData',kpiData);", "this.data.set('kpiData',kpiData);kpiData[0].value=1;")):
            with self.subTest(candidate=candidate):
                self.assertFalse(clone_audit(candidate)['local_scalar_writes_are_on_cloned_records'])


if __name__ == '__main__':
    unittest.main()
