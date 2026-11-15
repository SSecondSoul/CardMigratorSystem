"""Source-bound inline formatter recovery; no model requests or canonical writes."""
import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from migration_pipeline.utils.residual_semantics import residual_semantics
from migration_pipeline.stages.repair import RepairStage
from migration_pipeline.stages.repair import RepairStageInput
from migration_pipeline.repair_client import RepairResult
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.utils.repair_scheduler import candidate_gate
from migration_pipeline.utils.repair_prompt import RepairPromptInput, build_repair_prompt

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/experiments/snapshots/formal_30_v4_full_regression_v2_results_20261104_214821'
BODY = "const labels={high:'High',low:'Low'};return labels[value]||value;"


def fixture(body=BODY, prefix="const labels={high:'High',low:'Low'};", arrow='labels[value]||value',
            binding='label(item.level)', extra='', script_prefix=''):
    vue = '{methods:{label(value){' + body + '}}}'
    ssm = {'script': {'options': {'components': [{'registered_tag': 'panel-card',
        'inline_definition': {'source_code': vue}}]}}}
    code = '''<template><panel-card></panel-card></template><script>
const san=require('san');%s
const Panel=san.defineComponent({
template:`<div>{{%s}}</div>`,
computed:{label(){%s return value=>%s;},kept(){return 1;}},%s
});module.exports=san.defineComponent({components:{'panel-card':Panel}});
</script><style>.keep{color:red}</style>''' % (script_prefix, binding, prefix, arrow, extra)
    return code, ssm


