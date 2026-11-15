"""Source-proven single payload at both ends, with real San listener fixtures."""
import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from migration_pipeline.utils.source_payload_semantics import source_payload_semantics, _run
from migration_pipeline.stages.repair import RepairStage, RepairStageInput
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.utils.repair_scheduler import candidate_gate
from migration_pipeline.utils.repair_prompt import RepairPromptInput, build_repair_prompt
from migration_pipeline.repair_client import RepairResult

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data/experiments/analysis/formal_30_v4_source_dom_closure_v1_20261110'
SOURCE=ROOT/'data/experiments/snapshots/formal_30_v4_full_regression_v2_results_20261104_214821'


def fixture(*, direct=False, params='field, choice', second=False):
    src='''{template:`<div><select @change="$emit('choose', 'mode', $event.target.value)"></select></div>`}'''
    target='''const Picker=san.defineComponent({template:`<div><select on-change="change($event.target.value)"></select></div>`,
change(choice){this.fire('choose','mode',choice);}});'''
    if direct:
        target='''const Picker=san.defineComponent({template:`<div><select on-change="fire('choose', 'mode', $event.target.value)"></select></div>`});'''
    a='<picker @choose="receive"/>'*(2 if second else 1)
    b='<picker on-choose="receive"/>'*(2 if second else 1)
    vue=f'<template><div>{a}</div></template><script>const Picker={src};export default {{components:{{Picker}},methods:{{receive({params}){{this.keep(field,choice);}}}}}};</script>'
    code=f'<template><div>{b}</div></template><script>const san=require("san");{target}module.exports=san.defineComponent({{components:{{"picker":Picker}},receive({params}){{this.seen=[field,choice];}}}});</script><style>.keep{{color:red}}</style>'
    ssm={'script':{'options':{'components':[{'registered_tag':'picker','inline_definition':{'source_code':src}}]}},
         'template':{'event_bindings':[{'event_name':'choose','handler_expression':'receive'}]}}
    return code,vue,ssm


