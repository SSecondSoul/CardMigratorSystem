"""Native source computed collections; equal demand is not constructor parity."""
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
BASE=ROOT/'data/experiments/analysis/formal_30_v4_computed_collections_v1_input_20261115'
ISSUE='source_computed_collection_not_landed'
CHANGE='restored_source_native_computed_collection'


def fixture():
    b=json.loads((BASE/'baseline.json').read_text(encoding='utf-8'))
    return tuple((ROOT/b[k]['path']).read_text(encoding='utf-8') for k in ['candidate','source'])


def native(code=None):
    c,v=fixture();text=code if code is not None else inspect_semantics(c,v,repair=True)['code']
    p=subprocess.run(['node','migration_pipeline/probe_source_computed_collections_v1.cjs'],cwd=ROOT,
        input=json.dumps({'vue':v,'code':text,'runtime':str(ROOT/'data/experiments/manual_followups/task_manager_async_scope_v7_prepared_20261113/vendor/vue-2.7.16.js')}),
        capture_output=True,text=True,encoding='utf-8',timeout=30)
    if p.returncode:raise AssertionError(p.stderr)
    return json.loads(p.stdout)


def body_oracle():
    c,v=fixture();fixed=inspect_semantics(c,v,repair=True)['code']
    script=r'''
const fs=require('fs'),san=require('san'),{parse}=require('@vue/compiler-sfc'),x=JSON.parse(fs.readFileSync(0,'utf8')),m={exports:{}};
Function('module',parse(x.vue).descriptor.script.content)(m);
function computed(code){let options;Function('require','module',/<script\b[^>]*>([\s\S]*?)<\/script>/.exec(code)[1])(
 name=>({...san,defineComponent:o=>{options=o;return san.defineComponent(o);}}),{exports:{}});return options.computed;}
const old=computed(x.before),fixed=computed(x.after),out={};
for(const name of ['dayItems','totalCost'])for(const mode of ['sparse','append','record-identity','explicit-null']){
 const run=(f,target)=>{const root={items:[],activeDayId:'d1'},calls=[];
 const b={id:2,dayId:'d1',start:'11:00',cost:3},a={id:1,dayId:'d1',start:'09:00',cost:2};
 if(mode==='append')Object.defineProperty(a,name==='dayItems'?'dayId':'cost',{get(){calls.push('get');root.items.push(b);return name==='dayItems'?'d1':2;}});
 root.items=mode==='sparse'?[a,,b]:mode==='explicit-null'?[a,null]:mode==='append'?[a]:[a,b];
 const prior=root.items.slice();let value,error=null;try{value=f.call(target?{data:{get:k=>root[k]}}:root);}catch(e){error=e.name;}
 return {error,calls,result:Array.isArray(value)?value.map(r=>r.id):value,length:root.items.length,
  newArray:Array.isArray(value)?value!==root.items:null,recordIdentity:Array.isArray(value)?value.every(r=>prior.includes(r)):null};};
 out[name+':'+mode]={source:run(m.exports.computed[name],false),before:run(old[name],true),after:run(fixed[name],true)};
}
process.stdout.write(JSON.stringify(out),()=>process.exit(0));
'''
    p=subprocess.run(['node','-e',script],input=json.dumps({'vue':v,'before':c,'after':fixed}),cwd=ROOT,
        capture_output=True,text=True,encoding='utf-8',timeout=25)
    if p.returncode:raise AssertionError(p.stderr)
    return json.loads(p.stdout)


