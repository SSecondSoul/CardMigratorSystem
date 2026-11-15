"""Expanded native counterexamples; passing diagnostics do not certify V9."""
import json
import unittest

from migration_pipeline.audit_shape_input_expansion import inputs, node, ROOT, BASE, RUNTIME, ORIGINAL_RUNTIME
from migration_pipeline.audit_v7_source_queue_contract import sha, verify
from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
from migration_pipeline.utils.repair_scheduler import candidate_gate

GAPS = {'pure_getter_value', 'getter_setter_value', 'nonconfigurable_data_value', 'symbol_properties_value',
        'null_prototype_value', 'custom_prototype_value', 'false_ref_marker_value', 'true_ref_marker_value',
        'skip_true_marker_value', 'skip_false_marker_value', 'regexp_value', 'map_value', 'set_value', 'external_new_path'}


class ShapeInputExpansionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.input = inputs(); cls.observed = node(ROOT / RUNTIME, cls.input)

    def rows(self, scenario):
        return [p for p in self.observed['pairs'] if p['scenario'] == scenario]

    def frame(self, scenario, variant, index=0, subject='generic'):
        return next(r['frames'][index] for r in self.observed['runs']
                    if r['scenario'] == scenario and r['variant'] == variant and r['subject'] == subject)

    def control(self, name):
        rows = self.rows(name); self.assertTrue(rows); self.assertTrue(all(p['equal'] for p in rows), rows)

    def test_24_scenarios_96_runs_152_action_pairs_with_80_mismatches(self):
        self.assertEqual(len(self.observed['scenarios']), 24)
        self.assertEqual(len(self.observed['runs']), 96)
        self.assertEqual(len(self.observed['pairs']), 152)
        self.assertEqual(sum(not p['equal'] for p in self.observed['pairs']), 80)
        for subject in ['task', 'generic']:
            self.assertEqual({p['scenario'] for p in self.observed['pairs'] if p['subject'] == subject and not p['equal']}, GAPS)

    def test_old_116_pair_matrix_is_still_equal_no_code_regression(self):
        old = node(ROOT / ORIGINAL_RUNTIME, self.input)
        self.assertEqual(len(old['pairs']), 116); self.assertTrue(all(p['equal'] for p in old['pairs']))

    def test_sealed_value_control(self): self.control('sealed_value')
    def test_nonextensible_value_control(self): self.control('prevent_extensions_value')
    def test_frozen_container_skips_nested_dependencies_control(self): self.control('frozen_with_observed_child')
    def test_sealed_container_reaches_existing_observed_child_control(self): self.control('sealed_with_observed_child')
    def test_detached_alias_can_be_restored_control(self): self.control('restored_observed_alias')
    def test_shared_dag_control(self): self.control('shared_dag_value')
    def test_function_assignment_control(self): self.control('function_value')
    def test_cyclic_value_action_phase_control_not_cleanup_waiver(self): self.control('cyclic_plain_value')

    def assert_source_accepts_adapter_rejects(self, scenario):
        source = self.frame(scenario, 'vue_source')
        candidate = self.frame(scenario, 'san_v9_expanded_inputs')
        self.assertEqual(source['errors'], [], scenario)
        self.assertEqual(candidate['errors'][0]['name'], 'TypeError', scenario)
        self.assertIn('unsupported observation shape', candidate['errors'][0]['message'], scenario)
        self.assertFalse(self.rows(scenario)[0]['stateEqual'])

    def test_pure_getter_value_source_acceptance_is_not_an_accessor_purity_proof(self):
        self.assert_source_accepts_adapter_rejects('pure_getter_value')
        self.assertIn('not a proof', self.observed['harness']['accessorCoverage'])

    def test_original_getter_setter_value_is_rejected_by_guard(self):
        self.assert_source_accepts_adapter_rejects('getter_setter_value')

    def test_nonconfigurable_property_should_be_skipped_not_rejected(self):
        self.assert_source_accepts_adapter_rejects('nonconfigurable_data_value')

    def test_symbol_properties_remain_source_values(self):
        self.assert_source_accepts_adapter_rejects('symbol_properties_value')
        extra = dict(self.frame('symbol_properties_value', 'vue_source')['state']['settings']['entries'])['extra']
        self.assertEqual(extra['symbols'], [['Symbol(hidden-key)', 7]])

    def test_null_and_custom_prototypes_are_not_plain_type_guard_equivalence(self):
        for name in ['null_prototype_value', 'custom_prototype_value']:
            self.assert_source_accepts_adapter_rejects(name)

    def test_false_ref_marker_is_not_a_ref_and_still_rejected(self):
        self.assert_source_accepts_adapter_rejects('false_ref_marker_value')
        extra = dict(self.frame('false_ref_marker_value', 'vue_source')['state']['settings']['entries'])['extra']
        self.assertFalse(dict(extra['entries'])['__v_isRef'])

    def test_true_marker_has_native_source_unwrapping_not_actual_ref_coverage_claim(self):
        self.assert_source_accepts_adapter_rejects('true_ref_marker_value')
        extra = dict(self.frame('true_ref_marker_value', 'vue_source')['state']['settings']['entries'])['extra']
        self.assertEqual(dict(extra['entries'])['name'], 'ref-value')

    def test_true_and_false_skip_markers_have_different_source_observation_policy(self):
        for name in ['skip_true_marker_value', 'skip_false_marker_value']:
            self.assert_source_accepts_adapter_rejects(name)
        raw = self.frame('skip_true_marker_value', 'vue_source', index=-1)
        reactive = self.frame('skip_false_marker_value', 'vue_source', index=-1)
        self.assertEqual(raw['events'], [])
        self.assertTrue(any(e.get('name') == 'recount' for e in reactive['events']))

    def test_regexp_map_set_assignment_acceptance_is_separate_from_observer_support(self):
        for name in ['regexp_value', 'map_value', 'set_value']:
            self.assert_source_accepts_adapter_rejects(name)

    def test_external_known_path_keeps_identity_and_notifications(self):
        self.control('external_known_path')
        events = self.frame('external_known_path', 'vue_source')['events']
        self.assertIn({'kind': 'mark', 'text': 'root-identity:true'}, events)

    def test_external_root_replace_control(self): self.control('external_root_replace')

    def test_external_new_path_clone_and_notification_gap_is_explicit_mapping(self):
        source = self.frame('external_new_path', 'vue_source')
        candidate = self.frame('external_new_path', 'san_v9_expanded_inputs')
        self.assertIn({'kind': 'mark', 'text': 'root-identity:true'}, source['events'])
        self.assertIn({'kind': 'mark', 'text': 'root-identity:false'}, candidate['events'])
        self.assertEqual(self.frame('external_new_path', 'vue_source', index=-1)['events'], [])
        self.assertTrue(self.frame('external_new_path', 'san_v9_expanded_inputs', index=-1)['events'])
        self.assertIn('without force/silent', self.observed['harness']['comparison'])

    def test_disposal_difference_is_counted_separately_not_silently_dropped(self):
        self.assertEqual(len(self.observed['cleanup_pairs']), 48)
        mismatches = [p for p in self.observed['cleanup_pairs'] if not p['equal']]
        self.assertEqual(mismatches, [{'subject': 'task', 'scenario': 'cyclic_plain_value', 'equal': False}])
        rows = [r for r in self.observed['runs'] if r['subject'] == 'task' and r['scenario'] == 'cyclic_plain_value']
        self.assertEqual([r['cleanupErrors'][0]['channel'] for r in rows], ['report-only', 'dispose'])

    def test_coverage_obligations_keep_five_independent_boundaries(self):
        self.assertEqual({r['id'] for r in self.observed['coverage_obligations']},
                         {'EXP-ACCESSOR', 'EXP-METADATA', 'EXP-OPAQUE', 'EXP-DATA-PATH', 'EXP-LIFECYCLE-ERROR'})
        self.assertTrue(all(r['category'] == 'remaining_risk' for r in self.observed['coverage_obligations']))

    def test_exact_device_extension_only_not_a_source_component_rewrite(self):
        harness = self.observed['harness']
        self.assertEqual(harness['extraBindings'], ['replaceRoot', 'setPath'])
        self.assertFalse(harness['componentCodeModified'] or harness['originalDeviceModified'])
        self.assertEqual(sha(ROOT / ORIGINAL_RUNTIME), harness['baseSha256'])
        self.assertNotEqual(harness['generatedSha256'], harness['baseSha256'])

    def test_protected_production_prompt_and_acceptance_files_unchanged(self):
        verify(BASE)
        for name, expected in json.loads((BASE / 'protected_files.json').read_text(encoding='utf-8')).items():
            self.assertEqual(sha(ROOT / name), expected, name)

    def test_all_three_production_blockers_and_forged_pass_gate_remain(self):
        diagnostic = source_parent_watch_semantics(self.input['san'], self.input['vue'])
        self.assertEqual(len(diagnostic['findings']), 3)
        before = {'generated_code': self.input['san'], 'vue_source': self.input['vue'], 'validation_errors': diagnostic['findings']}
        gate = candidate_gate(before, {**before, 'validation_errors': [], 'validation_passed': True})
        self.assertTrue(gate['should_stop']); self.assertEqual(len(gate['waived_source_parent_watch_boundaries']), 2)

    def test_repeat_native_observations_and_host_isolation(self):
        repeat = node(ROOT / RUNTIME, self.input)
        self.assertEqual(repeat, self.observed)
        self.assertTrue(repeat['host_prototype_clean'] and repeat['rejection_listener_restored'])


if __name__ == '__main__': unittest.main()
