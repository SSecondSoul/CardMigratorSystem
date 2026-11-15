"""Source render operands, refusal cases and installed San expression evaluation."""
import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from migration_pipeline.utils.source_render_call_semantics import source_render_call_semantics, _run
from migration_pipeline.stages.repair import RepairStage, RepairStageInput
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.utils.repair_scheduler import candidate_gate
from migration_pipeline.utils.repair_prompt import RepairPromptInput, build_repair_prompt
from migration_pipeline.repair_client import RepairResult

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data/experiments/analysis/formal_30_v4_source_payload_closure_v1_20261110'
SOURCE=ROOT/'data/experiments/snapshots/formal_30_v4_full_regression_v2_results_20261104_214821'


def fixture():
    src='''{template:`<section><strong>{{ Math.abs(amount) }}%</strong><span v-for="item in items" :key="item" class="tag" :class="{selected: items.includes(item)}">{{item}}</span></section>`,data(){return {amount:-2,items:['a']};}}'''
    target='''{template:`<section><strong>{{ Math.abs(amount) }}%</strong><span s-for="item in items trackby item" class="tag {{ items.includes(item) ? 'selected' : '' }}">{{item}}</span></section>`,initData(){return {amount:-2,items:['a']};},keep(){return 7;}}'''
    vue=f'<template><panel/></template><script>const Panel={src};export default {{components:{{Panel}}}};</script>'
    code=f'<template><panel/></template><script>const san=require("san");const Panel=san.defineComponent({target});module.exports=san.defineComponent({{components:{{panel:Panel,Panel}},initData(){{return {{}};}}}});</script><style>.tag{{color:red}}</style>'
    ssm={'script':{'options':{'components':[{'registered_tag':'panel','inline_definition':{'source_code':src}}]}}}
    return code,vue,ssm


