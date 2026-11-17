"""General class-map closure, actual San parser/evaluator; no model/browser calls."""
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from migration_pipeline.utils.class_binding_contract import CLASS_BINDING_CODES, CLASS_BINDING_RULE
from migration_pipeline.utils.class_binding_semantics import class_binding_semantics as analyze
from migration_pipeline.utils.repair_scheduler import candidate_gate
from migration_pipeline.utils.repair_prompt import RepairPromptInput, build_repair_prompt
from migration_pipeline.stages.repair import RepairStage, RepairStageInput
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.repair_client import RepairResult

ROOT = Path(__file__).resolve().parents[1]
VUE = '''<template><div class="panel" :class="{ 'dark-theme': dark, 'compact-mode': compact }"><button @click="toggle">Toggle</button></div></template>
<script>export default {data(){return {dark:false,compact:false};},methods:{toggle(){this.dark=!this.dark;}}};</script>'''
SAN = '''<template><div class="panel {{ 'dark-theme': dark, 'compact-mode': compact }}"><button on-click="toggle">Toggle</button></div></template>
<script>const san=require('san');module.exports=san.defineComponent({initData(){return {dark:false,compact:false};},toggle(){this.data.set('dark',!this.data.get('dark'));}});</script><style>.panel{color:red}</style>'''
BAD = "{{ 'dark-theme': dark, 'compact-mode': compact }}"
GOOD = "{{ dark ? 'dark-theme' : '' }} {{ compact ? 'compact-mode' : '' }}"
FIXED = SAN.replace(BAD, GOOD)


class NoModel:
    def repair(self, request):
        raise AssertionError('No model call authorized')


def native_states(code, fields=('dark', 'compact')):
    js = r'''const fs=require('fs'),san=require('san'),Data=require('san/src/runtime/data'),evalExpr=require('san/src/runtime/eval-expr');
const input=JSON.parse(fs.readFileSync(0,'utf8')),template=/<template\b[^>]*>([\s\S]*?)<\/template>/.exec(input.code)[1];
const root=san.parseTemplate(template).children.find(n=>n.tagName==='div'),prop=root.props.find(p=>p.name==='class');
const data=new Data({}),states=[];for(const a of [false,true])for(const b of [false,true]){data.set(input.fields[0],a);data.set(input.fields[1],b);states.push(evalExpr(prop.expr,data).trim().replace(/\s+/g,' '));}
data.set(input.fields[0],false);data.set(input.fields[1],false);states.push(evalExpr(prop.expr,data).trim().replace(/\s+/g,' '));
process.stdout.write(JSON.stringify(states));'''
    p = subprocess.run(['node', '-e', js], cwd=ROOT, input=json.dumps({'code': code, 'fields': fields}),
        text=True, encoding='utf-8', capture_output=True, check=True)
    return json.loads(p.stdout)


