"""Source wrapper phase/count contract: detection, bounded repair and gating."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from migration_pipeline.utils.bounded_semantics import inspect_semantics
from migration_pipeline.utils.repair_prompt import RepairPromptInput, build_repair_prompt
from migration_pipeline.utils.repair_scheduler import candidate_gate
from migration_pipeline.stages.repair import RepairStage, RepairStageInput
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.repair_client import RepairResult
from migration_pipeline.orchestrator import MigrationPipelineOrchestrator
from migration_pipeline.replay_formal_30_v4_repair_scheduling import ReplayGenerate
from migration_pipeline.stages.generate import GenerateStageInput
from migration_pipeline.stages.visual_eval import VisualEvalStage


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/experiments/snapshots/formal_30_v4_semantic_closure_v4_results_20261103_204227'
CODE = 'source_startup_phase_not_landed'


def fixture():
    vue = '''<template><div></div></template><script>export default {
data(){return {runs:0,settings:{},watchCalls:0};},
watch:{settings:{handler(v){},deep:true}},
mounted(){this.bootstrap();this.ready();},
methods:{bootstrap(){this.seed();this.load();}, seed(){this.runs+=1;},load(){},ready(){}}
}</script>'''
    code = '''<template><div></div></template><script>const san=require('san');
const child=san.defineComponent({inited(){this.kickoff();},kickoff(){}});
module.exports=san.defineComponent({
initData(){return {runs:0,settings:{},watchCalls:0};},
inited(){this.watch('settings', v=>{this.data.set('watchCalls',this.data.get('watchCalls')+1);});this.kickoff();},
attached(){this.kickoff();this.ready();},
kickoff(){this.seed();this.load();},seed(){this.data.set('runs',this.data.get('runs')+1);},load(){},ready(){}
});</script><style></style>'''
    return code, vue


class StartupPhaseClosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = json.loads((SOURCE / 'repair_reports/complex/MonitoringDashboard_repair_history.json').read_text(encoding='utf-8'))['state']
        cls.vue_path = SOURCE / 'protocol/frozen/data/datasets/components/03_complex/MonitoringDashboard/vue/MonitoringDashboard.vue'
        cls.vue = cls.vue_path.read_text(encoding='utf-8')
        cls.code = cls.state['generated_code']

    def test_frozen_automatic_pass_now_reports_proven_duplicate_without_modification(self):
        result = inspect_semantics(self.code, self.vue, ssm=self.state['ssm'])
        self.assertEqual(result['code'], self.code)
        self.assertEqual([f['code'] for f in result['findings']], [CODE])
        self.assertEqual(result['startup_contracts'][0]['inited_direct_calls'], 1)
        self.assertEqual(result['startup_contracts'][0]['attached_direct_calls'], 1)
        self.assertTrue(result['startup_contracts'][0]['repairable'])

    def test_frozen_repair_only_removes_early_call_preserving_watch_children_and_late_hook(self):
        fixed = inspect_semantics(self.code, self.vue, repair=True, ssm=self.state['ssm'])
        self.assertEqual(fixed['changes'], ['removed_source_proven_duplicate_startup'])
        self.assertEqual(fixed['code'], self.code.replace('this.initDataImpl();', '', 1))
        self.assertEqual(fixed['code'].split('module.exports')[0], self.code.split('module.exports')[0])
        self.assertEqual(inspect_semantics(fixed['code'], self.vue, ssm=self.state['ssm'])['findings'], [])
        self.assertEqual(inspect_semantics(fixed['code'], self.vue, repair=True, ssm=self.state['ssm'])['code'], fixed['code'])

    def test_frozen_first_repair_is_relocated_not_duplicated(self):
        first = self.state['repair_history'][0]['repair_result']['repaired_code']
        result = inspect_semantics(first, self.vue, repair=True, ssm=self.state['ssm'])
        self.assertIn('relocated_source_proven_startup_wrapper', result['changes'])
        self.assertEqual(result['code'].count('this.initDataImpl();'), 1)
        after = inspect_semantics(result['code'], self.vue, ssm=self.state['ssm'])
        self.assertEqual(after['findings'], [])
        self.assertEqual(after['startup_contracts'][0]['inited_direct_calls'], 0)
        self.assertEqual(after['startup_contracts'][0]['attached_direct_calls'], 1)

    def test_generic_source_method_and_different_alias_not_component_specific(self):
        code, vue = fixture()
        fixed = inspect_semantics(code, vue, repair=True)
        self.assertEqual(fixed['changes'], ['removed_source_proven_duplicate_startup'])
        self.assertEqual(fixed['code'].count('this.kickoff();'), 2)  # child + parent attached
        self.assertEqual(inspect_semantics(fixed['code'], vue)['findings'], [])

    def test_real_san_constructor_keeps_watcher_and_runs_initializer_once_after_attach_hook(self):
        code, vue = fixture()
        fixed = inspect_semantics(code, vue, repair=True)['code']
        script = fixed.split('<script>')[1].split('</script>')[0]
        js = r'''const fs=require('fs'),m={exports:{}};
new Function('require','module',fs.readFileSync(0,'utf8'))(require,m);
const c=new m.exports(),before=c.data.get('runs');c.attached();
c.data.set('settings',{changed:true});
process.stdout.write(JSON.stringify({before,after:c.data.get('runs'),watch:c.data.get('watchCalls')}));'''
        result = subprocess.run(['node','-e',js],input=script,capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {'before':0,'after':1,'watch':1})

    def test_unknown_early_effect_or_non_suffix_is_diagnosed_but_not_removed(self):
        code, vue = fixture()
        for bad in (code.replace("inited(){this.watch", "inited(){this.audit();this.watch"),
                    code.replace('});this.kickoff();}', '});this.kickoff();this.audit();}')):
            self.assertNotEqual(code, bad)
            result = inspect_semantics(bad, vue, repair=True)
            self.assertEqual(result['code'], bad)
            self.assertIn(CODE, [f['code'] for f in result['findings']])

    def test_ambiguous_alias_or_dynamic_access_spreads_and_early_source_hooks_refuse_repair(self):
        code, vue = fixture()
        candidates = [code.replace('kickoff(){this.seed();this.load();}', 'other(){this.seed();this.load();},kickoff(){this.seed();this.load();}'),
            code.replace('ready(){}', 'ready(){this[name]();}'),
            code.replace('initData(){return', '...external,initData(){return')]
        for bad in candidates:
            self.assertEqual(inspect_semantics(bad, vue, repair=True)['code'], bad)
        for changed in (vue.replace('mounted(){', 'created(){},mounted(){'),
                        vue.replace('this.bootstrap();this.ready();', 'this.bootstrap();this.bootstrap();this.ready();'),
                        vue.replace('this.seed();this.load();', 'if(this.runs){this.seed();}this.load();'),
                        vue.replace('bootstrap(){', 'async bootstrap(){'),
                        vue.replace('<div></div>', '<div @click="bootstrap"></div>')):
            self.assertEqual(inspect_semantics(code, changed, repair=True)['code'], code)

    def test_guarded_extra_or_multiple_calls_are_never_blindly_deleted(self):
        code, vue = fixture()
        for bad in (code.replace('});this.kickoff();}', '});if(true){this.kickoff();}}'),
                    code.replace('});this.kickoff();}', '});this.kickoff();this.kickoff();}'),
                    code.replace('attached(){this.kickoff();this.ready();}', 'attached(){this.ready();this.kickoff();}'),
                    code.replace('attached(){this.kickoff();', 'attached(){this.kickoff();this.kickoff();'),
                    code.replace('ready(){}', 'ready(){this.kickoff();}'),
                    code.replace('initData(){return', 'compiled(){},initData(){return')):
            self.assertNotEqual(code, bad)
            self.assertEqual(inspect_semantics(bad, vue, repair=True)['code'], bad)

    def test_watch_unknown_options_or_duplicate_registrations_refuse_repair(self):
        code, vue = fixture()
        for bad in (code.replace("'settings', v=>", "'other', v=>"),
                    code.replace("'settings', v=>", "'settings', async v=>"),
                    code.replace("inited(){this.watch", "inited(){this.watch('settings',v=>{});this.watch"),
                    code.replace('});this.kickoff();}', '}, {immediate:true});this.kickoff();}')):
            self.assertEqual(inspect_semantics(bad, vue, repair=True)['code'], bad)
        self.assertEqual(inspect_semantics(code, vue.replace('deep:true', 'deep:true,immediate:true'), repair=True)['code'], code)

    def test_missing_source_and_invalid_source_are_fail_closed(self):
        code, _ = fixture()
        for vue in ('', '<template><div></template><script>bad</script>'):
            self.assertEqual(inspect_semantics(code, vue, repair=True)['code'], code)

    def test_validator_gate_and_deterministic_stage_form_a_closed_loop(self):
        def validate(code):
            r = ValidateStage().run(ValidateStageInput(generated_code=code,ssm=self.state['ssm'],vue_file_path=str(self.vue_path)))
            return {'generated_code':code,'ssm':self.state['ssm'],'vue_file_path':str(self.vue_path),
                'validation_errors':r.validation_errors,'validation_passed':r.validation_passed,'visual_eval_passed':True}
        before = validate(self.code)
        self.assertEqual([e['code'] for e in before['validation_errors']], [CODE])
        fixed, repairs = RepairStage._deterministic_repair_plan(self.code,before['validation_errors'],[],self.state['ssm'],str(self.vue_path),enable_residual_v2=True)
        self.assertIn('removed_source_proven_duplicate_startup', [label for _,label in repairs])
        after = validate(fixed)
        self.assertTrue(after['validation_passed'])
        self.assertFalse(candidate_gate(before,after)['should_stop'])
        gate = candidate_gate(after,before)
        self.assertTrue(gate['should_stop'])
        self.assertIn(CODE, [x['code'] for x in gate['introduced_semantic_findings']])

    def test_adding_attached_call_without_moving_early_call_is_a_real_gate_regression(self):
        first = self.state['repair_history'][0]['repair_result']['repaired_code']
        before = {'generated_code':first,'ssm':self.state['ssm'],'vue_file_path':str(self.vue_path),
            'validation_errors':inspect_semantics(first,self.vue,ssm=self.state['ssm'])['findings']}
        after = {**before,'generated_code':self.code,'validation_errors':inspect_semantics(self.code,self.vue,ssm=self.state['ssm'])['findings']}
        self.assertTrue(candidate_gate(before,after)['should_stop'])

    def test_actual_stage_postprocessing_removes_duplicate_and_records_rule(self):
        source, code = self.state, self.code
        class Client:
            def repair(self, request):
                return RepairResult(source_file='fixture',ssm=source['ssm'],code=code,
                    saved_file_path=request.output_file_path,provider='fixture',model='captured',usage={})
        with tempfile.TemporaryDirectory() as directory:
            result = RepairStage(Client()).run(RepairStageInput(ssm=source['ssm'],generated_code=code,
                vue_file_path=str(self.vue_path),output_file_path=str(Path(directory)/'candidate.san'),
                metadata={'skip_deterministic_prepass':True,'semantic_rule_set':'residual_v2'}))
            self.assertIn('removed_source_proven_duplicate_startup', result.raw_response['pipeline_postprocessing'])
            self.assertEqual(result.repaired_code.count('this.initDataImpl();'), 1)

    def test_new_error_routes_to_focused_prompt_with_move_not_append_instruction(self):
        prompt = build_repair_prompt(RepairPromptInput(ssm={},current_code=fixture()[0],validation_errors=[{'code':CODE}]))
        self.assertTrue(prompt.startswith('You are repairing a standalone San'))
        self.assertIn('do not merely append another call in attached()', prompt)

    def test_actual_scheduler_fixes_frozen_pass_without_any_llm_call(self):
        class NoModel:
            def repair(self, request):
                raise AssertionError('Offline closure must not reach any model request')
        with tempfile.TemporaryDirectory() as directory:
            generate = ReplayGenerate(self.state, self.code, Path(directory)/'before.san')
            orchestrator = MigrationPipelineOrchestrator(generate,ValidateStage(),VisualEvalStage(),RepairStage(NoModel()))
            result = orchestrator.run_generate_validate_visual_eval_and_repair_loop(
                GenerateStageInput(vue_file_path=str(self.vue_path),metadata={
                    'repair_policy':'bounded_prepass_v1','semantic_rule_set':'residual_v2'}),max_repair_rounds=3).state
            self.assertTrue(result['final_passed'], result['validation_errors'])
            self.assertEqual(result['llm_repair_calls'], 0)
            self.assertEqual(result['deterministic_steps'], 1)
            self.assertEqual(result['generated_code'].count('this.initDataImpl();'), 1)


if __name__ == '__main__':
    unittest.main()