class SourceInlineFormatterClosureTests(unittest.TestCase):
    def apply(self, pair):
        result = residual_semantics(pair[0], pair[1], repair=True)
        self.assertNotIn('error', result, result)
        return result

    def test_literal_lookup_and_source_method_are_preserved(self):
        code, ssm = fixture()
        result = self.apply((code, ssm))
        self.assertEqual(result['changes'], ['restored_source_inline_callable_formatters'])
        self.assertEqual(len(result['formatter_proofs']), 1)
        self.assertIn('label(value)', result['code'])
        self.assertIn("kept(){return 1;}", result['code'])
        self.assertEqual(result['code'].split('</script>')[1], code.split('</script>')[1])
        self.assertEqual(result['code'].split('<script>')[0], code.split('<script>')[0])
        self.assertIn('{{label(item.level)}}', result['code'])
        self.assertEqual(self.apply((result['code'], ssm))['code'], result['code'])

    def test_source_changes_arity_and_missing_registry_are_not_guessed(self):
        code, ssm = fixture()
        wrong = copy.deepcopy(ssm)
        wrong['script']['options']['components'][0]['inline_definition']['source_code'] = '{methods:{label(value){return value;}}}'
        for pair in ((code, wrong), (code, {}),
                     (code.replace("'panel-card':Panel", "'other':Panel"), ssm),
                     (code.replace('label(item.level)', 'label(item.level,other)'), ssm)):
            self.assertEqual(self.apply(pair)['code'], pair[0])

    def test_bare_references_events_and_script_computed_consumers_are_refused(self):
        for binding in ('label', 'label(item.level)+label', 'label(...items)'):
            pair = fixture(binding=binding)
            self.assertEqual(self.apply(pair)['code'], pair[0])
        for extra in ("other(){return this.data.get('label');},", "other(){return this.label;},",
                      'label(value){return value;},'):
            pair = fixture(extra=extra)
            self.assertEqual(self.apply(pair)['code'], pair[0])
        code, ssm = fixture()
        code = code.replace('<div>{{label', '<div on-click="label">{{label')
        self.assertEqual(self.apply((code, ssm))['code'], code)

    def test_unknown_effectful_or_nonliteral_prefixes_stay_unchanged(self):
        cases = [('const labels=external;', 'const labels=external;return labels[value]||value;'),
                 ('const labels=make();', 'const labels=make();return labels[value]||value;'),
                 ('let labels={};', 'let labels={};return labels[value]||value;')]
        for prefix, body in cases:
            pair = fixture(body=body, prefix=prefix)
            self.assertEqual(self.apply(pair)['code'], pair[0])
        pair = fixture(body='return this.data.get("labels")[value];', prefix='',
                       arrow='this.data.get("labels")[value]')
        self.assertEqual(self.apply(pair)['code'], pair[0])

    def test_duplicate_contracts_escaped_component_and_spread_are_refused(self):
        code, ssm = fixture()
        duplicate = copy.deepcopy(ssm)
        duplicate['script']['options']['components'] *= 2
        self.assertEqual(self.apply((code, duplicate))['code'], code)
        for other in (code.replace('module.exports=', 'consume(Panel);module.exports='),
                      code.replace('computed:{', '...unknown,computed:{'),
                      code.replace('kept(){return 1;}', 'label(){return 2;}')):
            self.assertEqual(self.apply((other, ssm))['code'], other)

    def test_date_formatter_retains_fallback_and_refuses_shadowed_date(self):
        body="if(!value)return 'none';const d=new Date(value);return `${d.getMonth()+1}/${d.getDate()}`;"
        pair=fixture(body=body,prefix='',arrow='{'+body+'}')
        result=self.apply(pair)
        self.assertEqual(len(result['formatter_proofs']),1)
        self.assertIn("return 'none'",result['code'])
        shadow=fixture(body=body,prefix='',arrow='{'+body+'}',script_prefix='const Date=unknown;')
        self.assertEqual(self.apply(shadow)['code'],shadow[0])

    def test_no_repair_mode_or_malformed_source_does_not_edit(self):
        code, ssm=fixture()
        self.assertEqual(residual_semantics(code,ssm)['code'],code)
        ssm['script']['options']['components'][0]['inline_definition']['source_code']='{broken:'
        self.assertEqual(self.apply((code,ssm))['code'],code)
        broken=code.replace('const Panel=', 'const bad-name=')
        result=residual_semantics(broken,ssm,repair=True)
        self.assertEqual(result['code'],broken)
        self.assertIn('error',result)

    def test_registration_requires_same_lexical_binding_and_consistent_alias_sources(self):
        code,ssm=fixture()
        shadow=code.replace('const Panel=', 'function hidden(){const Panel=').replace(
            '});module.exports=', '});}const Panel=external;module.exports=')
        self.assertEqual(self.apply((shadow,ssm))['code'],shadow)
        aliases=copy.deepcopy(ssm)
        aliases['script']['options']['components'].append({'registered_tag':'other-panel',
            'inline_definition':{'source_code':'{methods:{label(value){return 0;}}}'}})
        ambiguous=code.replace("'panel-card':Panel", "'panel-card':Panel,'other-panel':Panel")
        self.assertEqual(self.apply((ambiguous,aliases))['code'],ambiguous)

    def test_dollar_in_method_name_keeps_exact_token_identity(self):
        code,ssm=fixture()
        code=code.replace('label','label$')
        ssm['script']['options']['components'][0]['inline_definition']['source_code']=ssm['script']['options']['components'][0]['inline_definition']['source_code'].replace('label','label$')
        self.assertEqual(len(self.apply((code,ssm))['formatter_proofs']),1)

    def test_installed_san_executes_lookup_and_date_methods(self):
        body="if(!value)return 'none';const d=new Date(value);return `${d.getMonth()+1}/${d.getDate()}`;"
        fixed=self.apply(fixture(body=body,prefix='',arrow='{'+body+'}'))['code']
        script=fixed.split('<script>')[1].split('</script>')[0]
        js="""const fs=require('fs'),m={exports:{}};
new Function('require','module',fs.readFileSync(0,'utf8')+';module.exports=Panel;')(require,m);
const c=new m.exports();process.stdout.write(JSON.stringify([c.label(''),c.label('2026-11-10T12:00:00')]));"""
        p=subprocess.run(['node','-e',js],input=script,text=True,encoding='utf-8',capture_output=True,cwd=ROOT)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(json.loads(p.stdout),['none','11/10'])

    @classmethod
    def setUpClass(cls):
        summary=json.loads((SOURCE/'formal_30_v4_full_regression_v2_summary.json').read_text(encoding='utf-8'))
        sample=next(s for s in summary['samples'] if s['id']=='TaskManager')
        cls.state=json.loads((SOURCE/'repair_reports/complex'/Path(sample['report_file']).name).read_text(encoding='utf-8'))['state']
        cls.vue=SOURCE/'protocol/frozen/data/datasets/components/03_complex/TaskManager/vue/TaskManager.vue'

    def test_frozen_task_manager_all_five_render_formatters_close_but_other_errors_remain(self):
        result=self.apply((self.state['final_code'],self.state['ssm']))
        self.assertEqual(len(result['formatter_proofs']),5)
        val=ValidateStage()
        def assess(code):
            return {**self.state,'generated_code':code,'vue_file_path':str(self.vue),
                    **val.run(ValidateStageInput(generated_code=code,ssm=self.state['ssm'],vue_file_path=str(self.vue))).to_state_update()}
        before,after=assess(self.state['final_code']),assess(result['code'])
        codes={e['code'] for e in after['validation_errors']}
        self.assertEqual(len([e for e in after['validation_errors'] if not e['code'].startswith('source_dom_')
                              and e['code'] not in {'source_event_payload_not_landed','source_render_call_not_landed',
                                                   'source_render_dependency_not_landed','source_array_transaction_not_landed',
                                                   'source_child_factory_not_landed','source_child_watch_not_landed','source_native_drag_not_landed','source_parent_watch_not_landed','source_parent_watch_exception_policy_unproven','source_parent_watch_dynamic_key_unproven'}]),9)
        for code in ('source_child_factory_not_landed','source_child_watch_not_landed','source_native_drag_not_landed','source_parent_watch_not_landed','source_parent_watch_exception_policy_unproven','source_parent_watch_dynamic_key_unproven'):
            self.assertIn(code,codes)
            self.assertEqual([e for e in before['validation_errors'] if e['code']==code],
                             [e for e in after['validation_errors'] if e['code']==code])
        self.assertEqual([e for e in before['validation_errors'] if e['code']=='source_array_transaction_not_landed'],
                         [e for e in after['validation_errors'] if e['code']=='source_array_transaction_not_landed'])
        self.assertIn('source_array_transaction_not_landed',codes)
        self.assertEqual([e for e in before['validation_errors'] if e['code']=='source_render_dependency_not_landed'],
                         [e for e in after['validation_errors'] if e['code']=='source_render_dependency_not_landed'])
        self.assertIn('source_render_dependency_not_landed',codes)
        self.assertEqual([e for e in before['validation_errors'] if e['code']=='source_event_payload_not_landed'],
                         [e for e in after['validation_errors'] if e['code']=='source_event_payload_not_landed'])
        self.assertIn('source_event_payload_not_landed',codes)
        self.assertEqual([e for e in before['validation_errors'] if e['code']=='source_render_call_not_landed'],
                         [e for e in after['validation_errors'] if e['code']=='source_render_call_not_landed'])
        self.assertEqual(len([e for e in after['validation_errors'] if e['code']=='source_render_call_not_landed']),2)
        self.assertEqual([e for e in before['validation_errors'] if e['code'].startswith('source_dom_')],
                         [e for e in after['validation_errors'] if e['code'].startswith('source_dom_')])
        self.assertNotIn('invalid_san_inline_computed_method_invocation',codes)
        self.assertIn('invalid_san_multi_argument_fire',codes)
        self.assertIn('nested_state_mutation',codes)
        self.assertFalse(candidate_gate(before,after)['should_stop'])
        self.assertTrue(candidate_gate(after,before)['should_stop'])
        self.assertFalse(after['validation_passed'])
        planned,changes=RepairStage._deterministic_repair_plan(self.state['final_code'],before['validation_errors'],[],
            self.state['ssm'],str(self.vue),enable_residual_v2=True)
        self.assertEqual(self.apply((planned,self.state['ssm']))['code'],planned)
        self.assertEqual(self.apply((planned,self.state['ssm']))['changes'],[])
        self.assertIn(('residual_v2_ast','restored_source_inline_callable_formatters'),changes)
        legacy,_=RepairStage._deterministic_repair_plan(self.state['final_code'],before['validation_errors'],[],
            self.state['ssm'],str(self.vue))
        self.assertEqual(legacy,self.state['final_code'])

    def test_prompt_preserves_source_setup_fallback_and_date_contract(self):
        prompt=build_repair_prompt(RepairPromptInput(ssm=self.state['ssm'],current_code=self.state['final_code'],
            validation_errors=[{'code':'invalid_san_inline_computed_method_invocation'}]))
        self.assertTrue('retain literal lookup tables' in prompt)
        self.assertTrue('date/locale' in prompt)

    def test_stubbed_model_postprocessor_uses_the_same_source_rule(self):
        code,ssm=fixture()
        class Client:
            def repair(self,request):
                return RepairResult(code=code,saved_file_path=request.output_file_path,
                    source_file='',ssm=ssm,provider='stub',model='stub',raw_response={})
        with tempfile.TemporaryDirectory() as tmp:
            result=RepairStage(Client()).run(RepairStageInput(ssm=ssm,generated_code=code,
                output_file_path=str(Path(tmp)/'out.san'),
                metadata={'skip_deterministic_prepass':True,'semantic_rule_set':'residual_v2'}))
            self.assertEqual(result.repaired_code.rstrip(),self.apply((code,ssm))['code'].rstrip())
            self.assertIn('restored_source_inline_callable_formatters',result.raw_response['pipeline_postprocessing'])

    def test_gate_allows_partial_repair_but_rejects_new_method_or_unstructured_error(self):
        def state(methods):
            return {'generated_code': '<template><div></div></template><script>module.exports={};</script>',
                    'ssm': {}, 'validation_errors': [{'code': 'invalid_san_inline_computed_method_invocation',
                    'location':'script.template', 'message': ','.join(methods),
                    'details': {'contract':'inline_computed_calls_v1','affected_methods':methods}}]}
        self.assertFalse(candidate_gate(state(['A.x','B.y']),state(['B.y']))['should_stop'])
        self.assertTrue(candidate_gate(state(['A.x','B.y']),state(['B.y','B.new']))['should_stop'])
        self.assertTrue(candidate_gate(state(['B.y']),state(['A.x','B.y']))['should_stop'])
        before=state(['A.x','B.y'])
        del before['validation_errors'][0]['details']
        self.assertTrue(candidate_gate(before,state(['B.y']))['should_stop'])
