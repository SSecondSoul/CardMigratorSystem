"""Closed readonly render DAGs; public API, argument and refusal protection."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from migration_pipeline.utils.source_render_dependency_semantics import source_render_dependency_semantics, _run
from migration_pipeline.utils.source_array_transaction_semantics import source_array_transaction_semantics
from migration_pipeline.utils.source_child_initialization_semantics import source_child_initialization_semantics
from migration_pipeline.utils.source_native_drag_semantics import source_native_drag_semantics
from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
from migration_pipeline.stages.repair import RepairStage, RepairStageInput
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.utils.repair_scheduler import candidate_gate
from migration_pipeline.utils.repair_prompt import RepairPromptInput, build_repair_prompt
from migration_pipeline.repair_client import RepairResult

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data/experiments/analysis/formal_30_v4_source_render_call_closure_v1_20261110'
SOURCE=ROOT/'data/experiments/snapshots/formal_30_v4_full_regression_v2_results_20261104_214821'


def fixture():
    data="{rows:[{done:false},{done:true}],flag:false,mode:'open'}"
    source="""total(mode){if(mode==='all')return this.rows.length;return this.rows.filter(row=>this.keep(row)).length;},
keep(row){return this.flag ? row.done : !row.done;},other(){return this.total('all');}"""
    target="""total(mode){const rows=this.data.get('rows');if(mode==='all')return rows.length;return rows.filter(row=>this.keep(row)).length;},
