"""Empty-class comparison must fail closed for attribute observers and unknown code."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest

PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT/'src'))
from card_migration_system.adapters.browser import BrowserEvaluator
from card_migration_system.config import load_settings
from card_migration_system.runtime import profile
from card_migration_system.stages.dom_comparison import compare_dom
from card_migration_system.stages.evaluation import assess,candidate_decision
from test_modular_system import FakeBrowser,FakeModel,ModularFixture,SAN

SOURCE='''<template><div><button :class="{selected:flag}" @click="toggle">Choose</button><p>{{flag ? 'on' : 'off'}}</p></div></template><script>module.exports={name:'EmptyClassCard',data(){return {flag:false}},methods:{toggle(){this.flag=!this.flag}}}</script><style>button.selected{color:rgb(10,100,50)}</style>'''
TARGET='''<template><div><button class="{{flag ? 'selected' : ''}}" on-click="toggle">Choose</button><p>{{flag ? 'on' : 'off'}}</p></div></template><script>const san=require('san');const DataTypes=san.DataTypes;module.exports=san.defineComponent({name:'EmptyClassCard',dataTypes:{},initData(){return {flag:false}},toggle(){this.data.set('flag',!this.data.get('flag'))}})</script><style>button.selected{color:rgb(10,100,50)}</style>'''
APPROVED={'version':'empty_class_presence_v1','approved':True,'reasons':[]}


def policy(source=SOURCE,code=TARGET):
    request={'repository':str(PROJECT/'engine'),'project':str(PROJECT),'source':source,'code':code,'action':'comparison-policy'}
    p=subprocess.run(['node',str(PROJECT/'browser/evaluate.mjs')],input=json.dumps(request).encode(),capture_output=True,timeout=30)
    if p.returncode:raise AssertionError(p.stdout.decode()[:500])
    return json.loads(p.stdout)['policy']


def node(attrs):
    return {'tag':'button','attributes':attrs,'label':'button|'+'|'.join(sorted(k+'='+v for k,v in attrs.items())),'children':[]}


class EmptyClassAnalysisTests(unittest.TestCase):
    def test_data_only_component_can_use_comparison_policy(self):
        self.assertTrue(policy()['approved'])

    def test_attribute_selectors_attr_function_and_external_styles_keep_exact_comparison(self):
        for css in ('button[class]{color:red}',r'button[cl\61 ss]{color:red}',
                    'button::after{content:attr(class)}','@import "other.css";'):
            with self.subTest(css=css):
                result=policy(SOURCE.replace('button.selected{color:rgb(10,100,50)}',css))
                self.assertFalse(result['approved']);self.assertTrue(result['reasons'])
        self.assertFalse(policy(SOURCE.replace('<style>','<style src="other.css">'))['approved'])

    def test_script_DOM_reflection_unknown_calls_and_runtime_extensions_block(self):
        for body in ('const x=document.querySelector("button")',
                     'const x=this.$el.hasAttribute("class")',
                     'unknownLibrary()', 'const x=this;Object.keys(x)',
                     'const x=this["get"+"El"]()', 'new Function("return 1")()'):
            with self.subTest(body=body):
                self.assertFalse(policy(SOURCE.replace('this.flag=!this.flag',body))['approved'])
        self.assertFalse(policy(SOURCE.replace("name:'EmptyClassCard'","name:'EmptyClassCard',mixins:[other]"))['approved'])

    def test_template_reflection_is_not_hidden_from_script_analysis(self):
        self.assertFalse(policy(SOURCE.replace("flag ? 'on' : 'off'","$el.hasAttribute('class')"))['approved'])
        self.assertFalse(policy(code=TARGET.replace("flag ? 'on' : 'off'","flag['con'+'structor']()"))['approved'])


class EmptyClassComparisonTests(unittest.TestCase):
    def test_raw_tree_is_retained_and_only_copy_is_normalized(self):
        a,b=node({'class':'','title':'a|b=c'}),node({'title':'a|b=c'})
        original=deepcopy(a)
        result=compare_dom(a,b,APPROVED)
        self.assertEqual(result['raw_metric']['distance'],1)
        self.assertEqual(result['metric']['distance'],0)
        self.assertEqual(a,original);self.assertFalse(result['raw_evidence_modified'])
        self.assertTrue(result['raw_differences']);self.assertFalse(result['differences'])

    def test_unavailable_denied_or_unversioned_policy_keeps_raw_difference(self):
        for value in (None,{'approved':True},{**APPROVED,'approved':False},{**APPROVED,'version':'unknown'}):
            self.assertEqual(compare_dom(node({'class':''}),node({}),value)['metric']['distance'],1)

    def test_label_only_historical_evidence_is_not_silently_rewritten(self):
        self.assertEqual(compare_dom({'label':'button|class=','children':[]},{'label':'button|','children':[]},APPROVED)['metric']['distance'],1)

    def test_nonempty_class_and_other_attributes_are_not_waived(self):
        for attrs in ({'class':'selected'},{'class':' '},{'disabled':''},{'value':''}):
            self.assertEqual(compare_dom(node(attrs),node({}),APPROVED)['metric']['distance'],1)

    def test_real_DOM_mismatch_is_sent_to_repair_with_path_and_attributes(self):
        data=FakeBrowser().evaluate('','',{},[])
        data['vue']['snapshots'][0]['dom']=node({'class':''})
        data['san']['snapshots'][0]['dom']=node({})
        data['comparison_policy']={**APPROVED,'approved':False,'reasons':['source:css_attribute_observation']}
        result=assess({'validation_passed':True,'validation_errors':[]},data,[],{'structure':.95,'ui':.95,'pixel_difference':.05})
        finding=next(f for f in result['diagnostics'] if f['code']=='rendered_dom_mismatch')
        self.assertEqual(finding['differences'][0]['path'],'root')
        self.assertIn('class=',finding['differences'][0]['expected'])
        self.assertEqual(result['dimensions']['structure'],'fail')

    def test_partial_DOM_progress_is_not_lost_when_template_score_is_unchanged(self):
        old={'dimensions':{'structure':'fail'},'source_blocked':False,'diagnostics':[{'code':'rendered_dom_mismatch'}],
             'structure_ted':{'similarity':1},'dom_ted':{'similarity':.5},'ui_restoration':100}
        new={**old,'dom_ted':{'similarity':.75}}
        self.assertTrue(candidate_decision(old,new)['accepted'])


class EmptyClassBrowserTests(unittest.TestCase):
    def test_click_toggle_uses_policy_but_retains_raw_DOM_difference(self):
        settings=load_settings(project_root=PROJECT,environ={})
        actions=[{'name':'on','type':'click','selector':'button'},{'name':'off','type':'click','selector':'button'}]
        data=BrowserEvaluator(settings,profile(settings)).evaluate(SOURCE,TARGET,{},actions)
        result=assess({'validation_passed':True,'validation_errors':[]},data,actions,{'structure':.95,'ui':.95,'pixel_difference':.05})
        self.assertTrue(data['comparison_policy']['approved'],data['comparison_policy'])
        self.assertTrue(result['passed'],result)
        self.assertGreater(result['raw_dom_ted']['distance'],0)
        self.assertEqual(result['dom_ted']['distance'],0)
        self.assertEqual(result['dimensions']['interaction'],'pass')

    def test_CSS_attribute_observer_remains_a_failure(self):
        settings=load_settings(project_root=PROJECT,environ={})
        source=SOURCE.replace('button.selected{color:rgb(10,100,50)}','button[class]{color:rgb(200,0,0)}')
        code=TARGET.replace('button.selected{color:rgb(10,100,50)}','button[class]{color:rgb(200,0,0)}')
        data=BrowserEvaluator(settings,profile(settings)).evaluate(source,code,{},[])
        result=assess({'validation_passed':True,'validation_errors':[]},data,[],{'structure':.95,'ui':.95,'pixel_difference':.05})
        self.assertFalse(data['comparison_policy']['approved'])
        self.assertEqual(result['dimensions']['structure'],'fail')
        self.assertFalse(result['passed'])


class EmptyClassRepairFeedbackTests(ModularFixture,unittest.TestCase):
    def test_exact_DOM_finding_reaches_the_existing_model_repair_message(self):
        class MismatchBrowser(FakeBrowser):
            def evaluate(self,source,code,props,actions):
                data=super().evaluate(source,code,props,actions)
                data['comparison_policy']={**APPROVED,'approved':False,'reasons':['test_requires_exact_presence']}
                data['vue']['snapshots'][0]['dom']=node({'class':''})
                data['san']['snapshots'][0]['dom']=node({} if 'BAD' in code else {'class':''})
                return data
        model=FakeModel([SAN.replace('Hello','BAD'),SAN]);messages=[];exchange=model.exchange
        def capture(value):messages.append(value);return exchange(value)
        model.exchange=capture;self.service.model=model;self.service.browser=MismatchBrowser()
        key=self.enqueue(max_repair_rounds=1);result=self.run_graph(key)
        self.assertEqual(result['status'],'finished');self.assertEqual(result['actual_cloud_model_calls'],0)
        self.assertEqual(len(messages),2)
        content=messages[1][1]['content']
        self.assertIn('rendered_dom_mismatch',content)
        self.assertIn('button|class=',content)
        self.assertIn('test_requires_exact_presence',content)
        self.assertIn('root',content)


if __name__=='__main__':unittest.main()
