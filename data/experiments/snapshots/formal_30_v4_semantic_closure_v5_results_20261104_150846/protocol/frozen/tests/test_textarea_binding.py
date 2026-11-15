"""Textarea v-model must become a value binding, not literal editor content."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from migration_pipeline.utils.textarea_binding import textarea_binding
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.stages.repair import RepairStage, RepairStageInput
from migration_pipeline.repair_client import RepairResult
from migration_pipeline.utils.repair_scheduler import candidate_gate


def component(template, inline=False):
    script = "const san=require('san');\n"
    if inline:
        script += 'const child=san.defineComponent({template: `' + template + '`, initData(){return {form:{description:""}};}});\n'
        outer = '<div></div>'
    else:
        outer = template
    script += "module.exports=san.defineComponent({dataTypes:{},initData(){return {form:{description:''}};}});"
    return '<template>' + outer + '</template><script>' + script + '</script><style></style>'


class TextareaBindingTests(unittest.TestCase):
    def test_parent_and_inline_are_fixed_and_idempotent(self):
        for inline in (False, True):
            original = component('<textarea rows="3" placeholder="说明">{= form.description =}</textarea>', inline)
            result = textarea_binding(original, True)
            self.assertEqual(result['changes'], ['normalized_textarea_value_binding'])
            self.assertIn('<textarea rows="3" placeholder="说明" value="{= form.description =}"></textarea>', result['code'])
            self.assertEqual(textarea_binding(result['code'], True)['code'], result['code'])

    def test_validator_rejects_original_and_accepts_fixed(self):
        original = component('<textarea>{= form.description =}</textarea>', True)
        before = ValidateStage().run(ValidateStageInput(generated_code=original, compile_check=False))
        self.assertIn('invalid_san_textarea_binding', {e['code'] for e in before.validation_errors})
        fixed = textarea_binding(original, True)['code']
        after = ValidateStage().run(ValidateStageInput(generated_code=fixed, compile_check=False))
        self.assertNotIn('invalid_san_textarea_binding', {e['code'] for e in after.validation_errors})

    def test_literal_text_and_one_way_content_are_not_erased(self):
        for body in ('说明文字', '{{ form.description }}', '用户输入的英文 defaultView'):
            original = component('<textarea>' + body + '</textarea>', True)
            self.assertEqual(textarea_binding(original, True)['code'], original)

    def test_mixed_content_and_conflicting_value_are_not_guessed(self):
        for textarea in ('<textarea>说明 {= form.description =}</textarea>',
                         '<textarea value="fixed">{= form.description =}</textarea>',
                         '<textarea>{= makeDescription() =}</textarea>'):
            original = component(textarea)
            result = textarea_binding(original, True)
            self.assertEqual(result['code'], original)
            self.assertEqual(len(result['findings']), 1)
            self.assertFalse(result['findings'][0]['repairable'])

    def test_script_examples_and_comments_are_not_templates(self):
        original = component('<div></div>').replace("const san=require('san');", "const san=require('san');\nconst sample='<textarea>{= example =}</textarea>';\n")
        original = original.replace('<div></div>', '<div><!-- <textarea>{= comment =}</textarea> --></div>')
        result = textarea_binding(original, True)
        self.assertEqual(result['code'], original)
        self.assertEqual(result['findings'], [])

    def test_quoted_greater_than_unicode_and_newline_offsets(self):
        original = component('说明🌟<textarea placeholder="a > b" rows="3">\n {= form.description =}\n</textarea>', True)
        fixed = textarea_binding(original, True)['code']
        self.assertIn('说明🌟<textarea placeholder="a > b" rows="3" value="{= form.description =}"></textarea>', fixed)

    def test_unrelated_malformed_template_does_not_trigger_broad_html_repair(self):
        original = component('<div><textarea>{= form.description =}</textarea>', True)
        fixed = textarea_binding(original, True)
        self.assertIn('<div><textarea value="{= form.description =}"></textarea>', fixed['code'])
        self.assertEqual(fixed['changes'], ['normalized_textarea_value_binding'])
        # This rule does not add a missing </div> or rewrite any other HTML.
        self.assertEqual(original.count('</div>'), fixed['code'].count('</div>'))

    def test_frozen_task_manager_real_inline_template_is_detected(self):
        root = Path(__file__).resolve().parents[1]
        original = (root / 'data/experiments/snapshots/formal_30_v4_semantic_closure_v2_results_20261103_160541/pipeline/complex/TaskManager_normalized_1_normalized_2_repaired_repaired.san').read_text(encoding='utf-8')
        result = textarea_binding(original, True)
        self.assertEqual(result['changes'], ['normalized_textarea_value_binding'])
        self.assertEqual(len(result['findings']), 1)
        self.assertIn('value="{= formData.description =}"', result['code'])

    def test_actual_san_parser_sees_a_two_way_value_and_no_literal_code(self):
        fixed = textarea_binding(component('<textarea>{= form.description =}</textarea>'), True)['code']
        template = fixed.split('<template>', 1)[1].split('</template>', 1)[0]
        js = """const fs=require('fs'), san=require('san'); const html=fs.readFileSync(0,'utf8');
const node=san.parseTemplate(html).children[0]; process.stdout.write(JSON.stringify({props:node.props,children:node.children}));"""
        result = subprocess.run(['node', '-e', js], input=template, text=True, encoding='utf-8', capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        parsed = json.loads(result.stdout)
        value = next(p for p in parsed['props'] if p['name'] == 'value')
        self.assertTrue(value['x'])
        self.assertEqual([p['value'] for p in value['expr']['paths']], ['form', 'description'])
        self.assertFalse(parsed['children'])

    def test_repair_stage_and_gate_record_and_protect_the_fix(self):
        original = component('<textarea>{= form.description =}</textarea>')
        class Client:
            def repair(self, request):
                return RepairResult(source_file='fixture', ssm=request.ssm, code=original,
                    saved_file_path=request.output_file_path, provider='fake', model='test', usage={})
        with tempfile.TemporaryDirectory() as directory:
            repaired = RepairStage(Client()).run(RepairStageInput(ssm={'script': {'options': {}}},
                generated_code=original, output_file_path=str(Path(directory) / 'fixed.san'),
                metadata={'skip_deterministic_prepass': True}))
        self.assertIn('normalized_textarea_value_binding', repaired.raw_response['pipeline_postprocessing'])
        errors = [{'code': 'invalid_san_textarea_binding', 'message': 'literal two-way marker', 'location': 'template'}]
        gate = candidate_gate({'generated_code': repaired.repaired_code, 'validation_errors': [], 'ssm': {}},
                              {'generated_code': original, 'validation_errors': errors, 'ssm': {}})
        self.assertTrue(gate['should_stop'])


if __name__ == '__main__':
    unittest.main()
