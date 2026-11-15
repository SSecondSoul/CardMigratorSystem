"""Source shared mutation is not a detachment proof; repair the shallow projection."""
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from migration_pipeline.utils.bounded_semantics import inspect_semantics
from migration_pipeline.utils.repair_scheduler import candidate_gate
from migration_pipeline.utils.repair_prompt import RepairPromptInput,build_repair_prompt
from migration_pipeline.stages.repair import RepairStage,RepairStageInput
from migration_pipeline.stages.validate import ValidateStage,ValidateStageInput
from migration_pipeline.repair_client import RepairResult

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data/experiments/analysis/formal_30_v4_shared_swap_v1_input_20261114'
ISSUE='source_shared_record_projection_not_landed'
CHANGE='restored_source_shared_swap_shallow_projection'


def fixture():
    b=json.loads((BASE/'baseline.json').read_text(encoding='utf-8'))
    return (ROOT/b['candidate_before']['path']).read_text(encoding='utf-8'),(ROOT/b['source']['path']).read_text(encoding='utf-8')


def native(case='forward'):
    code,vue=fixture();fixed=inspect_semantics(code,vue,repair=True)['code']
    script=r'''
const fs=require('fs'),{parse}=require('@vue/compiler-sfc'),x=JSON.parse(fs.readFileSync(0,'utf8'));
const Vue=require(x.runtime);
function source(){const m={exports:{}};Function('module',parse(x.vue).descriptor.script.content)(m);return new Vue(m.exports);}
function target(text){const m={exports:{}};Function('require','module',/<script\b[^>]*>([\s\S]*?)<\/script>/.exec(text)[1])(require,m);return new m.exports();}
function run(c,isVue){
 const get=k=>isVue?c[k]:c.data.get(k),set=(k,v)=>isVue?(c[k]=v):c.data.set(k,v);
 const a={id:1,dayId:'d1',start:'09:00',end:'10:00',place:'A',cost:1,meta:{tag:1}};
 const b={id:2,dayId:'d1',start:'11:00',end:'12:00',place:'B',cost:2,meta:{tag:2}};
 const z={id:3,dayId:'d2',start:'14:00',end:'15:00',place:'C',cost:3,meta:{tag:3}};
 if(x.case==='cycle')a.meta.self=a.meta;
 const records=x.case==='duplicate-ids'?[a,{...b,id:1},z]:[a,b,z];
 set('items',records);set('activeDayId','d1');set('saved',true);
 const old=get('items'),oldRecords=old.slice(),nested=oldRecords.map(r=>r.meta),events=[];
 const summarize=p=>({payloadIsState:p===get('items'),saved:get('saved'),oldStarts:oldRecords.map(r=>r.start),
  payloadStarts:p.map(r=>r.start),nested:p.map((r,i)=>r.meta===nested[i])});
 if(isVue)c.$on('itinerary-change',p=>events.push(summarize(p)));else c.on('itinerary-change',p=>events.push(summarize(p)));
 const args=x.case==='backward'?[1,-1]:x.case==='negative'?[0,-1]:x.case==='upper'?[1,1]:x.case==='same'?[0,0]
 :x.case==='fraction'?[0,0.5]:x.case==='nan'?[0,NaN]:[0,1];
 let error=null,result;try{result=c.moveItem(...args);}catch(e){error=e.name;}
 const now=get('items');const output={error,returnUndefined:result===undefined,rootChanged:now!==old,
  starts:now.map(r=>r.start),oldStarts:oldRecords.map(r=>r.start),sameRecords:now.map((r,i)=>r===oldRecords[i]),
  sameNested:now.map((r,i)=>r.meta===nested[i]),saved:get('saved'),events};
 if(isVue)c.$destroy();else c.dispose();return output;
}
const out={source:run(source(),true),before:run(target(x.before),false),after:run(target(x.after),false)};
process.stdout.write(JSON.stringify(out),()=>process.exit(0));
'''
    p=subprocess.run(['node','-e',script],cwd=ROOT,input=json.dumps({'vue':vue,'before':code,'after':fixed,'case':case,
        'runtime':str(ROOT/'data/experiments/manual_followups/task_manager_async_scope_v7_prepared_20261113/vendor/vue-2.7.16.js')}),
        capture_output=True,text=True,encoding='utf-8',timeout=25)
    if p.returncode:raise AssertionError(p.stderr)
    return json.loads(p.stdout)


