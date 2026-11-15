"""Fix the frozen nested-restore regression without promoting the candidate."""
import json
from pathlib import Path
import unittest

from test_parent_dynamic_key_adapter_probe import node,generic_pair,EXTENDED,UNSUPPORTED
from test_parent_dynamic_key_contract_audit import payload as v1_payload,PRIOR
from migration_pipeline.audit_formal_30_v4_parent_watch_boundaries_v1 import OUTPUT as BOUNDARY
from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
from migration_pipeline.utils.repair_scheduler import candidate_gate,PARENT_WATCH_REVIEW_CODES

ROOT=Path(__file__).resolve().parents[1]
ADAPTER=ROOT/'migration_pipeline/probe_parent_dynamic_key_adapter_v2.cjs'
CONTRACT=ROOT/'data/experiments/analysis/formal_30_v4_parent_dynamic_key_contract_v1_20261112'


def adapt(code,vue,**kwargs):
    return node(ADAPTER,{'code':code,'vue':vue,'experimental':True,**kwargs})


def nested_pair():
    normal,vue=generic_pair()
    nested="{enabled:false,extra:{groups:[{values:[null,{},[],true,3,'nested']}]}}"
    assert vue.count('this.settings={enabled:false};')==1
    assert normal.count("this.data.set('settings',{enabled:false});")==1
    return (normal.replace("this.data.set('settings',{enabled:false});","this.data.set('settings',"+nested+");"),
            vue.replace('this.settings={enabled:false};','this.settings='+nested+';'))


# Test the pure descriptor validator separately; does NOT simulate framework Data.
DESCRIPTORS=r"""
const fs=require('fs'),parser=require('@babel/parser'),generate=require('@babel/generator').default;
const vm=require('vm'),input=JSON.parse(fs.readFileSync(0,'utf8'));
const ast=parser.parse(/<script\b[^>]*>([\s\S]*?)<\/script>/.exec(input.code)[1]);
const wanted=[];const walk=n=>{if(!n||typeof n!=='object')return;
 if(n.type==='VariableDeclarator'&&['__dynamicKeyProbe_v1_0Scalar','__dynamicKeyJsonRoot_v2_0'].includes(n.id.name))wanted.push(n);
 for(const [k,v] of Object.entries(n))if(!['loc','extra'].includes(k))Array.isArray(v)?v.forEach(walk):walk(v);};walk(ast);
const c=vm.createContext({});vm.runInContext(wanted.map(n=>'const '+generate(n).code+';').join('\n')+`
let getterCalls=0;
const shared={value:1},sparse=[,1];sparse.extra=2;
const badAccessor=Object.defineProperty({},'value',{enumerable:true,get(){getterCalls++;throw Error('must not execute');}});
const cycle={};cycle.self=cycle;
const symbols={};symbols[Symbol('x')]=1;
const cases=[
 ['nested_json',{a:{groups:[{values:[null,{},[],true,3,'x']}]},empty:{}},true],
 ['shared_dag',{a:shared,b:shared},true],['undefined_leaf',{a:{v:undefined}},true],
 ['getter',{a:badAccessor},false],['date',{a:new Date()},false],['cycle',cycle,false],
 ['symbol',symbols,false],['root_array',[],false],['sparse_array',{a:[,1]},false],
 ['sparse_plus_extra',{a:sparse},false],['metadata',{a:{__ob__:1}},false],
 ['custom_prototype',{a:Object.create({inherited:1})},false],
 ['readonly',{a:Object.defineProperty({},'v',{value:1,enumerable:true})},false]
];
globalThis.result={rows:cases.map(([name,value,expected])=>({name,expected,actual:__dynamicKeyJsonRoot_v2_0(value)})),getterCalls};
`,c);process.stdout.write(JSON.stringify(c.result));
"""

