"""Fail-closed scope, independent diagnostics, regression refusal and zero-model review stop."""
import json
from pathlib import Path
import tempfile
import unittest

from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
from migration_pipeline.utils.class_binding_semantics import class_binding_semantics
from migration_pipeline.utils.repair_scheduler import candidate_gate, PARENT_WATCH_REVIEW_CODES
from migration_pipeline.utils.repair_prompt import RepairPromptInput, build_repair_prompt
from migration_pipeline.stages.repair import RepairStage, RepairStageInput
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.stages.generate import GenerateStageInput, GenerateStageResult
from migration_pipeline.stages.visual_eval import VisualEvalStage
from migration_pipeline.orchestrator import MigrationPipelineOrchestrator
from migration_pipeline.repair_client import RepairResult
from migration_pipeline.audit_formal_30_v4_parent_watch_boundaries_v1 import BASE, SAN, VUE, RAW


def fixture(source_method='', target_method='', callback='this.recount();'):
    source="""export default {data(){return {settings:{enabled:true},count:0};},
watch:{settings:{deep:true,handler(){CALLBACK}}},mounted(){this.load();},beforeDestroy(){},
methods:{EXTRA load(){this.settings={enabled:false};},recount(){this.count=this.settings.enabled?1:0;}}};"""
    target="""const san=require('san');module.exports=san.defineComponent({initData(){return {settings:{enabled:true},count:0};},
inited(){},attached(){this.load();this.watch('settings',()=>{CALLBACK});},disposed(){},
EXTRA load(){this.data.set('settings',{enabled:false});},recount(){this.data.set('count',this.data.get('settings.enabled')?1:0);}});"""
    return ('<template><main/></template><script>'+target.replace('EXTRA',target_method).replace('CALLBACK',callback)+'</script>',
            '<template><main/></template><script>'+source.replace('EXTRA',source_method).replace('CALLBACK',callback)+'</script>')


