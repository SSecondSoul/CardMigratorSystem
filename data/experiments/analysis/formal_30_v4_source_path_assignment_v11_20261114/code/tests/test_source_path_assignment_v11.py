"""Bounded native path-assignment closure, regressions and fail-closed controls."""
import json
import re
import unittest

from migration_pipeline.audit_source_path_assignment_v11 import (
    ROOT, BASE, V10, ADAPTER, PATH_RUNTIME, DESCRIPTOR_RUNTIME, EXPANDED_RUNTIME,
    RUNTIME, payload, node, candidates, broad_replay)
from migration_pipeline.audit_v7_source_queue_contract import sha, verify
from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
from migration_pipeline.utils.repair_scheduler import candidate_gate


class SourcePathAssignmentV11Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = payload(); cls.adapted = candidates(cls.data)
        assert all(a['changes'] for a in cls.adapted.values())
        cls.request = {**cls.data, **{n: a['code'] for n, a in cls.adapted.items()}}
        cls.paths = node(ROOT / PATH_RUNTIME, cls.request)
        cls.expanded = node(ROOT / EXPANDED_RUNTIME, cls.request)
        cls.original = node(ROOT / RUNTIME, cls.request)
        cls.descriptors = node(ROOT / DESCRIPTOR_RUNTIME, cls.request)
        cls.controls = node(ROOT / 'migration_pipeline/audit_source_path_assignment_v11_controls.cjs', cls.data)
        cls.mounted, cls.aliases = broad_replay()

    def scenarios(self, *names):
        for name in names:
            with self.subTest(scenario=name):
                rows = [p for p in self.paths['pairs'] if p['scenario'] == name]
                self.assertTrue(rows); self.assertTrue(all(p['equal'] for p in rows), rows)

    def test_all_28_path_scenarios_172_pairs_match(self):
        self.assertEqual(len(self.paths['scenarios']), 28)
        self.assertEqual(len(self.paths['pairs']), 172)
        self.assertTrue(all(p['equal'] for p in self.paths['pairs']))

    def test_new_keys_remain_raw_and_keep_object_identity(self):
        self.scenarios('new_property_repeat_keeps_identity', 'new_object_not_force_observed',
                       'new_top_level_property', 'deleted_known_property_is_raw')

    def test_native_data_get_reads_updated_new_property(self):
        self.scenarios('new_property_read_after_read', 'known_property_alias_identity')

    def test_array_indices_length_and_holes_use_raw_assignment(self):
        self.scenarios('new_array_index_raw', 'existing_array_index_raw', 'array_index_then_push_not_reobserve_old',
                       'array_length_truncate_raw', 'array_length_extend_holes', 'array_invalid_length_throws')

    def test_numeric_keys_are_not_array_index_coercion(self):
        self.scenarios('negative_numeric_property_is_raw', 'fractional_numeric_property_is_raw', 'string_numeric_key_not_coerced_to_index')

    def test_missing_null_primitive_and_nonextensible_targets_keep_native_errors(self):
        self.scenarios('missing_intermediate_throws', 'null_intermediate_throws', 'primitive_target_throws',
                       'frozen_target_native_error', 'new_property_on_sealed_throws')

    def test_accessors_and_nonconfigurable_slots_use_original_descriptor(self):
        self.scenarios('getter_only_target_noop', 'setter_target_receiver', 'nonconfigurable_target_native_write',
                       'existing_property_on_sealed_raw', 'inherited_setter_native_receiver')

    def test_quoted_keys_and_local_prototype_assignment(self):
        self.scenarios('non_identifier_keys', 'prototype_set_local_only')

    def test_new_raw_ref_marker_is_not_forced_through_existing_ref_observer(self):
        self.scenarios('new_raw_marker_not_unwrapped')

    def test_old_116_and_descriptor_104_pairs_have_no_regression(self):
        for observed, count in [(self.original, 116), (self.descriptors, 104)]:
            self.assertEqual(len(observed['pairs']), count)
            self.assertTrue(all(p['equal'] for p in observed['pairs']))

    def test_expanded_152_pairs_reduce_8_to_4_only_actual_ref_remains(self):
        self.assertEqual(len(self.expanded['pairs']), 152)
        mismatches = [p for p in self.expanded['pairs'] if not p['equal']]
        self.assertEqual(len(mismatches), 4)
        self.assertEqual({p['scenario'] for p in mismatches}, {'true_ref_marker_value'})
        old = json.loads((BASE / 'v10_expanded_observations.json').read_text(encoding='utf-8'))
        for before, after in zip(old['pairs'], self.expanded['pairs']):
            self.assertEqual(tuple(before[k] for k in ['subject', 'scenario', 'phase']),
                             tuple(after[k] for k in ['subject', 'scenario', 'phase']))
            if before['equal']: self.assertTrue(after['equal'])

    def test_cleanup_error_difference_remains_separate_and_visible(self):
        self.assertEqual(len(self.expanded['cleanup_pairs']), 48)
        self.assertEqual([p for p in self.expanded['cleanup_pairs'] if not p['equal']],
                         [{'subject': 'task', 'scenario': 'cyclic_plain_value', 'equal': False}])

    def test_removing_local_strict_mode_reproduces_six_frozen_error_mismatches(self):
        anchor = "const data=instance.data,original=data.set;\n  const wrapped=function(expr,value,option){\n   'use strict';"
        replacement = "const data=instance.data,original=data.set;\n  const wrapped=function(expr,value,option){"
        changed = {}
        for name, a in self.adapted.items():
            self.assertEqual(a['code'].count(anchor), 1)
            changed[name] = a['code'].replace(anchor, replacement)
        observed = node(ROOT / PATH_RUNTIME, {**self.data, **changed})
        mismatches = [p for p in observed['pairs'] if not p['equal']]
        self.assertEqual(len(mismatches), 6)
        self.assertEqual({p['scenario'] for p in mismatches},
                         {'primitive_target_throws', 'frozen_target_native_error', 'new_property_on_sealed_throws'})

    def test_explicit_options_dynamic_paths_and_other_roots_are_delegated(self):
        rows = self.controls['results']
        self.assertEqual({r['label'] for r in rows},
                         {'force', 'silent', 'null-option', 'empty-option', 'dynamic-path', 'unrelated-root', 'root-replace'})
        for r in rows:
            self.assertEqual(len(r['calls']), 1, r)
            self.assertTrue(r['calls'][0]['optionSame'], r)
            self.assertTrue(r['restored'], r)
            self.assertEqual(r['finalValue'], 'object' if r['label'] == 'root-replace' else 'changed')
        self.assertTrue(next(r for r in rows if r['label'] == 'root-replace')['rootIdentity'])

    def test_instance_wrapper_removed_and_framework_prototype_unchanged(self):
        self.assertTrue(self.controls['whileMapped'])
        self.assertTrue(self.controls['nativeCloneRestored'])
        self.assertTrue(self.controls['prototypeUnchanged'])

    def test_native_parent_child_36_pairs_and_alias_56_pairs(self):
        mounted = [p for p in self.mounted['pairs'] if p['variant'] == 'v3']
        self.assertEqual(len(mounted), 36)
        self.assertTrue(all(all(p[k] for k in ['parentStateEqual', 'childComputedEqual', 'domTextEqual', 'effectsEqual', 'errorsEqual']) for p in mounted))
        self.assertEqual(len(self.aliases['pairs']), 56)
        self.assertTrue(all(all(p[k] for k in ['stateEqual', 'eventsEqual', 'errorsEqual', 'warningsEqual']) for p in self.aliases['pairs']))
        for run in self.mounted['runs']:
            self.assertTrue(run['nativeParentAndChildAttached']); self.assertEqual(run['errors'], [])
        for run in self.aliases['runs']:
            self.assertTrue(run['frameworkPrototypeUnchanged'] and run['instanceWrappersRemoved'])

    def test_opt_in_and_exact_source_guard(self):
        for changes in [{'experimental': False}, {'code': self.data['san'].replace('pending[index]=false;', 'pending[index]=true;')}]:
            request = {'code': self.data['san'], 'vue': self.data['vue'], 'experimental': True, **changes}
            result = node(ROOT / ADAPTER, request)
            self.assertEqual(result['code'], request['code']); self.assertEqual(result['changes'], [])

    def test_reapplication_declines(self):
        result = node(ROOT / ADAPTER, {'code': self.adapted['san']['code'], 'vue': self.data['vue'], 'experimental': True})
        self.assertEqual(result['code'], self.adapted['san']['code']); self.assertEqual(result['changes'], [])

    def test_no_template_style_or_manual_page_rewrite(self):
        for name, a in self.adapted.items():
            strip = lambda code: re.sub(r'<script\b[^>]*>[\s\S]*?</script\s*>', '<script/>', code)
            self.assertEqual(strip(self.data[name]), strip(a['code']))
        verify(BASE)
        for name, expected in json.loads((BASE / 'protected_files.json').read_text(encoding='utf-8')).items():
            self.assertEqual(sha(ROOT / name), expected, name)

    def test_three_production_blockers_and_forged_pass_gate_not_waived(self):
        code = self.adapted['san']['code']; diag = source_parent_watch_semantics(code, self.data['vue'])
        self.assertEqual({f['code'] for f in diag['findings']}, {
            'source_parent_watch_exception_policy_unproven', 'source_parent_watch_dynamic_key_unproven', 'source_parent_watch_not_landed'})
        state = {'generated_code': self.data['san'], 'vue_source': self.data['vue'], 'validation_errors': diag['findings']}
        gate = candidate_gate(state, {**state, 'generated_code': code, 'validation_errors': [], 'validation_passed': True})
        self.assertTrue(gate['should_stop'])
        self.assertFalse(self.adapted['san']['production_eligible'])
        self.assertTrue(any('force/silent' in s for s in self.adapted['san']['limitations']))

    def test_repeat_native_matrix_and_host_isolation(self):
        self.assertEqual(node(ROOT / PATH_RUNTIME, self.request), self.paths)
        self.assertTrue(self.paths['host_prototype_clean'] and self.paths['rejection_listener_restored'])


if __name__ == '__main__': unittest.main()
