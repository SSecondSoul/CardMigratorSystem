"""Source-bound render-field and conditional class repairs; no model requests."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from migration_pipeline.utils.source_template_semantics import source_template_semantics
from migration_pipeline.utils.repair_scheduler import candidate_gate
from migration_pipeline.utils.repair_prompt import RepairPromptInput, build_repair_prompt
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.stages.repair import RepairStage, RepairStageInput
from migration_pipeline.repair_client import RepairResult

ROOT=Path(__file__).resolve().parents[1]
VUE="""<template><section :class="'meter '+status"><strong>{{count}}</strong><button :disabled="count===0" @click="act">Run</button></section></template>
<script>export default {props:{count:{type:Number,default:0}},computed:{status(){return this.count?'on':'off';}},methods:{act(){}}};</script>"""
SAN="""<template><section class="{{ 'meter '+(this.data.get('status')||'') }}"><strong>{{this.data.get('count')}}</strong><button disabled="{{this.data.get('count')===0}}" on-click="act">Run</button></section></template>
<script>const san=require('san');const DataTypes=san.DataTypes;module.exports=san.defineComponent({dataTypes:{count:DataTypes.number},initData(){return {count:0};},computed:{status(){return this.data.get('count')?'on':'off';}},act(){return this.data.get('count');}});</script><style>.meter{color:red}</style>"""
CLASS_VUE="""<template><div><article v-for="(row,index) in rows" :key="row.id" class="entry" :class="{active:row.active}">{{row.name}}</article></div></template><script>export default {props:{rows:{type:Array,default:()=>[{id:1,name:'A',active:true}]}}};</script>"""
CLASS_SAN="""<template><div><article s-for="row, index in rows trackby row.id" class="entry" class="{{row.active?'active':''}">{{row.name}}</article></div></template><script>const san=require('san');const DataTypes=san.DataTypes;module.exports=san.defineComponent({dataTypes:{rows:DataTypes.array},initData(){return {rows:[{id:1,name:'A',active:true}]};}});</script><style>.entry{color:red}</style>"""
CODE='invalid_san_template_data_store_access'


class SourceTemplateClosureTests(unittest.TestCase):
    def apply(self,code=SAN,vue=VUE):
        return source_template_semantics(code,vue,repair=True)

    def test_render_api_calls_are_found_and_source_equivalent_fields_restored(self):
        result=self.apply()
        self.assertEqual(len(result['findings']),3)
        self.assertEqual(result['changes'],['restored_source_render_field_bindings'])
        template=result['code'].split('</template>')[0]
        self.assertNotIn('this.data',template)
        self.assertIn('disabled="{{count===0}}"',template)
        self.assertIn("'meter '+status",template)
        self.assertEqual(source_template_semantics(result['code'])['findings'],[])

    def test_script_css_event_and_other_attributes_keep_exact_bytes(self):
        result=self.apply()['code']
        for tag in ('script','style'):
            self.assertEqual(result.split('<'+tag+'>')[1],SAN.split('<'+tag+'>')[1])
        self.assertIn('on-click="act"',result)
        self.assertIn("act(){return this.data.get('count');}",result)

    def test_single_missing_class_closer_is_restored_only_with_source_map_proof(self):
        result=self.apply(CLASS_SAN,CLASS_VUE)
        self.assertIn('merged_source_class_bindings',result['changes'])
        self.assertIn('restored_source_class_interpolation_delimiter',result['changes'])
        self.assertIn('class="entry {{row.active?',result['code'])
        self.assertEqual(result['code'].split('</template>')[0].count('class='),1)

    def test_balanced_duplicate_classes_are_merged_with_the_same_proof(self):
        balanced=CLASS_SAN.replace("?'active':''}","?'active':''}}")
        result=self.apply(balanced,CLASS_VUE)
        self.assertEqual(result['changes'],['merged_source_class_bindings'])

    def test_installed_san_class_binding_evaluates_updated_data(self):
        fixed=self.apply(CLASS_SAN,CLASS_VUE)['code']
        # Installed San parser/evaluator and data updates; not a browser DOM
        # repaint test. No uninstalled DOM library or simulated browser claim.
        js="""const fs=require('fs'),san=require('san'),Data=require('san/src/runtime/data'),evalExpr=require('san/src/runtime/eval-expr');
