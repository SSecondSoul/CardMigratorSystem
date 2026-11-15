"""Isolated observer candidate: native frozen negative replay plus identity/queue controls."""
import json
from pathlib import Path
import unittest

from test_parent_dynamic_key_adapter_probe import node,EXTENDED
from test_parent_dynamic_key_object_values_v3 import original_payload,sequence_fixture,BOUNDARY
from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
from migration_pipeline.utils.repair_scheduler import PARENT_WATCH_REVIEW_CODES,candidate_gate

ROOT=Path(__file__).resolve().parents[1]
PRIOR=ROOT/'data/experiments/analysis/formal_30_v4_parent_alias_child_audit_v1_20261112'
V3=ROOT/'data/experiments/analysis/formal_30_v4_parent_dynamic_keys_probe_v3_20261112'
ADAPTER=ROOT/'migration_pipeline/probe_parent_dynamic_key_adapter_v4.cjs'
RUNTIME=ROOT/'migration_pipeline/audit_parent_alias_observer_v4_runtime.cjs'


def adapt(code,vue,**kw):return node(ADAPTER,{'code':code,'vue':vue,'experimental':True,**kw})


def payloads():
    old=json.loads((PRIOR/'audit.json').read_text(encoding='utf-8'))
    common={k:(ROOT/next(n for n in old['source_inputs'] if n.endswith(end))).read_bytes().decode('utf-8')
            for k,end in [('vueRuntime','vue.runtime.common.dev.js'),('sanRuntime','san.dev.js')]}
    f=old['fixture'];candidate=adapt(f['normal'],f['vue'])
    return old,common,candidate


GUARDS=r"""
const fs=require('fs'),vm=require('vm'),i=JSON.parse(fs.readFileSync(0,'utf8'));
const c=vm.createContext({console,Promise,process:{env:{NODE_ENV:'development'}}});c.global=c;
c.module={exports:{}};c.exports=c.module.exports;vm.runInContext(i.sanRuntime,c);const san=c.module.exports;
c.module={exports:{}};c.exports=c.module.exports;c.require=()=>san;
vm.runInContext(/<script\b[^>]*>([\s\S]*?)<\/script>/.exec(i.code)[1],c);
const Parent=c.module.exports;Parent.prototype.template='<main></main>';c.p=new Parent();c.p.attached();
const rows=[];for(const expression of ['[Symbol("x"),1]','["__ob__",1]',
 '["extra",{__v_isRef:true,value:1}]','["extra",new Date()]','["extra",Object.freeze({v:1})]',
 '["extra",Object.defineProperty({},"v",{enumerable:true,get(){throw Error("getter must not execute");}})]',
 '["extra",(()=>{const v={};v.self=v;return v;})()]','["extra",[,1]]',
 '["__proto__",{nested:{v:1}}]']){
 const before=JSON.stringify(c.p.data.get('settings')),proto=Object.getPrototypeOf(c.p.data.get('settings'));let error;
 try{vm.runInContext('p.assign(...'+expression+')',c);}catch(e){error=e.message;}
 rows.push({error,unchanged:before===JSON.stringify(c.p.data.get('settings'))&&proto===Object.getPrototypeOf(c.p.data.get('settings'))});
}
let cycleError;const before=JSON.stringify(c.p.data.get('settings'));
try{vm.runInContext("const a=p.data.get('settings').extra.items;a.push(a)",c);}catch(e){cycleError=e.message;}
const cycleUnchanged=before===JSON.stringify(c.p.data.get('settings'));c.p.dispose(true,true);
process.stdout.write(JSON.stringify({rows,cycleError,cycleUnchanged}));
"""


