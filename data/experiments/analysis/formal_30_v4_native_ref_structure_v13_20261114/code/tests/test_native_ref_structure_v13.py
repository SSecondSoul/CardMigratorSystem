"""Bounded structural dependencies and preserved private-property counterexamples."""
import json
import re
import unittest

from migration_pipeline.audit_native_ref_structure_v13 import (
    ROOT, BASE, ADAPTER, STRUCTURE_RUNTIME, REF_RUNTIME, PATH_RUNTIME, DESCRIPTOR_RUNTIME,
    EXPANDED_RUNTIME, RUNTIME, payload, node, candidates, broad_replay)
from migration_pipeline.audit_v7_source_queue_contract import verify, sha
from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
from migration_pipeline.utils.repair_scheduler import candidate_gate


class NativeRefStructureV13Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = payload(); cls.adapted = candidates(cls.data)
        assert all(a['changes'] for a in cls.adapted.values())
        cls.request = {**cls.data, **{n: a['code'] for n, a in cls.adapted.items()}}
        cls.refs = node(ROOT / REF_RUNTIME, cls.request)
        cls.structure = node(ROOT / STRUCTURE_RUNTIME, cls.request)
        cls.old_matrices = {name: node(ROOT / runtime, cls.request) for name, runtime in
                            [('original', RUNTIME), ('expanded', EXPANDED_RUNTIME),
                             ('descriptors', DESCRIPTOR_RUNTIME), ('paths', PATH_RUNTIME)]}
        cls.controls = node(ROOT / 'migration_pipeline/audit_native_ref_structure_v13_controls.cjs', cls.data)
        cls.mounted, cls.aliases = broad_replay()

    def scenarios(self, *names):
        for name in names:
            with self.subTest(scenario=name):
                rows = [p for p in self.structure['pairs'] if p['scenario'] == name]
                self.assertTrue(rows); self.assertTrue(all(p['equal'] for p in rows), rows)

    def test_original_ref_matrix_192_points_six_to_four_no_regression(self):
        self.assertEqual(len(self.refs['pairs']), 192)
        gaps = [p for p in self.refs['pairs'] if not p['equal']]
        self.assertEqual(len(gaps), 4)
        self.assertEqual({p['scenario'] for p in gaps},
                         {'native_deep_ref_nested_property_dependency', 'native_deep_ref_array_element_dependency'})
        before = json.loads((BASE / 'v12_ref_observations.json').read_text(encoding='utf-8'))
        for a, b in zip(before['pairs'], self.refs['pairs']):
            self.assertEqual(tuple(a[k] for k in ['subject', 'scenario', 'phase']),
                             tuple(b[k] for k in ['subject', 'scenario', 'phase']))
            if a['equal']: self.assertTrue(b['equal'])

    def test_11_new_structural_scenarios_116_points_have_two_unresolved_private_writes(self):
        self.assertEqual(len(self.structure['scenarios']), 11)
        self.assertEqual(len(self.structure['pairs']), 116)
        gaps = [p for p in self.structure['pairs'] if not p['equal']]
        self.assertEqual(len(gaps), 2)
        self.assertTrue(all(p['scenario'] == 'native_new_property_dependency_still_private'
                            and p['phase'] == 'action_2_tick' and not p['eventsEqual'] for p in gaps))

    def test_array_push_pop_splice_sort_reverse(self):
        self.scenarios('native_array_push_pop_splice', 'native_array_reverse_sort')

    def test_nested_array_structure(self): self.scenarios('native_nested_array_structural_dependency')

    def test_native_set_delete_array_element_and_ref_object_structure(self):
        self.scenarios('native_array_element_add_delete_structure', 'native_ref_object_add_delete_structure')

    def test_detached_alias_notification_before_flush_and_cleanup_after_recollection(self):
        self.scenarios('detached_native_array_stops_after_recollection', 'detached_native_array_before_first_flush_notifies')

    def test_shallow_ref_of_previously_observed_array_is_structural(self):
        self.scenarios('shallow_ref_of_existing_observed_array')

    def test_raw_shallow_array_does_not_subscribe_element_structure(self):
        self.scenarios('raw_shallow_array_must_not_subscribe_child_structure')

    def test_raw_array_index_remains_nonreactive(self): self.scenarios('native_raw_array_index_assignment_stays_raw')

    def test_all_new_observer_and_ref_subscriptions_released(self):
        self.assertEqual(len(self.structure['nativeObserverCleanup']), 44)
        self.assertTrue(all(r['allReleased'] for r in self.structure['nativeObserverCleanup']))
        self.assertTrue(all(all(p[k] for k in ['errorsEqual', 'sourceSubscribersReleased', 'sanSubscribersReleased'])
                            for p in self.structure['cleanup_pairs']))

    def test_shared_ref_array_and_element_deps_one_subscription_each(self):
        self.assertEqual(self.controls['subscribers'], [1, 1, 0])
        self.assertEqual(self.controls['structuralBefore'], [1, 1, 1])
        self.assertEqual(self.controls['structuralAfter'], [0, 0, 0])
        self.assertEqual(self.controls['first'], [1, 1]); self.assertEqual(self.controls['second'], [1, 2])
        self.assertEqual(self.controls['third'], [1, 2])

    def test_identity_getters_observers_framework_prototypes_and_global_target_untouched(self):
        for key in ['restored', 'valueIdentityPreserved', 'observerIdentityPreserved', 'propertyAccessorPreserved',
                    'depPrototypeUnchanged', 'dataPrototypeUnchanged', 'globalDepTargetUnchanged']:
            self.assertTrue(self.controls[key], key)

    def test_old_116_152_104_172_point_matrices_unchanged(self):
        for name, count in [('original', 116), ('expanded', 152), ('descriptors', 104), ('paths', 172)]:
            self.assertEqual(len(self.old_matrices[name]['pairs']), count)
            self.assertTrue(all(p['equal'] for p in self.old_matrices[name]['pairs']))

    def test_old_lifecycle_error_still_counted(self):
        self.assertEqual([p for p in self.old_matrices['expanded']['cleanup_pairs'] if not p['equal']],
                         [{'subject': 'task', 'scenario': 'cyclic_plain_value', 'equal': False}])

    def test_removing_structural_collection_reproduces_array_mutator_failure(self):
        anchor = 'if(collecting&&native){'; changed = {}
        for name, a in self.adapted.items():
            self.assertEqual(a['code'].count(anchor), 1)
            changed[name] = a['code'].replace(anchor, 'if(false){')
        observed = node(ROOT / REF_RUNTIME, {**self.data, **changed})
        rows = [p for p in observed['pairs'] if p['scenario'] == 'native_deep_ref_array_mutator_dependency'
                and p['phase'] == 'action_1_tick']
        self.assertEqual(len(rows), 2); self.assertTrue(all(not p['equal'] for p in rows))

    def test_overcollecting_raw_shallow_array_reproduces_false_notification(self):
        anchor = 'if(collectNativeObserver(result)&&Array.isArray(result))dependNativeArray(result);'
        changed = {}
        for name, a in self.adapted.items():
            self.assertEqual(a['code'].count(anchor), 1)
            changed[name] = a['code'].replace(anchor, 'collectNativeObserver(result);if(Array.isArray(result))dependNativeArray(result);')
        observed = node(ROOT / STRUCTURE_RUNTIME, {**self.data, **changed})
        rows = [p for p in observed['pairs'] if p['scenario'] == 'raw_shallow_array_must_not_subscribe_child_structure'
                and p['phase'] == 'action_1_tick']
        self.assertEqual(len(rows), 2); self.assertTrue(all(not p['equal'] for p in rows))

    def test_native_parent_child_36_and_alias_56_regression(self):
        rows = [p for p in self.mounted['pairs'] if p['variant'] == 'v3']
        self.assertEqual(len(rows), 36)
        self.assertTrue(all(all(p[k] for k in ['parentStateEqual', 'childComputedEqual', 'domTextEqual', 'effectsEqual', 'errorsEqual']) for p in rows))
        self.assertEqual(len(self.aliases['pairs']), 56)
        self.assertTrue(all(all(p[k] for k in ['stateEqual', 'eventsEqual', 'errorsEqual', 'warningsEqual']) for p in self.aliases['pairs']))

    def test_opt_in_source_guard_reapplication_and_templates(self):
        for changes in [{'experimental': False}, {'code': self.adapted['san']['code']},
                        {'code': self.data['san'].replace('pending[index]=false;', 'pending[index]=true;')}]:
            request = {'code': self.data['san'], 'vue': self.data['vue'], 'experimental': True, **changes}
            result = node(ROOT / ADAPTER, request)
            self.assertEqual(result['code'], request['code']); self.assertEqual(result['changes'], [])
        for name, result in self.adapted.items():
            strip = lambda c: re.sub(r'<script\b[^>]*>[\s\S]*?</script\s*>', '<script/>', c)
            self.assertEqual(strip(self.data[name]), strip(result['code']))

    def test_production_blockers_and_forged_pass_gate_remain(self):
        result = self.adapted['san']; self.assertFalse(result['production_eligible'])
        self.assertTrue(any('private property deps' in s for s in result['limitations']))
        diag = source_parent_watch_semantics(result['code'], self.data['vue'])
        self.assertEqual({f['code'] for f in diag['findings']}, {
            'source_parent_watch_exception_policy_unproven', 'source_parent_watch_dynamic_key_unproven', 'source_parent_watch_not_landed'})
        state = {'generated_code': self.data['san'], 'vue_source': self.data['vue'], 'validation_errors': diag['findings']}
        gate = candidate_gate(state, {**state, 'generated_code': result['code'], 'validation_errors': [], 'validation_passed': True})
        self.assertTrue(gate['should_stop'])

    def test_previous_code_production_and_manual_files_protected(self):
        verify(BASE)
        for name, expected in json.loads((BASE / 'protected_files.json').read_text(encoding='utf-8')).items():
            self.assertEqual(sha(ROOT / name), expected, name)

    def test_repeat_native_observation_host_and_listener_cleanup(self):
        self.assertEqual(node(ROOT / STRUCTURE_RUNTIME, self.request), self.structure)
        self.assertTrue(self.structure['host_prototype_clean'] and self.structure['rejection_listener_restored'])


if __name__ == '__main__': unittest.main()
