"""Bounded Ref successes, native deep-ref negatives and unchanged production gates."""
import json
import re
import unittest

from migration_pipeline.audit_ref_contract_v12 import (
    ROOT, BASE, ADAPTER, REF_RUNTIME, EXPANDED_RUNTIME, DESCRIPTOR_RUNTIME,
    PATH_RUNTIME, RUNTIME, payload, node, candidates, broad_replay)
from migration_pipeline.audit_v7_source_queue_contract import verify, sha
from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
from migration_pipeline.utils.repair_scheduler import candidate_gate

DEEP_GAPS = {'native_deep_ref_nested_property_dependency', 'native_deep_ref_array_mutator_dependency',
             'native_deep_ref_array_element_dependency'}


class RefContractV12Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = payload(); cls.adapted = candidates(cls.data)
        assert all(a['changes'] and not a['production_eligible'] for a in cls.adapted.values())
        cls.request = {**cls.data, **{n: a['code'] for n, a in cls.adapted.items()}}
        cls.refs = node(ROOT / REF_RUNTIME, cls.request)
        cls.expanded = node(ROOT / EXPANDED_RUNTIME, cls.request)
        cls.original = node(ROOT / RUNTIME, cls.request)
        cls.descriptors = node(ROOT / DESCRIPTOR_RUNTIME, cls.request)
        cls.paths = node(ROOT / PATH_RUNTIME, cls.request)
        cls.controls = node(ROOT / 'migration_pipeline/audit_ref_contract_v12_controls.cjs', cls.data)
        cls.mounted, cls.aliases = broad_replay()

    def scenarios(self, *names):
        for name in names:
            with self.subTest(scenario=name):
                rows = [p for p in self.refs['pairs'] if p['scenario'] == name]
                self.assertTrue(rows); self.assertTrue(all(p['equal'] for p in rows), rows)

    def test_original_expansion_152_points_marker_gap_4_to_0(self):
        self.assertEqual(len(self.expanded['pairs']), 152)
        self.assertTrue(all(p['equal'] for p in self.expanded['pairs']))
        before = json.loads((BASE / 'v11_expanded_observations.json').read_text(encoding='utf-8'))
        self.assertEqual(sum(not p['equal'] for p in before['pairs']), 4)
        for a, b in zip(before['pairs'], self.expanded['pairs']):
            self.assertEqual(tuple(a[k] for k in ['subject', 'scenario', 'phase']),
                             tuple(b[k] for k in ['subject', 'scenario', 'phase']))
            if a['equal']: self.assertTrue(b['equal'])

    def test_new_24_ref_scenarios_192_points_have_six_explicit_unresolved_points(self):
        self.assertEqual(len(self.refs['scenarios']), 24)
        self.assertEqual(len(self.refs['pairs']), 192)
        mismatches = [p for p in self.refs['pairs'] if not p['equal']]
        self.assertEqual(len(mismatches), 6)
        self.assertEqual({p['scenario'] for p in mismatches}, DEEP_GAPS)
        self.assertTrue(all(p['phase'] == 'action_1_tick' and not p['eventsEqual'] for p in mismatches))

    def test_structural_marker_is_unwrapped_without_force_observing_inner_value(self):
        self.scenarios('marker_object_unwrap', 'marker_value_mutation_is_raw', 'marker_no_value')

    def test_marker_writeback_keeps_original_ref_and_replacement_keeps_old_value(self):
        self.scenarios('marker_writeback_keeps_ref', 'marker_ref_replacement')

    def test_false_or_truthy_nonboolean_marker_is_not_a_ref(self):
        self.scenarios('marker_false_not_unwrapped', 'marker_truthy_string_not_ref')

    def test_frozen_and_getter_only_marker_writeback_preserve_native_errors(self):
        self.scenarios('marker_frozen_writeback_throws', 'marker_getter_only_writeback_throws')

    def test_native_scalar_ref_external_updates_and_parent_writeback(self):
        self.scenarios('native_scalar_ref_external_value_update', 'native_scalar_parent_writeback')

    def test_native_ref_same_value_nan_signed_zero(self):
        self.scenarios('native_scalar_same_value_no_notification', 'native_ref_nan_same_value', 'native_ref_signed_zero')

    def test_native_ref_replacement_cleans_old_subscription_at_source_timing(self):
        self.scenarios('native_ref_replacement_cleans_old_subscription', 'native_ref_old_alias_before_first_flush')

    def test_array_elements_are_refs_not_automatically_unwrapped(self):
        self.scenarios('native_ref_array_element_not_auto_unwrapped')

    def test_native_shallow_ref_raw_child_and_whole_value_changes(self):
        self.scenarios('native_shallow_ref_raw_nested_mutation', 'native_shallow_ref_value_replacement',
                       'native_shallow_ref_parent_writeback')

    def test_native_deep_ref_whole_value_replacement_does_not_prove_inner_dependencies(self):
        self.scenarios('native_deep_ref_value_replacement')
        for name in DEEP_GAPS:
            rows = [p for p in self.refs['pairs'] if p['scenario'] == name and p['phase'] == 'action_1_tick']
            self.assertEqual(len(rows), 2)
            self.assertTrue(all(not p['equal'] for p in rows))

    def test_genuine_native_refs_are_constructed_on_both_sides_not_just_markers(self):
        self.assertIn('Frozen Vue2.7.16 ref/shallowRef', self.refs['harness']['nativeRefConstructor'])
        self.assertIn('not as a parent/watch/effect', self.refs['harness']['nativeRefConstructor'])
        runs = [r for r in self.refs['runs'] if r['scenario'].startswith('native_')]
        self.assertEqual(len(runs), 60)
        for variant in ['vue_source', 'san_v7']:
            run = next(r for r in runs if r['subject'] == 'generic' and r['variant'] == variant
                       and r['scenario'] == 'native_scalar_ref_external_value_update')
            self.assertEqual(run['refSubscribersBeforeDispose'], [1])
            self.assertEqual(run['refSubscribersAfterDispose'], [0])

    def test_all_48_ref_cleanup_comparisons_release_subscriptions(self):
        self.assertEqual(len(self.refs['cleanup_pairs']), 48)
        self.assertTrue(all(all(p[k] for k in ['errorsEqual', 'sourceSubscribersReleased', 'sanSubscribersReleased'])
                            for p in self.refs['cleanup_pairs']))

    def test_shared_ref_owners_keep_one_subscription_until_last_dispose(self):
        self.assertEqual(self.controls['subscribers'], [1, 1, 0])
        self.assertEqual(self.controls['first'], [1, 1])
        self.assertEqual(self.controls['second'], [1, 2])
        self.assertEqual(self.controls['third'], [1, 2])
        self.assertTrue(self.controls['restored'] and self.controls['dataPrototypeUnchanged'])
        self.assertTrue(self.controls['globalDepTargetUnchanged'])

    def test_original_116_descriptor_104_and_path_172_have_no_regression(self):
        for observed, count in [(self.original, 116), (self.descriptors, 104), (self.paths, 172)]:
            self.assertEqual(len(observed['pairs']), count)
            self.assertTrue(all(p['equal'] for p in observed['pairs']))

    def test_lifecycle_cleanup_mismatch_not_waived_by_ref_successes(self):
        self.assertEqual([p for p in self.expanded['cleanup_pairs'] if not p['equal']],
                         [{'subject': 'task', 'scenario': 'cyclic_plain_value', 'equal': False}])

    def test_native_parent_child_36_and_alias_56_regression(self):
        mounted = [p for p in self.mounted['pairs'] if p['variant'] == 'v3']
        self.assertEqual(len(mounted), 36)
        self.assertTrue(all(all(p[k] for k in ['parentStateEqual', 'childComputedEqual', 'domTextEqual', 'effectsEqual', 'errorsEqual']) for p in mounted))
        self.assertEqual(len(self.aliases['pairs']), 56)
        self.assertTrue(all(all(p[k] for k in ['stateEqual', 'eventsEqual', 'errorsEqual', 'warningsEqual']) for p in self.aliases['pairs']))
        for run in self.aliases['runs']:
            self.assertTrue(run['frameworkPrototypeUnchanged'] and run['instanceWrappersRemoved'])

    def test_no_native_ref_subscription_mutant_reproduces_scalar_update_failure(self):
        anchor = 'record.sub={update(){changed(value,record.token);}};'
        changed = {}
        for name, result in self.adapted.items():
            self.assertEqual(result['code'].count(anchor), 1)
            changed[name] = result['code'].replace(anchor, 'record.sub={update(){}};')
        observed = node(ROOT / REF_RUNTIME, {**self.data, **changed})
        rows = [p for p in observed['pairs'] if p['scenario'] == 'native_scalar_ref_external_value_update'
                and p['phase'] == 'action_1_tick']
        self.assertEqual(len(rows), 2); self.assertTrue(all(not p['equal'] for p in rows))

    def test_no_writeback_mutant_reproduces_marker_assignment_failure(self):
        anchor = 'else if(isRef(before)&&!isRef(next)){before.value=next;return;}'
        changed = {}
        for name, result in self.adapted.items():
            self.assertEqual(result['code'].count(anchor), 1)
            changed[name] = result['code'].replace(anchor, 'else if(false){before.value=next;return;}')
        observed = node(ROOT / REF_RUNTIME, {**self.data, **changed})
        rows = [p for p in observed['pairs'] if p['scenario'] == 'marker_writeback_keeps_ref' and p['phase'] == 'action_1_sync']
        self.assertEqual(len(rows), 2); self.assertTrue(all(not p['equal'] for p in rows))

    def test_opt_in_exact_source_guard_and_reapplication_decline(self):
        requests = [{'code': self.data['san'], 'vue': self.data['vue'], 'experimental': False},
                    {'code': self.adapted['san']['code'], 'vue': self.data['vue'], 'experimental': True},
                    {'code': self.data['san'].replace('pending[index]=false;', 'pending[index]=true;'),
                     'vue': self.data['vue'], 'experimental': True}]
        for request in requests:
            result = node(ROOT / ADAPTER, request)
            self.assertEqual(result['code'], request['code']); self.assertEqual(result['changes'], [])

    def test_templates_old_code_prompt_gate_and_manual_pages_unchanged(self):
        for name, result in self.adapted.items():
            strip = lambda code: re.sub(r'<script\b[^>]*>[\s\S]*?</script\s*>', '<script/>', code)
            self.assertEqual(strip(self.data[name]), strip(result['code']))
        verify(BASE)
        for name, expected in json.loads((BASE / 'protected_files.json').read_text(encoding='utf-8')).items():
            self.assertEqual(sha(ROOT / name), expected, name)

    def test_deep_ref_limits_and_three_production_blockers_remain(self):
        result = self.adapted['san']; self.assertFalse(result['production_eligible'])
        self.assertTrue(any('deep foreign observers' in s and 'custom/computed Ref' in s for s in result['limitations']))
        diag = source_parent_watch_semantics(result['code'], self.data['vue'])
        self.assertEqual({f['code'] for f in diag['findings']}, {
            'source_parent_watch_exception_policy_unproven', 'source_parent_watch_dynamic_key_unproven', 'source_parent_watch_not_landed'})
        state = {'generated_code': self.data['san'], 'vue_source': self.data['vue'], 'validation_errors': diag['findings']}
        gate = candidate_gate(state, {**state, 'generated_code': result['code'], 'validation_errors': [], 'validation_passed': True})
        self.assertTrue(gate['should_stop'])

    def test_repeat_observation_and_no_host_listener_or_prototype_leak(self):
        self.assertEqual(node(ROOT / REF_RUNTIME, self.request), self.refs)
        self.assertTrue(self.refs['host_prototype_clean'] and self.refs['rejection_listener_restored'])


if __name__ == '__main__': unittest.main()
