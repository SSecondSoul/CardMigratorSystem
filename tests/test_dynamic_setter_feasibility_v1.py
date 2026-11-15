import unittest

from migration_pipeline.replay_dynamic_setter_feasibility_v1 import replay, verify_inputs


class DynamicSetterFeasibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result=replay()
        cls.native=cls.result['native']

    def test_frozen_inputs_remain_unchanged(self):
        b=verify_inputs()
        self.assertEqual(len(b['protected']),38)
        self.assertEqual(b['scope_decision'],'retain_arbitrary_public_keys_and_continue_blocking')

    def test_scope_is_conditional_not_all_architectures(self):
        a=self.result['audit']
        self.assertEqual(a['classification'],'conditional_namespace_conflict_under_current_direct_instance_contract')
        self.assertEqual(len(a['assumptions']),4)
        self.assertFalse(a['general_impossibility_for_all_architectures_claimed'])
        self.assertIn('unsupported_under_current_combined_constraints',a['decision'])

    def test_source_accepts_namespace_keys_then_real_business_method(self):
        for variant in self.native['variants'].values():
            for case in ['data-null','data-number','data-object','coerced-data-null']:
                source=variant[case]['source']
                self.assertTrue(source['publicDataMatchesInput'])
                self.assertTrue(source['nativeStorePointerIntact'])
                self.assertIsNone(source['setterError'])
                self.assertIsNone(source['businessError'])
                self.assertIsNone(source['watchError'])
                self.assertEqual(source['budgetAfterBusinessCall'],321)

    def test_path_preserves_runtime_but_not_public_data(self):
        for case in ['data-null','data-number','data-object']:
            target=self.native['variants']['path'][case]['target']
            self.assertTrue(target['nativeStorePointerIntact'])
            self.assertFalse(target['publicDataMatchesInput'])
            self.assertIsNone(target['businessError'])
            self.assertEqual(target['budgetAfterBusinessCall'],321)

    def test_instance_and_fallback_destroy_runtime_slot(self):
        for name in ['instance','coerced_finite_fallback']:
            for case in ['data-null','data-number','data-object','coerced-data-null']:
                target=self.native['variants'][name][case]['target']
                self.assertTrue(target['publicDataMatchesInput'])
                self.assertFalse(target['nativeStorePointerIntact'])
                self.assertEqual(target['businessError'],'TypeError')
                self.assertEqual(target['watchError'],'TypeError')
                self.assertEqual(target['budgetAfterBusinessCall'],500)

    def test_rejecting_reserved_key_changes_source_contract(self):
        for case in ['data-null','data-number','data-object','coerced-data-null']:
            target=self.native['variants']['reject_data_then_finite'][case]['target']
            self.assertEqual(target['setterError'],'RangeError')
            self.assertTrue(target['nativeStorePointerIntact'])
            self.assertFalse(target['publicDataMatchesInput'])

    def test_positive_root_controls_do_not_prove_arbitrary_keys(self):
        for name in ['path','coerced_finite_fallback','reject_data_then_finite']:
            self.assertTrue(self.native['variants'][name]['root-control']['declaredObservationEqual'])
            self.assertFalse(self.native['variants'][name]['data-null']['declaredObservationEqual'])

    def test_key_conversion_runs_once_before_namespace_write(self):
        for name in ['instance','coerced_finite_fallback','reject_data_then_finite']:
            row=self.native['variants'][name]['coerced-data-null']
            self.assertEqual(row['source']['keyCoercions'],['string'])
            self.assertEqual(row['target']['keyCoercions'],['string'])

    def test_missing_original_interface_is_not_reclassified_as_pass(self):
        for row in self.native['variants']['missing'].values():
            self.assertEqual(row['target']['setterError'],'TypeError')
            self.assertFalse(row['declaredObservationEqual'])

    def test_cleanup_is_not_a_production_repair(self):
        self.assertTrue(self.native['cleanup_restore_is_test_disposal_only'])
        self.assertFalse(self.native['production_adapter_installed'])
        self.assertFalse(self.native['browser_or_dom_render_verified'])
        self.assertFalse(self.result['audit']['automatic_repair_implemented'])

    def test_no_new_scores_model_calls_or_scope_waiver(self):
        a=self.result['audit']
        for key in ['new_full_component_pass','new_component_browser_acceptance','production_code_or_prompt_changed',
                    'diagnostics_waived','scope_narrowed','runtime_fork_or_compatibility_layer_added',
                    'canonical_or_manual_files_changed','shared_notification_resolved','exception_phase_resolved',
                    'new_full30_run','historical_scores_rewritten']:
            self.assertFalse(a[key])
        self.assertEqual(a['new_model_calls'],0)
        self.assertEqual(a['original_batch'],{'configured':30,'passed':24,'failed':6,'execution_errors':0,'total_tokens':1821544})
        self.assertEqual(a['source_public_business_method_exercised'],'updateBudget')


if __name__=='__main__':
    unittest.main()