STRUCTURE=r"""
const fs=require('fs'),parser=require('@babel/parser');
const {parentOf}=require('./migration_pipeline/utils/inline_identifier_recovery.cjs');
const {one,walk,same}=require('./migration_pipeline/utils/source_render_call_semantics.cjs');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const parse=s=>parser.parse(/<script\b[^>]*>([\s\S]*?)<\/script>/.exec(s)[1],{sourceType:'unambiguous'});
const before=parse(input.before),after=parse(input.after),init=one(parentOf(after),'inited');
let added=0,replaced=0;
init.body.body=init.body.body.filter(statement=>{
 const id=statement.type==='VariableDeclaration'&&statement.declarations.length===1&&statement.declarations[0].id.name;
 if(id&&id.startsWith('__dynamicKeyJsonRoot_v2_')){added++;return false;}return true;
});
walk(init,n=>{if(n.type==='CallExpression'&&n.callee.type==='Identifier'&&n.callee.name.startsWith('__dynamicKeyJsonRoot_v2_')){
 const slot=n.callee.name.slice('__dynamicKeyJsonRoot_v2_'.length);
 n.callee.name='__dynamicKeyProbe_v1_'+slot+'Plain';replaced++;
}});
process.stdout.write(JSON.stringify({added,replaced,rest_of_script_unchanged:same(before,after)}));
"""


