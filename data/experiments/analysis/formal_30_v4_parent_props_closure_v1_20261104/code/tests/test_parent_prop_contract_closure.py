"""Source-proven parent prop additions, refusal boundaries, and real repair entry points."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from migration_pipeline.utils.parent_prop_semantics import parent_prop_semantics
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.stages.repair import RepairStage, RepairStageInput
from migration_pipeline.repair_client import RepairResult
from migration_pipeline.utils.repair_prompt import RepairPromptInput, build_repair_prompt
from migration_pipeline.utils.repair_scheduler import candidate_gate

ROOT = Path(__file__).resolve().parents[1]
VUE = """<template><div></div></template><script>export default {props:{
title:{type:String,default:'Example'}, rows:{type:Array,default:()=>[{id:1,active:false}]},
settings:{type:Object,default:function(){return {enabled:true};}}, count:{type:Number,default:-2},
requiredValue:{type:Boolean,required:true}}};</script>"""
SAN = """<template><div></div></template><script>const san=require('san');
module.exports=san.defineComponent({initData(){return {local:3};}});</script><style></style>"""


class ParentPropContractClosureTests(unittest.TestCase):
    def apply(self, code=SAN, vue=VUE):
        return parent_prop_semantics(code, vue, repair=True)

    def test_adds_literal_defaults_and_required_types_only_to_parent(self):
        result = self.apply()
        self.assertNotIn('error', result)
        self.assertEqual(set(result['changes']), {'restored_source_parent_prop_schema', 'restored_source_parent_prop_defaults'})
        for text in ('title: DataTypes.string', 'rows: DataTypes.array', 'settings: DataTypes.object',
                     'requiredValue: DataTypes.bool.isRequired', 'count: -2', 'local:3'):
            self.assertIn(text, result['code'])
        self.assertIn('const DataTypes = san.DataTypes;', result['code'])

    def test_literal_factory_results_are_fresh_per_instance_and_supplied_props_override(self):
        fixed = self.apply()['code'].split('<script>')[1].split('</script>')[0]
        js = """const fs=require('fs'),san=require('san'),m={exports:{}};