keep(row){return this.data.get('flag') ? row.done : !row.done;},other(){return this.total('all');}"""
    vue='<template><section><strong>{{ total(mode) }}</strong></section></template><script>export default {data(){return '+data+';},methods:{'+source+'}};</script>'
    code='<template><section><strong>{{total(mode)}}</strong></section></template><script>const san=require("san");module.exports=san.defineComponent({initData(){return '+data+';},'+target+'});</script><style>.keep{color:red}</style>'
    return code,vue


class SourceRenderDependencyClosureTests(unittest.TestCase):
    def apply(self,p,repair=True):
        result=source_render_dependency_semantics(*p,repair=repair)
        self.assertNotIn('error',result,result)
        return result

    def fixture_state(self,code,vue):
        return {'generated_code':code,'vue_source':vue,'ssm':{},
            'validation_errors':self.apply((code,vue),repair=False)['findings']}

    def test_transitive_fields_and_private_graph_not_just_direct_read(self):
        p=fixture();r=self.apply(p)
        self.assertEqual(r['changes'],['explicit_source_readonly_render_dependency_graph'])
        self.assertEqual(r['proofs'][0]['fields'],['flag','rows'])
        self.assertEqual(r['proofs'][0]['methods'],['keep','total'])
        self.assertIn('__sourceDependency_total(mode,flag,rows)',r['code'])
        self.assertIn('this.__sourceDependency_keep(row,__sourceField_flag)',r['code'])
        again=self.apply((r['code'],p[1]))
        self.assertEqual(again['code'],r['code']);self.assertEqual(again['findings'],[])
        self.assertTrue(again['proofs'][0]['explicit'])

    def test_public_signatures_bodies_and_all_other_script_callers_unchanged(self):
        p=fixture();r=self.apply(p)
        # Added methods are inserted before initData; the whole previous options tail stays.
        self.assertEqual(r['code'].split('initData(){')[1],p[0].split('initData(){')[1])
        self.assertEqual(r['code'].split('</script>')[1],p[0].split('</script>')[1])
        self.assertIn("other(){return this.total('all');}",r['code'])

    def test_readonly_mode_no_source_and_pure_parameter_only_method_no_edit(self):
        p=fixture();r=self.apply(p,repair=False)
        self.assertEqual(r['code'],p[0]);self.assertTrue(r['findings'])
        self.assertEqual(source_render_dependency_semantics(p[0],'',repair=True)['code'],p[0])
        vue=p[1].replace("this.rows.filter(row=>this.keep(row)).length","4").replace('this.rows.length','2')
        self.assertEqual(self.apply((p[0],vue))['code'],p[0])

    def test_unknown_source_call_recursive_graph_and_source_mutation_refused(self):
        p=fixture()
        for old,new in [('this.keep(row)','this.missing(row)'),('this.keep(row)','this.total(row)'),
                        ('return this.flag ?','this.flag=true;return this.flag ?')]:
            vue=p[1].replace(old,new);r=self.apply((p[0],vue))
            self.assertEqual(r['code'],p[0]);self.assertTrue(r['reviews'])

    def test_target_only_mutation_extra_state_or_changed_branch_not_overwritten(self):
        p=fixture()
        for old,new in [('return this.data.get(\'flag\') ?',"this.erase();return this.data.get('flag') ?"),
                        ('!row.done','row.done'),('return rows.length','rows.push({});return rows.length')]:
            code=p[0].replace(old,new);r=self.apply((code,p[1]))
            self.assertEqual(r['code'],code);self.assertTrue(r['findings'])

    def test_traditional_callback_unknown_array_method_and_parameter_mutation_refused(self):
        p=fixture()
        for old,new in [('row=>this.keep(row)','function(row){return this.keep(row);}'),
                        ('.filter(','.sort('),('return this.flag ?','row.done=true;return this.flag ?')]:
            vue=p[1].replace(old,new);r=self.apply((p[0],vue))
            self.assertEqual(r['code'],p[0]);self.assertTrue(r['reviews'])

    def test_math_date_global_shadowing_and_runtime_replacement_refused(self):
        p=fixture()
        for prefix in ('const Date=function(){};','const Math={};','Date.now=()=>0;','Array.prototype.filter=()=>[];'):
            code=p[0].replace('module.exports=',prefix+'module.exports=')
            self.assertEqual(self.apply((code,p[1]))['code'],code)
        code=p[0].replace('require("san")','require("other")')
        self.assertEqual(self.apply((code,p[1]))['code'],code)

    def test_wrong_path_loop_or_context_is_not_guessed(self):
        p=fixture()
        for old,new in [('<section>','<section s-if="flag">'),('<strong>','<small>'),
                        ('</strong>','%</strong>')]:
            code=p[0].replace(old,new);r=self.apply((code,p[1]))
            self.assertEqual(r['code'],code)

    def test_loop_alias_cannot_shadow_explicit_dependency(self):
        p=fixture()
        vue=p[1].replace('<strong>','<strong v-for="rows in rows">')
        code=p[0].replace('<strong>','<strong s-for="rows in rows">')
        r=self.apply((code,vue));self.assertEqual(r['code'],code);self.assertTrue(r['findings'])

    def test_private_graph_missing_field_wrong_body_and_hidden_read_stay_errors(self):
        p=fixture();fixed=self.apply(p)['code']
        for old,new in [('__sourceDependency_total(mode,flag,rows)','__sourceDependency_total(mode,rows)'),
                        ('row.done:!row.done','!row.done:!row.done'),
                        ('this.__sourceDependency_keep(row,__sourceField_flag)', 'this.keep(row)')]:
            code=fixed.replace(old,new);self.assertNotEqual(code,fixed)
            self.assertTrue(self.apply((code,p[1]),repair=False)['findings'])

    def test_gate_forward_reverse_body_tamper_and_lost_binding(self):
        p=fixture();fixed=self.apply(p)['code']
        self.assertFalse(candidate_gate(self.fixture_state(p[0],p[1]),self.fixture_state(fixed,p[1]))['should_stop'])
        self.assertTrue(candidate_gate(self.fixture_state(fixed,p[1]),self.fixture_state(p[0],p[1]))['should_stop'])
        for old,new in [('__sourceDependency_total(mode,flag,rows)','__sourceDependency_total(mode,rows)'),
                        ('<strong>','<small>')]:
            self.assertTrue(candidate_gate(self.fixture_state(fixed,p[1]),self.fixture_state(fixed.replace(old,new),p[1]))['should_stop'])

    def test_preexisting_explicit_public_render_graph_is_proven_not_rewritten(self):
        p=fixture()
        before=p[0].split('total(mode){')[1].split('});</script>')[0]
        explicit="""total(mode,flag,rows){if(mode==='all')return rows.length;return rows.filter(row=>this.keep(row,flag)).length;},