class ClassBindingClosureTests(unittest.TestCase):
    def test_bare_map_static_prefix_was_silently_accepted_by_san(self):
        self.assertEqual(native_states(SAN), ['panel dark-theme'] * 5)
        self.assertIn('invalid_object_class_binding', [f['code'] for f in analyze(SAN)['findings']])

    def test_source_matched_multi_key_repair_and_all_native_states(self):
        result = analyze(SAN, VUE, repair=True)
        self.assertNotIn('error', result)
        self.assertEqual(result['code'], FIXED)
        self.assertEqual(result['changes'], ['restored_source_conditional_class_map'])
        self.assertEqual(native_states(result['code']), ['panel','panel compact-mode','panel dark-theme','panel dark-theme compact-mode','panel'])
        self.assertEqual(analyze(FIXED, VUE)['findings'], [])
        self.assertEqual(analyze(FIXED, VUE)['mapped_bindings'], ['template/div[0]@class'])

    def test_single_key_and_object_wrapper_variants_are_detected(self):
        for expression in ("{{active:dark}}", "{{ {active:dark} }}", "{{{active:dark}}}"):
            with self.subTest(expression=expression):
                code=SAN.replace(BAD,expression)
                self.assertIn('invalid_object_class_binding', [f['code'] for f in analyze(code)['findings']])

    def test_source_exact_single_key_object_wrapper_is_repaired(self):
        src=VUE.replace("{ 'dark-theme': dark, 'compact-mode': compact }",'{active:dark}')
        for expression in ("{{active:dark}}", "{{ {active:dark} }}", "{{{active:dark}}}"):
            result=analyze(SAN.replace(BAD,expression),src,repair=True)
            self.assertIn("{{ dark ? 'active' : '' }}",result['code'])

    def test_fixed_point_inspection_and_other_bytes_preserved(self):
        self.assertEqual(analyze(SAN,VUE)['code'],SAN)
        result=analyze(FIXED,VUE,repair=True)
        self.assertEqual(result['code'],FIXED)
        self.assertEqual(result['changes'],[])
        self.assertEqual(SAN.split('</template>')[1],FIXED.split('</template>')[1])
        self.assertIn('on-click="toggle"',FIXED)

    def test_without_source_or_with_wrong_condition_static_shape_no_guess(self):
        variants=[('',SAN),(VUE,SAN.replace('dark,','!dark,')),(VUE,SAN.replace('class="panel','class="other')),
                  (VUE.replace('<button','<aside></aside><button'),SAN),
                  (VUE.replace('data(){','mixins:[opaque],data(){'),SAN),
                  (VUE,SAN.replace('compact:false','other:false'))]
        for vue,code in variants:
            with self.subTest(vue=vue,code=code):
                result=analyze(code,vue,repair=True)
                self.assertEqual(result['code'],code)
                self.assertEqual(result['changes'],[])

    def test_dynamic_keys_spreads_calls_and_unknown_fields_are_not_rewritten(self):
        for expression in ('{[name]:dark}','{...classes}',"{active:check(dark)}",'{active:unknown}',"{'__proto__':dark}",
                           '{active:dark?.check()}', '{active:dark?.x}', '{active:dark**2}', '{active:`x`}', '{active:typeof dark}'):
            src=VUE.replace("{ 'dark-theme': dark, 'compact-mode': compact }",expression)
            code=SAN.replace(BAD,'{{ '+expression+' }}')
            result=analyze(code,src,repair=True)
            self.assertEqual(result['code'],code)
            self.assertIn('invalid_object_class_binding',[f['code'] for f in result['findings']])
            self.assertIn('source_class_binding_unproven',[f['code'] for f in result['findings']])

    def test_always_on_missing_condition_missing_class_and_missing_separator_blocked(self):
        for binding in ('panel dark-theme compact-mode','panel '+"{{ dark ? 'dark-theme' : '' }}",
                        'panel'+GOOD,"panel {{ !dark ? 'dark-theme' : '' }} {{ compact ? 'compact-mode' : '' }}"):
            code=SAN.replace('panel '+BAD,binding)
            self.assertIn('source_class_binding_not_landed',[f['code'] for f in analyze(code,VUE)['findings']])
        code=SAN.replace('class="panel '+BAD+'"','')
        self.assertIn('source_class_binding_not_landed',[f['code'] for f in analyze(code,VUE)['findings']])

    def test_optional_class_whitespace_is_normalized_only_after_boundary_proof(self):
        for binding in (
            "panel{{ dark ? ' dark-theme' : '' }}{{ compact ? ' compact-mode' : '' }}",
            "panel {{ dark ? ' dark-theme ' : '' }} {{ compact ? ' compact-mode ' : '' }}",
            "panel{{ dark ? '\\tdark-theme' : '' }}{{ compact ? '\\ncompact-mode' : '' }}",
        ):
            with self.subTest(binding=binding):
                code=SAN.replace('panel '+BAD,binding)
                self.assertEqual(analyze(code,VUE)['findings'],[])
                self.assertEqual(analyze(code,VUE,repair=True)['code'],code)
                self.assertEqual(native_states(code),native_states(FIXED))

    def test_whitespace_normalization_does_not_allow_wrong_condition_or_token_join(self):
        for binding in (
            "panel{{ dark ? 'dark-theme' : '' }}{{ compact ? ' compact-mode' : '' }}",
            "panel{{ !dark ? ' dark-theme' : '' }}{{ compact ? ' compact-mode' : '' }}",
            "panel{{ dark ? ' wrong-theme' : '' }}{{ compact ? ' compact-mode' : '' }}",
            "panel{{ dark ? ' dark-theme ': '' }}tail{{ compact ? ' compact-mode' : '' }}",
        ):
            with self.subTest(binding=binding):
                code=SAN.replace('panel '+BAD,binding)
                self.assertIn('source_class_binding_not_landed',[f['code'] for f in analyze(code,VUE)['findings']])

    def test_multi_token_source_keys_preserve_their_class_contract(self):
        vue=VUE.replace("'dark-theme': dark","'dark-theme  extra': dark")
        code=FIXED.replace("'dark-theme'","' dark-theme   extra '")
        self.assertEqual(analyze(code,vue)['findings'],[])
        self.assertEqual(native_states(code),['panel','panel compact-mode','panel dark-theme extra','panel dark-theme extra compact-mode','panel'])

    def test_literal_text_comments_style_and_quoted_example_are_not_attributes(self):
        code=SAN.replace('<div class="panel '+BAD+'">', '<div><!-- class="{{active:dark}}" --><code>class="{{active:dark}}"</code>')
        code=code.replace("const san=", "const example=`class=\"{{active:dark}}\"`;const san=")
        self.assertEqual(analyze(code)['findings'],[])

    def test_loop_and_conditional_scope_proof(self):
        vue=VUE.replace('<button @click="toggle">Toggle</button>', '').replace('<div class=', '<div v-for="row in rows" v-if="dark" class=').replace("'dark-theme': dark", "'dark-theme': row.active").replace('dark:false','rows:[],dark:false')
        code=SAN.replace('<button on-click="toggle">Toggle</button>', '').replace('<div class=', '<div s-for="row in rows" s-if="dark" class=').replace("'dark-theme': dark", "'dark-theme': row.active").replace('dark:false','rows:[],dark:false')
        self.assertTrue(analyze(code,vue,repair=True)['changes'])
        for other in (code.replace('s-if="dark"','s-if="!dark"'),code.replace('row in rows','item in rows')):
            self.assertEqual(analyze(other,vue,repair=True)['code'],other)

    def test_actual_inline_registered_child_uses_same_bounded_rule(self):
        vue='''<template><child-box></child-box></template><script>const Child={template:`<i class="badge" :class="{active:flag}"></i>`,data(){return {flag:false};}};export default {components:{ChildBox:Child}};</script>'''
        code='''<template><child-box></child-box></template><script>const san=require('san');const Child=san.defineComponent({template:`<i class="badge {{active:flag}}"></i>`,initData(){return {flag:false};}});module.exports=san.defineComponent({components:{'child-box':Child}});</script><style></style>'''
        result=analyze(code,vue,repair=True)
        self.assertNotIn('error',result)
        self.assertIn("badge {{ flag ? 'active' : '' }}",result['code'])
        self.assertEqual(analyze(result['code'],vue)['findings'],[])
        unregistered=code.replace("components:{'child-box':Child}",'components:{}')
        self.assertEqual(analyze(unregistered,vue,repair=True)['code'],unregistered)

    def test_unregistered_and_string_literal_inline_templates_are_still_diagnosed(self):
        for tpl in ('`<i class="badge {{active:flag}}"></i>`', "'<i class=\"badge {{active:flag}}\"></i>'"):
            code=SAN.replace('module.exports=', 'const Child=san.defineComponent({template:'+tpl+'});module.exports=')
            result=analyze(code)
            self.assertTrue(any(f['location'].startswith('script.Child.template') for f in result['findings']))

    def test_validator_unconditionally_finds_bare_maps_with_no_other_trigger(self):
        result=ValidateStage().run(ValidateStageInput(generated_code=SAN))
        self.assertFalse(result.validation_passed)
        self.assertIn('invalid_object_class_binding',[f['code'] for f in result.validation_errors])
        self.assertTrue(result.san_compile_result['passed'])

    def test_validator_analyzer_failure_is_not_compile_success(self):
        with patch('migration_pipeline.stages.validate.class_binding_semantics',return_value={'findings':[],'error':'missing node'}):
            result=ValidateStage().run(ValidateStageInput(generated_code=FIXED))
        self.assertIn('class_binding_analysis_unavailable',[f['code'] for f in result.validation_errors])

    def test_non_class_invalid_script_does_not_masquerade_as_class_regression(self):
        result=analyze('<template><button></button></template><script>handler(item){}</script>')
        self.assertNotIn('error',result)
        self.assertEqual(result['findings'],[])

    def test_bridge_failure_or_bad_response_preserves_code_with_explicit_error(self):
        for response in ('[]','null','{}','not json'):
            analyze.cache_clear()
            with patch('migration_pipeline.utils.class_binding_semantics.subprocess.run',return_value=SimpleNamespace(stdout=response)):
                result=analyze(SAN,VUE,repair=True)
            self.assertEqual(result['code'],SAN)
            self.assertTrue(result.get('error'))
        analyze.cache_clear()

    def test_prepass_all_profiles_uses_zero_model_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            vue=Path(tmp)/'source.vue';vue.write_text(VUE,encoding='utf-8')
            for profile in ({},{'semantic_rule_set':'residual_v2'}):
                result=RepairStage(NoModel()).run(RepairStageInput(ssm={},generated_code=SAN,vue_file_path=str(vue),
                    validation_errors=[{'code':'invalid_object_class_binding'}],output_file_path=str(Path(tmp)/'out.san'),metadata=profile))
                self.assertEqual(result.repaired_code,FIXED)
                self.assertEqual(result.provider,'deterministic')
                self.assertEqual(result.usage['total_tokens'],0)

    def test_model_response_reintroduced_map_is_postprocessed_with_provenance(self):
        class Stub:
            def repair(self,request):
                return RepairResult(code=SAN,saved_file_path=request.output_file_path,source_file='',ssm={},provider='stub',model='stub',raw_response={})
        with tempfile.TemporaryDirectory() as tmp:
            vue=Path(tmp)/'source.vue';vue.write_text(VUE,encoding='utf-8')
            result=RepairStage(Stub()).run(RepairStageInput(ssm={},generated_code=FIXED,vue_file_path=str(vue),
                output_file_path=str(Path(tmp)/'out.san'),metadata={'skip_deterministic_prepass':True}))
            self.assertEqual(result.repaired_code.rstrip(),FIXED.rstrip())
            self.assertIn('restored_source_conditional_class_map',result.raw_response['pipeline_postprocessing'])

    def test_no_source_prepass_does_not_claim_a_repair(self):
        code,steps=RepairStage._deterministic_repair_plan(SAN,[{'code':'invalid_object_class_binding'}],[])
        self.assertEqual(code,SAN)
        self.assertEqual(steps,[])

    def test_generation_repair_and_server_fallback_share_constraint(self):
        from local_server.api.evaluation_routes import _build_generation_prompt,_build_repair_prompt
        for prompt in (_build_generation_prompt({}),_build_repair_prompt({}),
                       build_repair_prompt(RepairPromptInput(ssm={},current_code=SAN,validation_errors=[{'code':'invalid_object_class_binding'}]))):
            self.assertIn(CLASS_BINDING_RULE,prompt)
            self.assertIn('parent AND every inline child',prompt)
        self.assertEqual(_build_repair_prompt({'repair_prompt':'explicit provided prompt'}),'explicit provided prompt')

    def test_independent_gate_rejects_forged_validation_success(self):
        before={'generated_code':FIXED,'vue_source':VUE,'validation_errors':[],'ssm':{}}
        for broken in (SAN,SAN.replace('panel '+BAD,'panel dark-theme'),SAN.replace('class="panel '+BAD+'"','')):
            after={**before,'generated_code':broken,'validation_passed':True}
            gate=candidate_gate(before,after)
            self.assertTrue(gate['should_stop'])
            self.assertEqual(gate['decision'],'reject')
            self.assertTrue(gate['lost_source_class_bindings'])
        self.assertFalse(candidate_gate(before,before)['should_stop'])

    def test_gate_does_not_waive_analyzer_failure(self):
        before={'generated_code':FIXED,'vue_source':VUE,'validation_errors':[],'ssm':{}}
        with patch('migration_pipeline.utils.class_binding_semantics.class_binding_semantics',return_value={'findings':[],'mapped_bindings':[],'error':'unavailable'}):
            self.assertTrue(candidate_gate(before,before)['should_stop'])

    def test_class_guard_does_not_relabel_an_unrelated_event_review(self):
        state={'generated_code':'<template><div></div></template>','ssm':{},'validation_errors':[]}
        with patch('migration_pipeline.utils.repair_scheduler.assess_event_contract_regression',
                   return_value={'should_stop':True,'decision':'review'}):
            gate=candidate_gate(state,state)
        self.assertTrue(gate['should_stop'])
        self.assertEqual(gate['decision'],'review')

    def test_default_and_bounded_loops_reject_even_with_forged_validator_pass(self):
        from migration_pipeline.orchestrator import MigrationPipelineOrchestrator
        from migration_pipeline.stages.generate import GenerateStageInput, GenerateStageResult
        class Generate:
            def run(self, _):
                return GenerateStageResult(source_file='fixture.vue',ssm={},generation_code=FIXED,
                    saved_file_path='fixture.san',provider='stub',model='stub',usage={},raw_response={})
        class Validate:
            def run_from_state(self,state):
                errors=[{'code':'other_error'}] if state['generated_code']==FIXED else []
                result={'validation_passed':not errors,'validation_errors':errors,'validation_warnings':[]}
                return {**result,'validate_result':result}
        class Visual:
            def run_from_state(self,state):
                result={'visual_eval_passed':True,'visual_eval_errors':[]}
                return {**result,'visual_eval_result':result}
        class Repair(RepairStage):
            def run_from_state(self,state):
                return {'generated_code':SAN,'generated_file_path':'candidate.san','repair_attempt':1,
                    'repair_provider':'stub','repair_prompt':'ordinary prompt, no focused marker','repair_result':{}}
        for metadata in ({},{'repair_policy':'bounded_prepass_v1'}):
            runner=MigrationPipelineOrchestrator(Generate(),Validate(),Visual(),Repair(NoModel()))
            result=runner.run_generate_validate_visual_eval_and_repair_loop(
                GenerateStageInput(vue_source=VUE,metadata=metadata),max_repair_rounds=1).state
            self.assertTrue(result['repair_regression_rejected'])
            self.assertFalse(result['final_passed'])
            self.assertTrue(result['repair_history'][0]['repair_regression_gate']['should_stop'])

    def test_real_frozen_candidate_replay_fixes_class_not_other_known_blockers(self):
        base=ROOT/'data/experiments/analysis/formal_30_v4_class_binding_pre_fix_20261113'
        old=json.loads((base/'audit.json').read_text(encoding='utf-8'))
        path=ROOT/old['candidate_reference'];original=path.read_bytes()
        code=path.read_text(encoding='utf-8');vue=ROOT/old['source_reference']
        result=analyze(code,vue.read_text(encoding='utf-8'),repair=True)
        self.assertEqual(result['code'].split('</template>')[1],code.split('</template>')[1])
        self.assertEqual(native_states(result['code'],('isDarkMode','isCompactMode')),
            ['task-manager','task-manager compact-mode','task-manager dark-theme','task-manager dark-theme compact-mode','task-manager'])
        val=ValidateStage().run(ValidateStageInput(generated_code=result['code'],vue_file_path=str(vue)))
        self.assertFalse(val.validation_passed)
        self.assertFalse(CLASS_BINDING_CODES & {f['code'] for f in val.validation_errors})
        self.assertIn('source_parent_watch_dynamic_key_unproven',{f['code'] for f in val.validation_errors})
        self.assertEqual(path.read_bytes(),original)


if __name__=='__main__':unittest.main()
