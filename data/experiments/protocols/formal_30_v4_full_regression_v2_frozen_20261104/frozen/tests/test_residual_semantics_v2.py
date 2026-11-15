"""Opt-in residual transformations and their refusal boundaries."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from migration_pipeline.utils.residual_semantics import residual_semantics
from migration_pipeline.utils.repair_prompt import RepairPromptInput, build_repair_prompt
from migration_pipeline.stages.repair import RepairStage, RepairStageInput
from migration_pipeline.repair_client import RepairResult
from migration_pipeline.run_batch_pipeline import validate_batch_config


def code(method="if (values.length <= 1) return width / 2; return index / (values.length - 1) * width;", name='point'):
    return f'''<template><div></div></template><script>const san = require('san');
const Chart = san.defineComponent({{
  template: `<div>{{{{ points }}}}</div>`,
  initData() {{ return {{values: [1,2,3], width: 60}}; }},
  computed: {{ points() {{ return this.{name}(1, this.data.get('values'), this.data.get('width')); }} }},
  {name}(index, values, width) {{ {method} }}
}});
module.exports = san.defineComponent({{components: {{'chart-card': Chart}}}});
</script><style></style>'''


class ResidualSemanticsTests(unittest.TestCase):
    def test_lift_calculation_without_changing_instance_method(self):
        original = code()
        fixed = residual_semantics(original, repair=True)
        self.assertEqual(fixed['changes'], ['lifted_self_contained_computed_helper'])
        self.assertIn('function __sanComputed_point_0', fixed['code'])
        self.assertNotIn('return this.point(', fixed['code'])
        self.assertIn('point(index, values, width)', fixed['code'])
        self.assertEqual(residual_semantics(fixed['code'], repair=True)['code'], fixed['code'])
        script = fixed['code'].split('<script>', 1)[1].split('</script>', 1)[0]
        js = r"""const fs=require('fs'); const text=fs.readFileSync(0,'utf8');
const m={exports:{}}; new Function('require','module',text+'\nmodule.exports=Chart;')(require,m);
const c=new m.exports();
const rows=[[],[1],[1,2,3]].map(values=>{c.data.set('values',values); return [c.data.get('points'),c.point(1,values,60)];});
process.stdout.write(JSON.stringify(rows));"""
        result = subprocess.run(['node', '-e', js], input=script, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [[30,30],[30,30],[30,30]])

    def test_local_date_computation_is_allowed_but_never_parameter_mutation(self):
        original = code('const today = new Date(); today.setHours(0,0,0,0); return new Date(index) < today;')
        self.assertIn('lifted_self_contained_computed_helper', residual_semantics(original, repair=True)['changes'])
        for body in ('values.push(index); return 0;', 'values.x = 1; return 0;',
                     'return values.pop();', 'return this.data.get("width");',
                     'return external * width;', 'return Math.random();',
                     'return console.log(index);', 'return (()=>this.data.get("width"))();'):
            with self.subTest(body=body):
                self.assertEqual(residual_semantics(code(body), repair=True)['code'], code(body))

    def test_closed_over_module_state_is_not_a_self_contained_helper(self):
        original = code('return factor * width;').replace("const san = require('san');", "const san = require('san'); let factor = 2;")
        self.assertEqual(residual_semantics(original, repair=True)['code'], original)

    def test_date_helper_matches_instance_method_with_a_fixed_clock(self):
        original = code('''if (index.completed || !index.dueDate) return false;
const dueDate = new Date(index.dueDate); const today = new Date();
today.setHours(0,0,0,0); return dueDate < today;''')
        fixed = residual_semantics(original, repair=True)['code']
        script = fixed.split('<script>', 1)[1].split('</script>', 1)[0]
        js = r"""const fs=require('fs'); const script=fs.readFileSync(0,'utf8');
