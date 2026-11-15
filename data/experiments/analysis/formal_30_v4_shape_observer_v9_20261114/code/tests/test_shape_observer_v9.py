"""Native frozen counterexamples, alias/child regression and fail-closed controls."""
import json
import unittest

from migration_pipeline.audit_shape_observer_v9 import candidates, BASE, PROTECTED, ADAPTER
from migration_pipeline.audit_v7_dynamic_shape import payload, node, ROOT, RUNTIME
from migration_pipeline.audit_v7_source_queue_contract import sha, verify
from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
from migration_pipeline.utils.repair_scheduler import candidate_gate
from test_parent_dynamic_key_adapter_probe import node as eval_node

PRIOR = ROOT / 'data/experiments/analysis/formal_30_v4_parent_alias_child_audit_v1_20261112'


class ShapeObserverV9Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = payload(); cls.adapted = candidates(cls.data)
        cls.observed = node(ROOT / RUNTIME, {**cls.data, **{n: a['code'] for n, a in cls.adapted.items()}})
        old = json.loads((PRIOR / 'audit.json').read_text(encoding='utf-8'))
        cls.fixture = old['fixture']
        cls.candidate = node(ROOT / ADAPTER, {'code': cls.fixture['normal'], 'vue': cls.fixture['vue'],
                                             'experimental': True})
        common = {name: (ROOT / next(p for p in old['source_inputs'] if p.endswith(end))).read_text(encoding='utf-8')
                  for name, end in [('vueRuntime', 'vue.runtime.common.dev.js'), ('sanRuntime', 'san.dev.js')]}
        cls.common = common
        cls.mounted = node(PRIOR / 'code/migration_pipeline/audit_parent_alias_child_runtime.cjs',
                           {**cls.fixture, **common, 'v3': cls.candidate['code']})
        cls.extended = node(ROOT / 'migration_pipeline/audit_parent_alias_observer_v4_runtime.cjs',
                            {'vue': cls.fixture['vue'], 'v4': cls.candidate['code'], **common})

    def scenario(self, name):
        rows = [p for p in self.observed['pairs'] if p['scenario'] == name]
        self.assertTrue(rows); self.assertTrue(all(p['equal'] for p in rows), rows)

    def test_all_116_frozen_dynamic_shape_pairs_match(self):
        self.assertEqual(len(self.observed['pairs']), 116)
        self.assertTrue(all(p['equal'] for p in self.observed['pairs']))
        self.assertFalse(self.observed['production_eligible'])

    def test_date_value_retained(self): self.scenario('date_value')
    def test_frozen_value_retained(self): self.scenario('frozen_value')
    def test_sparse_array_holes_retained(self): self.scenario('sparse_array_value')
    def test_deleted_property_first_notification_and_later_cleanup(self): self.scenario('delete_then_mutate_detached_alias')
    def test_redefined_property_subscription_cleanup(self): self.scenario('redefine_then_mutate_detached_alias')
    def test_nonenumerable_property_subscription_cleanup(self): self.scenario('nonenumerable_then_mutate_alias')
    def test_source_native_dynamic_key_controls_retained(self):
        for name in ['numeric_key', 'symbol_key', 'coerced_existing_key', 'coerced_new_key', 'throwing_key_coercion', 'new_symbol_value']:
            self.scenario(name)

    def test_new_keys_not_force_observed(self): self.scenario('new_scalar_repeat')
    def test_inherited_setter_and_prototype_controls(self):
        for name in ['inherited_setter', 'prototype_plain', 'prototype_null']: self.scenario(name)

    def test_native_mounted_parent_child_computed_and_text_regression_36_pairs(self):
        rows = [p for p in self.mounted['pairs'] if p['variant'] == 'v3']
        self.assertEqual(len(rows), 36)
        self.assertTrue(all(all(p[k] for k in ['parentStateEqual', 'childComputedEqual', 'domTextEqual', 'effectsEqual', 'errorsEqual']) for p in rows), rows)

    def test_native_alias_identity_shared_instance_and_mutator_regression_56_pairs(self):
        self.assertEqual(len(self.extended['pairs']), 56)
        self.assertTrue(all(all(p[k] for k in ['stateEqual', 'eventsEqual', 'errorsEqual', 'warningsEqual']) for p in self.extended['pairs']), self.extended['pairs'])

    def test_receiver_cleanup_and_framework_prototypes_untouched(self):
        self.assertTrue(self.extended['rejectionListenerRestored'])
        for run in self.extended['runs']:
            self.assertTrue(run['frameworkPrototypeUnchanged'] and run['instanceWrappersRemoved'])

    def test_normal_native_child_mount_remains_error_free(self):
        for run in self.mounted['runs']:
            self.assertTrue(run['nativeParentAndChildAttached']); self.assertEqual(run['errors'], [])

    def test_removing_dispatch_refresh_reproduces_frozen_subscription_counterexamples(self):
        altered = {name: a['code'].replace('this.__aliasBridge_v4Parent.refresh(index);', '') for name, a in self.adapted.items()}
        for name in altered: self.assertNotEqual(altered[name], self.adapted[name]['code'])
        observed = node(ROOT / RUNTIME, {**self.data, **altered})
        self.assertTrue(any(not p['equal'] for p in observed['pairs']))

    def test_eager_current_shape_cleanup_loses_first_legitimate_notification(self):
        old = 'const affected=new Set([node]),targets=[],bound=[];'
        new = 'for(const owner of owners)for(const row of owner.rows)refresh(owner,row);' + old
        altered = {name: a['code'].replace(old, new) for name, a in self.adapted.items()}
        for name in altered: self.assertNotEqual(altered[name], self.adapted[name]['code'])
        observed = node(ROOT / RUNTIME, {**self.data, **altered})
        rows = [p for p in observed['pairs'] if p['scenario'] == 'delete_then_mutate_detached_alias' and p['phase'] == 'action_0_tick']
        self.assertTrue(rows); self.assertTrue(all(not p['eventsEqual'] for p in rows))

    def test_object_identity_and_sparse_shape_use_real_san_data(self):
        script = r'''
const fs=require('fs'),vm=require('vm'),i=JSON.parse(fs.readFileSync(0,'utf8'));
const c=vm.createContext({Promise,console,process:{env:{NODE_ENV:'development'}}});c.global=c;c.module={exports:{}};c.exports=c.module.exports;
vm.runInContext(i.runtime,c);const san=c.module.exports;c.module={exports:{}};c.exports=c.module.exports;c.require=name=>{if(name!=='san')throw Error(name);return san;};
vm.runInContext(/<script\b[^>]*>([\s\S]*?)<\/script>/.exec(i.code)[1],c);c.Parent=c.module.exports;
const observed=vm.runInContext(`(()=>{const p=new Parent();p.attached();const rows=[];
 for(const value of [new Date(0),Object.freeze({name:'frozen'}),[,1]]){
  p.assign('extra',value);rows.push({identity:p.data.get('settings').extra===value,
   sparse:Array.isArray(value)?!Object.prototype.hasOwnProperty.call(value,'0')&&value.length===2:null});
 }p.dispose(true,true);return rows;})()`,c);
process.stdout.write(JSON.stringify(observed));
'''
        rows = eval_node(script, {'runtime': self.common['sanRuntime'], 'code': self.candidate['code']})
        self.assertTrue(all(r['identity'] for r in rows)); self.assertTrue(rows[-1]['sparse'])

    def test_explicit_opt_in_and_source_mismatch_decline(self):
        for changes in [{'experimental': False}, {'code': self.data['san'].replace('pending[index]=false;', 'pending[index]=true;')}]:
            request = {'code': self.data['san'], 'vue': self.data['vue'], 'experimental': True, **changes}
            result = node(ROOT / ADAPTER, request)
            self.assertEqual(result['code'], request['code']); self.assertEqual(result['changes'], [])

    def test_reapplication_declines_without_changing_frozen_candidate(self):
        result = node(ROOT / ADAPTER, {'code': self.adapted['san']['code'], 'vue': self.data['vue'], 'experimental': True})
        self.assertEqual(result['code'], self.adapted['san']['code']); self.assertEqual(result['changes'], [])

    def test_broad_unproved_input_and_error_boundaries_are_not_claimed(self):
        result = self.adapted['san']
        self.assertFalse(result['production_eligible'])
        self.assertTrue(any('Ref' in text and 'Proxy' in text for text in result['limitations']))
        self.assertTrue(any('not a production bridge' in text for text in result['limitations']))

    def test_original_v7_v8_observer_and_production_acceptance_files_unchanged(self):
        verify(BASE)
        protected = json.loads((BASE / 'protected_files.json').read_text(encoding='utf-8'))
        self.assertEqual(set(protected), set(PROTECTED))
        for name, expected in protected.items(): self.assertEqual(sha(ROOT / name), expected, name)

    def test_production_blockers_and_independent_candidate_gate_are_not_waived(self):
        diagnostic = source_parent_watch_semantics(self.adapted['san']['code'], self.data['vue'])
        self.assertEqual(len(diagnostic['findings']), 3)
        state = {'generated_code': self.data['san'], 'vue_source': self.data['vue'],
                 'validation_errors': source_parent_watch_semantics(self.data['san'], self.data['vue'])['findings']}
        forged = candidate_gate(state, {**state, 'generated_code': self.adapted['san']['code'], 'validation_errors': [], 'validation_passed': True})
        self.assertTrue(forged['should_stop']); self.assertEqual(len(forged['waived_source_parent_watch_boundaries']), 2)

    def test_repeat_native_matrix_is_deterministic_and_host_clean(self):
        repeat = node(ROOT / RUNTIME, {**self.data, **{n: a['code'] for n, a in self.adapted.items()}})
        self.assertEqual(repeat, self.observed)
        self.assertTrue(repeat['host_prototype_clean'] and repeat['rejection_listener_restored'])


if __name__ == '__main__': unittest.main()
