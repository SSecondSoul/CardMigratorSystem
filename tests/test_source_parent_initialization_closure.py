"""Parent startup projection must preserve source shallow references, not detach them."""
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from migration_pipeline.utils.bounded_semantics import inspect_semantics
from migration_pipeline.utils.repair_scheduler import candidate_gate
from migration_pipeline.utils.repair_prompt import RepairPromptInput, build_repair_prompt
from migration_pipeline.stages.repair import RepairStage, RepairStageInput
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.repair_client import RepairResult

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data/experiments/analysis/formal_30_v4_parent_initialization_v1_input_20261114'
ISSUE='source_parent_initialization_not_landed'
CHANGE='restored_source_parent_shallow_initialization'


def fixture():
    b=json.loads((BASE/'baseline.json').read_text(encoding='utf-8'))
    return tuple((ROOT/b[k]['path']).read_text(encoding='utf-8') for k in ['candidate','source'])


def native(case='nested',isolated=False):
    code,vue=fixture();fixed=inspect_semantics(code,vue,repair=True)['code']
    script=r'''
const fs=require('fs'),{parse}=require('@vue/compiler-sfc'),x=JSON.parse(fs.readFileSync(0,'utf8')),Vue=require(x.runtime);
const sourceModule={exports:{}};Function('module',parse(x.vue).descriptor.script.content)(sourceModule);
function rows(){const a={id:1,dayId:'d1',start:'09:00',end:'10:00',cost:1,meta:{tag:1}};
 if(x.case==='cycle')a.meta.self=a.meta;
 if(x.case==='symbol')a[Symbol.for('marker')]='kept';
 if(x.case==='sparse')return [a,,{...a,id:3}];
 if(x.case==='empty')return [];return [a];}
function run(text,isVue){
 const initialItems=rows(),days=x.case==='days-hole'?Array(1):x.case==='days-null'?[null]:x.case==='empty-days'?[]:[{id:'d1',label:'one'}];
 let c,error=null;const captured=[];const old=Vue.config.errorHandler;Vue.config.errorHandler=e=>captured.push(e.name);
 try{if(isVue)c=new Vue({...sourceModule.exports,...(x.isolated?{computed:{}}:{}),propsData:{initialItems,days}});
 else{const m={exports:{}};const req=name=>{const san=require(name);return x.isolated?{...san,defineComponent:o=>san.defineComponent({...o,computed:{}})}:san;};
 Function('require','module',/<script\b[^>]*>([\s\S]*?)<\/script>/.exec(text)[1])(req,m);c=new m.exports({data:{initialItems,days}});}}
 catch(e){error=e.name;}finally{Vue.config.errorHandler=old;}
 if(!c)return {error};
 const get=k=>isVue?c[k]:c.data.get(k),items=get('items'),prop=get('initialItems');
 const out={error:captured[0]||error,newArray:items!==prop,length:items.length,keys:Object.keys(items),
 freshRecord:items[0]?items[0]!==prop[0]:null,sameNested:items[0]?items[0].meta===prop[0].meta:null,
 symbol:items[0]?.[Symbol.for('marker')]||null,activeDayId:get('activeDayId')};
 if(items[0]){items[0].meta.tag=2;out.nestedWriteVisible=prop[0].meta.tag===2;items[0].cost=99;out.recordWriteIsolated=prop[0].cost===1;}
 if(isVue)c.$destroy();else c.dispose();return out;
}
process.stdout.write(JSON.stringify({source:run('',true),before:run(x.before,false),after:run(x.after,false)}),()=>process.exit(0));
'''
    p=subprocess.run(['node','-e',script],cwd=ROOT,input=json.dumps({'vue':vue,'before':code,'after':fixed,'case':case,'isolated':isolated,
        'runtime':str(ROOT/'data/experiments/manual_followups/task_manager_async_scope_v7_prepared_20261113/vendor/vue-2.7.16.js')}),
        capture_output=True,text=True,encoding='utf-8',timeout=25)
    if p.returncode:raise AssertionError(p.stderr)
    return json.loads(p.stdout)