class ParentDynamicKeyJsonRootV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old=v1_payload();cls.candidate=adapt(cls.old['normal'],cls.old['vue'])
        cls.generic=adapt(cls.old['generic']['normal'],cls.old['generic']['vue'])
        cls.payload={**cls.old,'candidate':cls.candidate['code'],
            'generic':{**cls.old['generic'],'candidate':cls.generic['code']}}
        cls.oracle=CONTRACT/'code/migration_pipeline/audit_parent_dynamic_key_reachability_runtime.cjs'
        cls.runtime=node(cls.oracle,cls.payload)
        cls.prior=json.loads((CONTRACT/'audit.json').read_text(encoding='utf-8'))['runtime_observations']
        cls.boundary_payload={'code':cls.candidate['code'],'vue':cls.old['vue'],
            'vueRuntime':cls.old['vueRuntime'],'sanRuntime':cls.old['sanRuntime']}
        cls.boundary=node(BOUNDARY/'code/migration_pipeline/audit_formal_30_v4_parent_watch_boundaries_v1.cjs',cls.boundary_payload)

    def test_explicit_opt_in_and_candidate_only(self):
        self.assertEqual(self.candidate['changes'],['experimental_nested_json_root_observation_compatibility'])
        self.assertFalse(self.candidate['production_eligible'])
        r=adapt(self.old['normal'],self.old['vue'],experimental=False)
        self.assertEqual(r['code'],self.old['normal']);self.assertFalse(r['changes'])

    def test_only_root_observation_guard_changes_not_writer_queue_or_children(self):
        result=node(STRUCTURE,{'before':self.old['candidate'],'after':self.candidate['code']})
        self.assertEqual(result,{'added':1,'replaced':1,'rest_of_script_unchanged':True})

    def test_both_frozen_nested_restore_counterexamples_match_source_all_six_phases(self):
        for scenario in ['restore_extra_nested_object','restore_declared_object_value']:
            pairs=[r for r in self.runtime['pairs'] if r['scenario']==scenario and r['variant']=='san_dynamic_candidate']
            self.assertEqual(len(pairs),6)
            self.assertTrue(all(r['stateEqual'] and r['eventsEqual'] and r['errorsEqual'] for r in pairs))
            run=next(r for r in self.runtime['runs'] if r['scenario']==scenario and r['variant']=='san_dynamic_candidate')
            self.assertTrue(all(p['state']['taskIds']==[901] for p in run['phases']))
            self.assertTrue(all(not p['warnings'] and not p['errors'] for p in run['phases']))

    def test_source_and_old_normal_flow_runs_unchanged_against_frozen_contract(self):
        for variant in ['vue_source','san_normal_flow']:
            self.assertEqual([r for r in self.runtime['runs'] if r['variant']==variant],
                             [r for r in self.prior['runs'] if r['variant']==variant])

    def test_four_supported_contract_scenarios_have_24_matching_candidate_pairs(self):
        pairs=[r for r in self.runtime['pairs'] if r['variant']=='san_dynamic_candidate' and r['scenario']!='public_new_object_value']
        self.assertEqual(len(pairs),24)
        self.assertTrue(all(r['stateEqual'] and r['eventsEqual'] and r['errorsEqual'] for r in pairs))

    def test_public_object_write_is_still_an_explicit_unresolved_gap(self):
        actual=[r for r in self.runtime['runs'] if r['scenario']=='public_new_object_value']
        old=[r for r in self.prior['runs'] if r['scenario']=='public_new_object_value']
        self.assertEqual(actual,old)
        self.assertTrue(any(not r['stateEqual'] for r in self.runtime['pairs'] if r['scenario']=='public_new_object_value' and r['variant']=='san_dynamic_candidate'))

    def test_seven_boundary_key_controls_still_match_all_seventy_pairs(self):
        rows=[p for p in self.boundary['pairs'] if not p['scenario'].startswith('write_failure')]
        self.assertEqual(len(rows),70)
        self.assertTrue(all(p['stateEqual'] and p['businessEffectsEqual'] for p in rows))

    def test_both_exception_routes_are_unmodified_and_still_not_closed(self):
        prior=json.loads((BOUNDARY/'audit.json').read_text(encoding='utf-8'))['observations']
        for scenario in ['write_failure_captured','write_failure_headless_default']:
            self.assertEqual([r for r in self.boundary['runs'] if r['scenario']==scenario],
                             [r for r in prior['runs'] if r['scenario']==scenario])
            self.assertTrue(any(not(p['stateEqual'] and p['businessEffectsEqual']) for p in self.boundary['pairs'] if p['scenario']==scenario))

    def test_plain_nested_array_restore_and_identity_sequences_with_native_frameworks(self):
        normal,vue=nested_pair();candidate=adapt(normal,vue)
        result=node(EXTENDED,{**self.boundary_payload,'code':candidate['code'],'vue':vue})
        self.assertTrue(result['equal'],result)
        self.assertEqual(len(result['vue']['snapshots']),31)
        self.assertEqual(result['vue']['errors'],[])
        initial=result['san']['snapshots'][0]['shape']['values']
        self.assertTrue(any(pair[0]=='extra' and pair[1]['groups'][0]['values']==[None,{},[],True,3,'nested'] for pair in initial))

    def test_descriptor_guard_allows_nested_data_not_exotic_or_cyclic_inputs(self):
        result=node(DESCRIPTORS,{'code':self.candidate['code']})
        self.assertEqual(len(result['rows']),13)
        self.assertTrue(all(row['actual']==row['expected'] for row in result['rows']),result)
        self.assertEqual(result['getterCalls'],0)

    def test_writer_key_value_and_proto_rejections_not_relaxed(self):
        normal,vue=generic_pair();candidate=adapt(normal,vue)
        result=node(UNSUPPORTED,{**self.boundary_payload,'code':candidate['code']})
        self.assertEqual(len(result),5)
        self.assertTrue(all(row['unchanged'] and row['error']=='Dynamic-key probe: unsupported key or value' for row in result))

    def test_renamed_generic_root_uses_same_rule(self):
        normal,vue=nested_pair();normal=normal.replace('settings','options').replace('assign','change')
        vue=vue.replace('settings','options').replace('assign','change')
        result=adapt(normal,vue);self.assertEqual(result['changes'],self.candidate['changes'])
        self.assertNotIn('TaskManager',result['code']);self.assertEqual(result['writers'][0]['field'],'options')

    def test_shadowed_array_global_refuses_v2_without_rewriting(self):
        normal,vue=generic_pair();normal=normal.replace('const san=','const Array=class {};const san=')
        result=adapt(normal,vue);self.assertEqual(result['code'],normal)
        self.assertIn('shadowed_v2_array_global',result['reviews'])

    def test_repeated_candidate_is_not_rewritten(self):
        result=adapt(self.candidate['code'],self.old['vue'])
        self.assertEqual(result['code'],self.candidate['code']);self.assertFalse(result['changes'])

    def test_both_production_boundaries_and_forged_pass_guard_remain(self):
        before={'generated_code':self.old['normal'],'vue_source':self.old['vue'],
                'validation_errors':source_parent_watch_semantics(self.old['normal'],self.old['vue'])['findings']}
        actual=source_parent_watch_semantics(self.candidate['code'],self.old['vue'])
        self.assertEqual({r['code'] for r in actual['blocked_boundaries']},PARENT_WATCH_REVIEW_CODES)
        after={**before,'generated_code':self.candidate['code'],'validation_errors':[],'validation_passed':True}
        gate=candidate_gate(before,after);self.assertTrue(gate['should_stop'])
        self.assertEqual({r['code'] for r in gate['waived_source_parent_watch_boundaries']},PARENT_WATCH_REVIEW_CODES)

    def test_no_production_imports_or_integration(self):
        for folder in ['migration_pipeline/stages','migration_pipeline/utils','local_server']:
            for path in (ROOT/folder).rglob('*'):
                if path.suffix in {'.py','.cjs','.js'}:
                    self.assertNotIn('probe_parent_dynamic_key_adapter_v2',path.read_text(encoding='utf-8'),str(path))


if __name__=='__main__':unittest.main()
