"""Bounded parent async watch group, source effect parity, refusals and rollback."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics, _run
from migration_pipeline.stages.repair import RepairStage, RepairStageInput
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.utils.repair_scheduler import candidate_gate
from migration_pipeline.utils.repair_prompt import RepairPromptInput, build_repair_prompt
from migration_pipeline.repair_client import RepairResult
from migration_pipeline.audit_formal_30_v4_parent_watch_oracle_v1 import SAN, VUE, RAW
from migration_pipeline.replay_formal_30_v4_parent_watch_closure_v1 import oracle_runtime
from migration_pipeline.replay_formal_30_v4_parent_watch_closure_v1 import OUTPUT as NORMAL_BASE

BOUNDARIES={'source_parent_watch_exception_policy_unproven','source_parent_watch_dynamic_key_unproven'}


def fixture():
    data="{rows:[],count:0,key:'cache'}"
    source='''export default {data(){return DATA;},
watch:{rows:{deep:true,handler(){this.tally();this.save();}}},
mounted(){this.load();},beforeDestroy(){this.save();},
methods:{load(){this.rows=[{title:'sample'}];},tally(){this.count=this.rows.length;},
save(){this.count=this.rows.length;}}};'''.replace('DATA',data)
    target='''const san=require('san');module.exports=san.defineComponent({initData(){return DATA;},
inited(){},attached(){this.load();this.watch('rows',()=>{this.tally();this.save();},{deep:true});},disposed(){this.save();},
load(){this.data.set('rows',[{title:'sample'}]);},tally(){this.data.set('count',this.data.get('rows').length);},
save(){this.data.set('count',this.data.get('rows').length);}});'''.replace('DATA',data)
    return '<template><section/></template><script>'+target+'</script><style>.keep{color:red}</style>', '<template><section/></template><script>'+source+'</script>'


class SourceParentWatchClosureTests(unittest.TestCase):
    def apply(self,pair,repair=True):
        result=source_parent_watch_semantics(*pair,repair=repair);self.assertNotIn('error',result,result);return result

    def state(self,code,vue):
        return {'generated_code':code,'vue_source':vue,'ssm':{},'validation_errors':self.apply((code,vue),repair=False)['findings']}

    def test_generic_group_transformation_and_fixedpoint(self):
        code,vue=fixture();r=self.apply((code,vue))
        self.assertEqual(r['changes'],['restored_source_parent_async_watch_group'])
        self.assertIn('Promise.resolve().then(flush)',r['code']);self.assertIn('pending[index]=false',r['code'])
        self.assertIn('this.__sourceParentWatchDispose_v1()',r['code'])
        self.assertEqual(code.split('</script>')[1],r['code'].split('</script>')[1])
        again=self.apply((r['code'],vue));self.assertEqual(again['code'],r['code']);self.assertEqual(again['findings'],[])
        self.assertTrue(again['proofs'][0]['landed'])

    def test_renamed_fields_methods_and_registration_are_not_task_specific(self):
        code,vue=fixture()
        for old,new in [('rows','items'),('tally','recount'),('load','restore'),('save','persist'),('count','total')]:
            code,vue=code.replace(old,new),vue.replace(old,new)
        r=self.apply((code,vue));self.assertTrue(r['changes']);self.assertEqual(r['mapped_contracts'],['script.parent.watch@items'])

    def test_special_watch_options_and_handler_signatures_not_invented(self):
        code,vue=fixture()
        for replacement in ['deep:true,immediate:true','deep:true,sync:true','deep:false']:
            changed=vue.replace('deep:true',replacement);r=self.apply((code,changed));self.assertEqual(r['code'],code);self.assertEqual(r['mapped_contracts'],[])
        r=self.apply((code,vue.replace('handler(){','handler(value){')));self.assertEqual(r['code'],code)

    def test_source_or_target_effect_method_mismatch_is_unproven(self):
        code,vue=fixture()
        for before,after in [("this.data.get('rows').length","0"),("'sample'","'wrong'"),('this.save();},{deep:true})','this.save();this.extra();},{deep:true})')]:
            candidate=code.replace(before,after);self.assertNotEqual(candidate,code)
            r=self.apply((candidate,vue));self.assertEqual(r['code'],candidate);self.assertTrue(r['findings'])

    def test_unknown_hook_work_duplicate_watch_and_opaque_callback_refused(self):
        code,vue=fixture()
        for candidate in [code.replace('inited(){}','inited(){this.extra();}'),
            code.replace('this.load();this.watch','this.extra();this.load();this.watch'),
            code.replace('inited(){}',"inited(){this.watch('rows',()=>this.save());}"),
            code.replace("()=>{this.tally();this.save();}",'opaque')]:
            r=self.apply((candidate,vue));self.assertEqual(r['code'],candidate);self.assertTrue(r['findings'])

    def test_watched_root_writes_or_recursive_effect_graph_refused(self):
        code,vue=fixture()
        changed_vue=vue.replace('this.count=this.rows.length;',"this.rows=[{title:'recursive'}];")
        changed_code=code.replace("this.data.set('count',this.data.get('rows').length);","this.data.set('rows',[{title:'recursive'}]);")
        self.assertEqual(self.apply((changed_code,changed_vue))['code'],changed_code)
        changed_vue=vue.replace('this.count=this.rows.length;','this.tally();')
        changed_code=code.replace("this.data.set('count',this.data.get('rows').length);",'this.tally();')
        self.assertEqual(self.apply((changed_code,changed_vue))['code'],changed_code)

    def test_global_shadow_framework_mutation_mixins_and_dynamic_this_refused(self):
        code,vue=fixture()
        for candidate in [code.replace('const san=', 'const Promise=other;const san='),
            code.replace('inited(){}','inited(){this[name]();}'),code.replace('initData(){','mixins:[],initData(){'),
            code.replace('module.exports=', 'san.nextTick=other;module.exports=')]:
            self.assertEqual(self.apply((candidate,vue))['code'],candidate)

    def test_candidate_gate_rejects_removed_cancel_order_or_queue_dedup(self):
        code,vue=fixture();fixed=self.apply((code,vue))['code'];before,after=self.state(code,vue),self.state(fixed,vue)
        self.assertFalse(candidate_gate(before,after)['should_stop']);self.assertTrue(candidate_gate(after,before)['should_stop'])
        for candidate in [fixed.replace('pending[index]=false','pending[index]=true'),
            fixed.replace('this.__sourceParentWatchDispose_v1();',''),fixed.replace('queue.sort((a,b)=>a-b)','queue.sort((a,b)=>b-a)')]:
            self.assertNotEqual(candidate,fixed);self.assertTrue(candidate_gate(after,self.state(candidate,vue))['should_stop'])
        gate=candidate_gate(after,self.state('<template><section/></template>',vue))
        self.assertEqual(gate['lost_source_parent_watch_contracts'],['script.parent.watch@rows'])

    def test_analysis_failure_and_readonly_are_nonmutating(self):
        code,vue=fixture();self.assertEqual(self.apply((code,vue),False)['code'],code)
        self.assertEqual(source_parent_watch_semantics(code,'',repair=True)['code'],code)
        _run.cache_clear()
        with patch('migration_pipeline.utils.source_parent_watch_semantics.subprocess.run',side_effect=OSError):
            r=source_parent_watch_semantics(code,vue,repair=True);self.assertEqual(r['code'],code);self.assertIn('error',r)
        _run.cache_clear()

    def test_prepass_postprocessing_and_legacy_boundary(self):
        code,vue=fixture()
        class Client:
            def repair(self,request):return RepairResult(code=code,saved_file_path=request.output_file_path,source_file='',ssm={},provider='stub',model='stub',raw_response={})
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'source.vue';source.write_text(vue,encoding='utf-8')
            legacy,_=RepairStage._deterministic_repair_plan(code,[],[],{},str(source));self.assertEqual(legacy,code)
            fixed,steps=RepairStage._deterministic_repair_plan(code,[],[],{},str(source),enable_residual_v2=True)
            self.assertEqual(fixed,self.apply((code,vue))['code']);self.assertIn(('source_parent_watch_contracts','restored_source_parent_async_watch_group'),steps)
            result=RepairStage(Client()).run(RepairStageInput(ssm={},generated_code=code,vue_file_path=str(source),
                output_file_path=str(Path(folder)/'out.san'),metadata={'skip_deterministic_prepass':True,'semantic_rule_set':'residual_v2'}))
            self.assertEqual(result.repaired_code.rstrip(),fixed.rstrip())

    def test_prompt_declares_queue_and_unproven_exception_boundary(self):
        prompt=build_repair_prompt(RepairPromptInput(ssm={},current_code='',validation_errors=[{'code':'source_parent_watch_not_landed'}]))
        self.assertIn('coalesce per instance/field',prompt);self.assertIn('Exception policy equivalence',prompt)

    @classmethod
    def setUpClass(cls):
        cls.code=SAN.read_text(encoding='utf-8');cls.vue=VUE.read_text(encoding='utf-8')
        cls.ssm=json.loads((RAW/'repair_reports/complex/TaskManager_repair_history.json').read_text(encoding='utf-8'))['state']['ssm']

    def test_frozen_source_90_phase_pair_business_effect_and_state_oracle(self):
        current=self.apply((self.code,self.vue));self.assertEqual(current['code'],self.code)
        self.assertEqual({e['code'] for e in current['findings']},BOUNDARIES|{'source_parent_watch_not_landed'})
        fixed=(NORMAL_BASE/'TaskManager_parent_async_watch_offline.san').read_text(encoding='utf-8')
        before,after=oracle_runtime(self.code,self.vue),oracle_runtime(fixed,self.vue)
        self.assertFalse(before['matched']);self.assertTrue(after['matched']);self.assertEqual(len(after['pairs']),90)

    def test_same_value_clone_guard_and_unknown_writer_body_refused(self):
        fixed=(NORMAL_BASE/'TaskManager_parent_async_watch_offline.san').read_text(encoding='utf-8');again=self.apply((fixed,self.vue))
        self.assertEqual({e['code'] for e in again['findings']},BOUNDARIES)
        self.assertFalse(again['proofs'][0]['automatic_repair_eligible'])
        self.assertTrue(again['proofs'][0]['source_nested_clone_writers'][0]['same_value_guard'])
        self.assertIn('Object.is(',fixed)
        bad=fixed.replace('Object.is(','Object.isNot(')
        self.assertEqual(self.apply((bad,self.vue))['code'],bad);self.assertTrue(self.apply((bad,self.vue))['findings'])
        bad=self.code.replace('const newSettings = { ...settings, [key]: newValue };', 'const newSettings = { ...settings, [key]: value };')
        self.assertNotEqual(bad,self.code);self.assertEqual(self.apply((bad,self.vue))['code'],bad)

    def test_frozen_validator_effect_methods_and_pipeline_prepass(self):
        fixed=(NORMAL_BASE/'TaskManager_parent_async_watch_offline.san').read_text(encoding='utf-8')
        def assess(text):return ValidateStage().run(ValidateStageInput(generated_code=text,ssm=self.ssm,vue_file_path=str(VUE))).to_state_update()
        before,after=assess(self.code),assess(fixed)
        self.assertEqual({e['code'] for e in before['validation_errors']},BOUNDARIES|{'source_parent_watch_not_landed'})
        self.assertEqual({e['code'] for e in after['validation_errors']},BOUNDARIES)
        self.assertFalse(after['validation_passed'])
        planned,_=RepairStage._deterministic_repair_plan(self.code,before['validation_errors'],[],self.ssm,str(VUE),enable_residual_v2=True)
        self.assertEqual(planned,self.code)


if __name__=='__main__':unittest.main()