class SourcePayloadClosureTests(unittest.TestCase):
    def apply(self,inputs,repair=True):
        code,vue,ssm=inputs
        result=source_payload_semantics(code,vue,ssm,repair=repair)
        self.assertNotIn('error',result,result)
        return result

    def test_two_ends_use_source_parameter_names_not_task_manager_special_case(self):
        p=fixture();r=self.apply(p)
        self.assertEqual(r['changes'],['restored_source_single_payload_contract'])
        self.assertIn("this.fire('choose',{field:'mode',choice:choice})",r['code'])
        self.assertIn('on-choose="receive($event.field,$event.choice)"',r['code'])
        self.assertIn('receive(field, choice){this.seen=[field,choice];}',r['code'])
        self.assertEqual(r['proofs'][0]['fields'],['field','choice'])
        self.assertEqual(self.apply((r['code'],p[1],p[2]))['changes'],[])
        self.assertEqual(self.apply((r['code'],p[1],p[2]),repair=False)['findings'],[])
        self.assertEqual(r['code'].split('</script>')[1],p[0].split('</script>')[1])

    def test_direct_template_emitter_and_all_consumer_instances(self):
        p=fixture(direct=True,second=True);r=self.apply(p)
        self.assertIn("fire('choose',{field:'mode',choice:$event.target.value})",r['code'])
        self.assertEqual(r['code'].count('receive($event.field,$event.choice)'),2)
        self.assertEqual(r['proofs'][0]['consumers'],2)
        self.assertEqual(self.apply((r['code'],p[1],p[2]))['findings'],[])

    def test_sender_only_and_receiver_only_fixes_remain_diagnostic(self):
        p=fixture();fixed=self.apply(p)['code']
        variants=[fixed.replace('receive($event.field,$event.choice)','receive'),
                  fixed.replace("this.fire('choose',{field:'mode',choice:choice})","this.fire('choose','mode',choice)")]
        for code in variants:
            r=self.apply((code,p[1],p[2]),repair=False)
            self.assertEqual(r['findings'][0]['code'],'source_event_payload_not_landed')
            self.assertEqual(r['proven_bindings'],[])
            self.assertEqual(self.apply((code,p[1],p[2]))['code'],fixed)

    def test_existing_parent_method_and_unrelated_callers_stay_byte_identical(self):
        p=fixture();code=p[0].replace('receive(field, choice)',"other(){this.receive('x',2);},receive(field, choice)")
        r=self.apply((code,p[1],p[2]))
        self.assertIn("other(){this.receive('x',2);},receive(field, choice){this.seen=[field,choice];}",r['code'])

    def test_conflicting_unknown_parent_binding_is_not_overwritten(self):
        p=fixture()
        for value in ('other','receive($event.choice,$event.field)','receive()'):
            code=p[0].replace('on-choose="receive"',f'on-choose="{value}"')
            r=self.apply((code,p[1],p[2]))
            self.assertEqual(r['code'],code)
            self.assertTrue(r['findings'])

    def test_refuse_unknown_event_dynamic_emission_or_unaccounted_sender(self):
        p=fixture()
        for extra in ("extra(){this.fire('choose','mode',9);},",'extra(){this.fire(name,1,2);},'):
            code=p[0].replace('change(choice){',extra+'change(choice){')
            self.assertEqual(self.apply((code,p[1],p[2]))['code'],code)

    def test_refuse_changed_source_ssm_shape_loop_or_handler_arguments(self):
        p=fixture()
        wrong=copy.deepcopy(p[2]);wrong['script']['options']['components'][0]['inline_definition']['source_code']='{template:`<div/>`}'
        self.assertEqual(self.apply((p[0],p[1],wrong))['code'],p[0])
        for old,new in [('<select on-change','<input on-change'),("'mode',choice","'other',choice"),
                        ('change($event.target.value)','change($event.target.checked)'),
                        ('<picker on-choose','<picker s-if="flag" on-choose')]:
            code=p[0].replace(old,new)
            self.assertEqual(self.apply((code,p[1],p[2]))['code'],code)

    def test_escaping_ctor_conflicting_alias_and_destructured_params_refused(self):
        p=fixture()
        for old,new in [('module.exports=', 'consume(Picker);module.exports='),
                        ('"picker":Picker','"picker":Picker,"other":Picker'),('receive(field, choice)','receive({field,choice})')]:
            code=p[0].replace(old,new)
            self.assertEqual(self.apply((code,p[1],p[2]))['code'],code)

    def test_no_source_and_already_single_payload_source_are_unchanged(self):
        p=fixture()
        self.assertEqual(source_payload_semantics(p[0],'',p[2],repair=True)['code'],p[0])
        src=p[1].replace("$emit('choose', 'mode', $event.target.value)","$emit('choose', $event.target.value)")
        self.assertEqual(self.apply((p[0],src,p[2]))['code'],p[0])

    def test_unknown_source_emitter_runtime_override_and_indirect_fire_refused(self):
        p=fixture()
        for old,new in [('change(choice){','fire(){},change(choice){'),
                        ('change(choice){',"extra(){this['fire']('choose',1,2);},change(choice){"),
                        ('change(choice){','extra(){const send=this.fire;},change(choice){'),
                        ('require("san")','require("other")')]:
            code=p[0].replace(old,new)
            self.assertEqual(self.apply((code,p[1],p[2]))['code'],code)
        src=p[2]['script']['options']['components'][0]['inline_definition']['source_code']
        added=src[:-1]+",methods:{extra(){this.$emit('choose','other',2);}}}"
        ssm=copy.deepcopy(p[2]);ssm['script']['options']['components'][0]['inline_definition']['source_code']=added
        self.assertEqual(self.apply((p[0],p[1].replace(src,added),ssm))['code'],p[0])

    def test_three_parameters_preserve_false_value_and_declared_field_order(self):
        p=fixture(params='field, choice, enabled')
        code=p[0].replace("'mode',choice)","'mode',choice,false)")
        vue=p[1].replace("'mode', $event.target.value)","'mode', $event.target.value, false)")
        ssm=copy.deepcopy(p[2]);ssm['script']['options']['components'][0]['inline_definition']['source_code']=ssm['script']['options']['components'][0]['inline_definition']['source_code'].replace("'mode', $event.target.value)","'mode', $event.target.value, false)")
        r=self.apply((code,vue,ssm))
        self.assertIn("{field:'mode',choice:choice,enabled:false}",r['code'])
        self.assertIn('receive($event.field,$event.choice,$event.enabled)',r['code'])
        self.assertEqual(self.apply((r['code'],vue,ssm))['changes'],[])

    def test_unknown_second_consumer_prevents_any_partial_rewrite(self):
        p=fixture(second=True)
        code=p[0].replace('on-choose="receive"','on-choose="other"',1)
        r=self.apply((code,p[1],p[2]))
        self.assertEqual(r['code'],code)
        self.assertTrue(r['findings'])

    def test_script_examples_and_comments_are_not_global_replacements(self):
        p=fixture();sample="const example=\"fire('choose','mode',choice)\";/* on-choose=receive */"
        code=p[0].replace('module.exports=',sample+'module.exports=')
        self.assertIn(sample,self.apply((code,p[1],p[2]))['code'])

    def test_proven_unpacking_whitespace_is_traceable_without_alias_guess(self):
        p=fixture();fixed=self.apply(p)['code']
        spaced=fixed.replace('receive($event.field,$event.choice)','receive( $event.field, $event.choice )')
        result=self.apply((spaced,p[1],p[2]),repair=False)
        self.assertEqual(result['findings'],[])
        before={'generated_code':p[0],'ssm':p[2],'vue_source':p[1],'validation_errors':[]}
        after={**before,'generated_code':spaced}
        self.assertFalse(candidate_gate(before,after)['should_stop'])

    def test_malformed_analyzer_fails_closed(self):
        p=fixture();_run.cache_clear()
        with patch('migration_pipeline.utils.source_payload_semantics.subprocess.run',side_effect=OSError):
            r=source_payload_semantics(*p,repair=True)
            self.assertEqual(r['code'],p[0]);self.assertIn('error',r)
        _run.cache_clear()

    def test_installed_san_fire_and_parent_listener_receive_both_values(self):
        p=fixture();code=self.apply(p)['code']
        js=r'''const fs=require('fs'),san=require('san'),listener=require('san/src/view/get-event-listener');
const code=JSON.parse(fs.readFileSync(0,'utf8')),m={exports:{}};
new Function('require','module',/<script>([\s\S]*?)<\/script>/.exec(code)[1])(require,m);
const parent=new m.exports(),child=new parent.components.picker();
const root=san.parseTemplate(/<template>([\s\S]*?)<\/template>/.exec(code)[1]);
const binding=root.children[0].children[0].events[0];
child.on('choose',listener(binding,parent,parent.data,true));child.change('board');
process.stdout.write(JSON.stringify(parent.seen));'''
        r=subprocess.run(['node','-e',js],input=json.dumps(code),text=True,encoding='utf-8',capture_output=True,cwd=ROOT)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(json.loads(r.stdout),['mode','board'])

    def test_gate_accepts_both_ends_and_rejects_regression_or_mapping_loss(self):
        p=fixture();fixed=self.apply(p)['code']
        def state(code):
            r=self.apply((code,p[1],p[2]),repair=False)
            return {'generated_code':code,'ssm':p[2],'vue_source':p[1],'validation_errors':r['findings']}
        self.assertFalse(candidate_gate(state(p[0]),state(fixed))['should_stop'])
        self.assertTrue(candidate_gate(state(fixed),state(p[0]))['should_stop'])
        for old,new in [('on-choose="receive($event.field,$event.choice)"',''),
                        ("{field:'mode',choice:choice}","{field:'mode',choice:'wrong'}"),
                        ('<select on-change','<input on-change')]:
            gate=candidate_gate(state(fixed),state(fixed.replace(old,new)))
            self.assertTrue(gate['should_stop'],gate)

    def test_prompt_shared_path_has_both_ends_and_no_unknown_schema_guess(self):
        for code in ('invalid_san_multi_argument_fire','source_event_payload_not_landed'):
            prompt=build_repair_prompt(RepairPromptInput(ssm={},current_code='',validation_errors=[{'code':code}]))
            self.assertIn('Two-ended source event payload contract',prompt)
            self.assertIn('Keep the original receiver method signature/body',prompt)

    @classmethod
    def setUpClass(cls):
        cls.state=json.loads((SOURCE/'repair_reports/complex/TaskManager_repair_history.json').read_text(encoding='utf-8'))['state']
        cls.code=(BASE/'TaskManager_source_dom_offline.san').read_text(encoding='utf-8')
        cls.vue=SOURCE/'protocol/frozen/data/datasets/components/03_complex/TaskManager/vue/TaskManager.vue'

    def test_frozen_real_artifact_four_senders_one_receiver_partial_only(self):
        p=(self.code,self.vue.read_text(encoding='utf-8'),self.state['ssm']);r=self.apply(p)
        self.assertEqual(r['proofs'][0]['emissions'],4)
        self.assertEqual(r['proofs'][0]['fields'],['key','value'])
        self.assertIn('on-update="updateSettings($event.key,$event.value)"',r['code'])
        def assess(code):
            return {'generated_code':code,'ssm':p[2],'vue_file_path':str(self.vue),
                **ValidateStage().run(ValidateStageInput(generated_code=code,ssm=p[2],vue_file_path=str(self.vue))).to_state_update()}
        before,after=assess(self.code),assess(r['code'])
        self.assertEqual(len(before['validation_errors']),6)
        self.assertEqual({e['code'] for e in after['validation_errors']},{'unsupported_san_inline_template_math_global',
            'unsupported_san_inline_template_member_call','hidden_template_reactive_dependency','nested_state_mutation'})
        self.assertFalse(after['validation_passed'])
        self.assertFalse(candidate_gate(before,after)['should_stop'])
        self.assertTrue(candidate_gate(after,before)['should_stop'])

    def test_frozen_real_settings_routes_preserve_false_and_numeric_conversion_in_san(self):
        code=self.apply((self.code,self.vue.read_text(encoding='utf-8'),self.state['ssm']))['code']
        js=r'''const fs=require('fs'),san=require('san'),listener=require('san/src/view/get-event-listener');
const code=JSON.parse(fs.readFileSync(0,'utf8')),m={exports:{}};
new Function('require','module',/<script>([\s\S]*?)<\/script>/.exec(code)[1])(require,m);
// Construct only, never attach: no browser, startup timers or persistence hooks.
const parent=new m.exports(),child=new parent.components['settings-panel']();
const notes=[];parent.showNotification=(text,type)=>notes.push({text,type});
let node;const visit=n=>{if(n.tagName==='settings-panel')node=n;(n.children||[]).forEach(visit);};
visit(san.parseTemplate(/<template>([\s\S]*?)<\/template>/.exec(code)[1]));
child.on('update',listener(node.events.find(e=>e.name==='update'),parent,parent.data,true));
child.updateDefaultView('board');child.updateAutoSave(false);child.updateNotifications(false);child.updateSyncInterval('30');
process.stdout.write(JSON.stringify({settings:parent.data.get('settings'),notes}));'''
        r=subprocess.run(['node','-e',js],input=json.dumps(code),text=True,encoding='utf-8',capture_output=True,cwd=ROOT)
        self.assertEqual(r.returncode,0,r.stderr)
        result=json.loads(r.stdout)
        self.assertEqual(result['settings'],{'defaultView':'board','autoSave':False,'notifications':False,'syncInterval':30})
        self.assertEqual(len(result['notes']),4)
        self.assertEqual(result['notes'][3],{'text':'设置已更新：syncInterval','type':'success'})

    def test_prepass_and_stub_model_return_are_both_integrated(self):
        p=fixture()
        class Client:
            def repair(self,request):return RepairResult(code=p[0],saved_file_path=request.output_file_path,
                source_file='',ssm=p[2],provider='stub',model='stub',raw_response={})
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'a.vue';path.write_text(p[1],encoding='utf-8')
            code,steps=RepairStage._deterministic_repair_plan(p[0],[],[],p[2],str(path),enable_residual_v2=True)
            self.assertEqual(code,self.apply(p)['code'])
            self.assertIn(('source_single_payload_contracts','restored_source_single_payload_contract'),steps)
            legacy,_=RepairStage._deterministic_repair_plan(p[0],[],[],p[2],str(path))
            self.assertEqual(legacy,p[0])
            r=RepairStage(Client()).run(RepairStageInput(ssm=p[2],generated_code=p[0],vue_file_path=str(path),
                output_file_path=str(Path(tmp)/'out.san'),metadata={'skip_deterministic_prepass':True,'semantic_rule_set':'residual_v2'}))
            self.assertEqual(r.repaired_code.rstrip(),code.rstrip())
            self.assertIn('restored_source_single_payload_contract',r.raw_response['pipeline_postprocessing'])


if __name__=='__main__':unittest.main()