const code=fs.readFileSync(0,'utf8'),template=/<template>([\\s\\S]*?)<\\/template>/.exec(code)[1];
const article=san.parseTemplate(template).children[0].children.find(n=>n.tagName==='article');
const binding=article.props.find(p=>p.name==='class'),data=new Data({row:{active:true}});
const before=evalExpr(binding.expr,data);data.set('row.active',false);
process.stdout.write(JSON.stringify([before,evalExpr(binding.expr,data)]));"""
        p=subprocess.run(['node','-e',js],cwd=ROOT,input=fixed,text=True,encoding='utf-8',capture_output=True)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual([s.strip() for s in json.loads(p.stdout)],['entry active','entry'])

    def test_unmatched_class_token_condition_static_anchor_or_loop_is_not_guessed(self):
        for code in (CLASS_SAN.replace("?'active'", "?'other'"),CLASS_SAN.replace('row.active?', '!row.active?'),
                     CLASS_SAN.replace('class="entry"','class="different"'),
                     CLASS_SAN.replace('row, index in rows','other, index in rows'),
                     CLASS_SAN.replace('row, index in rows','row, index in otherRows')):
            self.assertEqual(self.apply(code,CLASS_VUE)['code'],code)

    def test_ambiguous_three_classes_or_more_missing_braces_are_not_repaired(self):
        for code in (CLASS_SAN.replace('class="entry"','class="entry" class="extra"'),
                     CLASS_SAN.replace("?'active':''}","?'active':''")):
            self.assertEqual(self.apply(code,CLASS_VUE)['code'],code)

    def test_unrelated_template_shape_or_source_parse_errors_forbid_repair(self):
        for vue in (VUE.replace('<strong>','<em>').replace('</strong>','</em>'),
                    VUE.replace('<strong>','<aside></aside><strong>'), VUE.replace('</section>','</div>')):
            self.assertEqual(self.apply(vue=vue)['code'],SAN)

    def test_no_source_or_opaque_parent_does_not_get_a_guessed_binding(self):
        self.assertEqual(self.apply(vue='')['code'],SAN)
        vue=VUE.replace('props:{','mixins:[external],props:{')
        self.assertEqual(self.apply(vue=vue)['code'],SAN)

    def test_wrong_field_dynamic_path_argument_and_hidden_assignment_stay_diagnostics(self):
        for old,new in (("this.data.get('count')===0","this.data.get('count')===1"),
                        ("{{this.data.get('count')}}","{{this.data.get(name)}}"),
                        ("{{this.data.get('count')}}","{{this.data.get('unknown')}}"),
                        ("{{this.data.get('count')}}","{{(count=this.data.get('count'))}}")):
            code=SAN.replace(old,new)
            fixed=self.apply(code)['code']
            self.assertIn(new,fixed)
            self.assertTrue(source_template_semantics(fixed)['findings'])

    def test_loop_alias_shadowing_and_different_conditions_prevent_substitution(self):
        source=VUE.replace('<strong>','<strong v-for="count in counts">').replace('count:{type:Number','counts:{type:Array},count:{type:Number')
        target=SAN.replace('<strong>','<strong s-for="count in counts">').replace('count:DataTypes.number','counts:DataTypes.array,count:DataTypes.number')
        fixed=self.apply(target,source)['code']
        self.assertIn("{{this.data.get('count')}}",fixed)
        source=VUE.replace('<strong>','<strong v-if="count">')
        target=SAN.replace('<strong>','<strong s-if="!count">')
        self.assertIn("{{this.data.get('count')}}",self.apply(target,source)['code'])
        for src, dst in (('v-for','s-for'),('v-if','s-if')):
            source=VUE.replace('<strong>','<strong '+src+'>')
            target=SAN.replace('<strong>','<strong '+dst+'>')
            self.assertIn("{{this.data.get('count')}}",self.apply(target,source)['code'])

    def test_falsy_computed_results_do_not_prove_redundant_fallback(self):
        vue=VUE.replace("?'on':'off'","?'on':''")
        code=SAN.replace("?'on':'off'","?'on':''")
        self.assertIn("this.data.get('status')||''",self.apply(code,vue)['code'])

    def test_comments_examples_and_literal_api_text_are_not_render_calls(self):
        code=SAN.replace(SAN.split('<template>')[1].split('</template>')[0],
            '''<div><!-- {{this.data.get('fake')}} --><code>this.data.get('fake')</code>{{ "this.data.get('fake')" }}</div>''')
        self.assertEqual(source_template_semantics(code)['findings'],[])

    def test_real_inline_child_is_diagnosed_but_not_rewritten_without_its_source_mapping(self):
        code=SAN.replace('module.exports=',"const Child=san.defineComponent({template:`<span>{{this.data.get('count')}}</span>`});module.exports=")
        result=self.apply(code)
        self.assertTrue(any(f['location'].startswith('script.Child.template') for f in result['findings']))
        self.assertIn("template:`<span>{{this.data.get('count')}}</span>`",result['code'])

    def test_string_literal_inline_templates_are_also_diagnosed(self):
        code=SAN.replace('module.exports=', '''const Child=san.defineComponent({template:"<span>{{this.data.get('count')}}</span>"});module.exports=''')
        result=self.apply(code)
        self.assertTrue(any(f['location'].startswith('script.Child.template') for f in result['findings']))
        val=ValidateStage().run(ValidateStageInput(generated_code=code))
        self.assertTrue(any(f['code']==CODE and f['location'].startswith('script.Child.template') for f in val.validation_errors))

    def test_fixed_point_and_inspection_mode_do_not_mutate(self):
        for code,vue in ((SAN,VUE),(CLASS_SAN,CLASS_VUE)):
            fixed=self.apply(code,vue)['code']
            self.assertEqual(self.apply(fixed,vue)['code'],fixed)
            self.assertEqual(self.apply(fixed,vue)['changes'],[])
            self.assertEqual(source_template_semantics(code,vue)['code'],code)

    def test_bad_syntax_or_bridge_failure_never_rewrites_generated_code(self):
        broken=SAN.replace("const san=require('san');","INVALID {{{;")
        self.assertEqual(self.apply(broken)['code'],broken)
        with patch('migration_pipeline.utils.source_template_semantics.subprocess.run',side_effect=OSError):
            source_template_semantics.cache_clear()
            self.assertEqual(self.apply()['code'],SAN)
            val=ValidateStage().run(ValidateStageInput(generated_code=SAN,compile_check=False))
            self.assertFalse(val.validation_passed)
            self.assertIn('template_binding_analysis_unavailable',[e['code'] for e in val.validation_errors])
        source_template_semantics.cache_clear()

    def test_validator_gate_and_prompt_share_the_new_diagnostic(self):
        with tempfile.TemporaryDirectory() as tmp:
            vue=Path(tmp)/'source.vue';vue.write_text(VUE,encoding='utf-8')
            def assess(code):
                val=ValidateStage().run(ValidateStageInput(generated_code=code,vue_file_path=str(vue)))
                return {'generated_code':code,'ssm':{},'vue_file_path':str(vue),**val.to_state_update()}
            before,after=assess(SAN),assess(self.apply()['code'])
            self.assertIn(CODE,[e['code'] for e in before['validation_errors']])
            self.assertNotIn(CODE,[e['code'] for e in after['validation_errors']])
            self.assertFalse(candidate_gate(before,after)['should_stop'])
            self.assertTrue(candidate_gate(after,before)['should_stop'])
            prompt=build_repair_prompt(RepairPromptInput(ssm={},current_code=SAN,validation_errors=[{'code':CODE}]))
            self.assertIn('Do not globally replace script calls',prompt)

    def test_prepass_and_model_postprocessing_share_rule_legacy_profile_is_unchanged(self):
        class Client:
            def repair(self,request):
                return RepairResult(code=SAN,saved_file_path=request.output_file_path,source_file='',ssm={},provider='stub',model='stub',raw_response={})
        with tempfile.TemporaryDirectory() as tmp:
            vue=Path(tmp)/'source.vue';vue.write_text(VUE,encoding='utf-8')
            fixed,rules=RepairStage._deterministic_repair_plan(SAN,[{'code':CODE}],[],{},str(vue),enable_residual_v2=True)
            self.assertIn('restored_source_render_field_bindings',[r for _,r in rules])
            result=RepairStage(Client()).run(RepairStageInput(ssm={},generated_code=SAN,vue_file_path=str(vue),
                output_file_path=str(Path(tmp)/'out.san'),metadata={'skip_deterministic_prepass':True,'semantic_rule_set':'residual_v2'}))
            self.assertEqual(result.repaired_code.rstrip(),fixed.rstrip())
            self.assertIn('restored_source_render_field_bindings',result.raw_response['pipeline_postprocessing'])
            legacy,_=RepairStage._deterministic_repair_plan(SAN,[{'code':CODE}],[],{},str(vue))
            self.assertEqual(legacy,SAN)

    def run_frozen_scheduler(self,name,level):
        from migration_pipeline.replay_formal_30_v4_parent_props_closure_v1 import SOURCE,NoModel
        from migration_pipeline.orchestrator import MigrationPipelineOrchestrator
        from migration_pipeline.replay_formal_30_v4_repair_scheduling import ReplayGenerate
        from migration_pipeline.stages.generate import GenerateStageInput
        from migration_pipeline.stages.visual_eval import VisualEvalStage
        state=json.loads((SOURCE/f'repair_reports/{level}/{name}_repair_history.json').read_text(encoding='utf-8'))['state']
        folder={'simple':'01_simple','complex':'03_complex'}[level]
        vue=SOURCE/f'protocol/frozen/data/datasets/components/{folder}/{name}/vue/{name}.vue'
        with tempfile.TemporaryDirectory() as tmp:
            generate=ReplayGenerate(state,state['final_code'],Path(tmp)/'before.san')
            runner=MigrationPipelineOrchestrator(generate,ValidateStage(),VisualEvalStage(),RepairStage(NoModel()))
            result=runner.run_generate_validate_visual_eval_and_repair_loop(GenerateStageInput(vue_file_path=str(vue),
                metadata={'repair_policy':'bounded_prepass_v1','semantic_rule_set':'residual_v2'}),max_repair_rounds=3).state
            self.assertTrue(result['final_passed'],result['validation_errors'])
            self.assertEqual(result['llm_repair_calls'],0)
            self.assertEqual(result['deterministic_steps'],1)
            self.assertTrue(result['visual_eval_passed'])
            self.assertFalse(result['repair_regression_rejected'])
            return state,result

    def test_actual_stock_scheduler_restores_text_class_and_disabled_without_a_model(self):
        before,after=self.run_frozen_scheduler('StockReservationBadge','simple')
        self.assertFalse(before['final_visual_eval_result']['visual_eval_passed'])
        self.assertNotIn('this.data',after['final_code'].split('</template>')[0])
        self.assertEqual(before['final_code'].split('<script>')[1],after['final_code'].split('<script>')[1])

    def test_actual_rule_scheduler_composes_template_and_parent_default_repairs(self):
        _,after=self.run_frozen_scheduler('RuleBuilder','complex')
        names=after['normalization_history'][0]['normalizations']
        self.assertIn('restored_source_parent_prop_defaults',names)
        self.assertIn('restored_source_class_interpolation_delimiter',names)
        self.assertIn('merged_source_class_bindings',names)

    def test_partial_class_fix_is_not_a_new_grouped_error_and_reverse_is_rejected(self):
        src_article=CLASS_VUE.split('<div>')[1].split('</div>')[0]
        bad_article=CLASS_SAN.split('<div>')[1].split('</div>')[0]
        fixed_article=self.apply(CLASS_SAN,CLASS_VUE)['code'].split('<div>')[1].split('</div>')[0]
        vue=CLASS_VUE.replace(src_article,src_article*2)
        bad=CLASS_SAN.replace(bad_article,bad_article*2)
        partial=bad.replace(bad_article,fixed_article,1)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'source.vue';path.write_text(vue,encoding='utf-8')
            def assess(code):
                result=ValidateStage().run(ValidateStageInput(generated_code=code,vue_file_path=str(path)))
                return {'generated_code':code,'ssm':{},'vue_file_path':str(path),**result.to_state_update()}
            before,after=assess(bad),assess(partial)
            self.assertEqual(sum(e['code']=='source_class_binding_not_landed' for e in before['validation_errors']),2)
            self.assertEqual(sum(e['code']=='source_class_binding_not_landed' for e in after['validation_errors']),1)
            self.assertFalse(candidate_gate(before,after)['should_stop'])
            self.assertTrue(candidate_gate(after,before)['should_stop'])


if __name__=='__main__':unittest.main()
