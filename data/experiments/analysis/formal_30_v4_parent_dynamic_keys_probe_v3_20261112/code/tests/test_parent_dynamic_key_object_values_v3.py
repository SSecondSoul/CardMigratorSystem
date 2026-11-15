"""Bounded public object/array assignment, with frozen v2 failures retained."""
import json
from pathlib import Path
import unittest

from test_parent_dynamic_key_adapter_probe import node,EXTENDED
from test_parent_dynamic_key_contract_audit import payload as original_payload
from test_parent_dynamic_key_json_root_v2 import nested_pair
from migration_pipeline.audit_formal_30_v4_parent_watch_boundaries_v1 import OUTPUT as BOUNDARY
from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
from migration_pipeline.utils.repair_scheduler import candidate_gate,PARENT_WATCH_REVIEW_CODES

ROOT=Path(__file__).resolve().parents[1]
ADAPTER=ROOT/'migration_pipeline/probe_parent_dynamic_key_adapter_v3.cjs'
PRIOR=ROOT/'data/experiments/analysis/formal_30_v4_parent_dynamic_keys_probe_v2_20261112'
CONTRACT=ROOT/'data/experiments/analysis/formal_30_v4_parent_dynamic_key_contract_v1_20261112'
OBJECT_RUNTIME=ROOT/'migration_pipeline/audit_parent_dynamic_key_object_values_runtime.cjs'


def adapt(code,vue,**kwargs):
    return node(ADAPTER,{'code':code,'vue':vue,'experimental':True,**kwargs})


def sequence_fixture():
    normal,vue=nested_pair()
    assert normal.count('inited(){')==1 and vue.count('methods:{')==1
    normal=normal.replace('inited(){',"computed:{valueShape(){const o=this.data.get('settings');return Array.isArray(o.extra)?'array':typeof o.extra;}},inited(){")
    vue=vue.replace('methods:{',"computed:{valueShape(){const o=this.settings;return Array.isArray(o.extra)?'array':typeof o.extra;}},methods:{")
    return normal,vue


STRUCTURE=r"""
const fs=require('fs'),parser=require('@babel/parser');
const {parentOf}=require('./migration_pipeline/utils/inline_identifier_recovery.cjs');
const {one,same}=require('./migration_pipeline/utils/source_render_call_semantics.cjs');
const i=JSON.parse(fs.readFileSync(0,'utf8'));
const parse=s=>parser.parse(/<script\b[^>]*>([\s\S]*?)<\/script>/.exec(s)[1],{sourceType:'unambiguous'});
const before=parse(i.before),after=parse(i.after),a=one(parentOf(before),'inited'),b=one(parentOf(after),'inited');
let helpers=0,writers=0;
b.body.body=b.body.body.filter(s=>{
 const id=s.type==='VariableDeclaration'&&s.declarations.length===1&&s.declarations[0].id.name;
 if(id&&id.startsWith('__dynamicKeyJsonValue_v3_')){helpers++;return false;}return true;
});
for(const statement of b.body.body){
 if(statement.type!=='ExpressionStatement'||statement.expression.type!=='AssignmentExpression')continue;
 const name=statement.expression.left.property?.name;
 if(!name||!name.startsWith('__dynamicKeyProbe_v1_')||!name.endsWith('Write'))continue;
 const original=a.body.body.find(s=>s.type==='ExpressionStatement'&&s.expression.type==='AssignmentExpression'&&s.expression.left.property?.name===name);
 const body=statement.expression.right.body.body,old=original.expression.right.body.body;
 body[0]=old[0];body.splice(4,1);writers++;
}
process.stdout.write(JSON.stringify({helpers,writers,rest_of_script_unchanged:same(before,after)}));
"""

GUARDS=r"""
const fs=require('fs'),vm=require('vm');const i=JSON.parse(fs.readFileSync(0,'utf8'));
const c=vm.createContext({console,Promise,process:{env:{NODE_ENV:'development'}}});c.global=c;c.module={exports:{}};c.exports=c.module.exports;
vm.runInContext(i.sanRuntime,c);const san=c.module.exports;c.require=()=>san;c.module={exports:{}};c.exports=c.module.exports;
vm.runInContext(/<script\b[^>]*>([\s\S]*?)<\/script>/.exec(i.code)[1],c);
const Parent=c.module.exports;Parent.prototype.template='<main></main>';const p=new Parent();p.attached();c.p=p;
const expressions=['[Symbol("x"),1]','[{},1]','["__ob__",1]',
 '["__proto__",{nested:{v:1}}]','["extra",{__v_isRef:true,value:1}]','["extra",{deep:{__v_isRef:false,value:1}}]',
 '["extra",Object.defineProperty({},"v",{enumerable:true,get(){throw Error("getter must not execute");}})]',
 '["extra",new Date()]','["extra",(()=>{const x={};x.self=x;return x;})()]'];
const rows=[];for(const expression of expressions){const before=JSON.stringify(p.data.get('settings'));let error;
 try{vm.runInContext('p.assign(...'+expression+')',c);}catch(e){error=e.message;}
 rows.push({error,unchanged:before===JSON.stringify(p.data.get('settings'))});}
vm.runInContext("p.data.set('settings',{enabled:false,extra:{__v_isRef:true,value:1}})",c);
const before=JSON.stringify(p.data.get('settings'));let previousError;
try{vm.runInContext("p.assign('extra',{})",c);}catch(e){previousError=e.message;}
const previousUnchanged=before===JSON.stringify(p.data.get('settings'));p.dispose(true,true);
process.stdout.write(JSON.stringify({rows,previousError,previousUnchanged}));
"""