new Function('require','module',fs.readFileSync(0,'utf8'))(require,m);
const a=new m.exports({data:{requiredValue:true}}),b=new m.exports({data:{requiredValue:true}}),
c=new m.exports({data:{requiredValue:true,rows:[{id:99}],title:'custom'}});
a.data.get('rows')[0].id=8;a.data.get('settings').enabled=false;
process.stdout.write(JSON.stringify({b:b.data.get(),c:c.data.get()}));"""
        p = subprocess.run(['node', '-e', js], cwd=ROOT, input=fixed, text=True, encoding='utf-8', capture_output=True, check=True)
        data = json.loads(p.stdout)
        self.assertEqual(data['b']['rows'], [{'id': 1, 'active': False}])
        self.assertEqual(data['b']['settings'], {'enabled': True})
        self.assertEqual(data['c']['rows'], [{'id': 99}])
        self.assertEqual(data['c']['title'], 'custom')

    def test_existing_values_custom_validators_and_unrelated_schema_are_not_replaced(self):
        code = SAN.replace('initData(){', 'dataTypes:{title:customValidator,extra:DataTypes.string},initData(){')
        code = code.replace("const san=require('san');", "const san=require('san');const DataTypes=san.DataTypes;")
        code = code.replace('local:3', "local:3,title:'keep'")
        fixed = self.apply(code)['code']
        self.assertIn('title:customValidator', fixed)
        self.assertIn("title:'keep'", fixed)
        self.assertIn('extra:DataTypes.string', fixed)
        self.assertNotIn("title: \"Example\"", fixed)
        self.assertEqual(self.apply(fixed)['code'], fixed)

    def test_children_template_css_and_hooks_keep_exact_bytes(self):
        child = "const child=san.defineComponent({initData(){return {title:'child'};}});\n"
        code = SAN.replace('module.exports=', child + 'module.exports=')
        code = code.replace('initData(){return {local:3};}', 'attached(){this.start();},initData(){return {local:3};}')
        fixed = self.apply(code)['code']
        self.assertIn(child, fixed)
        self.assertIn('attached(){this.start();}', fixed)
        for tag in ('template', 'style'):
            self.assertEqual(fixed.split('<'+tag+'>')[1].split('</'+tag+'>')[0], code.split('<'+tag+'>')[1].split('</'+tag+'>')[0])

    def test_fixed_point_and_inspection_mode_do_not_write_or_duplicate(self):
        fixed = self.apply()['code']
        self.assertEqual(self.apply(fixed)['changes'], [])
        self.assertEqual(self.apply(fixed)['code'], fixed)
        inspect = parent_prop_semantics(SAN, VUE)
        self.assertEqual(inspect['code'], SAN)
        self.assertEqual(inspect['changes'], [])
        self.assertEqual(inspect['addable_default_fields'], ['title', 'rows', 'settings', 'count'])

    def test_opaque_side_effecting_or_closure_factories_are_not_executed_or_copied(self):
        for expression in ('()=>loadRows()', '()=>externalRows', '()=>{notify();return [];}',
                           '()=>{const rows=[];return rows;}', '(props)=>[]', 'async()=>[]',
                           '()=>[{get id(){return read();}}]', '()=>[...shared]', '()=>({[key]:1})',
                           '()=>({__proto__:shared})', '()=>[{id:Date.now()}]'):
            vue = VUE.replace('()=>[{id:1,active:false}]', expression)
            self.assertEqual(self.apply(vue=vue)['code'], SAN)

    def test_shared_direct_mutable_defaults_custom_union_and_shadowed_types_are_refused(self):
        for vue in (VUE.replace('()=>[{id:1,active:false}]', '[]'),
                    VUE.replace('type:String', 'type:Custom'),
                    VUE.replace('type:String', 'type:[String,Number]'),
                    VUE.replace('export default', 'const Array=Custom;export default'),
                    VUE.replace("default:'Example'", "default:()=>42")):
            self.assertEqual(self.apply(vue=vue)['code'], SAN)

    def test_source_mixins_duplicates_spreads_and_script_setup_remain_unproven(self):
        for vue in (VUE.replace('props:{', 'mixins:[m],props:{'), VUE.replace('props:{', '...other,props:{'),
                    VUE.replace('props:{', 'props:{},props:{'), VUE.replace('<script>', '<script setup>')):
            self.assertEqual(self.apply(vue=vue)['code'], SAN)

    def test_complex_factory_or_target_spread_does_not_gain_defaults(self):
        for code in (SAN.replace('return {local:3};', 'const state={local:3};return state;'),
                     SAN.replace('return {local:3};', 'const state=unknown();return {local:3};'),
                     SAN.replace('return {local:3};', 'return {...other,local:3};'),
                     SAN.replace('initData(){', 'initData(arg){')):
            result = self.apply(code)
            self.assertNotIn('restored_source_parent_prop_defaults', result['changes'])
        for code in (SAN.replace('initData(){', '...options,initData(){'),
                     SAN.replace('initData(){', 'initData(){return {};},initData(){')):
            self.assertEqual(self.apply(code)['code'], code)

    def test_ambiguous_schema_and_alias_are_not_overwritten(self):
        for option in ('dataTypes:custom,', 'dataTypes:{...validators},', 'props:{title:String},', 'propTypes:{},',
                       'statics:{dataTypes:{title:customValidator}},'):
            code = SAN.replace('initData(){', option + 'initData(){')
            self.assertNotIn('restored_source_parent_prop_schema', self.apply(code)['changes'])
        code = SAN.replace('module.exports=', 'const DataTypes=custom;module.exports=')
        self.assertNotIn('restored_source_parent_prop_schema', self.apply(code)['changes'])
        for code in (SAN.replace('</script>', 'module.exports.dataTypes=custom;</script>'),
                     SAN.replace('</script>', 'san.DataTypes.array=custom;</script>')):
            self.assertEqual(self.apply(code)['code'], code)

    def test_methods_comments_strings_and_non_component_data_are_not_wrappers(self):
        for extra in ('// methods: {}\n', '/* methods: {} */', 'const note="methods: {";',
                      'const sample={methods:{}};'):
            script = extra + "const san=require('san');module.exports=san.defineComponent({initData(){return {};}});"
            issues = []
            ValidateStage()._validate_script_rules(script, {}, issues, [])
            self.assertNotIn('vue_methods_wrapper', [i.code for i in issues])

    def test_real_parent_and_child_wrappers_still_report_and_parse_failure_is_not_waived(self):
        for script in ("module.exports=san.defineComponent({methods:{save(){}}});",
                       "module.exports=san.defineComponent({'methods':{save(){}}});",
                       "const Child=san.defineComponent({methods:{save(){}}});",
                       "const options={methods:{save(){}}};module.exports=san.defineComponent(options);",
                       "module.exports=san.defineComponent({methods:{ BROKEN"):
            issues = []
            ValidateStage()._validate_script_rules(script, {}, issues, [])
            self.assertIn('vue_methods_wrapper', [i.code for i in issues])

    def test_process_failure_preserves_input_and_regex_diagnostic(self):
        with patch('migration_pipeline.utils.parent_prop_semantics.subprocess.run', side_effect=OSError):
            parent_prop_semantics.cache_clear()
            self.assertEqual(self.apply()['code'], SAN)
            issues = []
            ValidateStage()._validate_script_rules('// methods: {}', {}, issues, [])
            self.assertIn('vue_methods_wrapper', [i.code for i in issues])
        parent_prop_semantics.cache_clear()

    def test_repair_prepass_and_model_postprocessing_share_source_backed_rule(self):
        class Client:
            def repair(self, request):
                return RepairResult(code=SAN, saved_file_path=request.output_file_path,
                    source_file='', ssm={}, provider='stub', model='stub', raw_response={})
        with tempfile.TemporaryDirectory() as tmp:
            vue = Path(tmp) / 'source.vue'; vue.write_text(VUE, encoding='utf-8')
            fixed, rules = RepairStage._deterministic_repair_plan(SAN, [{'code':'missing_prop_defaults'}], [], {}, str(vue), enable_residual_v2=True)
            self.assertIn('restored_source_parent_prop_defaults', [r for _, r in rules])
            result = RepairStage(Client()).run(RepairStageInput(ssm={}, generated_code=SAN, vue_file_path=str(vue),
                output_file_path=str(Path(tmp)/'out.san'), metadata={'skip_deterministic_prepass':True, 'semantic_rule_set':'residual_v2'}))
            self.assertEqual(result.repaired_code.rstrip(), fixed.rstrip())
            self.assertIn('restored_source_parent_prop_defaults', result.raw_response['pipeline_postprocessing'])
            legacy, _ = RepairStage._deterministic_repair_plan(SAN, [{'code':'missing_prop_defaults'}], [], {}, str(vue))
            self.assertEqual(legacy, SAN)

    def test_prompt_has_complete_parent_default_contract_not_just_schema(self):
        prompt = build_repair_prompt(RepairPromptInput(ssm={}, current_code=SAN, vue_source=VUE,
            validation_errors=[{'code':'missing_prop_defaults'}]))
        for text in ('Source parent prop contract evidence', 'default_code', 'fresh array/object', 'never'):
            self.assertIn(text.lower(), prompt.lower())

    def test_missing_full_source_evidence_keeps_full_ssm_context(self):
        for vue in ('', VUE.replace('type:String', 'type:Custom')):
            prompt = build_repair_prompt(RepairPromptInput(ssm={'large_unrelated_contract':{'must_keep':True}},
                current_code=SAN, vue_source=vue, validation_errors=[{'code':'missing_prop_defaults'},
                    {'code':'invalid_san_computed_instance_method_call'}]))
            self.assertIn('large_unrelated_contract', prompt)

    def frozen_case(self, name, level):
        snapshot = ROOT / 'data/experiments/snapshots/formal_30_v4_full_regression_v2_results_20261104_214821'
        state = json.loads((snapshot / f'repair_reports/{level}/{name}_repair_history.json').read_text(encoding='utf-8'))['state']
        folder = {'simple':'01_simple','medium':'02_medium','complex':'03_complex'}[level]
        vue = snapshot / f'protocol/frozen/data/datasets/components/{folder}/{name}/vue/{name}.vue'
        return state, vue

    def test_frozen_stock_comment_is_not_a_real_methods_wrapper_but_raw_result_is_unchanged(self):
        state, vue = self.frozen_case('StockReservationBadge', 'simple')
        result = ValidateStage().run(ValidateStageInput(generated_code=state['final_code'], ssm=state['ssm'], vue_file_path=str(vue)))
        self.assertTrue(result.validation_passed, result.validation_errors)
        self.assertIn('vue_methods_wrapper', [e['code'] for e in state['final_validate_result']['validation_errors']])
        self.assertFalse(state['final_visual_eval_result']['visual_eval_passed'])

    def test_frozen_rejected_rule_candidate_lands_default_without_source_or_template_edits(self):
        state, vue = self.frozen_case('RuleBuilder', 'complex')
        original = state['repair_history'][0]['repair_result']['repaired_code']
        before = ValidateStage().run(ValidateStageInput(generated_code=original, ssm=state['ssm'], vue_file_path=str(vue)))
        result = parent_prop_semantics(original, vue.read_text(encoding='utf-8'), repair=True)
        self.assertEqual(result['changes'], ['restored_source_parent_prop_defaults'])
        after = ValidateStage().run(ValidateStageInput(generated_code=result['code'], ssm=state['ssm'], vue_file_path=str(vue)))
        self.assertTrue(after.validation_passed, after.validation_errors)
        a = {'generated_code':original,'ssm':state['ssm'],'vue_file_path':str(vue),**before.to_state_update()}
        b = {**a,'generated_code':result['code'],**after.to_state_update()}
        self.assertFalse(candidate_gate(a,b)['should_stop'])
        self.assertTrue(candidate_gate(b,a)['should_stop'])

    def test_actual_scheduler_repairs_frozen_habit_schema_with_zero_model_calls(self):
        from migration_pipeline.orchestrator import MigrationPipelineOrchestrator
        from migration_pipeline.replay_formal_30_v4_repair_scheduling import ReplayGenerate
        from migration_pipeline.stages.generate import GenerateStageInput
        from migration_pipeline.stages.visual_eval import VisualEvalStage
        state, vue = self.frozen_case('HabitWeekTracker', 'medium')
        class NoModel:
            def repair(self, request):
                raise AssertionError('Offline proof must not request a model')
        with tempfile.TemporaryDirectory() as tmp:
            generate = ReplayGenerate(state, state['final_code'], Path(tmp)/'before.san')
            runner = MigrationPipelineOrchestrator(generate, ValidateStage(), VisualEvalStage(), RepairStage(NoModel()))
            result = runner.run_generate_validate_visual_eval_and_repair_loop(GenerateStageInput(vue_file_path=str(vue),
                metadata={'repair_policy':'bounded_prepass_v1','semantic_rule_set':'residual_v2'}),max_repair_rounds=3).state
            self.assertTrue(result['final_passed'], result['validation_errors'])
            self.assertEqual(result['llm_repair_calls'], 0)
            self.assertEqual(result['deterministic_steps'], 1)


if __name__ == '__main__':
    unittest.main()
