"""Atomic array moves: source order, closed aliases, refusal and rollback."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from migration_pipeline.utils.source_array_transaction_semantics import source_array_transaction_semantics, _run
from migration_pipeline.utils.source_child_initialization_semantics import source_child_initialization_semantics
from migration_pipeline.utils.source_native_drag_semantics import source_native_drag_semantics
from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
from migration_pipeline.stages.repair import RepairStage, RepairStageInput
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.utils.repair_scheduler import candidate_gate
from migration_pipeline.utils.repair_prompt import RepairPromptInput, build_repair_prompt
from migration_pipeline.repair_client import RepairResult
from migration_pipeline.orchestrator import MigrationPipelineOrchestrator
from migration_pipeline.stages.generate import GenerateStageInput, GenerateStageResult
from migration_pipeline.stages.visual_eval import VisualEvalStage

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data/experiments/analysis/formal_30_v4_source_render_dependency_closure_v1_20261111'
SOURCE=ROOT/'data/experiments/snapshots/formal_30_v4_full_regression_v2_results_20261104_214821'


def fixture():
    data="{rows:[],view:[],drag:1}"
    before="""reshuffle(i,j,after=false){
if(i===null||i===undefined)return;
const picked=this.view[i];const down=i<j;const destination=this.view[j];
if(!picked||!destination||picked.id===destination.id)return;
const at=this.rows.findIndex(r=>r.id===picked.id);
let to=this.rows.findIndex(r=>r.id===destination.id);
if(at!==-1&&to!==-1){const [item]=this.rows.splice(at,1);
if(at<to){to-=1;}if(after||down){to+=1;}
this.rows.splice(to,0,item);this.drag=null;this.note('moved');}
}"""
    target=before.replace('const picked=this.view[i];',"const view=this.data.get('view');const picked=view[i];")
    target=target.replace('this.view[j]','view[j]').replace('const at=this.rows.',"const rows=this.data.get('rows');const at=rows.")
    target=target.replace('this.rows.','rows.').replace('this.drag=null;',"this.data.set('drag',null);this.data.set('rows',[...rows]);")
    vue='<template><section/></template><script>export default {data(){return '+data+';},methods:{'+before+",note(text){return text;}}};</script>"
    code='<template><section/></template><script>const san=require("san");module.exports=san.defineComponent({initData(){return '+data+';},'+target+",note(text){return text;}});</script><style>.keep{color:red}</style>"
    return code,vue


def node(script,payload):
    p=subprocess.run(['node','-e',script],input=json.dumps(payload),text=True,encoding='utf-8',capture_output=True,cwd=ROOT)
    if p.returncode:raise AssertionError(p.stderr)
    return json.loads(p.stdout)


class SourceArrayTransactionClosureTests(unittest.TestCase):
    def apply(self,p,repair=True):
        r=source_array_transaction_semantics(*p,repair=repair);self.assertNotIn('error',r,r);return r

    def fixture_state(self,code,vue):
        return {'generated_code':code,'vue_source':vue,'ssm':{},
            'validation_errors':self.apply((code,vue),repair=False)['findings']}

    def test_clone_commit_moved_before_source_observers_and_fixedpoint(self):
        p=fixture();r=self.apply(p)
        self.assertEqual(r['changes'],['detached_and_committed_source_array_transaction'])
        self.assertIn("const rows=[...this.data.get('rows')];",r['code'])
        self.assertIn('rows.splice(to,0,item);\n      this.data.set("rows", [...rows]);',r['code'])
        self.assertLess(r['code'].index('this.data.set("rows", [...rows]);'),r['code'].index("this.data.set('drag',null)"))
        self.assertEqual(r['code'].count('this.data.set("rows", [...rows]);'),1)
        self.assertEqual(r['code'].split('</script>')[1],p[0].split('</script>')[1])
        again=self.apply((r['code'],p[1]));self.assertEqual(again['code'],r['code']);self.assertEqual(again['findings'],[])
        self.assertTrue(again['proofs'][0]['copied_before_mutation']);self.assertTrue(again['proofs'][0]['commit_immediately_after_last_splice'])

    def test_already_copied_but_late_commit_still_repaired(self):
        p=fixture();code=p[0].replace("const rows=this.data.get('rows')","const rows=[...this.data.get('rows')]")
        r=self.apply((code,p[1]));self.assertTrue(r['changes']);self.assertTrue(r['proofs'][0]['copied_before_mutation'])
        self.assertFalse(r['proofs'][0]['commit_immediately_after_last_splice'])

    def test_missing_commit_added_only_after_full_source_body_proof(self):
        p=fixture();code=p[0].replace("this.data.set('rows',[...rows]);",'')
        r=self.apply((code,p[1]));self.assertTrue(r['changes']);self.assertFalse(self.apply((r['code'],p[1]))['findings'])

    def test_full_guard_index_signature_and_notification_mismatch_refused(self):
        p=fixture()
        for a,b in [('at<to','at>to'),('after||down','after&&down'),('after=false','after=true'),
                    ('!picked||!destination','!picked'),("this.note('moved')","this.note('different')")]:
            code=p[0].replace(a,b);self.assertNotEqual(code,p[0]);r=self.apply((code,p[1]))
            self.assertEqual(r['code'],code);self.assertTrue(r['findings'])

    def test_unknown_control_flow_or_mutation_between_splices_refused(self):
        p=fixture()
        for extra in ('this.refresh();','return;','item.id=99;','rows.push(item);','while(to>0){to--;}'):
            code=p[0].replace('if(at<to)',extra+'if(at<to)');r=self.apply((code,p[1]))
            self.assertEqual(r['code'],code);self.assertTrue(r['findings'])

    def test_unknown_source_transaction_and_extra_splice_are_not_invented(self):
        p=fixture()
        for extra in ('this.refresh();','return;','this.rows.splice(at,1);'):
            vue=p[1].replace('if(at<to)',extra+'if(at<to)')
            self.assertEqual(self.apply((p[0],vue))['code'],p[0])

    def test_alias_escape_reassignment_and_nested_record_mutation_refused(self):
        p=fixture()
        for extra in ('this.leak(rows);','const escaped=rows;','rows[0].id=9;','rows=[];'):
            code=p[0].replace('const at=rows.',extra+'const at=rows.');r=self.apply((code,p[1]))
            self.assertEqual(r['code'],code);self.assertTrue(r['findings'])

    def test_source_matching_alias_escape_is_not_proof_for_shallow_clone(self):
        p=fixture()
        vue=p[1].replace('const at=this.rows.', 'this.leak(this.rows);const at=this.rows.')
        code=p[0].replace('const at=rows.','this.leak(rows);const at=rows.')
        r=self.apply((code,vue));self.assertEqual(r['code'],code);self.assertTrue(r['findings'])

    def test_live_reread_cannot_observe_precommit_original_array(self):
        p=fixture()
        vue=p[1].replace("this.note('moved')","this.note(this.rows.length)")
        code=p[0].replace("this.note('moved')","this.note(this.data.get('rows').length)")
        r=self.apply((code,vue));self.assertEqual(r['code'],code);self.assertTrue(r['findings'])

    def test_unknown_callback_and_intervening_effect_refused_even_when_source_matches(self):
        p=fixture()
        for a,b in [('r=>r.id===picked.id','r=>this.check(r,picked)'),
                    ('let to=', 'this.refresh();let to=')]:
            vue=p[1].replace(a,b);code=p[0].replace(a,b);r=self.apply((code,vue))
            self.assertEqual(r['code'],code);self.assertTrue(r['findings'])

    def test_ambiguous_commit_value_duplicate_branch_and_fallback_refused(self):
        p=fixture()
        for a,b in [("this.data.set('rows',[...rows]);","this.data.set('rows',[]);"),
                    ("this.data.set('rows',[...rows]);","if(after)this.data.set('rows',[...rows]);"),
                    ("this.data.set('rows',[...rows]);","this.data.set('rows',[...rows]);this.data.set('rows',[...rows]);"),
                    ("const rows=this.data.get('rows')","const rows=this.data.get('rows')||[]")]:
            code=p[0].replace(a,b);r=self.apply((code,p[1]));self.assertEqual(r['code'],code);self.assertTrue(r['findings'])

    def test_redefined_runtime_array_or_nonarray_source_not_guessed(self):
        p=fixture()
        for extra in ('Array.prototype.splice=()=>[];','Array.prototype["splice"]=()=>[];','const Array=function(){};'):
            code=p[0].replace('module.exports=',extra+'module.exports=');self.assertEqual(self.apply((code,p[1]))['code'],code)
        self.assertEqual(self.apply((p[0],p[1].replace('rows:[]','rows:opaque()')))['code'],p[0])
        code=p[0].replace('require("san")','require("other")');self.assertEqual(self.apply((code,p[1]))['code'],code)
        for name in ('__proto__','constructor'):
            code,vue=(s.replace('rows',name) for s in p)
            self.assertEqual(self.apply((code,vue))['code'],code)

    def test_private_names_comments_template_css_and_unrelated_methods_preserved(self):
        p=fixture();code=p[0].replace('const san=', '/*rows.splice fake*/const example="this.rows.splice";const san=')
        r=self.apply((code,p[1]));self.assertIn('/*rows.splice fake*/const example="this.rows.splice";',r['code'])
        self.assertIn('note(text){return text;}',r['code']);self.assertTrue(r['code'].startswith(p[0].split('<script>')[0]))

    def test_inspection_mode_and_analysis_failure_leave_bytes_unchanged(self):
        p=fixture();self.assertEqual(self.apply(p,repair=False)['code'],p[0])
        self.assertEqual(source_array_transaction_semantics(p[0],'',repair=True)['code'],p[0])
        _run.cache_clear()
        with patch('migration_pipeline.utils.source_array_transaction_semantics.subprocess.run',side_effect=OSError):
            r=source_array_transaction_semantics(*p,repair=True);self.assertIn('error',r);self.assertEqual(r['code'],p[0])
        _run.cache_clear()

    def test_gate_rejects_lost_commit_clone_guard_and_method(self):
        p=fixture();fixed=self.apply(p)['code'];before=self.fixture_state(p[0],p[1]);after=self.fixture_state(fixed,p[1])
        self.assertFalse(candidate_gate(before,after)['should_stop']);self.assertTrue(candidate_gate(after,before)['should_stop'])
        for a,b in [('this.data.set("rows", [...rows]);',''),('[...this.data.get(\'rows\')]',"this.data.get('rows')"),
                    ('after||down','after&&down'),('reshuffle(i,j,after=false)','other(i,j,after=false)')]:
            bad=fixed.replace(a,b);self.assertNotEqual(bad,fixed)
            self.assertTrue(candidate_gate(after,self.fixture_state(bad,p[1]))['should_stop'])
        no_script=fixed.split('<script>')[0]+'<style>.keep{color:red}</style>'
        gate=candidate_gate(after,self.fixture_state(no_script,p[1]))
        self.assertTrue(gate['should_stop']);self.assertEqual(gate['lost_source_array_contracts'],['script.methods.reshuffle@rows'])

    @classmethod
    def setUpClass(cls):
        cls.code=(BASE/'TaskManager_source_render_dependency_offline.san').read_text(encoding='utf-8')
        cls.vue=SOURCE/'protocol/frozen/data/datasets/components/03_complex/TaskManager/vue/TaskManager.vue'
        cls.state=json.loads((SOURCE/'repair_reports/complex/TaskManager_repair_history.json').read_text(encoding='utf-8'))['state']

    def test_real_frozen_task_closes_static_error_not_entire_ui_acceptance(self):
        vue=self.vue.read_text(encoding='utf-8');r=self.apply((self.code,vue))
        self.assertEqual(r['proofs'][0]['contract'],'script.methods.moveTask@tasks')
        def assess(code):return {'generated_code':code,'ssm':self.state['ssm'],'vue_file_path':str(self.vue),
            **ValidateStage().run(ValidateStageInput(generated_code=code,ssm=self.state['ssm'],vue_file_path=str(self.vue))).to_state_update()}
        before,after=assess(self.code),assess(r['code'])
        self.assertEqual({e['code'] for e in before['validation_errors']},{'nested_state_mutation','source_array_transaction_not_landed',
            'source_child_factory_not_landed','source_child_watch_not_landed','source_native_drag_not_landed','source_parent_watch_not_landed'})
        self.assertFalse(after['validation_passed'])
        self.assertEqual({e['code'] for e in after['validation_errors']},{'source_child_factory_not_landed','source_child_watch_not_landed','source_native_drag_not_landed','source_parent_watch_not_landed'})
        self.assertFalse(candidate_gate(before,after)['should_stop']);self.assertTrue(candidate_gate(after,before)['should_stop'])
        fixed,steps=RepairStage._deterministic_repair_plan(self.code,before['validation_errors'],[],self.state['ssm'],str(self.vue),enable_residual_v2=True)
        expected=source_native_drag_semantics(source_child_initialization_semantics(r['code'],vue,repair=True)['code'],vue,repair=True)['code']
        self.assertEqual(fixed,source_parent_watch_semantics(expected,vue,repair=True)['code'])
        self.assertIn(('source_array_transaction_contracts','detached_and_committed_source_array_transaction'),steps)
        self.assertIn(('source_child_startup_contracts','restored_source_child_factory_initialization_and_watch'),steps)
        self.assertTrue(assess(fixed)['validation_passed'])

    def test_real_scheduler_uses_retained_frozen_code_not_a_new_generation(self):
        owner=self
        class NoModel:
            def repair(self,_):raise AssertionError('Offline normalization must not request an LLM')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'retained.san';path.write_text(self.code,encoding='utf-8')
            class FrozenGenerate:
                def run(self,_):return GenerateStageResult(source_file=str(owner.vue),ssm=owner.state['ssm'],
                    generation_code=owner.code,saved_file_path=str(path),provider='retained_frozen_artifact',model='none',usage={},raw_response={})
            result=MigrationPipelineOrchestrator(FrozenGenerate(),ValidateStage(),VisualEvalStage(),RepairStage(NoModel())).run_generate_validate_visual_eval_and_repair_loop(
                GenerateStageInput(vue_file_path=str(self.vue),metadata={'repair_policy':'bounded_prepass_v1','semantic_rule_set':'residual_v2'}),max_repair_rounds=3)
            state=result.state
            self.assertTrue(state['final_passed']);self.assertEqual(state['llm_repair_calls'],0)
            self.assertEqual(state['deterministic_steps'],1);self.assertEqual(state['repair_history'],[])
            self.assertTrue(state['normalization_history'][0]['accepted'])
            moved=self.apply((self.code,self.vue.read_text(encoding='utf-8')))['code']
            expected=source_child_initialization_semantics(moved,self.vue.read_text(encoding='utf-8'),repair=True)['code']
            expected=source_native_drag_semantics(expected,self.vue.read_text(encoding='utf-8'),repair=True)['code']
            expected=source_parent_watch_semantics(expected,self.vue.read_text(encoding='utf-8'),repair=True)['code']
            self.assertEqual(Path(state['final_file_path']).read_text(encoding='utf-8'),expected)

    def run_oracle(self,p,name,field,view,drag,notification):
        fixed=self.apply(p)['code']
        js=r'''const fs=require('fs'),parser=require('@babel/parser'),t=require('@babel/types'),generate=require('@babel/generator').default,san=require('san');
const x=JSON.parse(fs.readFileSync(0,'utf8')),m={exports:{}};
new Function('require','module',/<script>([\s\S]*?)<\/script>/.exec(x.code)[1])(require,m);
const ast=parser.parse(/<script>([\s\S]*?)<\/script>/.exec(x.vue)[1],{sourceType:'module'});
const root=require('./migration_pipeline/utils/source_render_call_semantics.cjs').sourceParent(ast);
const methods=root.properties.find(n=>n.key.name==='methods').value.properties;
const original=methods.find(n=>n.key.name===x.name);
const fn=new Function(...original.params.map(p=>generate(p).code),generate(original.body).code.slice(1,-1));
const cases=[[0,1,false],[2,0,false],[0,2,true],[1,0,false],[null,1,false],[undefined,1,false],[20,0,false],[0,20,false],[1,1,false],[0,1,false]];
const out=[];
for(let k=0;k<cases.length;k++){
 const all=['a','b','c','d','e'].map(id=>({id})),visible=(k===9?['b','absent']:['b','d','e']).map(id=>all.find(r=>r.id===id)||{id});
 const source={[x.field]:all.slice(),[x.view]:visible,[x.drag]:1},notes=[];
 source[x.notification]=(...args)=>notes.push(args);fn.apply(source,cases[k]);
 const c=new m.exports();c.data.set(x.field,all);c.data.set(x.view,visible);c.data.set(x.drag,1);
 const events=[],set=c.data.set.bind(c.data);c.data.set=(field,value)=>{events.push({field,order:c.data.get(x.field).map(r=>r.id),next:Array.isArray(value)?value.map(r=>r.id):value});return set(field,value);};
 c[x.notification]=(...args)=>events.push({note:args,order:c.data.get(x.field).map(r=>r.id)});
 c[x.name](...cases[k]);
 const actual=c.data.get(x.field),expected=source[x.field];
 out.push({order:actual.map(r=>r.id),expected:expected.map(r=>r.id),drag:c.data.get(x.drag),expectedDrag:source[x.drag],
  old:all.map(r=>r.id),sameArray:actual===all,elementIdentity:actual.every(r=>all.includes(r)),events,notes});
}
process.stdout.write(JSON.stringify(out));'''
        return node(js,{'code':fixed,'vue':p[1],'name':name,'field':field,'view':view,'drag':drag,'notification':notification})

    def assert_oracle(self,values,field,drag):
        for i,r in enumerate(values):
            self.assertEqual(r['order'],r['expected']);self.assertEqual(r['drag'],r['expectedDrag'])
            self.assertEqual(r['old'],['a','b','c','d','e']);self.assertTrue(r['elementIdentity'])
            moves=i<4;self.assertEqual(r['sameArray'],not moves)
            if moves:
                self.assertEqual([e.get('field') for e in r['events']],[field,drag,None])
                self.assertEqual(r['events'][1]['order'],r['order']);self.assertEqual(r['events'][2]['order'],r['order'])
                self.assertEqual(r['events'][2]['note'],r['notes'][0])
            else:self.assertEqual(r['events'],[])
        self.assertEqual(values[0]['order'],['a','c','d','b','e'])
        self.assertEqual(values[1]['order'],['a','e','b','c','d'])
        self.assertEqual(values[2]['order'],['a','c','d','e','b'])

    def test_installed_san_filtered_moves_match_source_identity_and_observer_order(self):
        self.assert_oracle(self.run_oracle(fixture(),'reshuffle','rows','view','drag','note'),'rows','drag')

    def test_real_frozen_filtered_move_oracle_uses_original_source_method(self):
        # Extract the real source method, but neutralize real computed view/timers:
        # supply a minimal San harness containing only that exact target method.
        js=r'''const fs=require('fs'),parser=require('@babel/parser'),generate=require('@babel/generator').default;
const {parentOf}=require('./migration_pipeline/utils/inline_identifier_recovery.cjs');
const x=JSON.parse(fs.readFileSync(0,'utf8')),ast=parser.parse(/<script>([\s\S]*?)<\/script>/.exec(x)[1]);
const m=parentOf(ast).properties.find(p=>p.key.name==='moveTask');
process.stdout.write(JSON.stringify('<template><section/></template><script>const san=require("san");module.exports=san.defineComponent({initData(){return {tasks:[],filteredTasks:[],dragStartIndex:1};},'+generate(m).code+'});</script>'));'''
        fixed=self.apply((self.code,self.vue.read_text(encoding='utf-8')))['code']
        harness=node(js,fixed)
        values=self.run_oracle((harness,self.vue.read_text(encoding='utf-8')),'moveTask','tasks','filteredTasks','dragStartIndex','showNotification')
        self.assert_oracle(values,'tasks','dragStartIndex')

    def test_pre_and_postprocessing_no_weaker_regex_in_residual_v2_legacy_preserved(self):
        p=fixture()
        class Client:
            def __init__(self,code):self.code=code
            def repair(self,request):return RepairResult(code=self.code,saved_file_path=request.output_file_path,source_file='',ssm={},provider='stub',model='stub',raw_response={})
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'a.vue';path.write_text(p[1],encoding='utf-8')
            for code in (p[0],p[0].replace('after||down','after&&down')):
                result=RepairStage(Client(code)).run(RepairStageInput(ssm={},generated_code=code,vue_file_path=str(path),
                    validation_errors=[{'code':'nested_state_mutation'}],output_file_path=str(Path(tmp)/'out.san'),
                    metadata={'skip_deterministic_prepass':True,'semantic_rule_set':'residual_v2'}))
                self.assertEqual(result.repaired_code.rstrip(),self.apply((code,p[1]))['code'].rstrip())
            legacy,steps=RepairStage._deterministic_repair_plan(self.code,[{'code':'nested_state_mutation'}],[],self.state['ssm'],str(self.vue))
            self.assertIn(('san_state_array_clone_normalizer','cloned_state_array_before_local_mutation'),steps)
            self.assertIn("const tasks = [...this.data.get('tasks')];",legacy)

    def test_prompt_requires_full_source_method_and_early_single_commit(self):
        prompt=build_repair_prompt(RepairPromptInput(ssm={},current_code='',validation_errors=[{'code':'source_array_transaction_not_landed'}]))
        self.assertIn('Source array transaction contract',prompt);self.assertIn('commit exactly once immediately',prompt)
        self.assertIn('A shallow clone is not proof',prompt)


if __name__=='__main__':unittest.main()
