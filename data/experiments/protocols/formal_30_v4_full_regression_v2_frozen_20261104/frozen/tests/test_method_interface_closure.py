"""Preserve unused source APIs without adding permission/UI/lifecycle triggers."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from migration_pipeline.utils.bounded_semantics import inspect_semantics
from migration_pipeline.utils.inline_identifier_recovery import recover_inline_identifiers
from migration_pipeline.utils.repair_scheduler import candidate_gate
from migration_pipeline.utils.repair_prompt import build_repair_prompt,RepairPromptInput
from migration_pipeline.stages.validate import ValidateStage,ValidateStageInput
from migration_pipeline.stages.repair import RepairStage,RepairStageInput
from migration_pipeline.repair_client import RepairResult
from migration_pipeline.orchestrator import MigrationPipelineOrchestrator
from migration_pipeline.replay_formal_30_v4_repair_scheduling import ReplayGenerate
from migration_pipeline.stages.generate import GenerateStageInput
from migration_pipeline.stages.visual_eval import VisualEvalStage

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'data/experiments/snapshots/formal_30_v4_semantic_closure_v4_results_20261103_204227'
OFFLINE=ROOT/'data/experiments/analysis/formal_30_v4_startup_phase_closure_v1_20261103'
MISSING='source_method_interface_not_landed'
TRIGGER='source_method_trigger_added'


def fixture(body="if ('Notification' in window && this.settings.enabled) {Notification.requestPermission();}"):
    vue='''<template><div></div></template><script>export default {
data(){return {settings:{enabled:false},label:'sample'};},
methods:{requestAccess(){__BODY__},kept(){}}
}</script>'''.replace('__BODY__',body)
    code='''<template><div></div></template><script>const san=require('san');
module.exports=san.defineComponent({initData(){return {settings:{enabled:false},label:'sample'};},
inited(){},attached(){},kept(){}});</script><style></style>'''
    return code,vue


class MethodInterfaceClosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state=json.loads((SOURCE/'repair_reports/complex/MonitoringDashboard_repair_history.json').read_text(encoding='utf-8'))['state']
        cls.vue_path=SOURCE/'protocol/frozen/data/datasets/components/03_complex/MonitoringDashboard/vue/MonitoringDashboard.vue'
        cls.vue=cls.vue_path.read_text(encoding='utf-8')
        cls.code=(OFFLINE/'final_automatic_pass_offline.san').read_text(encoding='utf-8')

    def test_frozen_method_loss_is_diagnosed_and_restored_without_changing_hooks_templates_or_children(self):
        before=inspect_semantics(self.code,self.vue,ssm=self.state['ssm'])
        self.assertEqual([f['code'] for f in before['findings']],[MISSING])
        fixed=inspect_semantics(self.code,self.vue,repair=True,ssm=self.state['ssm'])
        self.assertEqual(fixed['changes'],['restored_source_unreferenced_method_interfaces'])
        for block in ('template','style'):
            self.assertEqual(ValidateStage()._extract_blocks(self.code)[block],ValidateStage()._extract_blocks(fixed['code'])[block])
        a=self.code.split('module.exports =')[1];b=fixed['code'].split('module.exports =')[1]
        for name in ('initData','inited','attached','disposed'):
            self.assertEqual(ValidateStage()._extract_function_body(a,name),ValidateStage()._extract_function_body(b,name))
        self.assertEqual(self.code.split('module.exports =')[0],fixed['code'].split('module.exports =')[0])
        self.assertIn("this.data.get(\"settings\").desktopNotifications",fixed['code'])
        self.assertEqual(inspect_semantics(fixed['code'],self.vue,ssm=self.state['ssm'])['findings'],[])
        self.assertEqual(inspect_semantics(fixed['code'],self.vue,repair=True,ssm=self.state['ssm'])['code'],fixed['code'])

    def test_generic_name_and_pure_parameterized_method_restore_without_a_component_branch(self):
        code,vue=fixture('return prefix + this.label;')
        vue=vue.replace('requestAccess()','caption(prefix)')
        fixed=inspect_semantics(code,vue,repair=True)
        self.assertIn('caption(prefix)',fixed['code'])
        self.assertIn('this.data.get("label")',fixed['code'])
        self.assertEqual(inspect_semantics(fixed['code'],vue)['findings'],[])

    def test_controlled_permission_stub_only_runs_on_explicit_call_with_original_guard_true(self):
        code,vue=fixture();fixed=inspect_semantics(code,vue,repair=True)['code']
        script=fixed.split('<script>')[1].split('</script>')[0]
        js=r'''const fs=require('fs'),m={exports:{}},calls=[];
const api={requestPermission(){calls.push('requested');}},host={Notification:api};
new Function('require','module','window','Notification',fs.readFileSync(0,'utf8'))(
 name=>({defineComponent:o=>o}),m,host,api);
const p=m.exports,c={settings:{enabled:false},data:{get(){return c.settings;}}};
const before=calls.length;p.requestAccess.call(c);const disabled=calls.length;
c.settings={enabled:true};delete host.Notification;p.requestAccess.call(c);const unsupported=calls.length;
host.Notification=api;p.requestAccess.call(c);
process.stdout.write(JSON.stringify({before,disabled,unsupported,enabled:calls.length}));'''
        result=subprocess.run(['node','-e',js],input=script,text=True,encoding='utf-8',capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout),{'before':0,'disabled':0,'unsupported':0,'enabled':1})

    def test_source_or_target_internal_references_refuse_automatic_side_effect_restoration(self):
        code,vue=fixture()
        for c,v in ((code,vue.replace('kept(){}','kept(){this.requestAccess();}')),
                    (code.replace('attached(){}','attached(){this.requestAccess();}'),vue),
                    (code.replace('<div></div>','<button on-click="requestAccess">Ask</button>'),vue)):
            result=inspect_semantics(c,v,repair=True)
            self.assertEqual(result['code'],c)
            self.assertIn(MISSING,[f['code'] for f in result['findings']])
        added=inspect_semantics(code.replace('attached(){}','attached(){this.requestAccess();}'),vue)
        self.assertIn(TRIGGER,[f['code'] for f in added['findings']])

    def test_unknown_closures_writes_async_and_complex_signatures_are_reported_not_guessed(self):
        for body in ('return external;','this.label="changed";','this.settings.enabled=true;',
                     'return this.unknown;','fetch("/api");','window.fetch("/api");',
                     'return (()=>this.label)();','const x=this.label;return x;'):
            code,vue=fixture(body)
            result=inspect_semantics(code,vue,repair=True)
            self.assertEqual(result['code'],code,body)
            self.assertEqual([f['code'] for f in result['findings']],[MISSING])
        code,vue=fixture()
        for source in (vue.replace('requestAccess(){','async requestAccess(){'),
                       vue.replace('requestAccess(){','requestAccess({x}){'),
                       vue.replace('requestAccess(){','requestAccess(x=1){')):
            self.assertEqual(inspect_semantics(code,source,repair=True)['code'],code)

    def test_shadowed_browser_globals_are_not_copied_into_another_binding_scope(self):
        code,vue=fixture()
        for c,v in ((code,vue.replace('export default','const Notification=other;export default')),
                    (code.replace('module.exports','const Notification=other;module.exports'),vue)):
            self.assertEqual(inspect_semantics(c,v,repair=True)['code'],c)

    def test_existing_noncallable_option_is_not_overwritten_or_satisfied_by_child_method(self):
        code,vue=fixture()
        for bad in (code.replace('kept(){}','requestAccess:0,kept(){}'),
                    code.replace('kept(){}','requestAccess:external,kept(){}')):
            self.assertEqual(inspect_semantics(bad,vue,repair=True)['code'],bad)
            self.assertIn(MISSING,[f['code'] for f in inspect_semantics(bad,vue)['findings']])
        child=code.replace('module.exports',"const Child=san.defineComponent({requestAccess(){}});module.exports")
        self.assertIn(MISSING,[f['code'] for f in inspect_semantics(child,vue)['findings']])

    def test_reserved_factory_and_callable_public_alias_wrapper_are_preserved(self):
        code,vue=fixture()
        source=vue.replace('kept(){}','initData(){this.kept();},kept(){}')
        fixed=inspect_semantics(code,source,repair=True)
        self.assertIn("initData(){return {settings:{enabled:false},label:'sample'};}",fixed['code'])
        wrapper=code.replace('kept(){}','requestAccess(){return this.actualAccess();},actualAccess(){},kept(){}')
        self.assertEqual(inspect_semantics(wrapper,vue)['findings'],[])
        self.assertEqual(inspect_semantics(wrapper,vue,repair=True)['code'],wrapper)
        for definition in ('function alias(){}','const alias=function(){};','const alias=()=>{};'):
            bound=code.replace('module.exports',definition+'module.exports').replace('kept(){}','requestAccess:alias,kept(){}')
            self.assertEqual(inspect_semantics(bound,vue)['findings'],[])
        reassigned=code.replace('module.exports','let alias=()=>{};alias=1;module.exports').replace('kept(){}','requestAccess:alias,kept(){}')
        self.assertIn(MISSING,[f['code'] for f in inspect_semantics(reassigned,vue)['findings']])
        source=vue.replace('export default','function implementation(){return this.label;} export default')
        source=source.replace("requestAccess(){if ('Notification' in window && this.settings.enabled) {Notification.requestPermission();}}",'requestAccess:implementation')
        self.assertNotEqual(source,vue)
        restored=inspect_semantics(code,source,repair=True)
        self.assertIn('this.data.get("label")',restored['code'])

    def test_opaque_legacy_or_dynamic_contexts_do_not_acquire_automatic_restoration(self):
        code,vue=fixture()
        for bad in (code.replace('kept(){}','...external,kept(){}'),
                    code.replace('kept(){}','kept(){this[name]();}'),
                    code.replace('kept(){}','kept(){const self=this;}')):
            self.assertEqual(inspect_semantics(bad,vue,repair=True)['code'],bad)
        self.assertEqual(inspect_semantics(code,'',repair=True)['code'],code)
        legacy=code.replace('kept(){}','methods:{kept(){}}')
        observed=inspect_semantics(legacy,vue,repair=True)
        self.assertEqual(observed['code'],legacy)
        self.assertIn(MISSING,[f['code'] for f in observed['findings']])
        # Unwrapping an invalid legacy wrapper exposes no *new* missing API;
        # the unresolved contract remains an error and is not a false pass.
        before={'generated_code':legacy,'vue_source':vue,'ssm':{},'validation_errors':observed['findings']}
        after={**before,'generated_code':code,'validation_errors':inspect_semantics(code,vue)['findings']}
        self.assertFalse(candidate_gate(before,after)['should_stop'])
        self.assertTrue(after['validation_errors'])

    def test_validator_no_longer_requires_mounted_or_storage_to_check_a_plain_source_method(self):
        code,vue=fixture('return this.label;')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'Plain.vue';path.write_text(vue,encoding='utf-8')
            result=ValidateStage().run(ValidateStageInput(generated_code=code,ssm={},vue_file_path=str(path)))
            self.assertIn(MISSING,[e['code'] for e in result.validation_errors])

    def test_real_loss_is_rejected_but_restoration_is_accepted_by_candidate_gate(self):
        first=self.state['repair_history'][0]['repair_result']['repaired_code']
        def checked(code):
            return {'generated_code':code,'ssm':self.state['ssm'],'vue_file_path':str(self.vue_path),
                    'validation_errors':inspect_semantics(code,self.vue,ssm=self.state['ssm'])['findings']}
        gate=candidate_gate(checked(first),checked(self.state['generated_code']))
        self.assertTrue(gate['should_stop'])
        self.assertIn(MISSING,[e['code'] for e in gate['introduced_semantic_findings']])
        fixed=inspect_semantics(self.code,self.vue,repair=True,ssm=self.state['ssm'])['code']
        self.assertFalse(candidate_gate(checked(self.code),checked(fixed))['should_stop'])
        self.assertTrue(candidate_gate(checked(fixed),checked(self.code))['should_stop'])

    def test_added_trigger_is_rejected_even_when_method_interface_is_present(self):
        code,vue=fixture();fixed=inspect_semantics(code,vue,repair=True)['code']
        after=fixed.replace('attached(){}','attached(){this.requestAccess();}')
        before={'generated_code':fixed,'vue_source':vue,'validation_errors':[],'ssm':{}}
        bad={**before,'generated_code':after,'validation_errors':inspect_semantics(after,vue)['findings']}
        gate=candidate_gate(before,bad)
        self.assertTrue(gate['should_stop'])
        self.assertIn(TRIGGER,[f['code'] for f in gate['introduced_semantic_findings']])

    def test_registered_parse_recovery_explains_only_identical_preexisting_missing_interface(self):
        code,vue=fixture('return this.label;')
        broken=code.replace('module.exports',"const a-b=san.defineComponent({template:`<div></div>`});module.exports")
        broken=broken.replace('initData(){return',"components:{'a-b':a-b},initData(){return")
        ssm={'script':{'options':{'components':[{'registered_tag':'a-b'}]}}}
        recovered=recover_inline_identifiers(broken,ssm)['code']
        before={'generated_code':broken,'ssm':ssm,'vue_source':vue,'validation_errors':[]}
        after={**before,'generated_code':recovered,'validation_errors':inspect_semantics(recovered,vue,ssm=ssm)['findings']}
        gate=candidate_gate(before,after)
        self.assertFalse(gate['should_stop'],gate)
        self.assertIn(MISSING,[f['code'] for f in gate['newly_visible_preexisting_semantic_findings']])
        self.assertTrue(after['validation_errors'])  # no automatic pass/exemption
        deleted=recovered.replace('kept(){}','')
        bad={**after,'generated_code':deleted,'validation_errors':inspect_semantics(deleted,vue,ssm=ssm)['findings']}
        gate=candidate_gate(before,bad)
        self.assertTrue(gate['should_stop'])
        self.assertIn('script.methods.kept',[f['location'] for f in gate['introduced_semantic_findings']])
        triggered=recovered.replace('attached(){}','attached(){this.kept();}')
        bad={**after,'generated_code':triggered,'validation_errors':inspect_semantics(triggered,vue,ssm=ssm)['findings']}
        self.assertTrue(candidate_gate(before,bad)['should_stop'])

    def test_prepass_and_model_postprocessing_use_the_same_restoration(self):
        checked=ValidateStage().run(ValidateStageInput(generated_code=self.code,ssm=self.state['ssm'],vue_file_path=str(self.vue_path)))
        fixed,rules=RepairStage._deterministic_repair_plan(self.code,checked.validation_errors,[],self.state['ssm'],str(self.vue_path),enable_residual_v2=True)
        self.assertIn('restored_source_unreferenced_method_interfaces',[name for _,name in rules])
        code,source=self.code,self.state
        class Client:
            def repair(self,request):
                return RepairResult(source_file='fixture',ssm=source['ssm'],code=code,saved_file_path=request.output_file_path,provider='fixture',model='frozen',usage={})
        with tempfile.TemporaryDirectory() as directory:
            result=RepairStage(Client()).run(RepairStageInput(ssm=source['ssm'],generated_code=code,vue_file_path=str(self.vue_path),
                output_file_path=str(Path(directory)/'candidate.san'),metadata={'skip_deterministic_prepass':True,'semantic_rule_set':'residual_v2'}))
            self.assertEqual(result.repaired_code,fixed)
            self.assertIn('restored_source_unreferenced_method_interfaces',result.raw_response['pipeline_postprocessing'])

    def test_actual_scheduler_closes_the_interface_gap_without_model_requests(self):
        class NoModel:
            def repair(self,request):raise AssertionError('No model call allowed in offline test')
        with tempfile.TemporaryDirectory() as directory:
            generate=ReplayGenerate(self.state,self.code,Path(directory)/'before.san')
            orchestrator=MigrationPipelineOrchestrator(generate,ValidateStage(),VisualEvalStage(),RepairStage(NoModel()))
            result=orchestrator.run_generate_validate_visual_eval_and_repair_loop(GenerateStageInput(vue_file_path=str(self.vue_path),
                metadata={'repair_policy':'bounded_prepass_v1','semantic_rule_set':'residual_v2'}),max_repair_rounds=3).state
            self.assertTrue(result['final_passed'],result['validation_errors'])
            self.assertEqual(result['llm_repair_calls'],0)
            self.assertEqual(result['deterministic_steps'],1)

    def test_focused_prompt_supplies_the_missing_body_and_preserves_interface_on_other_routes(self):
        errors=[{'code':MISSING,'location':'script.methods.requestNotificationPermission'}]
        prompt=build_repair_prompt(RepairPromptInput(ssm=self.state['ssm'],current_code=self.code,validation_errors=errors))
        self.assertTrue(prompt.startswith('You are repairing'))
        self.assertIn('Notification.requestPermission()',prompt)
        self.assertIn('Do not add UI/lifecycle calls',prompt)
        self.assertIn('Source method names:',prompt)


if __name__=='__main__':unittest.main()