class SourceComputedCollectionClosureTests(unittest.TestCase):
    def apply(self,p,repair=True):
        r=inspect_semantics(*p,repair=repair);self.assertNotIn('error',r,r);return r

    def state(self,p):return {'generated_code':p[0],'vue_source':p[1],'ssm':{},'validation_errors':self.apply(p,False)['findings']}

    def test_two_independent_source_contracts_repair_and_fixed_point(self):
        p=fixture();old=self.apply(p,False);self.assertEqual(old['code'],p[0]);self.assertEqual(len(old['computed_collection_contracts']),2)
        self.assertEqual(sum(e['code']==ISSUE for e in old['findings']),2)
        r=self.apply(p);self.assertEqual(r['changes'],[CHANGE,'restored_source_native_filter_method']);again=self.apply((r['code'],p[1]))
        self.assertEqual(again['code'],r['code']);self.assertEqual(again['changes'],[])
        self.assertTrue(all(c['landed'] for c in again['computed_collection_contracts']));self.assertTrue(all(not c['global_helpers_modified'] for c in again['computed_collection_contracts']))
        self.assertEqual(self.apply((p[0],''))['code'],p[0])

    def test_no_component_field_helper_or_getter_name_allowlist(self):
        c,v=fixture()
        for a,b in [('TripItineraryPlanner','ScheduleBoard'),('dayItems','visibleEntries'),('totalCost','totalPrice'),('items','entries'),('activeDayId','selectedGroup'),('dayId','groupId'),('cost','price'),('start','begin')]:
            c=c.replace(a,b);v=v.replace(a,b)
        for name in ['filter','reduce','sort']:c=re.sub(r'(?<![.\w])'+name+r'\b',name+'Value',c)
        r=self.apply((c,v));self.assertIn(CHANGE,r['changes']);self.assertTrue(all(x['landed'] for x in self.apply((r['code'],v))['computed_collection_contracts']))

    def test_only_two_computed_bodies_change_helpers_and_other_code_unchanged(self):
        c,v=fixture();r=self.apply((c,v))['code']
        before,after=c.split('    computed: {',1),r.split('    computed: {',1)
        self.assertEqual(before[0],after[0])
        # Integrated source-native filter closure owns these two public bodies;
        # all other text is still protected and checked independently below.
        def mask(text):
            for name in ['removeItem','dayCount']:
                text=re.sub(r'    '+name+r'\(id\) \{[\s\S]*?\n    \},',name+'METHOD,',text)
                text=re.sub(r'    '+name+r'\(id\)\{[^\n]*\},',name+'METHOD,',text)
            return text
        self.assertEqual(mask(before[1].split('        remainingBudget()',1)[1]),mask(after[1].split('        remainingBudget()',1)[1]))
        self.assertEqual(c.split('</script>',1)[1],r.split('</script>',1)[1])

    def test_existing_native_const_root_alias_not_a_false_positive(self):
        rows=json.loads((ROOT/'data/experiments/analysis/formal_30_v4_parent_initialization_v1_20261114/inventory.json').read_text(encoding='utf-8'))
        row=next(r for r in rows if r['id']=='playback_queue');c=(ROOT/row['input_path']).read_text(encoding='utf-8');v=(ROOT/row['source_path']).read_text(encoding='utf-8')
        r=self.apply((c,v));self.assertEqual(r['code'],c)
        self.assertTrue(all(x['landed'] and x['native_root_alias_proven'] for x in r['computed_collection_contracts']))
        self.assertFalse(any(x['code']==ISSUE for x in r['findings']))
        bad=c.replace('return queue.reduce((sum, item) => sum + item.duration, 0);','extra();return queue.reduce((sum, item) => sum + item.duration, 0);')
        self.assertTrue(any(x['code']==ISSUE for x in self.apply((bad,v))['findings']))

    def test_unknown_legacy_helpers_or_extra_effects_not_repaired(self):
        c,v=fixture()
        for a,b,unlanded in [('if (predicate(items[i], i, items))','if (other(items[i]))','dayItems'),
                           ('accumulator = callback(accumulator, items[i], i, items);','accumulator = unknown(accumulator);','totalCost'),
                           ('return dayItemsGetter(items, activeDayId);','extra();return dayItemsGetter(items, activeDayId);','dayItems')]:
            changed=c.replace(a,b);self.assertNotEqual(c,changed);r=self.apply((changed,v));proof=next(x for x in r['computed_collection_contracts'] if x['name']==unlanded)
            self.assertFalse(proof['repair_eligible']);self.assertTrue(any(x['code']==ISSUE and unlanded in x['location'] for x in self.apply((r['code'],v),False)['findings']))

    def test_changed_source_guards_accumulator_or_extra_statements_not_guessed(self):
        c,v=fixture()
        for a,b,name in [('this.items.reduce((sum, item) => sum + item.cost, 0)','this.items.reduce((sum, item) => sum + item.cost, 1)','totalCost'),
                         ('item.dayId === this.activeDayId','item.dayId !== this.activeDayId','dayItems'),
                         ('return this.items.reduce','this.extra(); return this.items.reduce','totalCost')]:
            changed=v.replace(a,b);self.assertNotEqual(v,changed);r=self.apply((c,changed));self.assertFalse(any(x['name']==name for x in r['computed_collection_contracts']))

    def test_source_globals_runtime_and_state_collisions_refuse(self):
        c,v=fixture()
        for prefix in ['const Array=other;','const Object=other;','Array.prototype.filter=other;','san.defineComponent=other;']:
            changed=c.replace('module.exports = san.defineComponent',prefix+'module.exports = san.defineComponent')
            self.assertNotIn(CHANGE,self.apply((changed,v))['changes'])
        self.assertNotIn(CHANGE,self.apply((c.replace("require('san')","require('other')"),v))['changes'])
        self.assertNotIn(CHANGE,self.apply((c.replace('            items: [],','            items: {},'),v))['changes'])
        collision=v.replace('        items: [],','        dayItems: [], items: [],')
        self.assertNotEqual(collision,v);self.assertFalse(any(x['name']=='dayItems' for x in self.apply((c,collision))['computed_collection_contracts']))

    def test_missing_computed_and_forged_success_not_hidden(self):
        p=fixture();fixed=self.apply(p)['code'];state=self.state((fixed,p[1]));self.assertFalse(candidate_gate(self.state(p),state)['should_stop'])
        for bad in [p[0],fixed.replace('.filter(item=>item.dayId===this.data.get("activeDayId"))','.filter(item=>true)'),fixed.replace('dayItems(){','otherItems(){')]:
            self.assertNotEqual(bad,fixed);gate=candidate_gate(state,{**self.state((bad,p[1])),'validation_errors':[],'validation_passed':True})
            self.assertTrue(gate['should_stop']);self.assertTrue(gate['waived_source_computed_collection_findings'] or gate['lost_source_computed_collection_contracts'])

    def test_helper_escape_and_shadowing_refuse_automatic_change(self):
        c,v=fixture()
        changed=c.replace('function filter(items, predicate)', 'const escaped=filter;function filter(items, predicate)')
        r=self.apply((changed,v));self.assertFalse(next(x for x in r['computed_collection_contracts'] if x['name']=='dayItems')['repair_eligible'])
        changed=c.replace('const items = this.data.get(\'items\');\n            const activeDayId', 'const items = unknown;\n            const activeDayId')
        self.assertFalse(next(x for x in self.apply((changed,v))['computed_collection_contracts'] if x['name']=='dayItems')['repair_eligible'])

    def test_prepass_and_simulated_model_response_share_rule(self):
        p=fixture();fixed=self.apply(p)['code']
        class Client:
            def repair(self,request):return RepairResult(code=p[0],saved_file_path=request.output_file_path,source_file='',ssm={},provider='stub',model='stub',raw_response={})
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'source.vue';path.write_text(p[1],encoding='utf-8')
            code,steps=RepairStage._deterministic_repair_plan(p[0],self.apply(p,False)['findings'],[],{},str(path))
            self.assertEqual(code,fixed);self.assertIn(('bounded_ast_semantics',CHANGE),steps)
            out=RepairStage(Client()).run(RepairStageInput(ssm={},generated_code=p[0],vue_file_path=str(path),output_file_path=str(Path(tmp)/'out.san'),metadata={'skip_deterministic_prepass':True}))
            self.assertEqual(out.repaired_code.rstrip(),fixed.rstrip());self.assertIn(CHANGE,out.raw_response['pipeline_postprocessing'])

    def test_prompt_distinguishes_same_demand_and_source_exceptions(self):
        p=build_repair_prompt(RepairPromptInput(ssm={},current_code='',validation_errors=[{'code':ISSUE}]))
        for term in ['snapshot length','equal-demand','Native find visits holes','do not invent null guards','do not globally rewrite helpers']:self.assertIn(term,p)

    def test_native_normal_sparse_empty_and_explicit_empty_records(self):
        r=native()
        for case in ['normal','sparse','empty','undefined-record','null-record']:
            with self.subTest(case=case):self.assertEqual(r['cases'][case]['source'],r['cases'][case]['target'])
        before=native(fixture()[0]);self.assertEqual(before['cases']['sparse']['target']['constructorError'],'TypeError')
        self.assertEqual(r['cases']['sparse']['target']['computed']['totalCost']['value'],5)

    def test_native_reactive_root_replacement_and_selection_even_initially_empty(self):
        r=native()
        for name,row in r['reactive'].items():
            with self.subTest(case=name):self.assertEqual(row['source'],row['target'])
        self.assertEqual(r['reactive']['initially-empty']['target'][2],{'ids':[9],'sum':7})

    def test_native_find_shared_source_exception_and_timing_boundary_retained(self):
        r=native()
        for case in ['days-hole','days-null']:
            with self.subTest(case=case):
                pair=r['cases'][case];self.assertTrue(pair['source']['constructed']);self.assertEqual(pair['source']['computed']['activeDayLabel']['error'],'TypeError')
                self.assertFalse(pair['target']['constructed']);self.assertEqual(pair['target']['constructorError'],'TypeError')
        # No null filtering, fallback, lazy-runtime adapter or altered find helper.
        fixed=self.apply(fixture())['code'];self.assertIn('const day = find(days, item => item.id === activeDayId);',fixed)

    def test_native_callback_snapshot_length_holes_exceptions_and_record_identity(self):
        r=body_oracle()
        for name,row in r.items():
            with self.subTest(case=name):self.assertEqual(row['source'],row['after'])
        for name in ['dayItems','totalCost']:
            self.assertNotEqual(r[name+':append']['source'],r[name+':append']['before'])
            self.assertEqual(r[name+':explicit-null']['after']['error'],'TypeError')

    def test_real_validator_retains_two_other_blockers(self):
        c,v=fixture();baseline=json.loads((BASE/'baseline.json').read_text(encoding='utf-8'))
        state=json.loads((ROOT/'data/experiments/snapshots/formal_30_v4_full_regression_v2_results_20261104_214821/repair_reports/complex/TripItineraryPlanner_repair_history.json').read_text(encoding='utf-8'))['state']
        def assess(code):return ValidateStage().run(ValidateStageInput(generated_code=code,ssm=state['ssm'],vue_file_path=str(ROOT/baseline['source']['path'])))
        before=assess(c);after=assess(self.apply((c,v))['code'])
        self.assertEqual(len(before.validation_errors),6);self.assertEqual(sum(e['code']=='source_filter_method_not_landed' for e in before.validation_errors),2);self.assertEqual(len(after.validation_errors),2)
        self.assertEqual({e['code'] for e in after.validation_errors},{'nested_state_mutation','source_method_interface_not_landed'});self.assertFalse(after.validation_passed)


if __name__=='__main__':unittest.main()