class SourceSharedSwapClosureTests(unittest.TestCase):
    def apply(self,p,repair=True):
        r=inspect_semantics(*p,repair=repair);self.assertNotIn('error',r,r);return r

    def state(self,p):return {'generated_code':p[0],'vue_source':p[1],'ssm':{},'validation_errors':self.apply(p,False)['findings']}

    def test_complete_source_projection_and_shared_writes_preserved(self):
        p=fixture();r=self.apply(p);self.assertEqual(r['changes'],[CHANGE,'restored_source_parent_shallow_initialization','restored_source_native_computed_collection','restored_source_native_filter_method'])
        self.assertIn('Object.assign({},mapped[item.id])',r['code'])
        self.assertIn('rows[index].start=rows[target].start',r['code'])
        proof=r['shared_record_contracts'][0];self.assertFalse(proof['nested_mutation_exemption']);self.assertFalse(proof['landed'])
        again=self.apply((r['code'],p[1]));self.assertEqual(again['code'],r['code']);self.assertTrue(again['shared_record_contracts'][0]['landed'])

    def test_readonly_mode_no_source_and_only_move_method_changes(self):
        p=fixture();self.assertEqual(self.apply(p,False)['code'],p[0]);self.assertEqual(self.apply((p[0],''))['code'],p[0])
        fixed=self.apply(p)['code'];before=p[0].split('    moveItem(index, delta) {')[0]
        # Combined rules change inited and two source-proven computed bodies too.
        def hook(s):
            s=re.sub(r'inited\(\)\s*\{.*?\},\s*computed:', 'inited(){},computed:',s,flags=re.S)
            for name in ['removeItem','dayCount']:
                s=re.sub(r'    '+name+r'\(id\) \{[\s\S]*?\n    \},',name+'METHOD,',s)
                s=re.sub(r'    '+name+r'\(id\)\{[^\n]*\},',name+'METHOD,',s)
            return re.sub(r'\b(dayItems|totalCost)\(\)\s*\{.*?\},',lambda m:m[1]+'(){},',s,flags=re.S)
        self.assertEqual(hook(fixed.split('moveItem(index,delta)')[0]).rstrip(),hook(before).rstrip())
        self.assertEqual(hook(fixed.split('    updateBudget(event) {')[1]),hook(p[0].split('    updateBudget(event) {')[1]))

    def test_not_a_component_or_method_or_helper_name_allowlist(self):
        c,v=fixture()
        for old,new in [('TripItineraryPlanner','ScheduleBoard'),('dayItems','visibleRecords'),('items','records'),('moveItem','shiftEntry'),('itinerary-change','schedule-change')]:
            c=c.replace(old,new);v=v.replace(old,new)
        for name in ['slice','map','clone']:
            c=re.sub(r'(?<![.\w])'+name+r'\b',name+'Value',c)
        r=self.apply((c,v));self.assertIn(CHANGE,r['changes']);self.assertTrue(self.apply((r['code'],v))['shared_record_contracts'][0]['landed'])

    def test_unknown_or_changed_helper_body_is_not_guessed(self):
        c,v=fixture()
        for old,new in [('return result;','external();return result;'),('return result;','return obj;'),
                        ('const rows = slice(dayItems, 0);','const rows = unknown(dayItems, 0);'),
                        ('clone(mapped[item.id])','unknown(mapped[item.id])')]:
            changed=c.replace(old,new);self.assertNotEqual(changed,c)
            r=self.apply((changed,v));self.assertNotIn(CHANGE,r['changes']);self.assertTrue(any(e['code']==ISSUE for e in r['findings']))

    def test_changed_target_guard_write_commit_notification_or_extra_effect_refused(self):
        c,v=fixture()
        for old,new in [('target >= rows.length','target > rows.length'),('rows[index].start = rows[target].start;','rows[index].start = temp;'),
                        ("this.data.set('items', nextItems);","this.data.set('items', items);"),
                        ("this.fire('itinerary-change', nextItems);","this.fire('itinerary-change', []);"),
                        ('const temp = rows[index].start;','external();const temp = rows[index].start;')]:
            changed=c.replace(old,new);r=self.apply((changed,v));self.assertNotEqual(changed,c);self.assertNotIn(CHANGE,r['changes'])

    def test_source_mutation_and_hook_changes_not_silently_repaired(self):
        c,v=fixture()
        for old,new in [('rows[target].start = temp;','rows[target].start = temp; this.extra();'),
                        ('  methods: {',"  watch:{items(){this.extra();}}, methods: {"),
                        ('this[key] = value;','this[key] = value; this.extra();')]:
            r=self.apply((c,v.replace(old,new)));self.assertNotIn(CHANGE,r['changes'])

    def test_shadowed_globals_runtime_or_reserved_field_collision_refused(self):
        c,v=fixture()
        for prefix in ['const Object=other;','const Array=other;','const Math=other;','san.defineComponent=other;']:
            changed=c.replace('module.exports = san.defineComponent',prefix+'module.exports = san.defineComponent')
            self.assertNotIn(CHANGE,self.apply((changed,v))['changes'])
        self.assertNotIn(CHANGE,self.apply((c.replace("require('san')","require('other')"),v))['changes'])

    def test_gate_accepts_partial_progress_but_rejects_reverse_and_forged_success(self):
        p=fixture();fixed=self.apply(p)['code'];before=self.state(p);after=self.state((fixed,p[1]))
        self.assertFalse(candidate_gate(before,after)['should_stop'])
        for code in [p[0],fixed.replace('Object.assign({},mapped[item.id])','Object.assign({},item)'),fixed.replace("this.notify(next)","this.notify([])")]:
            self.assertNotEqual(code,fixed);bad={**self.state((code,p[1])),'validation_errors':[],'validation_passed':True}
            gate=candidate_gate(after,bad);self.assertTrue(gate['should_stop'])
            self.assertTrue(gate['waived_source_shared_record_findings'] or gate['lost_source_shared_record_contracts'])

    def test_prepass_and_simulated_model_response_use_same_rule(self):
        p=fixture()
        class Client:
            def repair(self,request):return RepairResult(code=p[0],saved_file_path=request.output_file_path,source_file='',ssm={},provider='stub',model='stub',raw_response={})
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'a.vue';path.write_text(p[1],encoding='utf-8')
            fixed,steps=RepairStage._deterministic_repair_plan(p[0],self.apply(p,False)['findings'],[],{},str(path))
            self.assertEqual(fixed,self.apply(p)['code']);self.assertIn(('bounded_ast_semantics',CHANGE),steps)
            result=RepairStage(Client()).run(RepairStageInput(ssm={},generated_code=p[0],vue_file_path=str(path),output_file_path=str(Path(tmp)/'out.san'),metadata={'skip_deterministic_prepass':True}))
            self.assertEqual(result.repaired_code.rstrip(),fixed.rstrip());self.assertIn(CHANGE,result.raw_response['pipeline_postprocessing'])

    def test_missing_event_helpers_do_not_hide_contract_and_repair_is_atomic(self):
        old=json.loads((ROOT/'data/experiments/analysis/formal_30_v4_trip_event_interface_v1_input_20261114/baseline.json').read_text(encoding='utf-8'))['input']
        c=(ROOT/old['candidate']['path']).read_text(encoding='utf-8');v=(ROOT/old['vue']['path']).read_text(encoding='utf-8')
        before=self.apply((c,v),False);self.assertTrue(any(e['code']==ISSUE for e in before['findings']))
        r=self.apply((c,v));self.assertIn(CHANGE,r['changes']);self.assertTrue(r['shared_record_contracts'][0]['reuses_planned_event_forwarders'])
        self.assertEqual(self.apply((r['code'],v))['code'],r['code'])
        ssm=json.loads((ROOT/'data/experiments/snapshots/formal_30_v4_full_regression_v2_results_20261104_214821/repair_reports/complex/TripItineraryPlanner_repair_history.json').read_text(encoding='utf-8'))['state']['ssm']
        def actual(code):return {'generated_code':code,'ssm':ssm,'vue_file_path':str(ROOT/old['vue']['path']),
            **ValidateStage().run(ValidateStageInput(generated_code=code,ssm=ssm,vue_file_path=str(ROOT/old['vue']['path']))).to_state_update()}
        self.assertFalse(candidate_gate(actual(c),actual(r['code']))['should_stop'])

    def test_prompt_does_not_confuse_projection_correction_with_detachment(self):
        text=build_repair_prompt(RepairPromptInput(ssm={},current_code='',validation_errors=[{'code':ISSUE}]))
        for term in ['nested-reference identity','NOT waive nested_state_mutation','arbitrary this[key]']:self.assertIn(term,text)

    def test_real_validator_retains_nested_mutation_and_missing_dynamic_setter(self):
        p=fixture();b=json.loads((BASE/'baseline.json').read_text(encoding='utf-8'))
        state=json.loads((ROOT/'data/experiments/snapshots/formal_30_v4_full_regression_v2_results_20261104_214821/repair_reports/complex/TripItineraryPlanner_repair_history.json').read_text(encoding='utf-8'))['state']
        def assess(c):return ValidateStage().run(ValidateStageInput(generated_code=c,ssm=state['ssm'],vue_file_path=str(ROOT/b['source']['path'])))
        before=assess(p[0]);after=assess(self.apply(p)['code'])
        self.assertEqual(len(before.validation_errors),8);self.assertEqual(sum(e['code']=='source_filter_method_not_landed' for e in before.validation_errors),2);self.assertEqual(len(after.validation_errors),2)
        self.assertEqual({e['code'] for e in after.validation_errors},{'nested_state_mutation','source_method_interface_not_landed'});self.assertFalse(after.validation_passed)

    def test_native_forward_swap_shallow_and_unaffected_identity_event_order(self):
        r=native();self.assertEqual(r['source'],r['after'])
        self.assertEqual(r['after']['sameRecords'],[False,False,True]);self.assertEqual(r['after']['sameNested'],[True,True,True])
        self.assertEqual(r['before']['sameNested'],[False,False,True]);self.assertEqual(r['after']['oldStarts'],['11:00','09:00','14:00'])
        self.assertEqual(len(r['after']['events']),1);self.assertTrue(r['after']['events'][0]['payloadIsState']);self.assertFalse(r['after']['events'][0]['saved'])

    def test_native_reverse_noop_and_boundaries_preserve_source_guards(self):
        for case in ['backward','negative','upper','same']:
            with self.subTest(case=case):
                r=native(case);self.assertEqual(r['source'],r['after']);self.assertIsNone(r['after']['error'])
                self.assertEqual(len(r['after']['events']),0 if case in ['negative','upper'] else 1)

    def test_native_fraction_nan_and_duplicate_ids_not_sanitized(self):
        for case in ['fraction','nan','duplicate-ids']:
            with self.subTest(case=case):
                r=native(case);self.assertEqual(r['source'],r['after'])
        self.assertEqual(native('nan')['after']['error'],'TypeError')

    def test_native_cycle_keeps_source_shallow_alias_not_recursive_clone(self):
        r=native('cycle');self.assertEqual(r['source'],r['after']);self.assertIsNone(r['after']['error']);self.assertEqual(r['before']['error'],'RangeError')

    def test_arbitrary_dynamic_setter_is_not_restored_or_reinterpreted_as_path(self):
        p=fixture();r=self.apply(p)
        self.assertTrue(any(e['code']=='source_method_interface_not_landed' and e['location']=='script.methods.setValue' for e in r['findings']))
        script=r'''const fs=require('fs'),{parse}=require('@vue/compiler-sfc'),x=JSON.parse(fs.readFileSync(0,'utf8')),Vue=require(x.runtime),m={exports:{}};
Function('module',parse(x.vue).descriptor.script.content)(m);const c=new Vue(m.exports),start=c.draft.start;
c.setValue('draft.start','literal');c.setValue('lateField',7);process.stdout.write(JSON.stringify({dottedInstanceProperty:c['draft.start'],nestedStart:c.draft.start,oldStart:start,lateField:c.lateField,lateDeclared:Object.prototype.hasOwnProperty.call(c.$data,'lateField')}));c.$destroy();'''
        out=subprocess.run(['node','-e',script],input=json.dumps({'vue':p[1],'runtime':str(ROOT/'data/experiments/manual_followups/task_manager_async_scope_v7_prepared_20261113/vendor/vue-2.7.16.js')}),cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=20)
        self.assertEqual(out.returncode,0,out.stderr);x=json.loads(out.stdout);self.assertEqual(x['dottedInstanceProperty'],'literal');self.assertEqual(x['nestedStart'],x['oldStart']);self.assertEqual(x['lateField'],7);self.assertFalse(x['lateDeclared'])


if __name__=='__main__':unittest.main()