class ParentAliasObserverV4Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old,cls.common,cls.candidate=payloads();f=cls.old['fixture']
        cls.mounted=node(PRIOR/'code/migration_pipeline/audit_parent_alias_child_runtime.cjs',
                         {**f,'v3':cls.candidate['code'],**cls.common})
        cls.extended=node(RUNTIME,{'vue':f['vue'],'v4':cls.candidate['code'],**cls.common})

    def frame(self,phase,variant='v4'):
        return next(f for r in self.extended['runs'] if r['variant']==variant for f in r['snapshots'] if f['name']==phase)

    def test_opt_in_and_no_production_eligibility(self):
        f=self.old['fixture'];r=adapt(f['normal'],f['vue'],experimental=False)
        self.assertFalse(r['changes']);self.assertEqual(r['code'],f['normal'])
        self.assertTrue(self.candidate['changes']);self.assertFalse(self.candidate['production_eligible'])

    def test_repeated_adapter_application_refuses_without_changes(self):
        r=adapt(self.candidate['code'],self.old['fixture']['vue'])
        self.assertEqual(r['code'],self.candidate['code']);self.assertFalse(r['changes'])

    def test_frozen_child_audit_dimensions_and_all_36_source_candidate_pairs_match(self):
        pairs=[p for p in self.mounted['pairs'] if p['variant']=='v3']
        self.assertEqual(len(pairs),36)
        self.assertTrue(all(all(p[k] for k in ['parentStateEqual','childComputedEqual','domTextEqual','effectsEqual','errorsEqual']) for p in pairs))

    def test_source_and_normal_control_observations_are_byte_equivalent_to_negative_evidence(self):
        for variant in ['vue_source','normal']:
            self.assertEqual([r for r in self.mounted['runs'] if r['variant']==variant],
                             [r for r in self.old['runtime_observations']['runs'] if r['variant']==variant])

    def test_original_negative_evidence_still_contains_eight_action_tick_counterexamples(self):
        self.assertEqual(len([r for r in self.old['action_tick_comparisons'] if not r['dom_text_equal']]),8)

    def test_native_mount_and_no_runtime_errors_or_warnings(self):
        for r in self.mounted['runs']:
            self.assertTrue(r['nativeParentAndChildAttached']);self.assertFalse(r['errors'])
            self.assertTrue(all(not f['errors'] and not f['warnings'] for f in r['frames']))

    def test_synchronous_child_computed_not_only_eventual_text_is_fixed(self):
        for scenario in ['writer_scalar','writer_object','borrowed_existing_property','borrowed_array_push','borrowed_nested_item']:
            p=next(p for p in self.mounted['pairs'] if p['variant']=='v3' and p['scenario']==scenario and p['phase']=='action_sync')
            self.assertTrue(p['childComputedEqual'] and p['domTextEqual'])

    def test_extended_native_identity_queue_observations_all_56_pairs_match(self):
        self.assertEqual(len(self.extended['pairs']),56)
        self.assertTrue(all(all(p[k] for k in ['stateEqual','eventsEqual','errorsEqual','warningsEqual']) for p in self.extended['pairs']))
        self.assertTrue(self.extended['rejectionListenerRestored'])

    def test_no_framework_prototype_patch_and_wrappers_removed_on_disposal(self):
        for r in self.extended['runs']:
            self.assertTrue(r['frameworkPrototypeUnchanged'] and r['instanceWrappersRemoved'])

    def test_external_root_child_and_array_references_preserved_before_replacement(self):
        for phase in ['borrow_name_tick','push_tick','inserted_alias_tick','splice_tick','sort_tick','reverse_tick']:
            identity=self.frame(phase)['state']['identity']
            self.assertTrue(identity['rootPreserved'] and identity['extraPreserved'] and identity['itemsPreserved'])

    def test_inserted_object_is_observed_without_replacing_its_reference(self):
        self.assertEqual(self.frame('inserted_alias_tick')['state']['a']['extra']['items'][-1]['value'],9)
        self.assertEqual([e['name'] for e in self.frame('inserted_alias_tick')['events']],['recount'])
        self.assertTrue(self.frame('replace_extra_tick')['state']['identity']['incomingIsExtra'])

    def test_all_seven_array_mutators_and_no_argument_push_follow_source_notification(self):
        for phase in ['push_tick','unshift_tick','shift_tick','splice_tick','sort_tick','reverse_tick','pop_tick','empty_push_not_silent_tick']:
            self.assertEqual([e['instance'] for e in self.frame(phase)['events']],['a'])

    def test_same_scalar_and_object_and_raw_new_key_values_do_not_overnotify(self):
        for phase in ['same_scalar_tick','same_name_tick','same_extra_tick','new_key_object_tick','unobserved_new_value_alias_tick','still_unobserved_new_key_tick']:
            self.assertEqual(self.frame(phase)['events'],[])

    def test_detached_alias_does_not_notify_current_root_and_old_identity_can_be_restored(self):
        self.assertEqual(self.frame('detached_alias_tick')['events'],[])
        self.assertTrue(self.frame('restore_original_root_tick')['state']['identity']['rootPreserved'])

    def test_two_instances_stay_independent_until_explicit_sharing(self):
        self.assertTrue(self.frame('push_tick')['state']['identity']['secondIndependent'])
        self.assertTrue(self.frame('share_between_instances_tick')['state']['identity']['shared'])
        self.assertEqual([e['instance'] for e in self.frame('shared_alias_tick')['events']],['a','b'])

    def test_disposal_cancels_only_own_pending_callback_then_all_subscriptions(self):
        self.assertEqual([e['instance'] for e in self.frame('dispose_pending_first_instance_tick')['events']],['b'])
        self.assertEqual(self.frame('dispose_both_then_mutate_tick')['events'],[])

    def test_static_existing_deep_data_api_control_matches_without_claiming_arbitrary_data_api(self):
        self.assertTrue(all(p['childComputedEqual'] and p['domTextEqual'] for p in self.mounted['pairs']
                            if p['variant']=='v3' and p['scenario']=='control_data_api_nested'))

    def test_frozen_object_assignment_identity_sequence_is_not_regressed(self):
        normal,vue=sequence_fixture();v4=adapt(normal,vue)
        old=json.loads((V3/'audit.json').read_text(encoding='utf-8'))
        f=old['object_sequence_fixture']
        r=node(ROOT/'migration_pipeline/audit_parent_dynamic_key_object_values_runtime.cjs',
               {**f,'v3':v4['code'],**self.common})
        self.assertTrue(all(p['stateEqual'] and p['eventsEqual'] and p['errorsEqual'] and p['warningsEqual'] for p in r['pairs'] if p['variant']=='v3'))

    def test_old_root_and_instance_and_numeric_controls_from_existing_probe(self):
        base=original_payload();v4=adapt(base['generic']['normal'],base['generic']['vue'])
        result=node(EXTENDED,{'code':v4['code'],'vue':base['generic']['vue'],**self.common})
        self.assertTrue(result['equal'])

    def test_real_task_manager_boundaries_and_forged_pass_refusal_remain(self):
        base=original_payload();v4=adapt(base['normal'],base['vue'])
        self.assertTrue(v4['changes']);self.assertFalse(v4['production_eligible'])
        diag=source_parent_watch_semantics(v4['code'],base['vue'])
        self.assertEqual({r['code'] for r in diag['blocked_boundaries']},PARENT_WATCH_REVIEW_CODES)
        before={'generated_code':base['normal'],'vue_source':base['vue'],
                'validation_errors':source_parent_watch_semantics(base['normal'],base['vue'])['findings']}
        gate=candidate_gate(before,{**before,'generated_code':v4['code'],'validation_errors':[],'validation_passed':True})
        self.assertTrue(gate['should_stop']);self.assertEqual(len(gate['waived_source_parent_watch_boundaries']),2)

    def test_actual_normal_boundary_all_70_phases_including_source_rhs_number_conversion(self):
        base=original_payload();v4=adapt(base['normal'],base['vue'])
        result=node(BOUNDARY/'code/migration_pipeline/audit_formal_30_v4_parent_watch_boundaries_v1.cjs',
                    {'code':v4['code'],'vue':base['vue'],**self.common})
        rows=[r for r in result['pairs'] if not r['scenario'].startswith('write_failure')]
        self.assertEqual(len(rows),70)
        self.assertTrue(all(r['stateEqual'] and r['businessEffectsEqual'] for r in rows))
        old=json.loads((V3/'audit.json').read_text(encoding='utf-8'))
        for scenario in result['scenarios']:
            if scenario.startswith('write_failure'):
                self.assertEqual([r for r in result['runs'] if r['scenario']==scenario],
                                 [r for r in old['boundary_runtime_observations']['runs'] if r['scenario']==scenario])

    def test_unsupported_inputs_and_array_cycle_refused_before_observed_mutation(self):
        r=node(GUARDS,{'code':self.candidate['code'],**self.common})
        self.assertEqual(len(r['rows']),9)
        self.assertTrue(all(row['unchanged'] and row['error'].startswith('Alias v4 probe: unsupported') for row in r['rows']))
        self.assertEqual(r['cycleError'],'Alias v4 probe: unsupported observed value');self.assertTrue(r['cycleUnchanged'])

    def test_frozen_writer_rhs_failure_remains_preserved(self):
        folder=ROOT/'data/experiments/analysis/formal_30_v4_parent_alias_observer_v4_writer_rhs_failed_20261112'
        data=json.loads((folder/'audit.json').read_text(encoding='utf-8'))
        self.assertTrue(data['failed_preflight']);self.assertEqual(len(data['normal_boundary_mismatches']),6)


if __name__=='__main__':unittest.main()