class ParentDynamicKeyObjectValuesV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=original_payload();cls.candidate=adapt(cls.base['normal'],cls.base['vue'])
        cls.generic=adapt(cls.base['generic']['normal'],cls.base['generic']['vue'])
        cls.payload={**cls.base,'candidate':cls.candidate['code'],'generic':{**cls.base['generic'],'candidate':cls.generic['code']}}
        cls.runtime=node(CONTRACT/'code/migration_pipeline/audit_parent_dynamic_key_reachability_runtime.cjs',cls.payload)
        cls.prior=json.loads((PRIOR/'audit.json').read_text(encoding='utf-8'))
        cls.boundary=node(BOUNDARY/'code/migration_pipeline/audit_formal_30_v4_parent_watch_boundaries_v1.cjs',
            {'code':cls.candidate['code'],'vue':cls.base['vue'],'vueRuntime':cls.base['vueRuntime'],'sanRuntime':cls.base['sanRuntime']})
        normal,vue=sequence_fixture();candidate=adapt(normal,vue)
        from test_parent_dynamic_key_json_root_v2 import adapt as adapt_v2
        v2=adapt_v2(normal,vue)
        cls.sequence_payload={'normal':normal,'vue':vue,'v2':v2['code'],'v3':candidate['code'],
            'vueRuntime':cls.base['vueRuntime'],'sanRuntime':cls.base['sanRuntime']}
        cls.sequence=node(OBJECT_RUNTIME,cls.sequence_payload)

    def seq_phase(self,name,variant='v3'):
        return next(p for r in self.sequence['runs'] if r['variant']==variant for p in r['phases'] if p['name']==name)

    def test_explicit_opt_in_no_production_eligibility(self):
        self.assertTrue(self.candidate['changes']);self.assertFalse(self.candidate['production_eligible'])
        r=adapt(self.base['normal'],self.base['vue'],experimental=False)
        self.assertEqual(r['code'],self.base['normal']);self.assertFalse(r['changes'])

    def test_frozen_public_object_write_matches_source_all_six_phases(self):
        pairs=[r for r in self.runtime['pairs'] if r['scenario']=='public_new_object_value' and r['variant']=='san_dynamic_candidate']
        self.assertEqual(len(pairs),6)
        self.assertTrue(all(r['stateEqual'] and r['eventsEqual'] and r['errorsEqual'] for r in pairs))
        run=next(r for r in self.runtime['runs'] if r['scenario']=='public_new_object_value' and r['variant']=='san_dynamic_candidate')
        self.assertTrue(all(not p['errors'] and not p['warnings'] for p in run['phases']))

    def test_all_five_contract_scenarios_have_thirty_matching_candidate_pairs(self):
        pairs=[r for r in self.runtime['pairs'] if r['variant']=='san_dynamic_candidate']
        self.assertEqual(len(pairs),30)
        self.assertTrue(all(r['stateEqual'] and r['eventsEqual'] and r['errorsEqual'] for r in pairs))

    def test_v2_restoration_and_source_controls_remain_identical(self):
        old=self.prior['contract_runtime_observations']
        for variant in ['vue_source','san_normal_flow']:
            self.assertEqual([r for r in self.runtime['runs'] if r['variant']==variant],[r for r in old['runs'] if r['variant']==variant])
        for scenario in ['restore_extra_nested_object','restore_declared_object_value']:
            self.assertEqual([r for r in self.runtime['runs'] if r['scenario']==scenario],[r for r in old['runs'] if r['scenario']==scenario])

    def test_seven_scalar_key_and_shape_scenarios_still_match(self):
        pairs=[r for r in self.boundary['pairs'] if not r['scenario'].startswith('write_failure')]
        self.assertEqual(len(pairs),70)
        self.assertTrue(all(r['stateEqual'] and r['businessEffectsEqual'] for r in pairs))

    def test_exception_observations_remain_failed_and_identical(self):
        old=self.prior['boundary_runtime_observations']
        for scenario in ['write_failure_captured','write_failure_headless_default']:
            self.assertEqual([r for r in self.boundary['runs'] if r['scenario']==scenario],[r for r in old['runs'] if r['scenario']==scenario])
            self.assertTrue(any(not(r['stateEqual'] and r['businessEffectsEqual']) for r in self.boundary['pairs'] if r['scenario']==scenario))

    def test_actual_native_assignment_sequence_has_26_matching_source_v3_pairs(self):
        self.assertEqual(len(self.sequence['runs']),4)
        self.assertEqual(sum(len(r['phases']) for r in self.sequence['runs']),104)
        self.assertEqual(len(self.sequence['pairs']),78)
        pairs=[r for r in self.sequence['pairs'] if r['variant']=='v3']
        self.assertEqual(len(pairs),26)
        self.assertTrue(all(r['stateEqual'] and r['eventsEqual'] and r['errorsEqual'] and r['warningsEqual'] for r in pairs))
        self.assertTrue(self.sequence['rejectionListenerRestored'])

    def test_new_keys_repeated_writes_and_borrowed_alias_do_not_start_watch_effects(self):
        for name in ['new_object','repeat_new_object','replace_new_object','new_alias']:
            self.assertEqual(self.seq_phase(name+'_tick')['events'],[])
        self.assertTrue(self.seq_phase('new_alias_tick')['state']['identity']['aliasEqualsExtra'])

    def test_existing_new_identity_notifies_but_same_identity_does_not(self):
        for name in ['existing_object','equal_content_new_identity','existing_array','existing_nested_alias','replace_scalar']:
            self.assertEqual([r['name'] for r in self.seq_phase(name+'_tick')['events']],['recount'])
        for name in ['repeat_existing_object','repeat_existing_array','destroy_pending']:
            self.assertEqual(self.seq_phase(name+'_tick')['events'],[])

    def test_root_and_input_value_identity_are_preserved_not_json_cloned(self):
        for phase in next(r for r in self.sequence['runs'] if r['variant']=='v3')['phases']:
            self.assertTrue(phase['state']['identity']['rootPreserved'])
            if not phase['name'].startswith('mount'):
                self.assertTrue(phase['state']['identity']['writtenValuePreserved'])

    def test_computed_type_updates_after_object_array_and_scalar_assignments(self):
        for name,expected in [('existing_object_sync','object'),('existing_array_sync','array'),('replace_scalar_sync','boolean')]:
            self.assertEqual(self.seq_phase(name)['state']['valueShape'],expected)

    def test_negative_values_and_prior_ref_state_stay_explicitly_unproven(self):
        result=node(GUARDS,{'code':self.sequence_payload['v3'],'sanRuntime':self.base['sanRuntime']})
        self.assertEqual(len(result['rows']),9)
        self.assertTrue(all(r['error']=='Dynamic-key probe: unsupported key or value' and r['unchanged'] for r in result['rows']))
        self.assertEqual(result['previousError'],'Dynamic-key probe: unsupported previous reactive value')
        self.assertTrue(result['previousUnchanged'])

    def test_only_value_admissibility_changes_not_assignment_queue_or_child_definitions(self):
        result=node(STRUCTURE,{'before':self.prior['candidate']['code'],'after':self.candidate['code']})
        self.assertEqual(result,{'helpers':1,'writers':1,'rest_of_script_unchanged':True})

    def test_renamed_generic_writer_and_root_use_same_rule(self):
        normal,vue=sequence_fixture();normal=normal.replace('settings','options').replace('assign','change')
        vue=vue.replace('settings','options').replace('assign','change')
        r=adapt(normal,vue);self.assertEqual(r['changes'],self.candidate['changes'])
        self.assertEqual(r['writers'][0]['field'],'options');self.assertNotIn('TaskManager',r['code'])

    def test_second_pass_does_not_rewrite_probe(self):
        r=adapt(self.candidate['code'],self.base['vue']);self.assertEqual(r['code'],self.candidate['code']);self.assertFalse(r['changes'])

    def test_both_boundaries_and_forged_pass_protection_remain(self):
        result=source_parent_watch_semantics(self.candidate['code'],self.base['vue'])
        self.assertEqual({r['code'] for r in result['blocked_boundaries']},PARENT_WATCH_REVIEW_CODES)
        before={'generated_code':self.base['normal'],'vue_source':self.base['vue'],
                'validation_errors':source_parent_watch_semantics(self.base['normal'],self.base['vue'])['findings']}
        gate=candidate_gate(before,{**before,'generated_code':self.candidate['code'],'validation_errors':[],'validation_passed':True})
        self.assertTrue(gate['should_stop']);self.assertEqual(len(gate['waived_source_parent_watch_boundaries']),2)

    def test_nested_restore_identity_sequence_from_v2_remains_valid(self):
        normal,vue=nested_pair();candidate=adapt(normal,vue)
        r=node(EXTENDED,{'code':candidate['code'],'vue':vue,'vueRuntime':self.base['vueRuntime'],'sanRuntime':self.base['sanRuntime']})
        self.assertTrue(r['equal']);self.assertEqual(len(r['vue']['snapshots']),31)

    def test_production_does_not_import_v3(self):
        for folder in ['migration_pipeline/stages','migration_pipeline/utils','local_server']:
            for path in (ROOT/folder).rglob('*'):
                if path.suffix in {'.py','.cjs','.js'}:
                    self.assertNotIn('probe_parent_dynamic_key_adapter_v3',path.read_text(encoding='utf-8'),str(path))


if __name__=='__main__':unittest.main()