class SourceParentInitializationClosureTests(unittest.TestCase):
    def apply(self,p,repair=True):
        r=inspect_semantics(*p,repair=repair);self.assertNotIn('error',r,r);return r

    def state(self,p):return {'generated_code':p[0],'vue_source':p[1],'ssm':{},'validation_errors':self.apply(p,False)['findings']}

    def test_detect_repair_idempotence_and_only_parent_hook_changed(self):
        c,v=fixture();before=self.apply((c,v),False);self.assertEqual(before['code'],c)
        self.assertIn(ISSUE,[e['code'] for e in before['findings']]);r=self.apply((c,v))
        self.assertEqual(r['changes'],[CHANGE,'restored_source_native_computed_collection','restored_source_native_filter_method']);self.assertFalse(r['parent_initialization_contracts'][0]['dynamic_setter_restored'])
        prefix,suffix=c.split('    inited() {');_,tail=suffix.split('    computed: {',1)
        # The integrated computed rule changes the first two getters, not the rest.
        self.assertTrue(r['code'].startswith(prefix))
        def mask(text):
            for name in ['removeItem','dayCount']:
                text=re.sub(r'    '+name+r'\(id\) \{[\s\S]*?\n    \},',name+'METHOD,',text)
                text=re.sub(r'    '+name+r'\(id\)\{[^\n]*\},',name+'METHOD,',text)
            return text
        self.assertEqual(mask(r['code'].split('        remainingBudget()',1)[1]),mask(c.split('        remainingBudget()',1)[1]))
        again=self.apply((r['code'],v));self.assertEqual(again['code'],r['code']);self.assertEqual(again['changes'],[])
        self.assertTrue(again['parent_initialization_contracts'][0]['landed'])
        self.assertEqual(self.apply((c,''))['code'],c)

    def test_renamed_component_fields_helpers_and_setter_not_allowlisted(self):
        c,v=fixture()
        for a,b in [('TripItineraryPlanner','ScheduleBoard'),('initialItems','seedRecords'),('items','records'),('activeDayId','selectedId'),('days','groups'),('setValue','putValue')]:
            c=c.replace(a,b);v=v.replace(a,b)
        for a in ['map','clone']:c=re.sub(r'(?<![.\w])'+a+r'\b',a+'Value',c)
        self.assertIn(CHANGE,self.apply((c,v))['changes'])

    def test_changed_source_setter_or_copy_policy_or_hook_refused(self):
        c,v=fixture()
        for a,b in [('Object.assign({}, item)','clone(item)'),('this[key] = value;','this[key] = value; this.extra();'),
                    ('  created() {','  created() { this.extra();'),('  methods: {','  watch:{items(){this.extra();}},methods: {')]:
            changed=v.replace(a,b);self.assertNotEqual(changed,v);self.assertNotIn(CHANGE,self.apply((c,changed))['changes'])

    def test_changed_target_helper_or_order_or_extra_effect_keeps_diagnostic(self):
        c,v=fixture()
        for a,b in [('const items = map(initialItems, item => clone(item));','const items = external(initialItems);'),
                    ('return obj;','return obj; external();'),("const initialItems = this.data.get('initialItems');","external();const initialItems = this.data.get('initialItems');"),
                    ("this.data.set('activeDayId', firstDayId);","this.data.set('activeDayId', firstDayId);external();")]:
            changed=c.replace(a,b);self.assertNotEqual(changed,c);r=self.apply((changed,v));self.assertNotIn(CHANGE,r['changes'])
            self.assertIn(ISSUE,[f['code'] for f in r['findings']])

    def test_globals_runtime_collisions_and_observers_refused(self):
        c,v=fixture()
        for prefix in ['const Object=other;','const Array=other;','Object.assign=other;','san.defineComponent=other;']:
            self.assertNotIn(CHANGE,self.apply((c.replace('module.exports = san.defineComponent',prefix+'module.exports = san.defineComponent'),v))['changes'])
        for a,b in [("require('san')","require('other')"),('    inited() {',"    inited() {this.watch('items',()=>{});")]:
            self.assertNotIn(CHANGE,self.apply((c.replace(a,b),v))['changes'])
        self.assertNotIn(CHANGE,self.apply((c.replace('            items: [],','            items: {},'),v))['changes'])

    def test_gate_rejects_reversed_copy_policy_and_hidden_findings(self):
        p=fixture();fixed=self.apply(p)['code'];after=self.state((fixed,p[1]))
        self.assertFalse(candidate_gate(self.state(p),after)['should_stop'])
        for text in [p[0],fixed.replace('Object.assign({},item)','clone(item)'),fixed.replace('inited(){','attached(){')]:
            self.assertNotEqual(text,fixed);gate=candidate_gate(after,{**self.state((text,p[1])),'validation_errors':[],'validation_passed':True})
            self.assertTrue(gate['should_stop']);self.assertTrue(gate['waived_source_parent_initialization_findings'] or gate['lost_source_parent_initialization_contracts'])

    def test_prepass_and_simulated_response_share_rule(self):
        p=fixture();fixed=self.apply(p)['code']
        class Client:
            def repair(self,request):return RepairResult(code=p[0],saved_file_path=request.output_file_path,source_file='',ssm={},provider='stub',model='stub',raw_response={})
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'source.vue';path.write_text(p[1],encoding='utf-8')
            result,steps=RepairStage._deterministic_repair_plan(p[0],self.apply(p,False)['findings'],[],{},str(path))
            self.assertEqual(result,fixed);self.assertIn(('bounded_ast_semantics',CHANGE),steps)
            out=RepairStage(Client()).run(RepairStageInput(ssm={},generated_code=p[0],vue_file_path=str(path),output_file_path=str(Path(tmp)/'out.san'),metadata={'skip_deterministic_prepass':True}))
            self.assertEqual(out.repaired_code.rstrip(),fixed.rstrip());self.assertIn(CHANGE,out.raw_response['pipeline_postprocessing'])

    def test_prompt_records_copy_semantics_without_mutation_waiver(self):
        p=build_repair_prompt(RepairPromptInput(ssm={},current_code='',validation_errors=[{'code':ISSUE}]))
        for term in ['shared nested references','sparse-array','do not restore an arbitrary dynamic setter','nested_state_mutation']:self.assertIn(term,p)

    def test_native_nested_sharing_and_top_record_isolation(self):
        r=native();self.assertEqual(r['source'],r['after']);self.assertTrue(r['after']['newArray']);self.assertTrue(r['after']['freshRecord'])
        self.assertTrue(r['after']['sameNested']);self.assertTrue(r['after']['nestedWriteVisible']);self.assertTrue(r['after']['recordWriteIsolated']);self.assertFalse(r['before']['sameNested'])

    def test_native_sparse_empty_symbol_cycle(self):
        for case in ['sparse','empty','symbol','cycle']:
            with self.subTest(case=case):
                r=native(case,isolated=case=='sparse');self.assertEqual(r['source'],r['after'])
        self.assertEqual(native('cycle')['before']['error'],'RangeError')
        self.assertEqual(native('symbol')['after']['symbol'],'kept')

    def test_native_first_element_guard_not_array_length_guess(self):
        for case in ['days-hole','days-null','empty-days']:
            with self.subTest(case=case):
                r=native(case,isolated=True);self.assertEqual(r['source'],r['after']);self.assertIsNone(r['after']['error']);self.assertEqual(r['after']['activeDayId'],'')
        self.assertEqual(native('days-hole',isolated=True)['before']['error'],'TypeError')

    def test_full_component_sparse_now_fixed_but_days_constructor_boundary_retained(self):
        # This historical constructor-only oracle does not demand Vue computed.
        # Equal-demand find exceptions are covered by the computed-collection suite.
        sparse=native('sparse');self.assertEqual(sparse['source'],sparse['after']);self.assertEqual(sparse['before']['error'],'TypeError')
        for case in ['days-hole','days-null']:
            with self.subTest(case=case):
                r=native(case);self.assertIsNone(r['source']['error']);self.assertEqual(r['after']['error'],'TypeError')

    def test_real_validation_retains_unrelated_blockers(self):
        c,v=fixture();baseline=json.loads((BASE/'baseline.json').read_text(encoding='utf-8'))
        state=json.loads((ROOT/'data/experiments/snapshots/formal_30_v4_full_regression_v2_results_20261104_214821/repair_reports/complex/TripItineraryPlanner_repair_history.json').read_text(encoding='utf-8'))['state']
        def assess(code):return ValidateStage().run(ValidateStageInput(generated_code=code,ssm=state['ssm'],vue_file_path=str(ROOT/baseline['source']['path'])))
        before=assess(c);after=assess(self.apply((c,v))['code'])
        self.assertEqual(len(before.validation_errors),7);self.assertEqual(sum(e['code']=='source_filter_method_not_landed' for e in before.validation_errors),2);self.assertEqual(len(after.validation_errors),2)
        self.assertEqual({e['code'] for e in after.validation_errors},{'nested_state_mutation','source_method_interface_not_landed'});self.assertFalse(after.validation_passed)


if __name__=='__main__':unittest.main()