const NativeDate=Date; global.Date=class extends NativeDate {constructor(value){super(arguments.length?value:'2026-11-03T12:00:00Z');}};
const m={exports:{}}; new Function('require','module',script+'\nmodule.exports={Chart,helper:__sanComputed_point_0};')(require,m);
const c=new m.exports.Chart(); const tasks=[{completed:true,dueDate:'2020-01-01'}, {}, {dueDate:'2020-01-01'}, {dueDate:'2030-01-01'}];
process.stdout.write(JSON.stringify(tasks.map(t=>[m.exports.helper(t,[],60),c.point(t,[],60)])));"""
        result = subprocess.run(['node', '-e', js], input=script, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [[False,False],[False,False],[True,True],[False,False]])

    def test_new_ruleset_requires_known_bounded_policy(self):
        root = Path(__file__).resolve().parents[1]
        original = json.loads((root / 'migration_pipeline/batch_configs/formal_30_v4_semantic_closure_v1.json').read_text(encoding='utf-8'))
        validate_batch_config({**original, 'semantic_rule_set': 'residual_v2'})
        with self.assertRaisesRegex(ValueError, 'requires bounded_prepass_v1'):
            validate_batch_config({**original, 'semantic_rule_set': 'residual_v2', 'repair_policy': 'legacy'})
        with self.assertRaisesRegex(ValueError, 'Unsupported semantic_rule_set'):
            validate_batch_config({**original, 'semantic_rule_set': 'unknown'})

    def test_component_scopes_and_name_collisions_are_kept_separate(self):
        original = code().replace("const Chart =", 'function __sanComputed_point_0() {}\nconst Chart =')
        fixed = residual_semantics(original, repair=True)
        self.assertIn('function __sanComputed_point_0_(', fixed['code'])
        self.assertIn('function __sanComputed_point_0() {}', fixed['code'])

    def test_source_prop_array_becomes_nonempty_child_schema_not_dummy_parent_option(self):
        original = code()
        ssm = {'script': {'options': {'components': [{'source_name': 'SourceChart', 'registered_tag': 'chart-card',
            'inline_definition': {'source_code': "{props: ['values', 'width']}"}}]}}}
        fixed = residual_semantics(original, ssm, repair=True)
        self.assertIn('"values": san.DataTypes.any', fixed['code'])
        self.assertIn('"width": san.DataTypes.any', fixed['code'])
        self.assertNotIn('dataTypes: {}', fixed['code'])
        self.assertEqual(fixed['code'].count('dataTypes:'), 1)
        self.assertEqual(residual_semantics(fixed['code'], ssm, repair=True)['code'], fixed['code'])

    def test_source_typed_props_and_unknown_contracts(self):
        for props, expected in (("{width: Number}", 'san.DataTypes.number'),
                                ("{values: {type: Array, required: true}}", 'san.DataTypes.array.isRequired')):
            ssm = {'script': {'options': {'components': [{'registered_tag': 'chart-card',
                        'inline_definition': {'source_code': '{props: ' + props + '}'}}]}}}
            self.assertIn(expected, residual_semantics(code(), ssm, repair=True)['code'])
        for source in ('{props: {x: CustomType}}', '{props: [dynamic]}', '{props: {x: [String,Number]}}'):
            ssm = {'script': {'options': {'components': [{'registered_tag': 'chart-card',
                        'inline_definition': {'source_code': source}}]}}}
            self.assertNotIn('restored_inline_source_prop_schema', residual_semantics(code(), ssm, repair=True)['changes'])

    def test_unknown_registration_does_not_get_guessed_schema(self):
        ssm = {'script': {'options': {'components': [{'registered_tag': 'wrong-tag',
                    'inline_definition': {'source_code': "{props: ['width']}"}}]}}}
        self.assertNotIn('restored_inline_source_prop_schema', residual_semantics(code(), ssm, repair=True)['changes'])

    def test_focused_datatype_and_lifecycle_prompts_include_real_contract_and_call_chain(self):
        ssm = {'script': {'options': {'components': [{'registered_tag': 'chart-card',
                        'inline_definition': {'source_code': "{props: ['values']}"}}],
            'lifecycle_hooks': [{'vue_hook': 'mounted', 'san_hook': 'attached', 'body': '{this.initialize();}'}],
            'methods': [{'name': 'initialize', 'body_full': '{this.loadSettings();}'},
                        {'name': 'loadSettings', 'body_full': "{ localStorage.getItem('settings'); }"}]}}}
        for codes in (['missing_data_types'], ['missing_data_types', 'invalid_san_computed_instance_method_call'],
                      ['lifecycle_behavior_not_landed'], ['hidden_template_reactive_dependency']):
            prompt = build_repair_prompt(RepairPromptInput(ssm=ssm, current_code=code(),
                validation_errors=[{'code': c} for c in codes]))
            self.assertTrue(prompt.startswith('You are repairing a standalone San'))
            self.assertIn("['values']", prompt)
            self.assertIn("localStorage.getItem('settings')", prompt)
            self.assertNotIn('--- SSM ---', prompt)

    def test_real_stage_postprocessing_is_opt_in_and_recorded(self):
        class Client:
            def repair(self, request):
                return RepairResult(source_file='fixture', ssm=request.ssm, code=code(),
                    saved_file_path=request.output_file_path, provider='fake', model='test', usage={})
        with tempfile.TemporaryDirectory() as directory:
            for enabled in (False, True):
                result = RepairStage(Client()).run(RepairStageInput(ssm={'script': {'options': {}}},
                    generated_code=code(), output_file_path=str(Path(directory) / 'result.san'),
                    metadata={'skip_deterministic_prepass': True, 'semantic_rule_set': 'residual_v2' if enabled else 'bounded_v1'}))
                self.assertEqual('function __sanComputed_point_0' in result.repaired_code, enabled)
                if enabled:
                    self.assertIn('lifted_self_contained_computed_helper', result.raw_response['pipeline_postprocessing'])

    def test_malformed_code_stays_unchanged(self):
        original = code().replace('return width / 2;', 'return ( ;')
        self.assertEqual(residual_semantics(original, repair=True)['code'], original)


if __name__ == '__main__':
    unittest.main()