keep(row,flag){return flag ? row.done : !row.done;},other(){return this.total('all',this.data.get('flag'),this.data.get('rows'));}"""
        code=p[0].replace('total(mode){'+before,explicit).replace('{{total(mode)}}','{{total(mode,flag,rows)}}')
        r=self.apply((code,p[1]))
        self.assertEqual(r['code'],code);self.assertEqual(r['findings'],[])
        self.assertTrue(r['proofs'][0]['explicit'])

    def test_installed_san_evaluator_explicit_transitive_fields_and_public_results(self):
        p=fixture();code=self.apply(p)['code']
        js=r'''const fs=require('fs'),san=require('san'),m={exports:{}};
const code=JSON.parse(fs.readFileSync(0,'utf8'));
new Function('require','module',/<script>([\s\S]*?)<\/script>/.exec(code)[1])(require,m);
m.exports.prototype.template=/<template>([\s\S]*?)<\/template>/.exec(code)[1];
const c=new m.exports(),expression=c.aNode.children[0].children[0].textExpr;
const read=()=>({view:san.evalExpr(expression,c.data,c),public:c.total(c.data.get('mode')),other:c.other()});
const first=read();c.data.set('flag',true);c.data.set('rows',[{done:true},{done:true},{done:false}]);const second=read();
c.data.set('mode','all');const third=read();process.stdout.write(JSON.stringify([first,second,third]));'''
        r=subprocess.run(['node','-e',js],input=json.dumps(code),text=True,encoding='utf-8',capture_output=True,cwd=ROOT)
        self.assertEqual(r.returncode,0,r.stderr)
        values=json.loads(r.stdout)
        self.assertEqual([str(x['view']).strip() for x in values],['1','2','3'])
        self.assertEqual([x['public'] for x in values],[1,2,3]);self.assertEqual([x['other'] for x in values],[2,3,3])

    def test_fresh_names_and_source_target_argument_whitespace(self):
        p=fixture();code=p[0].replace('const san=', 'const __sourceDependency_total=1;const san=')
        code=code.replace('{{total(mode)}}','{{  total( mode )  }}')
        r=self.apply((code,p[1]));self.assertIn('__sourceDependency_total_(mode,flag,rows)',r['code'])
        self.assertEqual(self.apply((r['code'],p[1]))['findings'],[])

    def test_analysis_failure_does_not_return_guessed_repair(self):
        p=fixture();_run.cache_clear()
        with patch('migration_pipeline.utils.source_render_dependency_semantics.subprocess.run',side_effect=OSError):
            r=source_render_dependency_semantics(*p,repair=True);self.assertIn('error',r);self.assertEqual(r['code'],p[0])
        _run.cache_clear()

    @classmethod
    def setUpClass(cls):
        cls.state=json.loads((SOURCE/'repair_reports/complex/TaskManager_repair_history.json').read_text(encoding='utf-8'))['state']
        cls.code=(BASE/'TaskManager_source_render_call_offline.san').read_text(encoding='utf-8')
        cls.vue=SOURCE/'protocol/frozen/data/datasets/components/03_complex/TaskManager/vue/TaskManager.vue'

    def test_real_frozen_graph_closes_count_not_task_mutation(self):
        p=(self.code,self.vue.read_text(encoding='utf-8'));r=self.apply(p)
        self.assertEqual(r['proofs'][0]['methods'],['getTaskCount','isOverdue'])
        self.assertEqual(r['proofs'][0]['fields'],['tasks'])
        self.assertIn('__sourceDependency_getTaskCount(filter.value,tasks)',r['code'])
        def assess(code):return {'generated_code':code,'ssm':self.state['ssm'],'vue_file_path':str(self.vue),
            **ValidateStage().run(ValidateStageInput(generated_code=code,ssm=self.state['ssm'],vue_file_path=str(self.vue))).to_state_update()}
        before,after=assess(self.code),assess(r['code'])
        self.assertEqual(len(before['validation_errors']),8)
        self.assertEqual({e['code'] for e in after['validation_errors']},{'nested_state_mutation','source_array_transaction_not_landed',
            'source_child_factory_not_landed','source_child_watch_not_landed','source_native_drag_not_landed','source_parent_watch_not_landed'})
        self.assertFalse(after['validation_passed']);self.assertFalse(candidate_gate(before,after)['should_stop'])
        self.assertTrue(candidate_gate(after,before)['should_stop'])
        fixed,steps=RepairStage._deterministic_repair_plan(self.code,before['validation_errors'],[],self.state['ssm'],str(self.vue),enable_residual_v2=True)
        moved=source_array_transaction_semantics(r['code'],p[1],repair=True)['code']
        expected=source_native_drag_semantics(source_child_initialization_semantics(moved,p[1],repair=True)['code'],p[1],repair=True)['code']
        self.assertEqual(fixed,source_parent_watch_semantics(expected,p[1],repair=True)['code'])
        self.assertIn(('source_readonly_render_graph','explicit_source_readonly_render_dependency_graph'),steps)
        self.assertIn(('source_array_transaction_contracts','detached_and_committed_source_array_transaction'),steps)
        self.assertTrue(assess(fixed)['validation_passed'])

    def test_real_date_filter_branches_match_original_public_method_under_fixed_clock(self):
        code=self.apply((self.code,self.vue.read_text(encoding='utf-8')))['code']
        js=r'''const fs=require('fs'),san=require('san'),m={exports:{}};
const code=JSON.parse(fs.readFileSync(0,'utf8')),RealDate=Date;
class FixedDate extends RealDate{constructor(...args){super(...(args.length?args:[Date.UTC(2026,10,11,12)]));}}
new Function('require','module','Date',/<script>([\s\S]*?)<\/script>/.exec(code)[1])(require,m,FixedDate);
const c=new m.exports();
const rows=[{completed:false,dueDate:'2000-01-01',priority:'high'}, {completed:false,dueDate:'2100-01-01',priority:'low'},
 {completed:true,dueDate:'2000-01-01',priority:'high'}, {completed:false,dueDate:'invalid',priority:'medium'}];
c.data.set('tasks',rows);const modes=['all','active','completed','overdue','urgent','unknown'];
const actual=modes.map(mode=>[c.getTaskCount(mode),c.__sourceDependency_getTaskCount(mode,rows)]);
process.stdout.write(JSON.stringify(actual));'''
        r=subprocess.run(['node','-e',js],input=json.dumps(code),text=True,encoding='utf-8',capture_output=True,cwd=ROOT)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(json.loads(r.stdout),[[4,4],[2,2],[1,1],[1,1],[1,1],[0,0]])

    def test_stub_postprocessor_same_graph_without_paid_request_and_legacy_unchanged(self):
        p=fixture()
        class Client:
            def repair(self,request):return RepairResult(code=p[0],saved_file_path=request.output_file_path,source_file='',
                ssm={},provider='stub',model='stub',raw_response={})
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'a.vue';path.write_text(p[1],encoding='utf-8')
            legacy,_=RepairStage._deterministic_repair_plan(p[0],[],[],{},str(path));self.assertEqual(legacy,p[0])
            result=RepairStage(Client()).run(RepairStageInput(ssm={},generated_code=p[0],vue_file_path=str(path),
                output_file_path=str(Path(tmp)/'out.san'),metadata={'skip_deterministic_prepass':True,'semantic_rule_set':'residual_v2'}))
            self.assertEqual(result.repaired_code.rstrip(),self.apply(p)['code'].rstrip())
            self.assertIn('explicit_source_readonly_render_dependency_graph',result.raw_response['pipeline_postprocessing'])

    def test_shared_prompt_transitive_graph_public_interface_and_no_clock_timer(self):
        prompt=build_repair_prompt(RepairPromptInput(ssm={},current_code='',validation_errors=[{'code':'source_render_dependency_not_landed'}]))
        self.assertIn('Closed source render dependency graph',prompt)
        self.assertIn('Preserve public method signatures',prompt)
        self.assertIn('Do not invent timers',prompt)


if __name__=='__main__':unittest.main()
