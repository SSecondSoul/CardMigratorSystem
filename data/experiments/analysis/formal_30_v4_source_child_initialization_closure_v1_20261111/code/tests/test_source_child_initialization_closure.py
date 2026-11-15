"""Source factory/first-prop/watch parity, including native San runtime."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from migration_pipeline.utils.source_child_initialization_semantics import source_child_initialization_semantics, _run
from migration_pipeline.stages.repair import RepairStage, RepairStageInput
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.stages.visual_eval import VisualEvalStage
from migration_pipeline.stages.generate import GenerateStageInput, GenerateStageResult
from migration_pipeline.orchestrator import MigrationPipelineOrchestrator
from migration_pipeline.utils.repair_scheduler import candidate_gate
from migration_pipeline.utils.repair_prompt import RepairPromptInput, build_repair_prompt
from migration_pipeline.repair_client import RepairResult

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data/experiments/analysis/formal_30_v4_source_array_transaction_closure_v1_20261111'
SOURCE=ROOT/'data/experiments/snapshots/formal_30_v4_full_regression_v2_results_20261104_214821'


def fixture():
    source="""const Editor={props:['record'],template:`<section>{{draft.title}}</section>`,
data(){return {draft:this.buildDraft(this.record)};},
watch:{record:{handler(value){this.draft=this.buildDraft(value);}}},
methods:{buildDraft(record){return record?{...record,tags:[...(record.tags||[])]}:{title:'',tags:[]};}}};
export default {components:{Editor}};"""
    target="""const san=require('san');const Editor=san.defineComponent({
template:`<section>{{draft.title}}</section>`,dataTypes:{record:san.DataTypes.object},
initData(){return {record:null,draft:{}};},
computed:{buildDraft(){return (record)=>{if(record){return {...record,tags:[...(record.tags||[])]};}else{return {title:'',tags:[]};}};}},
inited(){const record=this.data.get('record');this.data.set('draft',this.computed.buildDraft(record));},
watch(){this.watch('record',(next)=>{this.data.set('draft',this.computed.buildDraft(next));});},
keep(){return 1;}
});module.exports=san.defineComponent({components:{editor:Editor,Editor},initData(){return {};}});"""
    return '<template><main/></template><script>'+target+'</script><style>.keep{color:red}</style>', '<template><main/></template><script>'+source+'</script>'


def node(script,payload):
    p=subprocess.run(['node','-e',script],input=json.dumps(payload),text=True,encoding='utf-8',capture_output=True,cwd=ROOT,timeout=20)
    if p.returncode:raise AssertionError(p.stderr)
    return json.loads(p.stdout),p.stderr


class SourceChildInitializationClosureTests(unittest.TestCase):
    def apply(self,p,repair=True):
        r=source_child_initialization_semantics(*p,repair=repair);self.assertNotIn('error',r,r);return r

    def fixture_state(self,code,vue):
        return {'generated_code':code,'vue_source':vue,'ssm':{},'validation_errors':self.apply((code,vue),repair=False)['findings']}

    def test_source_method_first_initialization_watch_and_fixedpoint(self):
        p=fixture();r=self.apply(p)
        self.assertEqual(r['changes'],['restored_source_child_factory_initialization_and_watch'])
        self.assertEqual({e['code'] for e in r['findings']},{'source_child_factory_not_landed','source_child_watch_not_landed'})
        self.assertNotIn('this.computed.buildDraft',r['code']);self.assertNotIn('watch(){',r['code'])
        self.assertIn('buildDraft(record){return record?',r['code'])
        self.assertIn('change.expr.paths.length===1',r['code'])
        self.assertIn('keep(){return 1;}',r['code']);self.assertEqual(r['code'].split('</script>')[1],p[0].split('</script>')[1])
        again=self.apply((r['code'],p[1]));self.assertEqual(again['code'],r['code']);self.assertEqual(again['findings'],[])
        self.assertTrue(again['proofs'][0]['factory_landed']);self.assertTrue(again['proofs'][0]['watch_landed'])
        self.assertTrue(again['proofs'][0]['shallow_root_change_guard'])

    def test_unknown_factory_body_or_conflicting_direct_method_refused(self):
        p=fixture()
        for a,b in [("title:'',tags:[]","title:'wrong',tags:[]"),('if(record){return','this.erase();if(record){return'),
                    ('keep(){return 1;}','buildDraft(record){return record;},keep(){return 1;}')]:
            code=p[0].replace(a,b);r=self.apply((code,p[1]));self.assertEqual(r['code'],code);self.assertTrue(r['findings'])

    def test_unknown_lifecycle_work_not_moved_or_deleted(self):
        p=fixture()
        for extra in ('this.load();','this.data.set("other",1);','if(this.ready)return;'):
            code=p[0].replace('inited(){','inited(){'+extra);r=self.apply((code,p[1]))
            self.assertEqual(r['code'],code);self.assertTrue(r['reviews'])

    def test_unknown_watch_effect_options_wrong_prop_or_callback_refused(self):
        p=fixture()
        for a,b in [('(next)=>{','(next)=>{this.notify();'),("this.watch('record'","this.watch('other'"),
                    ("buildDraft(next));});","buildDraft(next));},{deep:true});"),
                    ('(next)=>{','function(next){')]:
            code=p[0].replace(a,b);self.assertNotEqual(code,p[0]);r=self.apply((code,p[1]))
            self.assertEqual(r['code'],code);self.assertTrue(r['findings'])

    def test_source_nonpure_factory_alias_return_or_deep_watcher_not_guessed(self):
        p=fixture()
        for a,b in [('return record?','this.load();return record?'),('return record?','return external(record)||record?'),
                    ('record?{...record,tags:[...(record.tags||[])]}', 'record?record'),
                    ('handler(value){this.draft=this.buildDraft(value);}', 'handler(value){this.draft=this.buildDraft(value);},deep:true')]:
            vue=p[1].replace(a,b);self.assertNotEqual(vue,p[1]);self.assertEqual(self.apply((p[0],vue))['code'],p[0])

    def test_registration_alias_escape_duplicate_or_source_mixins_refused(self):
        p=fixture()
        for a,b in [('module.exports=', 'consume(Editor);module.exports='),('editor:Editor,Editor','editor:Editor,other:Editor')]:
            code=p[0].replace(a,b);self.assertEqual(self.apply((code,p[1]))['code'],code)
        self.assertEqual(self.apply((p[0],p[1].replace("props:['record']","mixins:[opaque],props:['record']")))['code'],p[0])

    def test_other_script_or_template_factory_use_not_globally_rewritten(self):
        p=fixture()
        for a,b in [('keep(){return 1;}','keep(){return this.computed.buildDraft(this.data.get("record"));}'),
                    ('keep(){return 1;}','keep(name){return this[name];}'),
                    ('keep(){return 1;}','keep(name){return this.computed[name];}'),
                    ('keep(){return 1;}','keep(name){return this.data.get(name);}'),
                    ('{{draft.title}}','{{buildDraft(record)}}'),('{{draft.title}}','{{this[chosen](record)}}')]:
            code=p[0].replace(a,b);self.assertEqual(self.apply((code,p[1]))['code'],code)

    def test_dollar_named_factory_detects_external_template_call(self):
        code,vue=(s.replace('buildDraft','build$Draft') for s in fixture())
        self.assertTrue(self.apply((code,vue))['changes'])
        wrong=code.replace('{{draft.title}}','{{build$Draft(record)}}')
        self.assertEqual(self.apply((wrong,vue))['code'],wrong)

    def test_wrong_runtime_or_rewritten_san_constructor_refused(self):
        p=fixture()
        for a,b in [("require('san')","require('other')"),('const Editor=', 'san.defineComponent=opaque;const Editor='),
                    ("const san=", "const require=opaque;const san=")]:
            code=p[0].replace(a,b);self.assertEqual(self.apply((code,p[1]))['code'],code)

    def test_missing_initialization_and_registration_restored_from_complete_source(self):
        p=fixture();start=p[0].index('inited(){');end=p[0].index('keep(){')
        code=p[0][:start]+p[0][end:];r=self.apply((code,p[1]));self.assertTrue(r['changes'])
        self.assertEqual(self.apply((r['code'],p[1]))['findings'],[])

    def test_duplicate_watch_registration_is_not_silently_deduplicated(self):
        p=fixture();code=p[0].replace("this.computed.buildDraft(record));}","this.computed.buildDraft(record));this.watch('record',(next)=>{this.data.set('draft',this.computed.buildDraft(next));});}")
        self.assertNotEqual(code,p[0]);self.assertEqual(self.apply((code,p[1]))['code'],code)

    def test_unchecked_shallow_and_wrong_guard_remain_diagnostics(self):
        p=fixture();fixed=self.apply(p)['code']
        bad=fixed.replace('change.expr.paths.length===1','change.expr.paths.length>=1');self.assertNotEqual(bad,fixed)
        self.assertTrue(self.apply((bad,p[1]),repair=False)['findings'])
        self.assertEqual(self.apply((bad,p[1]))['code'],bad)

    def test_gate_forward_reverse_and_factory_watch_contract_loss(self):
        p=fixture();fixed=self.apply(p)['code'];before=self.fixture_state(*p);after=self.fixture_state(fixed,p[1])
        self.assertFalse(candidate_gate(before,after)['should_stop']);self.assertTrue(candidate_gate(after,before)['should_stop'])
        for a,b in [('change.expr.paths.length===1','change.expr.paths.length>=1'),('buildDraft(record){return record?', 'buildDraft(record){return false?')]:
            code=fixed.replace(a,b);self.assertNotEqual(code,fixed)
            self.assertTrue(candidate_gate(after,self.fixture_state(code,p[1]))['should_stop'])
        missing=fixed.split('<script>')[0]
        gate=candidate_gate(after,self.fixture_state(missing,p[1]));self.assertTrue(gate['should_stop'])
        self.assertEqual(gate['lost_source_child_startup_contracts'],['script.editor.draft@record'])

    def test_analysis_failure_no_source_and_readonly_inspection_leave_input_unchanged(self):
        p=fixture();self.assertEqual(self.apply(p,repair=False)['code'],p[0])
        self.assertEqual(source_child_initialization_semantics(p[0],'',repair=True)['code'],p[0])
        _run.cache_clear()
        with patch('migration_pipeline.utils.source_child_initialization_semantics.subprocess.run',side_effect=OSError):
            r=source_child_initialization_semantics(*p,repair=True);self.assertEqual(r['code'],p[0]);self.assertIn('error',r)
        _run.cache_clear()

    def runtime(self,p,tag,factory_name,prop,field):
        code=self.apply(p)['code']
        js=r'''const fs=require('fs'),san=require('san'),m={exports:{}};const x=JSON.parse(fs.readFileSync(0,'utf8'));
new Function('require','module',/<script\b[^>]*>([\s\S]*?)<\/script>/.exec(x.code)[1])(require,m);
const F=m.exports.prototype.components[x.tag],base=F.prototype[x.factory],calls=[];
F.prototype[x.factory]=function(value){calls.push(value);return base.call(this,value);};
const nativeWatch=san.Component.prototype.watch,registrations=[];
san.Component.prototype.watch=function(name,fn){registrations.push({name,initialType:typeof this.data.get(x.field),initialTitle:this.data.get(x.field).title});return nativeWatch.call(this,name,fn);};
const original={title:'first',description:'desc',tags:['a'],meta:{ok:true}};
const a=new F({data:{[x.prop]:original}}),b=new F({data:{[x.prop]:original}});
const first=a.data.get(x.field),other=b.data.get(x.field),separate=first!==other&&first.tags!==other.tags&&first.tags!==original.tags;
const initial={title:first.title,description:first.description,tags:first.tags.slice(),calls:calls.length};
a.data.set(x.field+'.title','draft edit');a.data.set(x.field+'.tags',['b']);
const propUnchanged=original.title==='first'&&original.tags.join(',')==='a';
a.data.set(x.prop+'.title','nested incoming');
const nested={title:a.data.get(x.field).title,calls:calls.length};
const next={title:'replacement',tags:['z']};a.data.set(x.prop,next);
const replacement={title:a.data.get(x.field).title,tags:a.data.get(x.field).tags.slice(),calls:calls.length,detached:a.data.get(x.field).tags!==next.tags};
a.data.set(x.prop,null);const empty={...a.data.get(x.field),calls:calls.length};
const builtIn=a.watch===san.Component.prototype.watch;
san.Component.prototype.watch=nativeWatch;
process.stdout.write(JSON.stringify({initial,separate,propUnchanged,nested,replacement,empty,registrations,builtIn}));'''
        return node(js,{'code':code,'tag':tag,'factory':factory_name,'prop':prop,'field':field})

    def assert_runtime(self,r,warnings,prop):
        self.assertEqual(r['initial']['title'],'first');self.assertEqual(r['initial']['tags'],['a']);self.assertEqual(r['initial']['calls'],2)
        self.assertTrue(r['separate']);self.assertTrue(r['propUnchanged']);self.assertTrue(r['builtIn'])
        self.assertEqual(r['nested'],{'title':'draft edit','calls':2})
        self.assertEqual(r['replacement'],{'title':'replacement','tags':['z'],'calls':3,'detached':True})
        self.assertEqual(r['empty']['title'],'');self.assertEqual(r['empty']['tags'],[]);self.assertEqual(r['empty']['calls'],4)
        self.assertEqual(r['registrations'],[{'name':prop,'initialType':'object','initialTitle':'first'}]*2)
        self.assertNotIn('reserved key',warnings)

    def test_installed_san_first_props_root_replace_nested_edit_and_instance_isolation(self):
        r,w=self.runtime(fixture(),'editor','buildDraft','record','draft');self.assert_runtime(r,w,'record')

    @classmethod
    def setUpClass(cls):
        cls.code=(BASE/'TaskManager_source_array_transaction_offline.san').read_text(encoding='utf-8')
        cls.vue=SOURCE/'protocol/frozen/data/datasets/components/03_complex/TaskManager/vue/TaskManager.vue'
        cls.state=json.loads((SOURCE/'repair_reports/complex/TaskManager_repair_history.json').read_text(encoding='utf-8'))['state']

    def test_real_frozen_task_form_runtime_without_parent_attach_or_timers(self):
        r,w=self.runtime((self.code,self.vue.read_text(encoding='utf-8')),'task-form','createFormData','task','formData')
        self.assert_runtime(r,w,'task')
        self.assertEqual(r['empty']['priority'],'medium');self.assertEqual(r['empty']['assignee'],'')

    def test_real_frozen_source_validator_gate_and_prepass(self):
        vue=self.vue.read_text(encoding='utf-8');r=self.apply((self.code,vue))
        def assess(code):return {'generated_code':code,'ssm':self.state['ssm'],'vue_file_path':str(self.vue),
            **ValidateStage().run(ValidateStageInput(generated_code=code,ssm=self.state['ssm'],vue_file_path=str(self.vue))).to_state_update()}
        before,after=assess(self.code),assess(r['code'])
        self.assertEqual({e['code'] for e in before['validation_errors']},{'source_child_factory_not_landed','source_child_watch_not_landed'})
        self.assertTrue(after['validation_passed'],after['validation_errors'])
        self.assertFalse(candidate_gate(before,after)['should_stop']);self.assertTrue(candidate_gate(after,before)['should_stop'])
        fixed,steps=RepairStage._deterministic_repair_plan(self.code,before['validation_errors'],[],self.state['ssm'],str(self.vue),enable_residual_v2=True)
        self.assertEqual(fixed,r['code']);self.assertIn(('source_child_startup_contracts','restored_source_child_factory_initialization_and_watch'),steps)

    def test_actual_offline_scheduler_closes_startup_with_zero_model_calls(self):
        owner=self
        class NoModel:
            def repair(self,_):raise AssertionError('No LLM allowed')
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'retained.san';path.write_text(self.code,encoding='utf-8')
            class Frozen:
                def run(self,_):return GenerateStageResult(source_file=str(owner.vue),ssm=owner.state['ssm'],generation_code=owner.code,
                    saved_file_path=str(path),provider='retained',model='none',usage={},raw_response={})
            result=MigrationPipelineOrchestrator(Frozen(),ValidateStage(),VisualEvalStage(),RepairStage(NoModel())).run_generate_validate_visual_eval_and_repair_loop(
                GenerateStageInput(vue_file_path=str(self.vue),metadata={'repair_policy':'bounded_prepass_v1','semantic_rule_set':'residual_v2'}),max_repair_rounds=3).state
            self.assertTrue(result['final_passed']);self.assertEqual(result['llm_repair_calls'],0);self.assertEqual(result['deterministic_steps'],1)
            self.assertEqual(result['repair_history'],[]);self.assertTrue(result['normalization_history'][0]['accepted'])

    def test_stub_postprocessing_same_closure_and_legacy_unchanged(self):
        p=fixture()
        class Client:
            def repair(self,request):return RepairResult(code=p[0],saved_file_path=request.output_file_path,source_file='',ssm={},provider='stub',model='stub',raw_response={})
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'sample.vue';path.write_text(p[1],encoding='utf-8')
            legacy,_=RepairStage._deterministic_repair_plan(p[0],[],[],{},str(path));self.assertEqual(legacy,p[0])
            out=RepairStage(Client()).run(RepairStageInput(ssm={},generated_code=p[0],vue_file_path=str(path),output_file_path=str(Path(tmp)/'out.san'),
                metadata={'skip_deterministic_prepass':True,'semantic_rule_set':'residual_v2'}))
            self.assertEqual(out.repaired_code.rstrip(),self.apply(p)['code'].rstrip())
            self.assertIn('restored_source_child_factory_initialization_and_watch',out.raw_response['pipeline_postprocessing'])

    def test_prompt_factory_not_computed_reserved_watch_and_no_deep_guess(self):
        prompt=build_repair_prompt(RepairPromptInput(ssm={},current_code='',validation_errors=[{'code':'source_child_factory_not_landed'}]))
        self.assertIn('Registered source child startup contract',prompt);self.assertIn('San built-in watch',prompt)
        self.assertIn('nested San change paths',prompt)


if __name__=='__main__':unittest.main()