class SourceRenderCallClosureTests(unittest.TestCase):
    def apply(self,p,repair=True):
        r=source_render_call_semantics(*p,repair=repair)
        self.assertNotIn('error',r,r)
        return r

    def test_lifts_both_calls_with_all_operands_percent_and_class_intact(self):
        p=fixture();r=self.apply(p)
        self.assertEqual(r['changes'],['lifted_source_render_calls_with_explicit_operands'])
        self.assertEqual([x['explicit_operands'] for x in r['proofs']],[['amount'],['items','item']])
        self.assertIn('__sourceRenderCall_0(amount) }}%',r['code'])
        self.assertIn("tag {{ __sourceRenderCall_1(items,item) ? 'selected' : '' }}",r['code'])
        self.assertIn('keep(){return 7;}',r['code'])
        self.assertEqual(r['code'].split('</script>')[1],p[0].split('</script>')[1])
        again=self.apply((r['code'],p[1],p[2]))
        self.assertEqual(again['code'],r['code']);self.assertEqual(again['findings'],[])
        self.assertTrue(all(x['lifted'] for x in again['proofs']))

    def test_readonly_inspection_leaves_input_bytes(self):
        p=fixture();r=self.apply(p,repair=False)
        self.assertEqual(r['code'],p[0]);self.assertEqual(r['changes'],[])
        self.assertEqual(len(r['findings']),2)

    def test_source_object_class_and_equivalent_quote_spelling_are_not_conflicts(self):
        p=fixture();code=p[0].replace("? 'selected' : ''",'? "selected" : ""')
        # Use alternate HTML quotes so the attribute remains well formed.
        code=code.replace('class="tag {{ items.includes(item) ? "selected" : "" }}"',"class='tag {{ items.includes(item) ? \"selected\" : \"\" }}'")
        r=self.apply((code,p[1],p[2]))
        self.assertEqual(len(r['proofs']),2)

    def test_unknown_or_conflicting_class_and_operand_are_not_guessed(self):
        p=fixture()
        for old,new in [("'selected'","'different'"),('Math.abs(amount)','Math.floor(amount)'),
                        ('items.includes(item)','items.includes(other)')]:
            code=p[0].replace(old,new)
            r=self.apply((code,p[1],p[2]))
            # Independent other binding may progress, but this wrong expression stays.
            self.assertIn(new,r['code']);self.assertTrue(r['findings'])

    def test_extra_icon_subtree_does_not_weaken_local_element_path_proof(self):
        p=fixture();src=p[2]['script']['options']['components'][0]['inline_definition']['source_code']
        source=src.replace('<section>','<section><aside>icon</aside>')
        ssm=copy.deepcopy(p[2]);ssm['script']['options']['components'][0]['inline_definition']['source_code']=source
        vue=p[1].replace(src,source)
        code=p[0].replace('<section>','<section><aside><i>icon</i></aside>')
        self.assertEqual(len(self.apply((code,vue,ssm))['proofs']),2)

    def test_wrong_path_ancestor_loop_condition_or_slot_scope_refused(self):
        p=fixture()
        for old,new in [('<section>','<section s-if="flag">'),
                        ('<section>','<div>'),('<section>','<section slot-scope="ctx">')]:
            code=p[0].replace(old,new)
            self.assertEqual(self.apply((code,p[1],p[2]))['code'],code)
        code=p[0].replace('in items','in other')
        r=self.apply((code,p[1],p[2]))
        self.assertIn('items.includes(item)',r['code'])
        self.assertEqual([proof['kind'] for proof in r['proofs']],['math'])

    def test_shadowed_globals_and_runtime_replacement_refused(self):
        p=fixture()
        for prefix in ('const Math={abs:x=>x};','const Array=function(){};', 'Math.abs=x=>x;', 'Array.prototype.includes=()=>false;'):
            code=p[0].replace('const Panel=',prefix+'const Panel=')
            self.assertEqual(self.apply((code,p[1],p[2]))['code'],code)
        code=p[0].replace('require("san")','require("other")')
        self.assertEqual(self.apply((code,p[1],p[2]))['code'],code)

    def test_untyped_unknown_member_and_mutating_or_random_calls_not_lifted(self):
        p=fixture()
        for name in ('push','splice','unknown'):
            src=p[2]['script']['options']['components'][0]['inline_definition']['source_code']
            changed=src.replace('items.includes(item)',f'items.{name}(item)')
            ssm=copy.deepcopy(p[2]);ssm['script']['options']['components'][0]['inline_definition']['source_code']=changed
            code=p[0].replace('items.includes(item)',f'items.{name}(item)')
            r=self.apply((code,p[1].replace(src,changed),ssm))
            self.assertIn(f'items.{name}(item)',r['code'])
        src=p[2]['script']['options']['components'][0]['inline_definition']['source_code']
        changed=src.replace('Math.abs(amount)','Math.random()')
        ssm=copy.deepcopy(p[2]);ssm['script']['options']['components'][0]['inline_definition']['source_code']=changed
        code=p[0].replace('Math.abs(amount)','Math.random()')
        self.assertIn('Math.random()',self.apply((code,p[1].replace(src,changed),ssm))['code'])

    def test_unknown_array_factory_and_unaccounted_spread_do_not_prove_native_membership(self):
        p=fixture();src=p[2]['script']['options']['components'][0]['inline_definition']['source_code']
        for initial in ('opaque()',"{items:['a'],...opaque()}.items"):
            changed=src.replace("items:['a']",'items:'+initial)
            ssm=copy.deepcopy(p[2]);ssm['script']['options']['components'][0]['inline_definition']['source_code']=changed
            r=self.apply((p[0],p[1].replace(src,changed),ssm))
            self.assertIn('items.includes(item)',r['code'])

    def test_ctor_escape_conflicting_alias_and_ssm_drift_refused(self):
        p=fixture()
        for old,new in [('module.exports=','consume(Panel);module.exports='),('panel:Panel,Panel','panel:Panel,other:Panel')]:
            code=p[0].replace(old,new);self.assertEqual(self.apply((code,p[1],p[2]))['code'],code)
        ssm=copy.deepcopy(p[2]);ssm['script']['options']['components'][0]['inline_definition']['source_code']='{}'
        self.assertEqual(self.apply((p[0],p[1],ssm))['code'],p[0])

    def test_comments_script_examples_and_existing_generated_name_not_replaced(self):
        p=fixture();example='const __sourceRenderCall_0=4;const example="Math.abs(amount)";/*items.includes(item)*/'
        code=p[0].replace('const Panel=',example+'const Panel=')
        r=self.apply((code,p[1],p[2]))
        self.assertIn(example,r['code']);self.assertNotIn('__sourceRenderCall_0(amount)',r['code'])

    def test_fixed_helper_wrong_body_or_hidden_missing_operand_remains_error(self):
        p=fixture();fixed=self.apply(p)['code']
        for old,new in [('Math.abs(_operand0)','Math.floor(_operand0)'),
                        ('__sourceRenderCall_0(amount)','__sourceRenderCall_0()'),
                        ('_operand0.includes(_operand1)','this.data.get("items").includes(_operand1)')]:
            code=fixed.replace(old,new);r=self.apply((code,p[1],p[2]),repair=False)
            self.assertTrue(r['findings'],code)

    def test_percent_suffix_and_static_class_cannot_disappear_after_lifting(self):
        p=fixture();fixed=self.apply(p)['code']
        for old,new in [(' }}%</strong>',' }}</strong>'),('class="tag {{','class="wrong {{')]:
            code=fixed.replace(old,new);self.assertNotEqual(code,fixed)
            r=self.apply((code,p[1],p[2]),repair=False)
            self.assertTrue(r['findings'])

    def test_native_includes_second_argument_order_is_explicit(self):
        p=fixture();src=p[2]['script']['options']['components'][0]['inline_definition']['source_code']
        changed=src.replace('items.includes(item)','items.includes(item, 1)')
        ssm=copy.deepcopy(p[2]);ssm['script']['options']['components'][0]['inline_definition']['source_code']=changed
        code=p[0].replace('items.includes(item)','items.includes(item, 1)')
        r=self.apply((code,p[1].replace(src,changed),ssm))
        self.assertEqual(r['proofs'][1]['explicit_operands'],['items','item','1'])
        self.assertEqual(self.apply((r['code'],p[1].replace(src,changed),ssm))['findings'],[])

    def test_gate_partial_progress_reverse_and_deleted_binding(self):
        p=fixture();fixed=self.apply(p)['code']
        def state(code):return {'generated_code':code,'ssm':p[2],'vue_source':p[1],
            'validation_errors':self.apply((code,p[1],p[2]),repair=False)['findings']}
        self.assertFalse(candidate_gate(state(p[0]),state(fixed))['should_stop'])
        self.assertTrue(candidate_gate(state(fixed),state(p[0]))['should_stop'])
        for old,new in [('{{ __sourceRenderCall_0(amount) }}',''),
                        ('Math.abs(_operand0)','Math.floor(_operand0)'),('in items','in other')]:
            self.assertTrue(candidate_gate(state(fixed),state(fixed.replace(old,new)))['should_stop'])

    def test_installed_san_expression_values_follow_explicit_operands(self):
        p=fixture();code=self.apply(p)['code']
        js=r'''const fs=require('fs'),san=require('san'),evaluate=san.evalExpr;
const code=JSON.parse(fs.readFileSync(0,'utf8')),m={exports:{}};
new Function('require','module',/<script>([\s\S]*?)<\/script>/.exec(code)[1])(require,m);
const p=new m.exports(),c=new p.components.panel();
const strong=c.aNode.children[0],span=c.aNode.children[1],text=strong.children[0].textExpr;
const klass=span.props.find(p=>p.name==='class').expr;
const read=()=>{const scope=new san.Data({item:'a'},c.data);return {text:evaluate(text,c.data,c),klass:evaluate(klass,scope,c)};};
const before=read();c.data.set('amount',-17);c.data.set('items',[]);const after=read();
process.stdout.write(JSON.stringify({before,after}));'''
        r=subprocess.run(['node','-e',js],input=json.dumps(code),text=True,encoding='utf-8',capture_output=True,cwd=ROOT)
        self.assertEqual(r.returncode,0,r.stderr)
        values=json.loads(r.stdout)
        self.assertIn('2%',values['before']['text']);self.assertIn('17%',values['after']['text'])
        self.assertIn('selected',values['before']['klass']);self.assertNotIn('selected',values['after']['klass'])

    def test_helper_preserves_native_nan_signed_zero_and_membership_edges(self):
        p=fixture();r=self.apply(p);math=r['proofs'][0]['helper'];member=r['proofs'][1]['helper']
        js=r'''const fs=require('fs'),san=require('san'),m={exports:{}};
const {code,math,member}=JSON.parse(fs.readFileSync(0,'utf8'));
new Function('require','module',/<script>([\s\S]*?)<\/script>/.exec(code)[1])(require,m);
const p=new m.exports(),c=new p.components.panel();let throws=false;try{c[member](null,'x');}catch(e){throws=e instanceof TypeError;}
process.stdout.write(JSON.stringify({nan:Number.isNaN(c[math](NaN)),zero:Object.is(c[math](-0),0),hasNaN:c[member]([NaN],NaN),empty:c[member]([],0),throws}));'''
        proc=subprocess.run(['node','-e',js],input=json.dumps({'code':r['code'],'math':math,'member':member}),
            text=True,encoding='utf-8',capture_output=True,cwd=ROOT)
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertEqual(json.loads(proc.stdout),{'nan':True,'zero':True,'hasNaN':True,'empty':False,'throws':True})

    def test_analysis_failures_no_source_and_bad_metadata_never_edit(self):
        p=fixture();_run.cache_clear()
        with patch('migration_pipeline.utils.source_render_call_semantics.subprocess.run',side_effect=OSError):
            r=source_render_call_semantics(*p,repair=True);self.assertIn('error',r);self.assertEqual(r['code'],p[0])
        _run.cache_clear()
        self.assertEqual(source_render_call_semantics(p[0],'',p[2],repair=True)['code'],p[0])
        self.assertEqual(source_render_call_semantics(p[0],p[1],{'script':None},repair=True)['code'],p[0])

    @classmethod
    def setUpClass(cls):
        cls.state=json.loads((SOURCE/'repair_reports/complex/TaskManager_repair_history.json').read_text(encoding='utf-8'))['state']
        cls.code=(BASE/'TaskManager_source_payload_offline.san').read_text(encoding='utf-8')
        cls.vue=SOURCE/'protocol/frozen/data/datasets/components/03_complex/TaskManager/vue/TaskManager.vue'

    def test_frozen_artifact_two_render_calls_close_not_dependency_or_mutation(self):
        p=(self.code,self.vue.read_text(encoding='utf-8'),self.state['ssm']);r=self.apply(p)
        self.assertEqual([x['kind'] for x in r['proofs']],['math','includes'])
        self.assertEqual(self.apply((r['code'],p[1],p[2]))['findings'],[])
        def assess(code):return {'generated_code':code,'ssm':p[2],'vue_file_path':str(self.vue),
            **ValidateStage().run(ValidateStageInput(generated_code=code,ssm=p[2],vue_file_path=str(self.vue))).to_state_update()}
        before,after=assess(self.code),assess(r['code'])
        self.assertEqual(len(before['validation_errors']),16)
        self.assertEqual({e['code'] for e in after['validation_errors']},{'hidden_template_reactive_dependency','nested_state_mutation',
            'source_render_dependency_not_landed','source_array_transaction_not_landed',
            'source_child_factory_not_landed','source_child_watch_not_landed','source_native_drag_not_landed','source_parent_watch_not_landed','source_parent_watch_exception_policy_unproven','source_parent_watch_dynamic_key_unproven',
            'invalid_object_class_binding','source_class_binding_not_landed'})
        self.assertFalse(after['validation_passed'])
        self.assertFalse(candidate_gate(before,after)['should_stop'])
        self.assertTrue(candidate_gate(after,before)['should_stop'])
        self.assertIn('{{getTaskCount(filter.value)}}',r['code'])
        self.assertEqual(r['code'].split('  getTaskCount(')[1],self.code.split('  getTaskCount(')[1])

    def test_prepass_and_stub_postprocessing_share_rule_legacy_unchanged(self):
        p=fixture()
        class Client:
            def repair(self,request):return RepairResult(code=p[0],saved_file_path=request.output_file_path,
                source_file='',ssm=p[2],provider='stub',model='stub',raw_response={})
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'a.vue';path.write_text(p[1],encoding='utf-8')
            code,steps=RepairStage._deterministic_repair_plan(p[0],[],[],p[2],str(path),enable_residual_v2=True)
            self.assertEqual(code,self.apply(p)['code'])
            self.assertIn(('source_render_operand_contracts','lifted_source_render_calls_with_explicit_operands'),steps)
            legacy,_=RepairStage._deterministic_repair_plan(p[0],[],[],p[2],str(path));self.assertEqual(legacy,p[0])
            result=RepairStage(Client()).run(RepairStageInput(ssm=p[2],generated_code=p[0],vue_file_path=str(path),
                output_file_path=str(Path(tmp)/'out.san'),metadata={'skip_deterministic_prepass':True,'semantic_rule_set':'residual_v2'}))
            self.assertEqual(result.repaired_code.rstrip(),code.rstrip())
            self.assertIn('lifted_source_render_calls_with_explicit_operands',result.raw_response['pipeline_postprocessing'])

    def test_shared_prompt_keeps_operands_suffix_and_native_behavior(self):
        for issue in ('source_render_call_not_landed','unsupported_san_inline_template_member_call'):
            p=build_repair_prompt(RepairPromptInput(ssm={},current_code='',validation_errors=[{'code':issue}]))
            self.assertIn('Source render operand contract',p);self.assertIn('percent suffix',p)
            self.assertIn('Do not insert empty-array/zero fallbacks',p)


if __name__=='__main__':unittest.main()
