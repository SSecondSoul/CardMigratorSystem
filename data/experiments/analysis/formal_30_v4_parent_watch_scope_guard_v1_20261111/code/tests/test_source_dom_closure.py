"""Source-scoped DOM contracts, refusal boundaries and installed San listeners."""
import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from migration_pipeline.utils.source_dom_semantics import source_dom_semantics, _run
from migration_pipeline.utils.source_payload_semantics import source_payload_semantics
from migration_pipeline.utils.source_render_call_semantics import source_render_call_semantics
from migration_pipeline.utils.source_render_dependency_semantics import source_render_dependency_semantics
from migration_pipeline.utils.source_array_transaction_semantics import source_array_transaction_semantics
from migration_pipeline.utils.source_child_initialization_semantics import source_child_initialization_semantics
from migration_pipeline.utils.source_native_drag_semantics import source_native_drag_semantics
from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.stages.repair import RepairStage, RepairStageInput
from migration_pipeline.repair_client import RepairResult
from migration_pipeline.utils.repair_scheduler import candidate_gate
from migration_pipeline.utils.repair_prompt import RepairPromptInput, build_repair_prompt

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'data/experiments/snapshots/formal_30_v4_full_regression_v2_results_20261104_214821'
BASE=ROOT/'data/experiments/analysis/formal_30_v4_inline_formatter_closure_v1_20261110'


def pair(a,b,methods='act(){}',source_methods='act(){}'):
    vue='<template>'+a+'</template><script>module.exports={data(){return {flag:true,rows:[],mode:true};},methods:{'+source_methods+'}};</script>'
    san='<template>'+b+'</template><script>const san=require("san");module.exports=san.defineComponent({initData(){return {flag:true,rows:[],mode:true};},'+methods+'});</script><style>.keep{color:red}</style>'
    return san,vue