class ParentWatchScopeGuardTests(unittest.TestCase):
    def apply(self,pair):
        r=source_parent_watch_semantics(*pair,repair=True);self.assertNotIn('error',r,r);return r

    def state(self,code,vue):
        classes=class_binding_semantics(code,vue)
        self.assertNotIn('error',classes)
        return {'generated_code':code,'vue_source':vue,'ssm':{},
                'validation_errors':[*source_parent_watch_semantics(code,vue)['findings'],*classes['findings']]}

    def test_pure_nonstorage_known_shape_group_remains_eligible_and_idempotent(self):
        p=fixture();r=self.apply(p)
        self.assertEqual(r['blocked_boundaries'],[])
        self.assertEqual(r['changes'],['restored_source_parent_async_watch_group'])
        self.assertTrue(r['proofs'][0]['automatic_repair_eligible'])
        again=self.apply((r['code'],p[1]));self.assertEqual(again['findings'],[]);self.assertEqual(again['code'],r['code'])

    def test_transitive_storage_access_blocks_without_inventing_error_policy(self):
        p=fixture("persist(){this.write();},write(){localStorage.setItem('x','v');},",
                  "persist(){this.write();},write(){localStorage.setItem('x','v');},",'this.persist();')
        r=self.apply(p);self.assertEqual(r['code'],p[0]);self.assertEqual(r['changes'],[])
        self.assertEqual([b['code'] for b in r['blocked_boundaries']],['source_parent_watch_exception_policy_unproven'])

    def test_existing_try_catch_is_conservatively_not_a_runtime_adapter_proof(self):
        method="persist(){try{localStorage.setItem('x','v');}catch(e){}},"
        p=fixture(method,method,'this.persist();');r=self.apply(p)
        self.assertEqual(r['code'],p[0]);self.assertTrue(r['blocked_boundaries'])

    def test_unknown_dynamic_writer_blocks_even_if_not_in_watch_effect_graph(self):
        source='assign(key,value){this.settings[key]=value;},'
        target="assign(key,value){const settings=this.data.get('settings');const newValue=value;const newSettings={...settings,[key]:newValue};this.data.set('settings',newSettings);},"
        p=fixture(source,target);r=self.apply(p)
        self.assertEqual(r['code'],p[0]);self.assertEqual(r['changes'],[])
        self.assertEqual([b['code'] for b in r['blocked_boundaries']],['source_parent_watch_dynamic_key_unproven'])

    def test_writer_after_other_statements_and_destructuring_are_not_missed(self):
        for body in ['let first=1;this.settings[key]=value;', '({value:this.settings[key]}=value);']:
            p=fixture('assign(key,value){'+body+'},','assign(key,value){},');r=self.apply(p)
            self.assertEqual(r['code'],p[0]);self.assertIn('source_parent_watch_dynamic_key_unproven',{b['code'] for b in r['blocked_boundaries']})

    def test_static_new_inherited_proto_and_deletion_keys_also_require_review(self):
        for expression in ['this.settings.extra=value','this.settings.toString=value',
                           "this.settings['__proto__']=value",'delete this.settings.enabled']:
            p=fixture('assign(value){'+expression+';},','assign(value){},');r=self.apply(p)
            self.assertEqual(r['code'],p[0]);self.assertIn('source_parent_watch_dynamic_key_unproven',{b['code'] for b in r['blocked_boundaries']})

    def test_known_existing_static_write_does_not_get_blanket_blocked(self):
        p=fixture('assign(value){this.settings.enabled=value;},',"assign(value){this.data.set('settings.enabled',value);},")
        self.assertEqual(self.apply(p)['blocked_boundaries'],[])
        self.assertTrue(self.apply(p)['changes'])

    def test_renamed_fields_and_writers_are_not_component_special_cases(self):
        p=fixture('assign(key,value){this.settings[key]=value;},','assign(key,value){},')
        p=tuple(s.replace('settings','options').replace('assign','changeOption') for s in p)
        r=self.apply(p);self.assertEqual(r['code'],p[0]);self.assertIn('changeOption:options',r['findings'][0]['message'])

    def test_normal_queue_can_remain_landed_but_full_validation_is_not_passed(self):
        code=SAN.read_text(encoding='utf-8');vue=VUE.read_text(encoding='utf-8');r=self.apply((code,vue))
        self.assertEqual(r['code'],code);self.assertEqual({b['code'] for b in r['blocked_boundaries']},PARENT_WATCH_REVIEW_CODES)
        self.assertTrue(r['proofs'][0]['landed']);self.assertFalse(r['proofs'][0]['automatic_repair_eligible'])
        self.assertEqual(r['proofs'][0]['proof_scope'],'normal_flow_only')

    def test_diagnostics_exist_before_target_recognition_and_survive_method_deletion(self):
        code=SAN.read_text(encoding='utf-8');vue=VUE.read_text(encoding='utf-8')
        bad=code.replace('updateStatistics() {','wrongStatistics() {')
        self.assertNotEqual(bad,code)
        self.assertEqual({b['code'] for b in self.apply((bad,vue))['blocked_boundaries']},PARENT_WATCH_REVIEW_CODES)

    def test_candidate_cannot_hide_boundary_diagnostics_to_forge_a_pass(self):
        code=SAN.read_text(encoding='utf-8');vue=VUE.read_text(encoding='utf-8');before=self.state(code,vue)
        after={**before,'validation_errors':[],'validation_passed':True}
        gate=candidate_gate(before,after)
        self.assertTrue(gate['should_stop']);self.assertEqual({b['code'] for b in gate['waived_source_parent_watch_boundaries']},PARENT_WATCH_REVIEW_CODES)
        self.assertFalse(candidate_gate(before,before)['should_stop'])

    def test_prompt_explicitly_refuses_invented_exception_or_dynamic_key_policy(self):
        p=build_repair_prompt(RepairPromptInput(ssm={},current_code='',
            validation_errors=[{'code':c} for c in PARENT_WATCH_REVIEW_CODES]))
        for text in ['scope requires review','Do not rewrite the watcher queue','catch-and-continue','force Vue2 new-property reactivity']:
            self.assertIn(text,p)

    def test_prepass_and_model_return_postprocessing_do_not_expand_blocked_group(self):
        code,vue=fixture("persist(){localStorage.setItem('x','v');},","persist(){localStorage.setItem('x','v');},",'this.persist();')
        class Client:
            def repair(self,request):return RepairResult(code=code,saved_file_path=request.output_file_path,source_file='',
                ssm={},provider='stub',model='stub',raw_response={})
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'source.vue';path.write_text(vue,encoding='utf-8')
            fixed,steps=RepairStage._deterministic_repair_plan(code,[],[],{},str(path),enable_residual_v2=True)
            self.assertEqual(fixed,code);self.assertFalse(any(k=='source_parent_watch_contracts' for k,_ in steps))
            result=RepairStage(Client()).run(RepairStageInput(ssm={},generated_code=code,vue_file_path=str(path),
                output_file_path=str(Path(folder)/'out.san'),metadata={'skip_deterministic_prepass':True,'semantic_rule_set':'residual_v2'}))
            self.assertEqual(result.repaired_code.rstrip(),code.rstrip())

    def test_real_scheduler_stops_for_review_without_spending_a_model_call(self):
        code=SAN.read_text(encoding='utf-8')
        ssm=json.loads((RAW/'repair_reports/complex/TaskManager_repair_history.json').read_text(encoding='utf-8'))['state']['ssm']
        class NoModel:
            def repair(self,_):raise AssertionError('Boundary review must not call a model')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'retained.san';path.write_text(code,encoding='utf-8')
            class Generate:
                def run(self,_):return GenerateStageResult(source_file=str(VUE),ssm=ssm,generation_code=code,
                    saved_file_path=str(path),provider='retained_frozen_artifact',model='none',usage={},raw_response={})
            state=MigrationPipelineOrchestrator(Generate(),ValidateStage(),VisualEvalStage(),RepairStage(NoModel())).run_generate_validate_visual_eval_and_repair_loop(
                GenerateStageInput(vue_file_path=str(VUE),metadata={'repair_policy':'bounded_prepass_v1','semantic_rule_set':'residual_v2'}),max_repair_rounds=3).state
            self.assertFalse(state['final_passed']);self.assertEqual(state['llm_repair_calls'],0)
            # The frozen fixture also contains the independently proven class
            # defect. Repairing that must not waive the watcher review boundary.
            expected=class_binding_semantics(code,VUE.read_text(encoding='utf-8'),repair=True)
            self.assertEqual(expected['changes'],['restored_source_conditional_class_map'])
            self.assertEqual(state['deterministic_steps'],1);self.assertEqual(state['stop_reason'],'source_parent_watch_scope_requires_review')
            self.assertEqual(state['normalization_history'][0]['normalizations'],['restored_source_conditional_class_map'])
            self.assertEqual(set(state['source_parent_watch_review_codes']),PARENT_WATCH_REVIEW_CODES)
            final=Path(state['final_file_path']).read_text(encoding='utf-8')
            self.assertEqual(final,expected['code'])
            self.assertEqual(final.split('</template>')[1],code.split('</template>')[1])


if __name__=='__main__':unittest.main()
