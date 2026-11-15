"""The diagnostic suite passes by reproducing real V7 counterexamples, not waiving them."""
import unittest

from migration_pipeline.audit_v7_dynamic_shape import payload, node, ROOT, RUNTIME, BASE
from migration_pipeline.audit_v7_source_queue_contract import sha, verify
from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
from migration_pipeline.utils.repair_scheduler import candidate_gate


GAPS = {'numeric_key', 'symbol_key', 'coerced_existing_key', 'coerced_new_key', 'throwing_key_coercion',
        'date_value', 'frozen_value', 'sparse_array_value', 'new_symbol_value',
        'delete_then_mutate_detached_alias', 'redefine_then_mutate_detached_alias', 'nonenumerable_then_mutate_alias'}


class V7DynamicShapeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.input = payload()
        cls.observed = node(ROOT / RUNTIME, cls.input)

    def pairs(self, name, subject=None):
        return [p for p in self.observed['pairs'] if p['scenario'] == name and (subject is None or p['subject'] == subject)]

    def frames(self, name, variant, subject='generic'):
        return next(r['frames'] for r in self.observed['runs'] if r['scenario'] == name and r['variant'] == variant and r['subject'] == subject)

    def assert_control(self, name):
        pairs = self.pairs(name)
        self.assertTrue(pairs); self.assertTrue(all(p['equal'] for p in pairs), pairs)

    def test_native_two_subject_matrix_dimensions_and_no_fake_all_pass(self):
        self.assertEqual(len(self.observed['scenarios']), 24)
        self.assertEqual(len(self.observed['runs']), 94)
        self.assertEqual(len(self.observed['pairs']), 116)
        self.assertEqual(sum(not p['equal'] for p in self.observed['pairs']), 39)
        for subject in ['task', 'generic']:
            self.assertEqual({p['scenario'] for p in self.observed['pairs'] if p['subject'] == subject and not p['equal']}, GAPS)

    def test_existing_same_value_no_overnotification(self): self.assert_control('existing_same_value')
    def test_existing_changed_value_remains_correct(self): self.assert_control('existing_changed_value')
    def test_new_key_repeat_does_not_become_reactive(self): self.assert_control('new_scalar_repeat')
    def test_own_undefined_property_retained(self): self.assert_control('new_undefined')
    def test_inherited_builtin_shadowing_control(self): self.assert_control('inherited_builtin')
    def test_inherited_setter_control(self): self.assert_control('inherited_setter')
    def test_local_proto_replacement_without_host_pollution(self): self.assert_control('prototype_plain')
    def test_null_proto_control(self): self.assert_control('prototype_null')
    def test_existing_borrowed_property_notifications_control(self): self.assert_control('borrowed_existing_property')
    def test_existing_array_mutator_control(self): self.assert_control('borrowed_array_push')
    def test_delete_readd_is_raw_source_assignment_not_automatic_vue_set(self): self.assert_control('delete_readd_scalar')
    def test_source_numeric_rhs_conversion_preserved(self): self.assert_control('source_rhs_number_conversion')

    def test_numeric_key_source_accepts_candidate_refuses(self):
        source = self.frames('numeric_key', 'vue_source')[0]
        candidate = self.frames('numeric_key', 'san_v7')[0]
        self.assertEqual(source['errors'], [])
        self.assertEqual(dict(source['state']['settings']['entries'])['7'], 42)
        self.assertEqual(candidate['errors'][0]['name'], 'TypeError')
        self.assertNotIn('7', dict(candidate['state']['settings']['entries']))

    def test_symbol_key_source_preserves_property_candidate_refuses(self):
        source = self.frames('symbol_key', 'vue_source')[0]
        candidate = self.frames('symbol_key', 'san_v7')[0]
        self.assertEqual(source['state']['settings']['symbols'], [['Symbol(audit-key)', 42]])
        self.assertEqual(candidate['state']['settings']['symbols'], [])

    def test_to_property_key_coercion_order_is_missing_in_adapter(self):
        for name in ['coerced_existing_key', 'coerced_new_key']:
            source = self.frames(name, 'vue_source')[0]; candidate = self.frames(name, 'san_v7')[0]
            self.assertTrue(any(e['kind'] == 'mark' for e in source['events']))
            self.assertFalse(any(e['kind'] == 'mark' for e in candidate['events']))
            self.assertEqual(source['errors'], []); self.assertEqual(candidate['errors'][0]['name'], 'TypeError')

    def test_thrown_key_coercion_category_and_original_message_preserved_in_evidence(self):
        source = self.frames('throwing_key_coercion', 'vue_source')[0]
        candidate = self.frames('throwing_key_coercion', 'san_v7')[0]
        self.assertEqual(source['errors'][0]['name'], 'RangeError')
        self.assertEqual(source['errors'][0]['message'], 'KeyCoercionFailure')
        self.assertEqual(candidate['errors'][0]['name'], 'TypeError')

    def test_date_and_frozen_and_sparse_values_not_equivalent_to_experimental_refusal(self):
        for name in ['date_value', 'frozen_value', 'sparse_array_value', 'new_symbol_value']:
            source = self.frames(name, 'vue_source')[0]; candidate = self.frames(name, 'san_v7')[0]
            self.assertEqual(source['errors'], [], name)
            self.assertEqual(candidate['errors'][0]['name'], 'TypeError', name)
            self.assertFalse(self.pairs(name, 'generic')[0]['stateEqual'])

    def test_deleted_alias_first_tick_matches_but_later_subscription_is_stale(self):
        self.assert_subscription_gap('delete_then_mutate_detached_alias')

    def test_redefined_alias_has_the_same_subscription_gap(self):
        self.assert_subscription_gap('redefine_then_mutate_detached_alias')

    def test_nonenumerable_alias_has_the_same_subscription_gap(self):
        self.assert_subscription_gap('nonenumerable_then_mutate_alias')

    def assert_subscription_gap(self, name):
        for subject in ['task', 'generic']:
            first = self.pairs(name, subject)[:2]
            self.assertTrue(all(p['equal'] for p in first), first)
            last = self.pairs(name, subject)[-1]
            self.assertTrue(last['stateEqual'] and last['errorsEqual']); self.assertFalse(last['eventsEqual'])
        source = self.frames(name, 'vue_source')[-1]; candidate = self.frames(name, 'san_v7')[-1]
        self.assertEqual(source['events'], [])
        self.assertEqual([e['name'] for e in candidate['events'] if e['kind'] == 'call'], ['recount'])

    def test_raw_array_reflection_kept_separate_from_semantic_comparison(self):
        source = self.frames('existing_same_value', 'vue_source')[0]
        candidate = self.frames('existing_same_value', 'san_v7')[0]
        self.assertIn('__ob__', source['rawRootOwnNames'])
        self.assertNotIn('__ob__', candidate['rawRootOwnNames'])
        self.assertNotEqual(source['rawArrayFacts'], candidate['rawArrayFacts'])
        self.assertTrue(self.pairs('existing_same_value')[0]['equal'])
        self.assertFalse(self.observed['scope']['vueMetadataAndFullReflectionEquivalenceClaimed'])

    def test_browser_build_probes_are_explicit_not_a_general_html_parser(self):
        for run in self.observed['runs']:
            self.assertEqual(run['compilerFeatureProbes'], 2 if run['variant'] == 'vue_source' else 0)
        self.assertTrue(self.observed['scope']['minimalRootRender'])
        self.assertFalse(self.observed['scope']['fullBrowser'])

    def test_no_cross_scenario_host_prototype_or_rejection_listener_pollution(self):
        self.assertTrue(self.observed['host_prototype_clean'])
        self.assertTrue(self.observed['rejection_listener_restored'])
        self.assertTrue(all(not r['cleanupErrors'] for r in self.observed['runs']))

    def test_frozen_observer_and_public_input_files_unchanged(self):
        verify(BASE)
        self.assertEqual(sha(BASE / 'observer_before.cjs'), sha(ROOT / 'migration_pipeline/probe_parent_alias_observer_v4.cjs'))

    def test_diagnostic_and_forged_pass_refusal_remain(self):
        result = source_parent_watch_semantics(self.input['san'], self.input['vue'])
        self.assertEqual(len(result['findings']), 3)
        before = {'generated_code': self.input['san'], 'vue_source': self.input['vue'], 'validation_errors': result['findings']}
        gate = candidate_gate(before, {**before, 'validation_errors': [], 'validation_passed': True})
        self.assertTrue(gate['should_stop']); self.assertEqual(len(gate['waived_source_parent_watch_boundaries']), 2)

    def test_repeat_observations_deterministic(self):
        self.assertEqual(node(ROOT / RUNTIME, self.input), self.observed)


if __name__ == '__main__': unittest.main()
