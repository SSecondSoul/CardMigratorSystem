"""Scope-aware persistence closure, refusal cases and actual scheduler integration."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from migration_pipeline.utils.bounded_semantics import inspect_semantics
from migration_pipeline.utils.repair_scheduler import candidate_gate
from migration_pipeline.utils.repair_prompt import RepairPromptInput, build_repair_prompt
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.stages.repair import RepairStage, RepairStageInput
from migration_pipeline.repair_client import RepairResult
from migration_pipeline.orchestrator import MigrationPipelineOrchestrator
from migration_pipeline.replay_formal_30_v4_repair_scheduling import ReplayGenerate
from migration_pipeline.stages.generate import GenerateStageInput
from migration_pipeline.stages.visual_eval import VisualEvalStage

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/experiments/snapshots/formal_30_v4_semantic_closure_v5_results_20261104_150846'
CODE = 'source_watch_persistence_not_landed'
RULE = 'restored_source_watch_persistence'


def fixture():
    vue = '''<template><div></div></template><script>export default {
data(){return {settings:{enabled:false},timer:null};},
watch:{settings:{handler(value){
  if(value.enabled&&!this.timer){this.start();}else if(!value.enabled&&this.timer){this.stop();}
  localStorage.setItem('preferences',JSON.stringify(value));
},deep:true}},methods:{start(){},stop(){}}
}</script>'''
    san = '''<template><div></div></template><script>const san=require('san');
module.exports=san.defineComponent({initData(){return {settings:{enabled:false},timer:null};},
inited(){this.watch('settings',(next,previous)=>{
  if(next.enabled&&!this.data.get('timer')){this.start();}else if(!next.enabled&&this.data.get('timer')){this.stop();}
});},start(){},stop(){}});</script><style></style>'''
    ssm = {'script': {'options': {'data': [{'name': 'settings'}, {'name': 'timer'}]}}}
    return san, vue, ssm


class WatchPersistenceClosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = json.loads((SOURCE / 'repair_reports/complex/MonitoringDashboard_repair_history.json').read_text(encoding='utf-8'))['state']
        cls.vue_path = SOURCE / 'protocol/frozen/data/datasets/components/03_complex/MonitoringDashboard/vue/MonitoringDashboard.vue'
        cls.vue = cls.vue_path.read_text(encoding='utf-8')
        cls.code = cls.state['final_code']

    def apply(self, san=None, vue=None, repair=True):
        a, b, ssm = fixture()
        return inspect_semantics(san if san is not None else a, vue if vue is not None else b, repair=repair, ssm=ssm)

    def test_renamed_current_and_unused_previous_are_restored_without_parameter_changes(self):
        result = self.apply()
        self.assertNotIn('error', result)
        self.assertEqual(result['changes'], [RULE])
        self.assertIn('(next,previous)=>', result['code'])
        self.assertIn('JSON.stringify(next)', result['code'])
        self.assertEqual(result['watcher_contracts'][0]['source_parameter'], 'value')
        self.assertTrue(result['watcher_contracts'][0]['repairable'])

    def test_single_renamed_parameter_and_function_listener_are_supported(self):
        san, _, _ = fixture()
        for candidate in (san.replace('(next,previous)=>', 'next=>'),
                          san.replace('(next,previous)=>', 'function(next,previous)')):
            with self.subTest(candidate=candidate):
                self.assertEqual(self.apply(san=candidate)['changes'], [RULE])

    def test_no_parameter_local_current_value_is_supported(self):
        san, _, _ = fixture()
        candidate = san.replace('(next,previous)=>{', "()=>{const next=this.data.get('settings');")
        self.assertEqual(self.apply(san=candidate)['changes'], [RULE])

    def test_diagnostic_without_repair_keeps_exact_input(self):
        san, _, _ = fixture()
        result = self.apply(repair=False)
        self.assertEqual(result['code'], san)
        self.assertIn(CODE, [f['code'] for f in result['findings']])

    def test_existing_correct_write_is_a_fixed_point_without_duplicates(self):
        fixed = self.apply()['code']
        self.assertEqual(self.apply(san=fixed)['code'], fixed)
        self.assertEqual(self.apply(san=fixed)['findings'], [])
        self.assertEqual(self.apply(san=fixed)['watcher_contracts'][0]['status'], 'trailing_write_present')
        self.assertEqual(fixed.count('localStorage.setItem'), 1)

    def test_used_old_value_is_reported_but_not_automatically_repaired(self):
        san, _, _ = fixture()
        bad = san.replace('if(next.enabled', 'if(previous.enabled&&next.enabled')
        result = self.apply(san=bad)
        self.assertEqual(result['code'], bad)
        self.assertIn(CODE, [f['code'] for f in result['findings']])
        self.assertEqual(result['watcher_contracts'][0]['reason'], 'old_value_parameter_used')

    def test_altered_conditions_extra_effects_and_other_write_remain_diagnostics(self):
        san, _, _ = fixture()
        for extra in ('this.stop();', "localStorage.setItem('other','value');", 'return;',
                      'const nested=()=>next;', 'eval("next=other");'):
            candidate = san.replace('if(next.enabled', extra + 'if(next.enabled')
            with self.subTest(extra=extra):
                result = self.apply(san=candidate)
                self.assertEqual(result['code'], candidate)
                self.assertIn(CODE, [f['code'] for f in result['findings']])
        bad = san.replace('if(next.enabled', 'if(!next.enabled')
        self.assertEqual(self.apply(san=bad)['code'], bad)

    def test_complex_signatures_async_and_parameter_reassignment_are_not_guessed(self):
        san, _, _ = fixture()
        cases = [san.replace('(next,previous)', '(next={},previous)'),
                 san.replace('(next,previous)', '({enabled},previous)'),
                 san.replace('(next,previous)=>', 'async (next,previous)=>'),
                 san.replace('if(next.enabled', 'next={};if(next.enabled')]
        for candidate in cases:
            with self.subTest(candidate=candidate):
                result = self.apply(san=candidate)
                self.assertEqual(result['code'], candidate)
                self.assertIn(CODE, [f['code'] for f in result['findings']])

    def test_target_global_shadow_is_reported_but_never_gets_a_guessed_write(self):
        san, _, _ = fixture()
        for candidate in (san.replace('module.exports', 'const localStorage={};module.exports'),
                          san.replace('(next,previous)', '(next,JSON)'),
                          san.replace('if(next.enabled', 'const JSON={};if(next.enabled')):
            result = self.apply(san=candidate)
            self.assertEqual(result['code'], candidate)
            self.assertIn(CODE, [f['code'] for f in result['findings']])

    def test_shadowed_source_storage_is_not_assumed_to_be_browser_persistence(self):
        san, vue, _ = fixture()
        changed = vue.replace('export default', 'const localStorage={};export default')
        self.assertEqual(self.apply(vue=changed)['code'], san)
        self.assertNotIn(RULE, self.apply(vue=changed)['changes'])

    def test_scoped_renaming_does_not_rewrite_property_keys_or_capture_free_variables(self):
        san, vue, _ = fixture()
        # Source's free `next` must not become the target current-value binding.
        changed = vue.replace('if(value.enabled', 'if(next&&value.enabled')
        self.assertEqual(self.apply(vue=changed)['code'], san)
        changed = san.replace('if(next.enabled', 'if(next.value&&next.enabled')
        self.assertEqual(self.apply(san=changed)['code'], changed)

    def test_installed_san_watcher_writes_only_when_settings_changes(self):
        fixed = self.apply()['code'].split('<script>')[1].split('</script>')[0]
        js = '''const fs=require('fs'),san=require('san'),m={exports:{}},writes=[];
global.localStorage={setItem:(key,value)=>writes.push([key,JSON.parse(value)])};
new Function('require','module',fs.readFileSync(0,'utf8'))(require,m);
const c=new m.exports();const before=writes.length;
c.data.set('settings',{enabled:true});c.data.set('settings',{enabled:false});
process.stdout.write(JSON.stringify({before,writes}));'''
        proc = subprocess.run(['node', '-e', js], cwd=ROOT, input=fixed, text=True, encoding='utf-8', capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout), {'before': 0, 'writes': [
            ['preferences', {'enabled': True}], ['preferences', {'enabled': False}]]})

    def test_real_frozen_candidate_only_adds_the_proven_write(self):
        result = inspect_semantics(self.code, self.vue, repair=True, ssm=self.state['ssm'])
        self.assertEqual(result['changes'], [RULE])
        self.assertEqual(result['code'].count('localStorage.setItem'), self.code.count('localStorage.setItem') + 1)
        # Exact insertion only; all original HTML/script/CSS bytes otherwise remain.
        added = '\nlocalStorage.setItem("dashboard_settings", JSON.stringify(newValue));\n'
        self.assertEqual(result['code'].replace(added, '', 1), self.code)
        self.assertEqual(inspect_semantics(result['code'], self.vue, ssm=self.state['ssm'])['findings'], [])

    def test_validation_prepass_and_reverse_gate_use_the_same_contract(self):
        def assess(code):
            v = ValidateStage().run(ValidateStageInput(generated_code=code, ssm=self.state['ssm'], vue_file_path=str(self.vue_path)))
            return {'generated_code': code, 'ssm': self.state['ssm'], 'vue_file_path': str(self.vue_path),
                    'validation_errors': v.validation_errors}
        before = assess(self.code)
        fixed, rules = RepairStage._deterministic_repair_plan(self.code, before['validation_errors'], [],
            self.state['ssm'], str(self.vue_path), enable_residual_v2=True)
        self.assertIn(RULE, [r for _, r in rules])
        after = assess(fixed)
        self.assertEqual(after['validation_errors'], [])
        self.assertFalse(candidate_gate(before, after)['should_stop'])
        self.assertTrue(candidate_gate(after, before)['should_stop'])

    def test_unknown_effect_diagnostic_cannot_be_hidden_by_lower_error_counts(self):
        san, vue, ssm = fixture()
        fixed = self.apply()['code']
        broken = san.replace('if(next.enabled', 'this.stop();if(next.enabled')
        good = {'generated_code': fixed, 'ssm': ssm, 'vue_source': vue, 'validation_errors': []}
        bad = {**good, 'generated_code': broken, 'validation_errors': self.apply(san=broken, repair=False)['findings']}
        self.assertTrue(candidate_gate(good, bad)['should_stop'])

    def test_model_return_postprocessing_uses_the_same_rule_and_full_prompt_evidence(self):
        original = self.code
        class Client:
            def repair(self, request):
                return RepairResult(code=original, saved_file_path=request.output_file_path,
                    source_file='', ssm={}, provider='stub', model='stub', raw_response={})
        with tempfile.TemporaryDirectory() as directory:
            result = RepairStage(Client()).run(RepairStageInput(ssm=self.state['ssm'], generated_code=self.code,
                vue_file_path=str(self.vue_path), output_file_path=str(Path(directory) / 'candidate.san'),
                validation_errors=[{'code': CODE}], metadata={'skip_deterministic_prepass': True, 'semantic_rule_set': 'residual_v2'}))
            self.assertIn(RULE, result.raw_response['pipeline_postprocessing'])
            self.assertIn('localStorage.setItem', result.repair_prompt)
            self.assertIn('newVal', result.repair_prompt)
            self.assertIn('unused old-value parameter', result.repair_prompt)

    def test_actual_scheduler_closes_frozen_gap_without_any_model_request(self):
        class NoModel:
            def repair(self, request):
                raise AssertionError('No model request is authorized in offline verification')
        with tempfile.TemporaryDirectory() as directory:
            generate = ReplayGenerate(self.state, self.code, Path(directory) / 'source.san')
            orchestrator = MigrationPipelineOrchestrator(generate, ValidateStage(), VisualEvalStage(), RepairStage(NoModel()))
            result = orchestrator.run_generate_validate_visual_eval_and_repair_loop(
                GenerateStageInput(vue_file_path=str(self.vue_path), metadata={
                    'repair_policy': 'bounded_prepass_v1', 'semantic_rule_set': 'residual_v2'}), max_repair_rounds=3).state
            self.assertTrue(result['final_passed'], result['validation_errors'])
            self.assertEqual(result['llm_repair_calls'], 0)
            self.assertEqual(result['deterministic_steps'], 1)


if __name__ == '__main__':
    unittest.main()