class SourceDomClosureTests(unittest.TestCase):
    def apply(self,p,ssm=None,repair=True):
        r=source_dom_semantics(p[0],p[1],ssm,repair=repair)
        self.assertNotIn('error',r,r)
        return r

    def test_boolean_self_preserves_inner_click_and_generates_explicit_event(self):
        p=pair('<div @click.self="flag = false"></div>','<div on-click="flag = false"></div>')
        r=self.apply(p)
        self.assertIn('event.target === event.currentTarget',r['code'])
        self.assertIn('this.data.set("flag",false)',r['code'])
        self.assertIn('($event)',r['code'])
        self.assertEqual(len(r['findings']),1)
        self.assertEqual(self.apply((r['code'],p[1]))['changes'],[])
        self.assertEqual(r['code'].split('</script>')[1],p[0].split('</script>')[1])

    def test_named_self_guard_is_source_proven_not_a_method_name_guess(self):
        p=pair('<div @click.self="act"></div>','<div on-click="act"></div>')
        r=self.apply(p)
        second=self.apply((r['code'],p[1]),repair=False)
        self.assertEqual(second['native_guards'][0]['source_handler'],'act')
        wrong=r['code'].replace('event.target === event.currentTarget','event.target !== event.currentTarget')
        refused=self.apply((wrong,p[1]))
        self.assertEqual(refused['code'],wrong)
        self.assertTrue(refused['findings'])

    def test_known_boolean_setter_is_wrapped_but_unknown_handler_is_not_overwritten(self):
        p=pair('<div @click.self="flag=false"></div>','<div on-click="setFlag"></div>',
               'setFlag(){this.data.set("flag",false);}')
        self.assertTrue(self.apply(p)['changes'])
        unknown=pair(p[1].split('<template>')[1].split('</template>')[0],
                     '<div on-click="setFlag"></div>','setFlag(){this.erase();}')
        self.assertEqual(self.apply(unknown)['code'],unknown[0])

    def test_stop_and_prevent_move_to_value_without_changing_handler_arguments(self):
        p=pair('<div><button @click.stop="act"></button><form @submit.prevent="act"></form></div>',
               '<div><button on-click.stop="act"></button><form on-submit.prevent="act"></form></div>')
        fixed=self.apply(p)['code']
        self.assertIn('on-click="stop:act"',fixed)
        self.assertIn('on-submit="prevent:act"',fixed)

    def test_modifier_only_empty_and_missing_dragover_get_proven_noop(self):
        for target in ('<div on-dragover=""></div>','<div></div>'):
            p=pair('<div @dragover.prevent></div>',target)
            r=self.apply(p)
            self.assertIn('on-dragover="prevent:',r['code'])
            self.assertIn('__sourceDomNoop_',r['code'])
            no_prevent=r['code'].replace('prevent:','')
            self.assertTrue(self.apply((no_prevent,p[1]),repair=False)['findings'])
            self.assertIn('prevent:',self.apply((no_prevent,p[1]))['code'])

    def test_enter_uses_explicit_key_guard_not_ignored_san_modifier(self):
        for target in ('<input on-keyup.enter="act"/>','<input on-keyup="enter:act"/>'):
            p=pair('<input @keyup.enter="act"/>',target)
            r=self.apply(p)
            self.assertNotIn('on-keyup="enter:',r['code'])
            self.assertIn("event.key === 'Enter'",r['code'])
            self.assertIn('event.keyCode === 13',r['code'])
            self.assertEqual(self.apply((r['code'],p[1]))['changes'],[])

    def run_listener(self,code,event,events):
        js="""const fs=require('fs'),san=require('san'),listener=require('san/src/view/get-event-listener');
const {code,event,events}=JSON.parse(fs.readFileSync(0,'utf8')),m={exports:{}};
new Function('require','module',/<script>([\\s\\S]*?)<\\/script>/.exec(code)[1])(require,m);
const c=new m.exports();let calls=0,prevent=0,stop=0;c.act=()=>calls++;
const root=san.parseTemplate(/<template>([\\s\\S]*?)<\\/template>/.exec(code)[1]).children[0];
const bind=root.events.find(e=>e.name===event),fn=listener(bind,c,c.data,false),target={};
for(const e of events)fn({...e,target,currentTarget:e.inner?{}:target,preventDefault(){prevent++;},stopPropagation(){stop++;}});
process.stdout.write(JSON.stringify({calls,prevent,stop,flag:c.data.get('flag')}));"""
        r=subprocess.run(['node','-e',js],input=json.dumps({'code':code,'event':event,'events':events}),
            text=True,encoding='utf-8',capture_output=True,cwd=ROOT)
        self.assertEqual(r.returncode,0,r.stderr)
        return json.loads(r.stdout)

    def test_installed_san_listener_obeys_self_and_does_not_close_on_inner_click(self):
        p=pair('<div @click.self="flag=false"></div>','<div on-click="flag=false"></div>')
        code=self.apply(p)['code']
        self.assertTrue(self.run_listener(code,'click',[{'inner':True}])['flag'])
        self.assertFalse(self.run_listener(code,'click',[{'inner':True},{}])['flag'])

    def test_installed_san_listener_enter_and_prevent_stop_effects(self):
        p=pair('<input @keyup.enter="act"/>','<input on-keyup.enter="act"/>')
        events=[{'key':'Escape','keyCode':13},{'key':'a','keyCode':65},{'key':'Enter','keyCode':13},{'keyCode':13}]
        self.assertEqual(self.run_listener(self.apply(p)['code'],'keyup',events)['calls'],2)
        # A parsed unknown modifier alone does not filter the key in installed San.
        raw=p[0].replace('on-keyup.enter="act"','on-keyup="enter:act"')
        self.assertEqual(self.run_listener(raw,'keyup',events)['calls'],4)
        for mod,event in [('prevent','submit'),('stop','click')]:
            p=pair(f'<form @{event}.{mod}="act"></form>',f'<form on-{event}.{mod}="act"></form>')
            result=self.run_listener(self.apply(p)['code'],event,[{}])
            self.assertEqual(result['calls'],1)
            self.assertEqual(result[mod],1)

    def test_native_drag_contracts_restore_missing_bindings_but_not_custom_names(self):
        p=pair('<div @dragover.prevent @drop.stop="act" @dragend="act"><child-widget @drag-start="act"/></div>',
               '<div><child-widget on-drag-start="act"/></div>')
        code=self.apply(p)['code']
        self.assertIn('on-drop="stop:act"',code)
        self.assertIn('on-dragend="act"',code)
        self.assertIn('<child-widget on-drag-start="act"/>',code)

    def test_loop_tuple_and_redundant_key_are_proven_from_source(self):
        p=pair('<ul><li v-for="(row,idx) in rows" :key="row.id">{{idx}}</li></ul>',
               '<ul><li s-for="(row, idx) in rows trackby row.id" key="{{row.id}}">{{idx}}</li></ul>')
        r=self.apply(p)
        self.assertIn('s-for="row, idx in rows trackby row.id"',r['code'])
        self.assertNotIn('key="',r['code'])
        self.assertEqual(self.apply((r['code'],p[1]))['changes'],[])

    def test_conflicting_keys_collections_aliases_or_conditions_are_not_guessed(self):
        p=pair('<div><span v-for="row in rows" :key="row.id" v-if="mode"/></div>',
               '<div><span s-for="row in rows trackby row.id" key="{{row.id}}" s-if="mode"/></div>')
        for old,new in [('key="{{row.id}}"','key="{{row.other}}"'),('in rows','in other'),
                        ('row in','item in'),('s-if="mode"','s-if="flag"')]:
            wrong=p[0].replace(old,new)
            self.assertEqual(self.apply((wrong,p[1]))['code'],wrong)

    def test_missing_key_uses_exact_source_path_not_a_guessed_identity_policy(self):
        p=pair('<div><span v-for="row in rows" :key="row.id"/></div>',
               '<div><span s-for="row in rows"/></div>')
        r=self.apply(p)
        self.assertIn('s-for="row in rows trackby row.id"',r['code'])
        self.assertEqual(r['findings'][0]['code'],'source_dom_loop_not_landed')
        unkeyed=pair('<div><span v-for="row in rows"/></div>','<div><span s-for="row in rows"/></div>')
        self.assertEqual(self.apply(unkeyed)['code'],unkeyed[0])

    def test_source_index_key_records_unproven_runtime_identity_review(self):
        p=pair('<div><span v-for="(row,idx) in rows" :key="idx"/></div>',
               '<div><span s-for="row, idx in rows"/></div>')
        r=self.apply(p)
        self.assertEqual(r['code'],p[0]);self.assertEqual(r['findings'],[])
        self.assertEqual(r['reviews'][0]['reason'],'source_index_key_runtime_identity_unproven')

    def test_boolean_self_can_call_one_exact_setter_but_not_add_extra_effects(self):
        p=pair('<div @click.self="flag=false"/>','<div on-click="guard($event)"/>',
            'guard(e){if(e && e.target===e.currentTarget)this.hide();},hide(){this.data.set("flag",false);}')
        self.assertEqual(self.apply(p)['findings'],[])
        bad=p[0].replace('this.data.set("flag",false);','this.data.set("flag",false);this.erase();')
        self.assertTrue(self.apply((bad,p[1]),repair=False)['findings'])

    def test_deleting_an_event_cannot_hide_a_source_modifier_defect(self):
        p=pair('<button @click.stop="act"/>','<button on-click.stop="act"/>')
        fixed=self.apply(p)['code']
        deleted=fixed.replace(' on-click="stop:act"','')
        r=self.apply((deleted,p[1]))
        self.assertTrue(r['findings'])
        self.assertEqual(r['code'],deleted)

    def test_deleting_all_key_metadata_cannot_hide_a_loop_defect(self):
        p=pair('<div><span v-for="row in rows" :key="row.id"/></div>',
               '<div><span s-for="(row) in rows trackby row.id" key="{{row.id}}"/></div>')
        fixed=self.apply(p)['code']
        deleted=fixed.replace(' trackby row.id','')
        self.assertTrue(self.apply((deleted,p[1]),repair=False)['findings'])

    def test_losing_a_previously_mapped_scope_is_a_gate_regression(self):
        p=pair('<div><button @click.stop="act"/></div>','<div><button on-click="stop:act"/></div>')
        before={'generated_code':p[0],'ssm':{},'vue_source':p[1],'validation_errors':[]}
        after={**before,'generated_code':p[0].replace('<button','<span')}
        gate=candidate_gate(before,after)
        self.assertTrue(gate['should_stop'])
        self.assertEqual(gate['lost_source_dom_scopes'],['template'])

    def test_changing_loop_or_condition_cannot_disable_node_contract_checks(self):
        p=pair('<div><span v-for="row in rows" v-if="mode" @click.stop="act"/></div>',
               '<div><span s-for="row in rows" s-if="mode" on-click="stop:act"/></div>')
        before={'generated_code':p[0],'ssm':{},'vue_source':p[1],'validation_errors':[]}
        for old,new in [('in rows','in other'),('s-if="mode"','s-if="flag"')]:
            after={**before,'generated_code':p[0].replace(old,new)}
            gate=candidate_gate(before,after)
            self.assertTrue(gate['should_stop'])
            self.assertEqual(gate['lost_source_dom_scopes'],[])
            self.assertTrue(gate['lost_source_dom_nodes'])

    def test_alias_shadowing_slots_unsupported_modifiers_and_ambiguous_events_refuse_edits(self):
        cases=[pair('<div v-for="flag in rows" @click.self="flag=false"/>',
                    '<div s-for="flag in rows" on-click="flag=false"/>'),
               pair('<div v-slot="slotProps" @click.self="flag=false"/>','<div on-click="flag=false"/>'),
               pair('<div @click.once="act"/>','<div on-click.once="act"/>'),
               pair('<div @click.stop="act"/>','<div on-click="act" on-click.stop="act"/>')]
        for p in cases:self.assertEqual(self.apply(p)['code'],p[0])

    def test_unknown_behavior_cannot_replace_existing_handler(self):
        p=pair('<div @click.stop="act"/>','<div on-click="unknown($event)"/>')
        self.assertEqual(self.apply(p)['code'],p[0])
        p=pair('<div @click.self="flag=false"/>','<div on-click="act"/>')
        self.assertEqual(self.apply(p)['code'],p[0])

    def test_emit_quote_spelling_does_not_change_event_identity(self):
        p=pair("<button @click.stop='$emit(\"edit\", rows)'/>",
               '<button on-click.stop="fire(\'edit\', rows)"/>')
        code=self.apply(p)['code']
        self.assertNotIn('on-click.stop',code)
        self.assertIn('stop:fire(',code)

    def test_no_source_bad_shape_comments_and_js_examples_are_not_rewritten(self):
        p=pair('<div @click.stop="act"/>','<div on-click.stop="act"/>')
        self.assertEqual(self.apply((p[0],''))['code'],p[0])
        self.assertEqual(self.apply((p[0],p[1].replace('<div','<span').replace('/>','/>')))['code'],p[0])
        example=p[0].replace('const san=', 'const example=`<button on-click.stop="act"/>`;const san=')
        fixed=self.apply((example,p[1]))['code']
        self.assertIn('const example=`<button on-click.stop="act"/>`;',fixed)
        r=self.apply(p,repair=False)
        self.assertEqual(r['code'],p[0]);self.assertTrue(r['findings'])

    def test_analyzer_failure_never_returns_a_guessed_fix(self):
        p=pair('<div @click.stop="act"/>','<div on-click.stop="act"/>')
        _run.cache_clear()
        with patch('migration_pipeline.utils.source_dom_semantics.subprocess.run',side_effect=OSError):
            r=source_dom_semantics(p[0],p[1],repair=True)
            self.assertEqual(r['code'],p[0]);self.assertIn('error',r)
        _run.cache_clear()

    @classmethod
    def setUpClass(cls):
        cls.state=json.loads((SOURCE/'repair_reports/complex/TaskManager_repair_history.json').read_text(encoding='utf-8'))['state']
        cls.code=(BASE/'TaskManager_inline_formatter_offline.san').read_text(encoding='utf-8')
        cls.vue=SOURCE/'protocol/frozen/data/datasets/components/03_complex/TaskManager/vue/TaskManager.vue'

    def test_frozen_task_manager_closes_supported_contracts_not_remaining_business_errors(self):
        r=self.apply((self.code,self.vue.read_text(encoding='utf-8')),self.state['ssm'])
        def assess(code):
            val=ValidateStage().run(ValidateStageInput(generated_code=code,ssm=self.state['ssm'],vue_file_path=str(self.vue))).to_state_update()
            return {**val,'generated_code':code,'ssm':self.state['ssm'],'vue_file_path':str(self.vue)}
        before,after=assess(self.code),assess(r['code'])
        self.assertEqual(len(before['validation_errors']),33)
        self.assertEqual({e['code'] for e in after['validation_errors']},{'unsupported_san_inline_template_math_global',
            'unsupported_san_inline_template_member_call','invalid_san_multi_argument_fire','hidden_template_reactive_dependency',
            'nested_state_mutation','source_event_payload_not_landed','source_render_call_not_landed',
            'source_render_dependency_not_landed','source_array_transaction_not_landed',
            'source_child_factory_not_landed','source_child_watch_not_landed','source_native_drag_not_landed','source_parent_watch_not_landed','source_parent_watch_exception_policy_unproven','source_parent_watch_dynamic_key_unproven'})
        self.assertFalse(after['validation_passed'])
        self.assertFalse(candidate_gate(before,after)['should_stop'])
        self.assertTrue(candidate_gate(after,before)['should_stop'])
        fixed,steps=RepairStage._deterministic_repair_plan(self.code,before['validation_errors'],[],self.state['ssm'],str(self.vue),enable_residual_v2=True)
        payload=source_payload_semantics(r['code'],self.vue.read_text(encoding='utf-8'),self.state['ssm'],repair=True)
        render_calls=source_render_call_semantics(payload['code'],self.vue.read_text(encoding='utf-8'),self.state['ssm'],repair=True)
        dependency=source_render_dependency_semantics(render_calls['code'],self.vue.read_text(encoding='utf-8'),repair=True)
        transaction=source_array_transaction_semantics(dependency['code'],self.vue.read_text(encoding='utf-8'),repair=True)
        expected=source_native_drag_semantics(source_child_initialization_semantics(transaction['code'],self.vue.read_text(encoding='utf-8'),repair=True)['code'],self.vue.read_text(encoding='utf-8'),repair=True)['code']
        self.assertEqual(fixed,source_parent_watch_semantics(expected,self.vue.read_text(encoding='utf-8'),repair=True)['code'])
        self.assertIn(('source_readonly_render_graph','explicit_source_readonly_render_dependency_graph'),steps)
        self.assertEqual({e['code'] for e in assess(fixed)['validation_errors']},{'source_parent_watch_not_landed','source_parent_watch_exception_policy_unproven','source_parent_watch_dynamic_key_unproven'})
        self.assertIn(('source_array_transaction_contracts','detached_and_committed_source_array_transaction'),steps)
        self.assertIn(('source_render_operand_contracts','lifted_source_render_calls_with_explicit_operands'),steps)
        self.assertIn(('source_single_payload_contracts','restored_source_single_payload_contract'),steps)
        self.assertNotIn('invalid_san_multi_argument_fire',{e['code'] for e in assess(fixed)['validation_errors']})
        self.assertIn(('source_scoped_dom_contracts','restored_source_loop_syntax'),steps)
        self.assertIn(('source_scoped_dom_contracts','restored_source_native_event_contract'),steps)
        self.assertIn('on-drag-start="onDragStart"',fixed)
        self.assertIn('on-dragend="onDragEnd"',fixed)
        self.assertIn('on-keyup="__sourceDomEnter_',fixed)
        self.assertEqual(self.apply((fixed,self.vue.read_text(encoding='utf-8')),self.state['ssm'])['changes'],[])

    def test_partial_repair_allows_progress_but_regression_is_rejected_per_node(self):
        p=pair('<div><button @click.stop="act"/><button @click.stop="act"/></div>',
               '<div><button on-click.stop="act"/><button on-click.stop="act"/></div>')
        partial=p[0].replace('on-click.stop="act"','on-click="stop:act"',1)
        with tempfile.TemporaryDirectory() as tmp:
            vue=Path(tmp)/'a.vue';vue.write_text(p[1],encoding='utf-8')
            def assess(code):
                return {'generated_code':code,'ssm':{},'vue_file_path':str(vue),
                    **ValidateStage().run(ValidateStageInput(generated_code=code,vue_file_path=str(vue))).to_state_update()}
            before,after=assess(p[0]),assess(partial)
            self.assertFalse(candidate_gate(before,after)['should_stop'])
            self.assertTrue(candidate_gate(after,before)['should_stop'])

    def test_parent_enter_guard_traceability_and_model_postprocessing(self):
        p=pair('<input @keyup.enter="act"/>','<input on-keyup.enter="act"/>')
        ssm={'template':{'event_bindings':[{'event_name':'keyup','handler_expression':'act'}]}}
        class Client:
            def repair(self,request):
                return RepairResult(code=p[0],saved_file_path=request.output_file_path,source_file='',ssm=ssm,provider='stub',model='stub',raw_response={})
        with tempfile.TemporaryDirectory() as tmp:
            vue=Path(tmp)/'a.vue';vue.write_text(p[1],encoding='utf-8')
            result=RepairStage(Client()).run(RepairStageInput(ssm=ssm,generated_code=p[0],vue_file_path=str(vue),
                output_file_path=str(Path(tmp)/'out.san'),metadata={'skip_deterministic_prepass':True,'semantic_rule_set':'residual_v2'}))
            self.assertIn('restored_source_native_event_contract',result.raw_response['pipeline_postprocessing'])
            before={'generated_code':p[0],'ssm':ssm,'vue_file_path':str(vue),'validation_errors':[]}
            after={**before,'generated_code':result.repaired_code}
            gate=candidate_gate(before,after)
            self.assertFalse(gate['should_stop'],gate)
            self.assertTrue(gate['after']['proven_native_guards'])
            self.assertFalse(gate['after']['proven_self_wrappers'])

    def test_shared_repair_prompt_documents_runtime_enter_and_native_custom_boundary(self):
        prompt=build_repair_prompt(RepairPromptInput(ssm={},current_code=self.code,
            validation_errors=[{'code':'source_dom_event_not_landed'}]))
        self.assertTrue('does not enforce Enter-only filtering' in prompt)
        self.assertTrue('custom drag-start/drag-end' in prompt)
