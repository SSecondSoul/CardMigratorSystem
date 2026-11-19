"""Real parsers, bounded rule negatives and application routing; no cloud calls."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT/'src'))
from card_migration_system.adapters.syntax import target_syntax
from card_migration_system.config import load_settings
from card_migration_system.stages.syntax import failed_syntax,syntax_repair_messages
from card_migration_system.stages.evaluation import candidate_decision
from test_modular_system import ModularFixture,FakeBrowser,FakeModel,SAN,SOURCE

LOOP_SOURCE='''<template><select><option v-for="cat in categories" :key="cat" :value="cat">{{cat}}</option></select></template>
<script>export default {data(){return {categories:['a','b']}}}</script>'''
BROKEN='''<template><select><s-for="cat in categories trackby cat"><option value="{{cat}}">{{cat}}</option></s-for></select></template>
<script>const san=require('san');module.exports=san.defineComponent({initData(){return {categories:['a','b']}},clearAll(){if(true){return 1}}clearFilter(){return 2}})</script>'''


class RealSyntaxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.settings=load_settings(project_root=PROJECT,environ={})

    def inspect(self,code=BROKEN,source=LOOP_SOURCE,normalize=False):
        return target_syntax(self.settings,source,code,normalize=normalize)

    def test_SFC_and_script_errors_both_have_absolute_locations_and_excerpts(self):
        result=self.inspect()
        codes={d['code'] for d in result['diagnostics']}
        self.assertIn('target_sfc_syntax_error',codes);self.assertIn('target_script_syntax_error',codes)
        for item in result['diagnostics']:
            self.assertGreater(item['location']['column'],0)
            self.assertTrue(item['excerpt']);self.assertTrue(item['message'])

    def test_bounded_rules_restore_loop_attribute_and_adjacent_method_comma(self):
        result=self.inspect(normalize=True)
        self.assertEqual(result['after']['status'],'pass',result)
        self.assertEqual(len(result['changes']),2)
        self.assertIn('<option s-for="cat in categories trackby cat"',result['code'])
        self.assertIn('}} ,clearFilter'.replace(' ',''),result['code'])
        self.assertNotIn('<s-for=',result['code'])
        again=self.inspect(result['code'],normalize=True)
        self.assertEqual(again['code'],result['code']);self.assertEqual(again['changes'],[])

    def test_loop_scope_key_collection_and_element_must_match_source(self):
        for source in (LOOP_SOURCE.replace('v-for="cat','v-for="other'),
                       LOOP_SOURCE.replace(':key="cat"',':key="cat.id"'),
                       LOOP_SOURCE.replace('in categories','in otherCategories'),
                       LOOP_SOURCE.replace('<option','<span').replace('</option>','</span>'),
                       LOOP_SOURCE.replace(' :key="cat"','')):
            with self.subTest(source=source):
                result=self.inspect(source=source,normalize=True)
                self.assertIn('<s-for=',result['code'])

    def test_multiple_children_extra_attributes_and_nested_loops_are_not_guessed(self):
        for code in (BROKEN.replace('</option>','</option><b>x</b>'),
                     BROKEN.replace('<s-for=', '<s-for class="x" s-for='),
                     BROKEN.replace('<option value=', '<s-for="other in others trackby other"><option value=').replace('</option>','</option></s-for>')):
            with self.subTest(code=code):
                self.assertIn('<s-for',self.inspect(code,normalize=True)['code'])

    def test_no_comma_guess_for_statements_arrays_or_multiple_script_errors(self):
        for script in ('const x=[foo() bar()]','function a(){} function b( {}',
                       'const x={a(){return 1}b(){return (}}'):
            code='<template><div/></template><script>'+script+'</script>'
            self.assertEqual(self.inspect(code,normalize=True)['code'],code)

    def test_fake_loop_literal_in_attribute_comment_or_interpolation_is_never_rewritten(self):
        literal='<s-for="cat in categories trackby cat"><option>{{cat}}</option></s-for>'
        for body in ("<div title='"+literal+"'></div>", '<div><!--'+literal+'--></div>',
                     '<div>{{\''+literal+'\'}}</div>'):
            code=BROKEN.replace(BROKEN.split('<template>')[1].split('</template>')[0],body)
            result=self.inspect(code,normalize=True)
            self.assertIn(literal,result['code'])
            self.assertFalse(any(c['rule'].startswith('source_matched') for c in result['changes']))

    def test_valid_target_is_byte_identical_and_does_not_execute_script(self):
        code=SAN.replace('const san', 'throw Error("must-not-execute"); const san')
        result=self.inspect(code,normalize=True)
        self.assertEqual(result['after']['status'],'pass');self.assertEqual(result['code'],code)

    def test_missing_option_restores_only_the_unique_source_proven_leaf(self):
        code=BROKEN.replace('<option value="{{cat}}">{{cat}}</option>','{{cat}}')
        result=self.inspect(code,normalize=True)
        self.assertEqual(result['after']['status'],'pass',result)
        self.assertIn('<option s-for="cat in categories trackby cat" value="{{cat}}">{{cat}}</option>',result['code'])
        self.assertTrue(any(c['rule']=='source_proven_missing_option_leaf_v1' for c in result['changes']))
        self.assertEqual(self.inspect(result['code'],normalize=True)['code'],result['code'])

    def test_missing_option_with_unproved_attributes_scope_value_or_location_is_not_invented(self):
        code=BROKEN.replace('<option value="{{cat}}">{{cat}}</option>','{{cat}}')
        for source in (LOOP_SOURCE.replace(':value="cat"',':value="cat.id"'),
                       LOOP_SOURCE.replace('<option','<option disabled'),
                       LOOP_SOURCE.replace('<select>','<select v-if="visible">'),
                       LOOP_SOURCE.replace('<option','<option @click="choose"'),
                       LOOP_SOURCE.replace('{{cat}}','{{cat.label}}'),
                       LOOP_SOURCE.replace('</select>','<option v-for="cat in categories" :key="cat" :value="cat">{{cat}}</option></select>')):
            with self.subTest(source=source):self.assertIn('<s-for=',self.inspect(code,source,True)['code'])
        self.assertIn('<s-for=',self.inspect(code.replace('<select>','<div>').replace('</select>','</div>'),normalize=True)['code'])
        source=LOOP_SOURCE.replace('<select>','<select v-model="chosen">')
        wrong=code.replace('<select>','<select value="{= other =}">')
        self.assertIn('<s-for=',self.inspect(wrong,source,True)['code'])

    def test_multiple_adjacent_commas_are_atomic_and_require_full_parse(self):
        script='const san=require("san");module.exports=san.defineComponent({a(){return 1}b(){return 2}c(){return 3}})'
        code='<template><div/></template><script>'+script+'</script>'
        result=self.inspect(code,normalize=True)
        self.assertEqual(result['after']['status'],'pass',result)
        self.assertEqual(len(result['changes']),2)
        self.assertEqual(self.inspect(code.replace('return 3','return ('),normalize=True)['code'],code.replace('return 3','return ('))

    def test_source_leaf_closing_tokens_and_comma_repair_are_atomic(self):
        source='''<template><div/></template><script>export default {data(){return {records:[]}},methods:{
          save(){localStorage.setItem('items',JSON.stringify(this.records))},next(){return 1}}}</script>'''
        script='''const san=require('san');module.exports=san.defineComponent({
          a(){return 1}b(){return 2},save(){localStorage.setItem("items",JSON.stringify(this.data.get("records"))),next(){return 1}})'''
        code='<template><div/></template><script>'+script+'</script>'
        result=self.inspect(code,source,True)
        self.assertEqual(result['after']['status'],'pass',result)
        self.assertTrue(any(c['rule']=='source_proven_leaf_closing_tokens_v1' for c in result['changes']))
        self.assertIn('get("records")))},next()',result['code'])
        self.assertEqual(self.inspect(result['code'],source,True)['code'],result['code'])
        # Also cover a missing call parenthesis before an existing method brace.
        code=code.replace('"records"))),next','"records"))},next')
        self.assertEqual(self.inspect(code,source,True)['after']['status'],'pass')

    def test_leaf_repair_refuses_changed_operands_unknown_state_and_child_components(self):
        source='''<template><div/></template><script>export default {data(){return {records:[]}},methods:{
          save(){localStorage.setItem('items',JSON.stringify(this.records))},next(){return 1}}}</script>'''
        script='''const san=require('san');module.exports=san.defineComponent({save(){localStorage.setItem("items",JSON.stringify(this.data.get("records"))),next(){return 1}})'''
        def wrap(script):return '<template><div/></template><script>'+script+'</script>'
        for bad in (script.replace('"items"','"other"'),script.replace('JSON.stringify','JSON.parse'),
                    script.replace('"records"','"other"'),script.replace('module.exports=','const Child='),
                    script.replace('save(){','save(){danger();'),script.replace('save(){','save(){/*unknown*/')):
            with self.subTest(bad=bad):self.assertEqual(self.inspect(wrap(bad),source,True)['code'],wrap(bad))
        self.assertEqual(self.inspect(wrap(script),source.replace('records:[]','other:[]'),True)['code'],wrap(script))

    def test_complex_closing_brace_requires_exact_source_body_and_parent_method(self):
        source='''<template><div/></template><script>export default {methods:{
          clean(items){return items.map(x=>x+1).filter(Boolean)},next(){return 1}}}</script>'''
        script="const san=require('san');module.exports=san.defineComponent({clean(items){return items.map(x=>x+1).filter(Boolean),next(){return 1}})"
        def wrap(value):return '<template><div/></template><script>'+value+'</script>'
        result=self.inspect(wrap(script),source,True)
        self.assertEqual(result['after']['status'],'pass',result['after'])
        self.assertEqual(result['changes'][0]['rule'],'source_exact_method_closing_brace_v1')
        for bad in (script.replace('x+1','x+2'),script.replace('module.exports=','const Child='),
                    script.replace('.map(x=>x+1)','.map(x=>x+this.limit)')):
            with self.subTest(bad=bad):self.assertEqual(self.inspect(wrap(bad),source,True)['code'],wrap(bad))

    @unittest.skipUnless((PROJECT.parent/'data/experiments/evaluator_calibration/2026-11-17_modular_expense_tracker_syntax_closure_v1/frozen/source.vue').is_file(), 'Historical experiment corpus is not part of the standalone distribution')
    def test_frozen_real_failed_revisions_unblock_syntax_without_model_or_live_task_changes(self):
        evidence=PROJECT.parent/'data/experiments/evaluator_calibration/2026-11-17_modular_expense_tracker_syntax_closure_v1/frozen'
        source=(evidence/'source.vue').read_text(encoding='utf-8')
        for number in range(4):
            with self.subTest(number=number):
                original=(evidence/f'revisions/{number}.san').read_bytes()
                result=self.inspect(original.decode(),source,True)
                self.assertEqual(result['after']['status'],'pass',result)
                self.assertEqual(self.inspect(result['code'],source,True)['code'],result['code'])
                self.assertEqual((evidence/f'revisions/{number}.san').read_bytes(),original)

    def test_non_SFC_and_script_setup_remain_failures(self):
        for code in ('not an SFC','<template><div/></template><script setup>const a=1</script>'):
            self.assertEqual(self.inspect(code)['status'],'fail')

    def test_san_expression_failure_is_reported(self):
        # Unknown on-* attributes are plain HTML to Vue's outer parser; this
        # deliberately reaches San's event-expression parser, not Vue's parser.
        result=self.inspect(SAN.replace('class="card"','class="card" on-click="foo(,)"'))
        self.assertEqual(result['status'],'fail')
        self.assertTrue(result['diagnostics'])
        specific=[d for d in result['diagnostics'] if d['code']=='target_template_syntax_error']
        self.assertTrue(specific)
        self.assertEqual(specific[0]['location_precision'],'exact')
        self.assertEqual(specific[0]['attribute'],'on-click')


class SyntaxGateTests(unittest.TestCase):
    def old(self):
        return failed_syntax({'status':'fail','diagnostics':[{'code':'target_script_syntax_error'}],
            'diagnostic_count':2,'overflow':False},'old')

    def test_newly_visible_semantic_failure_after_syntax_repair_is_not_hidden_or_rejected(self):
        old=self.old();new=deepcopy(old)
        new.update(syntax={'status':'pass'},diagnostics=[{'code':'lifecycle_behavior_not_landed'}])
        decision=candidate_decision(old,new)
        self.assertTrue(decision['accepted']);self.assertFalse(decision['migration_passed'])
        self.assertEqual(new['dimensions']['static'],'fail')

    def test_syntax_transition_never_trades_away_previous_pass_or_source_block(self):
        old=self.old();new=deepcopy(old);new['syntax']={'status':'pass'}
        new['source_blocked']=True;self.assertFalse(candidate_decision(old,new)['accepted'])
        new['source_blocked']=False;old['dimensions']['interaction']='pass'
        self.assertFalse(candidate_decision(old,new)['accepted'])

    def test_partial_syntax_progress_is_bounded_and_new_syntax_errors_reject(self):
        old=self.old();new=deepcopy(old);new['syntax']['diagnostic_count']=1
        self.assertTrue(candidate_decision(old,new)['accepted'])
        new['diagnostics'].append({'code':'target_sfc_syntax_error'})
        self.assertFalse(candidate_decision(old,new)['accepted'])

    def test_focused_messages_have_current_source_code_and_locations_not_full_SSM(self):
        syntax={'diagnostics':[{'code':'target_script_syntax_error','location':{'line':3,'column':4}}],'diagnostic_count':1}
        messages=syntax_repair_messages(SOURCE,SAN,syntax)
        data=json.loads(messages[1]['content'])
        self.assertEqual(data['current_san'],SAN);self.assertEqual(data['source_vue'],SOURCE)
        self.assertNotIn('ssm',data);self.assertIn('location',data['diagnostics'][0])


class SyntaxApplicationTests(ModularFixture,unittest.TestCase):
    def feedback_browser(self):
        class SyntaxBrowser(FakeBrowser):
            def syntax(self,source,code,normalize=False):
                broken='BROKEN' in code
                value={'status':'fail' if broken else 'pass','policy':'test',
                    'diagnostics':[{'code':'target_script_syntax_error','message':'still broken','excerpt':code[:150]}] if broken else [],
                    'diagnostic_count':int(broken),'overflow':False}
                return {'code':code,'changes':[]} if normalize else value
        return SyntaxBrowser()

    def test_rejected_attempt_feedback_is_bound_and_changes_next_prompt_not_accepted_parent(self):
        original=SAN.replace('Hello','BROKEN original')
        rejected=SAN.replace('Hello','BROKEN rejected attempt')
        model=FakeModel([original,rejected,SAN]);messages=[];exchange=model.exchange
        def capture(value):messages.append(value);return exchange(value)
        model.exchange=capture;self.service.model=model;self.service.browser=self.feedback_browser()
        key=self.enqueue(max_repair_rounds=2);result=self.run_graph(key)
        self.assertEqual(result['status'],'finished');self.assertEqual(model.calls,3)
        first=json.loads(messages[1][1]['content']);second=json.loads(messages[2][1]['content'])
        self.assertEqual(first['rejected_attempts'],[])
        self.assertEqual(second['current_san'],original)
        self.assertEqual(second['rejected_attempts'][0]['reason'],'no_syntax_progress')
        self.assertIn('BROKEN rejected attempt',second['rejected_attempts'][0]['diagnostics'][0]['excerpt'])
        self.assertNotEqual(messages[1],messages[2])
        self.assertEqual(result['state']['decisions'][0]['accepted'],False)
        self.assertEqual(self.service.cached(key,'revisions/2.json')['parent'],self.service.cached(key,'revisions/0.json')['file']['sha256'])

    def test_exact_repair_prompt_resend_is_blocked_before_model_call(self):
        self.model.codes=[SAN.replace('Hello','BROKEN')];self.service.browser=self.feedback_browser()
        key=self.enqueue(max_repair_rounds=2)
        with patch('card_migration_system.application.migrations.syntax_repair_messages',return_value=[{'role':'user','content':'unchanged'}]):
            result=self.run_graph(key)
        self.assertEqual(result['stop_reason'],'repeated_repair_request_blocked')
        self.assertEqual(self.model.calls,2)
        self.assertIsNone(self.service.cached(key,'calls/2/request.json'))

    def test_unparsed_target_defers_semantics_and_browser_and_uses_focused_model_feedback(self):
        class SyntaxBrowser(FakeBrowser):
            def __init__(self):super().__init__();self.normalized=0
            def syntax(self,source,code,normalize=False):
                value={'status':'fail' if 'BROKEN' in code else 'pass','policy':'test',
                    'diagnostics':[{'code':'target_script_syntax_error','message':'expected comma','location':{'line':2,'column':9}}] if 'BROKEN' in code else [],
                    'diagnostic_count':int('BROKEN' in code),'overflow':False}
                if normalize:self.normalized+=1;return {'code':code,'changes':[],'after':value}
                return value
            def evaluate(self,source,code,props,actions):
                if 'BROKEN' in code:raise AssertionError('Broken syntax reached browser')
                return super().evaluate(source,code,props,actions)
        from test_modular_system import checks
        def guarded_checks(repository,action,**kwargs):
            if 'BROKEN' in kwargs['code']:raise AssertionError('Broken syntax reached semantic stage')
            return checks(repository,action,**kwargs)
        model=FakeModel([SAN.replace('Hello','BROKEN'),SAN]);messages=[];exchange=model.exchange
        def capture(value):messages.append(value);return exchange(value)
        model.exchange=capture;self.service.model=model;self.service.browser=SyntaxBrowser();self.service.checks=guarded_checks
        key=self.enqueue(max_repair_rounds=1);result=self.run_graph(key)
        self.assertEqual(result['status'],'finished');self.assertEqual(result['actual_cloud_model_calls'],0)
        self.assertEqual(len(messages),2)
        self.assertIn('expected comma',messages[1][1]['content'])
        first=self.service.cached(key,'evaluations/0.json')
        self.assertIn('static_semantics',first['deferred_checks'])
        self.assertEqual(first['dimensions']['source_baseline'],'not_run')
        self.assertEqual(result['state']['decisions'][0]['reason'],'syntax_unblocked_semantic_checks')

    def test_rule_syntax_candidate_is_retested_without_an_extra_model_call(self):
        class SyntaxBrowser(FakeBrowser):
            def syntax(self,source,code,normalize=False):
                value={'status':'fail' if 'BROKEN' in code else 'pass','diagnostics':
                    [{'code':'target_script_syntax_error'}] if 'BROKEN' in code else [],'diagnostic_count':int('BROKEN' in code),'overflow':False}
                return {'code':code.replace('BROKEN','Hello'),'changes':[{'rule':'test_only'}]} if normalize else value
        self.model.codes=[SAN.replace('Hello','BROKEN')];self.service.browser=SyntaxBrowser()
        key=self.enqueue(max_repair_rounds=1);result=self.run_graph(key)
        self.assertEqual(result['status'],'finished');self.assertEqual(self.model.calls,1)
        revision=self.service.cached(key,'revisions/1.json')
        self.assertEqual(revision['origin'],'rule_repair');self.assertEqual(revision['repair_focus'],'syntax')


if __name__=='__main__':unittest.main()
