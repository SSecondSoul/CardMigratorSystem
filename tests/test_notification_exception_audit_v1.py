import unittest

from migration_pipeline.replay_notification_exception_v1 import projection, replay, verify


class NotificationExceptionAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result=replay()
        cls.shared=cls.result['native']['shared']['proposals']
        cls.phases=cls.result['native']['phases']['variants']

    def test_inputs_and_existing_implementations_preserved(self):
        self.assertEqual(len(verify()['protected']),41)

    def test_five_ordinary_method_projections_still_match(self):
        for pair in self.shared['unchanged'].values():
            self.assertEqual(projection(pair['source']),projection(pair['target']))
            self.assertEqual(pair['source']['immediate'],pair['source']['afterTick'])

    def test_source_observer_has_two_shared_writes_then_root_commit(self):
        row=self.shared['unchanged']['forward']['source']
        self.assertEqual(len(row['notices']),3)
        self.assertEqual([n['rootIsOriginal'] for n in row['notices']],[True,True,False])
        self.assertEqual([n['valueIsOld'] for n in row['notices']],[True,True,False])
        self.assertEqual(row['notices'][0]['starts'],['10:00','10:00','14:00'])
        self.assertEqual(row['oldStarts'],['10:00','09:00','14:00'])
        self.assertEqual(row['sameRecords'],[False,False,True])

    def test_current_target_only_has_final_root_notice(self):
        row=self.shared['unchanged']['forward']['target']
        self.assertEqual(len(row['notices']),1)
        self.assertFalse(self.result['audit']['external_observer_is_new_mandatory_feature'])

    def test_deep_detach_changes_shared_alias_and_nested_identity(self):
        pair=self.shared['deep_detach']['forward']
        self.assertNotEqual(pair['source']['oldStarts'],pair['target']['oldStarts'])
        self.assertEqual(pair['target']['sameNested'],[False,False,True])
        self.assertNotEqual(projection(pair['source']),projection(pair['target']))

    def test_matching_three_notices_does_not_prove_root_identity(self):
        for name in ['nested_data_set','shallow_republish']:
            pair=self.shared[name]['forward']
            self.assertEqual(len(pair['target']['notices']),3)
            self.assertEqual([n['rootIsOriginal'] for n in pair['target']['notices']],[False,False,False])
            self.assertNotEqual(pair['source']['notices'],pair['target']['notices'])

    def test_nested_path_set_detaches_source_shared_records(self):
        pair=self.shared['nested_data_set']['forward']
        self.assertEqual(pair['target']['oldStarts'],['09:00','10:00','14:00'])
        self.assertNotEqual(pair['source']['oldStarts'],pair['target']['oldStarts'])

    def test_force_same_reference_fires_raw_changes_but_not_deep_watch(self):
        row=self.shared['force_same_root']['forward']['target']
        self.assertEqual(len(row['rawItemsChanges']),3)
        self.assertEqual([r['force'] for r in row['rawItemsChanges']],[True,True,False])
        self.assertEqual(len(row['notices']),1)

    def test_republishing_adds_spurious_noop_notices(self):
        pair=self.shared['shallow_republish']['noop']
        self.assertEqual(len(pair['source']['notices']),1)
        self.assertEqual(len(pair['target']['notices']),3)

    def test_bounds_controls_remain_no_effect(self):
        for variant in self.shared.values():
            for name in ['lower','upper']:
                pair=variant[name]
                self.assertEqual(projection(pair['source']),projection(pair['target']))
                self.assertEqual(pair['target']['notices'],[])

    def test_normal_and_empty_day_values_match_without_claiming_equal_phases(self):
        for name in ['normal','empty-days']:
            pair=self.phases['unchanged'][name]
            self.assertTrue(pair['source']['constructed'] and pair['target']['constructed'])
            self.assertEqual(pair['source']['firstRead'],pair['target']['firstRead'])
        source=self.phases['unchanged']['normal']['source']['trace']
        target=self.phases['unchanged']['normal']['target']['trace']
        self.assertGreater(source.index('label:evaluate'),source.index('construct:return'))
        self.assertLess(target.index('label:evaluate'),target.index('inited:enter'))

    def test_invalid_days_are_source_getter_errors_but_target_constructor_errors(self):
        for name in ['days-hole','days-null','days-undefined']:
            pair=self.phases['unchanged'][name]
            self.assertTrue(pair['source']['constructed'])
            self.assertEqual(pair['source']['firstRead'],{'kind':'error','name':'TypeError'})
            self.assertFalse(pair['target']['constructed'])
            self.assertEqual(pair['target']['constructorError'],'TypeError')
            self.assertNotIn('inited:enter',pair['target']['trace'])

    def test_source_can_recover_after_bad_getter_demand(self):
        for name in ['days-hole','days-null','days-undefined']:
            pair=self.phases['unchanged'][name]
            self.assertEqual(pair['source']['recovery'],{'error':None,'read':{'kind':'value','type':'string','value':'one'}})
            self.assertIsNone(pair['target']['recovery'])

    def test_catch_and_drop_are_not_exception_semantic_repairs(self):
        swallowed=self.phases['catch_return_empty']['days-hole']
        self.assertEqual(swallowed['source']['firstRead']['kind'],'error')
        self.assertEqual(swallowed['target']['firstRead'],{'kind':'value','type':'string','value':''})
        dropped=self.phases['drop_computed']['normal']
        self.assertEqual(dropped['source']['firstRead']['value'],'one')
        self.assertEqual(dropped['target']['firstRead']['type'],'undefined')

    def test_no_waiver_or_new_scope_score_model_claim(self):
        a=self.result['audit']
        for name in ['all_observer_equivalence_proven','exception_phase_equivalence_proven','general_impossibility_claimed',
                     'automatic_repair_implemented','diagnostics_waived','scope_changed','production_code_or_prompt_changed',
                     'canonical_or_manual_files_written','browser_started','server_started','new_manual_confirmation',
                     'new_full30_run','historical_scores_rewritten','whole_component_passed']:
            self.assertFalse(a[name])
        self.assertTrue(a['dynamic_public_key_block_retained'])
        self.assertEqual(a['model_calls'],0)
        self.assertEqual(a['original_batch'],{'configured':30,'passed':24,'failed':6,'execution_errors':0,'total_tokens':1821544})
        self.assertEqual(self.result['native']['runtime'],{'source':'2.7.16','target':'3.15.6'})


if __name__=='__main__':
    unittest.main()
