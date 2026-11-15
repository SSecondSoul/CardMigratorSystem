"""Coverage-aware gating, structural recovery and readonly helper closure."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from migration_pipeline.utils.inline_identifier_recovery import recover_inline_identifiers
from migration_pipeline.utils.stateful_helper_semantics import explicit_helper_dependencies
from migration_pipeline.utils.residual_semantics import residual_semantics
from migration_pipeline.utils.bounded_semantics import inspect_semantics
from migration_pipeline.utils.repair_scheduler import candidate_gate
from migration_pipeline.stages.repair import RepairStage, RepairStageInput
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.repair_client import RepairResult
from migration_pipeline.orchestrator import MigrationPipelineOrchestrator
from migration_pipeline.replay_formal_30_v4_repair_scheduling import ReplayGenerate, ReplayCandidate
from migration_pipeline.stages.generate import GenerateStageInput
from migration_pipeline.stages.visual_eval import VisualEvalStage


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/experiments/snapshots/formal_30_v4_semantic_closure_v3_results_20261103_175401'


def identifier_fixture():
    return '''<template><div></div></template><script>const san=require('san');
// const a-b = san.defineComponent({});
const literal = 'a-b';
const a-b = san.defineComponent({template: `<div>a-b</div>`});
module.exports=san.defineComponent({components:{'a-b':a-b}});
</script><style></style>''', {'script': {'options': {'components': [{'registered_tag': 'a-b'}]}}}


def helper_fixture(body=None, expression='x(i)', extra=''):
    body = body or "const values=this.data.get('values'); if(values.length<=1)return this.data.get('width')/2; return index/(values.length-1)*this.data.get('width');"
    return f'''<template><div></div></template><script>const san=require('san');
const Chart=san.defineComponent({{
template: `<svg><circle s-for="item, i in values" cx="{{{{{expression}}}}}"></circle></svg>`,
initData() {{return {{values:[1,2,3],width:600}};}},
computed: {{points() {{return this.data.get('values').map((v,i)=>this.x(i)).join(' ');}}}},
x(index) {{{body}}}, {extra}
}});
module.exports=san.defineComponent({{components:{{'chart-card':Chart}}}});
</script><style></style>'''


class CoverageHelperClosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = json.loads((SOURCE / 'repair_reports/complex/MonitoringDashboard_repair_history.json').read_text(encoding='utf-8'))['state']
        cls.entry = cls.source['repair_history'][0]
        cls.before = cls.source['generated_code']
        cls.after = cls.entry['repair_result']['repaired_code']
        cls.vue = SOURCE / 'protocol/frozen/data/datasets/components/03_complex/MonitoringDashboard/vue/MonitoringDashboard.vue'

    def states(self, code=None):
        before = {'generated_code': self.before, 'validation_errors': self.source['validation_errors'],
                  'visual_eval_passed': False, 'ssm': self.source['ssm']}
        after = {**before, 'generated_code': self.after if code is None else code,
                 'validation_errors': self.entry['validate_result']['validation_errors'], 'visual_eval_passed': True}
        return before, after

    def test_real_four_latent_findings_do_not_cause_rollback_or_disappear_as_errors(self):
        before, after = self.states()
        gate = candidate_gate(before, after)
        self.assertFalse(gate['should_stop'], gate)
        self.assertEqual(len(gate['newly_visible_preexisting_semantic_findings']), 4)
        self.assertEqual(len(after['validation_errors']), 7)
        self.assertEqual(gate['introduced_semantic_findings'], [])

    def test_changed_calculation_is_still_rejected_even_when_diagnostics_look_same(self):
        changed = self.after.replace('return (index * 800) / data.length + 2;', 'return (index * 800) / data.length + 3;')
        self.assertNotEqual(changed, self.after)
        gate = candidate_gate(*self.states(changed))
        self.assertTrue(gate['should_stop'])
        self.assertEqual(len(gate['introduced_semantic_findings']), 1)
        self.assertEqual(len(gate['newly_visible_preexisting_semantic_findings']), 3)

    def test_changed_template_call_unknown_source_or_unexplained_error_stays_rejected(self):
        changed = self.after.replace('cx="{{getX(idx)}}"', 'cx="{{getX(idx + 1)}}"')
        self.assertTrue(candidate_gate(*self.states(changed))['should_stop'])
        before, after = self.states()
        before['ssm'] = {}
        self.assertTrue(candidate_gate(before, after)['should_stop'])
        before, after = self.states()
        after['validation_errors'] = [*after['validation_errors'], {
            'code': 'hidden_template_reactive_dependency', 'location': 'other', 'message': 'new dependency'}]
        self.assertTrue(candidate_gate(before, after)['should_stop'])

    def test_recovery_only_changes_registered_code_positions_and_is_idempotent(self):
        code, ssm = identifier_fixture()
        recovered = recover_inline_identifiers(code, ssm)
        self.assertEqual(recovered['parse_status'], 'source_registered_recovery')
        self.assertIn("const literal = 'a-b'", recovered['code'])
        self.assertIn('// const a-b = san.defineComponent({});', recovered['code'])
        self.assertIn('template: `<div>a-b</div>`', recovered['code'])
        self.assertIn("'a-b':__sanInline_a_b", recovered['code'])
        self.assertEqual(recover_inline_identifiers(recovered['code'], ssm)['code'], recovered['code'])

    def test_recovery_refuses_unknown_tags_third_use_duplicate_and_other_syntax_error(self):
        code, ssm = identifier_fixture()
        self.assertEqual(recover_inline_identifiers(code)['code'], code)
        for bad in (code.replace('const literal', 'function other(){return a-b;} const literal'),
                    code.replace("'a-b':a-b", "'a-b':a-b,'a-b':a-b"),
                    code.replace('const literal', 'const broken = (; const literal')):
            self.assertEqual(recover_inline_identifiers(bad, ssm)['code'], bad)

    def test_recovery_collision_and_real_seven_source_components(self):
        code, ssm = identifier_fixture()
        collision = code.replace('const literal', 'const __sanInline_a_b = 1; const literal')
        self.assertEqual(recover_inline_identifiers(collision, ssm)['mappings'][0]['identifier'], '__sanInline_a_b_')
        recovered = recover_inline_identifiers(self.before, self.source['ssm'])
        self.assertEqual(len(recovered['mappings']), 7)
        self.assertEqual(recovered['parse_status'], 'source_registered_recovery')

    def test_helper_updates_every_template_and_computed_call_then_lifts_pure_math(self):
        original = helper_fixture()
        fixed = explicit_helper_dependencies(original)
        self.assertEqual(fixed['changes'], ['explicit_readonly_inline_helper_dependencies'])
        self.assertIn('x(i, values, width)', fixed['code'])
        self.assertIn("this.x(i, this.data.get('values'), this.data.get('width'))", fixed['code'])
        self.assertIn('x(index, __dep_values, __dep_width)', fixed['code'])
        self.assertEqual(explicit_helper_dependencies(fixed['code'])['code'], fixed['code'])
        lifted = residual_semantics(fixed['code'], repair=True)
        self.assertIn('lifted_self_contained_computed_helper', lifted['changes'])
        self.assertNotIn('=>this.x(', lifted['code'])

    def test_installed_san_computed_coordinates_follow_7_30_90_and_width_changes(self):
        fixed = residual_semantics(explicit_helper_dependencies(helper_fixture())['code'], repair=True)['code']
        script = fixed.split('<script>')[1].split('</script>')[0]
        js = r'''const fs=require('fs'),m={exports:{}};
new Function('require','module',fs.readFileSync(0,'utf8')+'\nmodule.exports=Chart;')(require,m);
const c=new m.exports(),rows=[];
for(const length of [0,1,7,30,90])for(const width of [600,1200]){
 const values=Array.from({length},(_,i)=>i);c.data.set('values',values);c.data.set('width',width);
 const line=c.data.get('points').split(' ').filter(x=>x!=='').map(Number);
 const dots=values.map((_,i)=>c.x(i,values,width));rows.push({length,width,line,dots});
}process.stdout.write(JSON.stringify(rows));'''
        result = subprocess.run(['node', '-e', js], input=script, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        for row in json.loads(result.stdout):
            self.assertEqual(row['line'], row['dots'])
            expected = [row['width']/2] if row['length'] == 1 else [i/(row['length']-1)*row['width'] for i in range(row['length'])]
            self.assertEqual(row['dots'], expected)

    def test_helper_refuses_writes_globals_parameter_mutation_and_ambiguous_uses(self):
        bodies = ["this.data.set('width', index); return this.data.get('width');",
                  "return this.data.get('values').pop();", "return this.data.get('width') + external;",
                  "return console.log(this.data.get('width'));", "return this.data.get(dynamic);",
                  "return Math.random() * this.data.get('width');"]
        for body in bodies:
            code = helper_fixture(body)
            self.assertEqual(explicit_helper_dependencies(code)['code'], code)
        for code in (helper_fixture(expression='x'), helper_fixture(expression='x(i, width)'),
                     helper_fixture(extra='other() {return this.x.bind(this);},'),
                     helper_fixture(extra='other() {return function(){return this.x(0);};},')):
            self.assertEqual(explicit_helper_dependencies(code)['code'], code)

    def test_dollar_named_helper_bare_reference_and_externally_used_component_are_refused(self):
        code = helper_fixture().replace('x(', 'x$(').replace('x(i)', 'x$(i)')
        self.assertTrue(explicit_helper_dependencies(code)['changes'])
        bare = code.replace('{{x$(i)}}', '{{x$}}')
        self.assertEqual(explicit_helper_dependencies(bare)['code'], bare)
        external = helper_fixture().replace('module.exports=', 'const external=Chart; module.exports=')
        self.assertEqual(explicit_helper_dependencies(external)['code'], external)

    def test_real_rejected_candidate_closes_without_overwriting_original(self):
        validated = self.entry['validate_result']
        fixed, rules = RepairStage._deterministic_repair_plan(self.after, validated['validation_errors'], [],
            self.source['ssm'], str(self.vue), enable_residual_v2=True)
        result = ValidateStage().run(ValidateStageInput(generated_code=fixed, ssm=self.source['ssm'], vue_file_path=str(self.vue)))
        self.assertTrue(result.validation_passed, result.validation_errors)
        labels = [x[1] for x in rules]
        for name in ('explicit_readonly_inline_helper_dependencies', 'lifted_self_contained_computed_helper',
                     'restored_source_loop_argument_binding', 'restored_source_watch_persistence',
                     'restored_unique_source_boolean_event_bindings'):
            self.assertIn(name, labels)
        self.assertIn("if (e.target === e.currentTarget)", fixed)

    def test_captured_candidate_can_continue_but_is_not_automatically_counted_passed(self):
        with tempfile.TemporaryDirectory() as directory:
            generate = ReplayGenerate(self.source, self.before, Path(directory)/'before.san')
            repair = ReplayCandidate(self.after, Path(directory)/'candidate.san')
            orchestrator = MigrationPipelineOrchestrator(generate, ValidateStage(), VisualEvalStage(), repair)
            with patch.object(RepairStage, '_deterministic_repair_plan', side_effect=lambda code,*_,**__: (code,[])):
                state = orchestrator.run_generate_validate_visual_eval_and_repair_loop(
                    GenerateStageInput(vue_file_path=str(self.vue), metadata={'repair_policy':'bounded_prepass_v1'}),
                    max_repair_rounds=1).state
            self.assertFalse(state['retained_previous_candidate'], state['repair_regression_gate'])
            self.assertFalse(state['final_passed'])
            self.assertEqual(state['generated_code'], self.after)
            self.assertEqual(state['llm_repair_calls'], 1)

    def test_actual_postprocessing_uses_same_closure_and_records_rules(self):
        source = self.source
        code = self.after
        class Client:
            def repair(self, request):
                return RepairResult(source_file='fixture', ssm=source['ssm'], code=code,
                    saved_file_path=request.output_file_path, provider='fixture', model='captured', usage={})
        with tempfile.TemporaryDirectory() as directory:
            result = RepairStage(Client()).run(RepairStageInput(ssm=self.source['ssm'], generated_code=self.before,
                vue_file_path=str(self.vue), output_file_path=str(Path(directory)/'candidate.san'),
                metadata={'skip_deterministic_prepass':True,'semantic_rule_set':'residual_v2'}))
            self.assertIn('explicit_readonly_inline_helper_dependencies', result.raw_response['pipeline_postprocessing'])
            checked = ValidateStage().run(ValidateStageInput(generated_code=result.repaired_code,
                ssm=self.source['ssm'], vue_file_path=str(self.vue)))
            self.assertTrue(checked.validation_passed, checked.validation_errors)

    def test_watch_visibility_requires_unchanged_parent_and_real_source_evidence(self):
        before, after = self.states()
        before['vue_file_path'] = str(self.vue)
        result = ValidateStage().run(ValidateStageInput(generated_code=self.after,
            ssm=self.source['ssm'], vue_file_path=str(self.vue)))
        after['validation_errors'] = result.validation_errors
        gate = candidate_gate(before, after)
        self.assertFalse(gate['should_stop'])
        self.assertEqual(len(gate['newly_visible_preexisting_semantic_findings']), 5)
        changed = self.after.replace("const saved = localStorage.getItem('dashboard_settings');",
                                     "const saved = localStorage.getItem('other_settings');")
        self.assertNotEqual(changed, self.after)
        gate = candidate_gate(before, {**after, 'generated_code': changed})
        self.assertTrue(gate['should_stop'])
        self.assertIn('source_watch_persistence_not_landed', [i['code'] for i in gate['introduced_semantic_findings']])

    def test_template_failure_does_not_hide_independent_watch_findings(self):
        recovered = recover_inline_identifiers(self.before, self.source['ssm'])['code']
        findings = inspect_semantics(recovered, self.vue.read_text(encoding='utf-8'), ssm=self.source['ssm'])
        self.assertIn('source_watch_persistence_not_landed', [i['code'] for i in findings['findings']])

    def test_boolean_event_rule_requires_boolean_default_and_preserves_backdrop_guard(self):
        vue = self.vue.read_text(encoding='utf-8')
        fixed = inspect_semantics(self.after, vue, repair=True, ssm=self.source['ssm'])
        self.assertIn('restored_unique_source_boolean_event_bindings', fixed['changes'])
        self.assertIn('on-click="closeModal"', fixed['code'])
        self.assertIn('if (e.target === e.currentTarget)', fixed['code'])
        wrong = self.after.replace('showSettings: false', 'showSettings: 0')
        refused = inspect_semantics(wrong, vue, repair=True, ssm=self.source['ssm'])
        self.assertIn('on-click="showSettings = true"', refused['code'])
        self.assertNotIn('restored_unique_source_boolean_event_bindings', refused['changes'])

    def test_binding_only_rule_does_not_discard_extra_handler_side_effects(self):
        wrong = self.after.replace('onKPIClick(kpi) {', 'onKPIClick(kpi) { this.extraEffect();')
        fixed = inspect_semantics(wrong, self.vue.read_text(encoding='utf-8'), repair=True, ssm=self.source['ssm'])
        self.assertIn('on-click="onKPIClick"', fixed['code'])
        self.assertIn('this.extraEffect()', fixed['code'])
        self.assertNotIn('restored_source_loop_argument_binding', fixed['changes'])

    def test_dependency_parameter_collision_is_avoided(self):
        original = helper_fixture("const __dep_width=2; return index+__dep_width+this.data.get('width');")
        fixed = explicit_helper_dependencies(original)
        self.assertIn('x(index, __dep_width_)', fixed['code'])
        self.assertIn('const __dep_width=2', fixed['code'])

    def test_single_object_property_reference_is_not_proof_of_private_registration(self):
        original = helper_fixture().replace("module.exports=san.defineComponent({components:{'chart-card':Chart}})",
                                             'module.exports={publicConstructor:Chart}')
        self.assertIn('publicConstructor', original)
        self.assertEqual(explicit_helper_dependencies(original)['code'], original)


if __name__ == '__main__':
    unittest.main()
