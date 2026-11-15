"""Source-matched V10 cases plus explicit unresolved counterexamples and gates."""
import json
import unittest

from migration_pipeline.audit_shape_observer_v10 import BASE, ADAPTER, candidates
from migration_pipeline.audit_v7_dynamic_shape import ROOT, payload, node, RUNTIME
from migration_pipeline.audit_shape_input_expansion import RUNTIME as EXPANDED_RUNTIME
from migration_pipeline.audit_v7_source_queue_contract import sha, verify
from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
from migration_pipeline.utils.repair_scheduler import candidate_gate

PRIOR = ROOT / 'data/experiments/analysis/formal_30_v4_parent_alias_child_audit_v1_20261112'
SUPPLEMENT = ROOT / 'migration_pipeline/audit_shape_descriptors_v10_runtime.cjs'


class ShapeObserverV10Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = payload(); cls.adapted = candidates(cls.data)
        assert all(a['changes'] for a in cls.adapted.values())
        cls.request = {**cls.data, **{n: a['code'] for n, a in cls.adapted.items()}}
        cls.original = node(ROOT / RUNTIME, cls.request)
        cls.expanded = node(ROOT / EXPANDED_RUNTIME, cls.request)
        cls.supplement = node(SUPPLEMENT, cls.request)
        old = json.loads((PRIOR / 'audit.json').read_text(encoding='utf-8'))
        fixture = old['fixture']
        composed = node(ROOT / 'migration_pipeline/probe_async_watcher_scope_adapter_v7.cjs',
                        {'code': fixture['normal'], 'vue': fixture['vue'], 'experimental': True,
                         'error_context_policy': 'private-async-parent-watch-source-context'})
        assert composed['changes'], composed['reviews']
        candidate = node(ROOT / ADAPTER, {'code': composed['code'], 'vue': fixture['vue'], 'experimental': True})
        assert candidate['changes'], candidate['reviews']
        common = {name: (ROOT / next(p for p in old['source_inputs'] if p.endswith(end))).read_text(encoding='utf-8')
                  for name, end in [('vueRuntime', 'vue.runtime.common.dev.js'), ('sanRuntime', 'san.dev.js')]}
        cls.mounted = node(PRIOR / 'code/migration_pipeline/audit_parent_alias_child_runtime.cjs',
                           {**fixture, **common, 'v3': candidate['code']})
        cls.alias = node(ROOT / 'migration_pipeline/audit_parent_alias_observer_v4_runtime.cjs',
                         {'vue': fixture['vue'], 'v4': candidate['code'], **common})

    def scenario(self, name, supplemental=False):
        observed = self.supplement if supplemental else self.expanded
        rows = [p for p in observed['pairs'] if p['scenario'] == name]
        self.assertTrue(rows); self.assertTrue(all(p['equal'] for p in rows), rows)

    def test_original_116_pairs_have_no_regression(self):
        self.assertEqual(len(self.original['pairs']), 116)
        self.assertTrue(all(p['equal'] for p in self.original['pairs']))

    def test_expanded_152_pairs_reduce_80_to_8_without_regressing_controls(self):
        self.assertEqual(len(self.expanded['pairs']), 152)
        mismatches = [p for p in self.expanded['pairs'] if not p['equal']]
        self.assertEqual(len(mismatches), 8)
        self.assertEqual({p['scenario'] for p in mismatches}, {'true_ref_marker_value', 'external_new_path'})
        old = json.loads((BASE / 'v9_expanded_observations.json').read_text(encoding='utf-8'))
        for before, after in zip(old['pairs'], self.expanded['pairs']):
            self.assertEqual((before['subject'], before['scenario'], before['phase']),
                             (after['subject'], after['scenario'], after['phase']))
            if before['equal']: self.assertTrue(after['equal'], after)

    def test_pure_getter_assignment(self): self.scenario('pure_getter_value')
    def test_getter_setter_updates(self): self.scenario('getter_setter_value')
    def test_nonconfigurable_data_is_skipped(self): self.scenario('nonconfigurable_data_value')
    def test_symbol_properties_preserved(self): self.scenario('symbol_properties_value')
    def test_null_and_custom_prototypes(self):
        for n in ['null_prototype_value', 'custom_prototype_value']: self.scenario(n)
    def test_false_ref_is_not_a_ref(self): self.scenario('false_ref_marker_value')
    def test_true_and_false_skip_follow_source_policy(self):
        for n in ['skip_true_marker_value', 'skip_false_marker_value']: self.scenario(n)
    def test_map_set_regexp_are_accepted_without_cloning(self):
        for n in ['map_value', 'set_value', 'regexp_value']: self.scenario(n)

    def test_supplemental_13_scenarios_104_pairs_all_match(self):
        self.assertEqual(len(self.supplement['scenarios']), 13)
        self.assertEqual(len(self.supplement['pairs']), 104)
        self.assertTrue(all(p['equal'] for p in self.supplement['pairs']))

    def test_getter_only_write_is_noop(self): self.scenario('getter_only_write_noop', True)
    def test_getter_only_fresh_child_not_force_observed(self): self.scenario('getter_only_fresh_child_not_observed', True)
    def test_original_setter_receives_original_object(self): self.scenario('getter_setter_receiver', True)
    def test_setter_transformation(self): self.scenario('setter_transform', True)
    def test_setter_exception_does_not_enqueue(self): self.scenario('setter_throw_no_notification', True)
    def test_configurable_readonly_is_converted_like_vue(self): self.scenario('configurable_readonly_data_becomes_reactive', True)
    def test_nonconfigurable_readonly_keeps_native_strict_error(self): self.scenario('nonconfigurable_readonly_data_stays_readonly', True)
    def test_nonconfigurable_accessor_reaches_existing_child(self): self.scenario('nonconfigurable_accessor_observed_child', True)
    def test_symbol_child_not_walked(self): self.scenario('symbol_child_is_not_walked', True)
    def test_raw_map_mutation(self): self.scenario('opaque_map_mutation_is_raw', True)
    def test_array_inserted_accessor(self): self.scenario('array_insert_descriptor', True)
    def test_skip_flag_after_observation_cleans_dependencies(self): self.scenario('skip_flag_changed_after_observation_reuses_node', True)
    def test_incoming_object_identity_not_only_encoded_snapshot(self):
        self.scenario('incoming_identity_is_preserved', True)
        for run in self.supplement['runs']:
            if run['scenario'] == 'incoming_identity_is_preserved':
                marks = [e['text'] for e in run['frames'][0]['events'] if e['kind'] == 'mark']
                self.assertEqual(marks, ['incoming-identity:true'] * 7)

    def test_lifecycle_cleanup_mismatch_not_dropped(self):
        self.assertEqual(len(self.expanded['cleanup_pairs']), 48)
        self.assertEqual([p for p in self.expanded['cleanup_pairs'] if not p['equal']],
                         [{'subject': 'task', 'scenario': 'cyclic_plain_value', 'equal': False}])

    def test_native_parent_child_36_pairs_and_mount(self):
        rows = [p for p in self.mounted['pairs'] if p['variant'] == 'v3']
        self.assertEqual(len(rows), 36)
        self.assertTrue(all(all(p[k] for k in ['parentStateEqual', 'childComputedEqual', 'domTextEqual', 'effectsEqual', 'errorsEqual']) for p in rows))
        for run in self.mounted['runs']:
            self.assertTrue(run['nativeParentAndChildAttached']); self.assertEqual(run['errors'], [])

    def test_native_alias_56_pairs_and_wrapper_cleanup(self):
        self.assertEqual(len(self.alias['pairs']), 56)
        self.assertTrue(all(all(p[k] for k in ['stateEqual', 'eventsEqual', 'errorsEqual', 'warningsEqual']) for p in self.alias['pairs']))
        self.assertTrue(self.alias['rejectionListenerRestored'])
        for run in self.alias['runs']:
            self.assertTrue(run['frameworkPrototypeUnchanged'] and run['instanceWrappersRemoved'])

    def test_exact_opt_in_and_source_contract_decline(self):
        for changes in [{'experimental': False}, {'code': self.data['san'].replace('pending[index]=false;', 'pending[index]=true;')}]:
            request = {'code': self.data['san'], 'vue': self.data['vue'], 'experimental': True, **changes}
            result = node(ROOT / ADAPTER, request)
            self.assertEqual(result['code'], request['code']); self.assertEqual(result['changes'], [])

    def test_reapplication_declines(self):
        result = node(ROOT / ADAPTER, {'code': self.adapted['san']['code'], 'vue': self.data['vue'], 'experimental': True})
        self.assertEqual(result['code'], self.adapted['san']['code']); self.assertEqual(result['changes'], [])

    def test_templates_and_styles_unchanged(self):
        import re
        for name, result in self.adapted.items():
            strip = lambda code: re.sub(r'<script\b[^>]*>[\s\S]*?</script\s*>', '<script/>', code)
            self.assertEqual(strip(self.data[name]), strip(result['code']))

    def test_remaining_boundaries_and_production_gate(self):
        result = self.adapted['san']; self.assertFalse(result['production_eligible'])
        self.assertTrue(any('Ref' in s and 'Proxy' in s for s in result['limitations']))
        diag = source_parent_watch_semantics(result['code'], self.data['vue'])
        self.assertEqual({f['code'] for f in diag['findings']}, {
            'source_parent_watch_exception_policy_unproven', 'source_parent_watch_dynamic_key_unproven',
            'source_parent_watch_not_landed'})
        state = {'generated_code': self.data['san'], 'vue_source': self.data['vue'], 'validation_errors': diag['findings']}
        gate = candidate_gate(state, {**state, 'generated_code': result['code'], 'validation_errors': [], 'validation_passed': True})
        self.assertTrue(gate['should_stop'])

    def test_old_code_prompt_gate_and_manual_config_protected(self):
        verify(BASE)
        for name, expected in json.loads((BASE / 'protected_files.json').read_text(encoding='utf-8')).items():
            self.assertEqual(sha(ROOT / name), expected, name)

    def test_repeat_native_matrix_is_deterministic_and_host_clean(self):
        self.assertEqual(node(ROOT / EXPANDED_RUNTIME, self.request), self.expanded)
        self.assertTrue(self.expanded['host_prototype_clean'] and self.expanded['rejection_listener_restored'])


if __name__ == '__main__': unittest.main()
