import json
import unittest

from migration_pipeline.audit_thesis_closeout_v1 import audit, inspect_bodies


def fixture(source='put(k,v){this[k]=v;}', target='put(k,v){this.data.set(k,v);}'):
    vue='<script>module.exports={methods:{'+source+'}};</script>'
    san='<script>const san=require(\'san\');module.exports=san.defineComponent({'+target+'});</script>'
    return inspect_bodies(vue,san,['put'])


class MethodBodyCalibrationTests(unittest.TestCase):
    def test_generic_names_not_component_whitelist(self):
        row=fixture()['rows'][0]
        self.assertEqual(row['source']['shape'],'dynamic_instance_assignment')
        self.assertEqual(row['target']['shape'],'dynamic_san_data_path_write')

    def test_missing_not_claimed_repaired(self):
        self.assertEqual(fixture(target='')['rows'][0]['target']['shape'],'missing')

    def test_effectful_or_arrow_body_not_certified(self):
        for source in ['put(k,v){this[k]=v;this.notify();}', 'put:(k,v)=>{this[k]=v;}',
                       'async put(k,v){this[k]=v;}', 'put(k,v){return this[k]=v;}']:
            with self.subTest(source=source):
                self.assertEqual(fixture(source=source)['rows'][0]['source']['shape'],'unassessed')

    def test_wrong_parameter_or_extra_effect_not_path_shape(self):
        for target in ['put(k,v){this.data.set(v,k);}', 'put(k,v){this.data.set(k,v);this.fire(\'x\');}',
                       'put(k,v){this.data.set(\'fixed\',v);}', 'put(k,v){this.data.set?.(k,v);}']:
            with self.subTest(target=target):
                self.assertEqual(fixture(target=target)['rows'][0]['target']['shape'],'unassessed')

    def test_duplicate_or_spread_options_unassessed(self):
        for target in ['put(k,v){},put(k,v){}','...external,put(k,v){this.data.set(k,v);}']:
            self.assertEqual(fixture(target=target)['scope'],'unassessed')

    def test_never_executes_source_or_generated_script(self):
        vue='<script>throw Error(\'must not execute\');module.exports={methods:{put(k,v){this[k]=v;}}};</script>'
        san='<script>throw Error(\'must not execute\');module.exports=san.defineComponent({put(k,v){this.data.set(k,v);}});</script>'
        self.assertEqual(inspect_bodies(vue,san,['put'])['rows'][0]['target']['shape'],'dynamic_san_data_path_write')


class FrozenInventoryAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result=audit()

    def test_exact_counts(self):
        self.assertEqual(self.result['counts'],{'configured':30,'source_dynamic_contracts':22,
            'new_unproven_diagnostics':21,'historically_passed_with_new_diagnostic':19,
            'recognized_path_write_bodies':21,'missing_interfaces':1})

    def test_shape_evidence_does_not_become_whole_component_pass(self):
        for row in self.result['methods']:
            self.assertFalse(row['whole_component_equivalence_proven'])
            self.assertFalse(row['new_component_native_execution'])
            self.assertFalse(row['diagnostic_waived'])
        self.assertTrue(self.result['native_evidence_reused_not_rerun'])

    def test_pixel_gap_is_evidence_not_completed_feature(self):
        facts=self.result['implementation_facts']
        self.assertEqual(facts['screenshot_helper_bytes'],0)
        self.assertEqual(facts['image_diff_helper_bytes'],0)
        self.assertFalse(facts['pixel_pipeline_complete'])
        self.assertIn('migration_pipeline.utils.dom_compare',facts['visual_eval_imports'])

    def test_scope_and_original_scores_unchanged(self):
        self.assertEqual(self.result['scope_decision'],'retain_arbitrary_public_keys_and_continue_blocking')
        self.assertEqual(self.result['original_batch'],{'configured':30,'passed':24,'failed':6,'execution_errors':0,'total_tokens':1821544})
        for key in ['production_rules_changed','prompt_changed','canonical_written','new_browser_or_manual_acceptance',
                    'new_full30_run','historical_scores_rewritten','compatibility_layer_added']:
            self.assertFalse(self.result[key])
        self.assertEqual(self.result['new_model_calls'],0)

    def test_all_recorded_diagnostics_still_have_exact_path_shape(self):
        for row in self.result['methods']:
            if row['new_findings']:
                methods=row['method_body_audit']['rows']
                self.assertEqual(len(methods),1)
                self.assertEqual(methods[0]['calibration'],'recognized_body_matches_existing_counterexample_class')
                self.assertEqual(methods[0]['counterexample_reference']['variant'],'path')


if __name__=='__main__':
    unittest.main()
