"""Generic positive/negative controls; real parsers/runtime, no model calls."""
from copy import deepcopy
from hashlib import sha256
import json
import subprocess
import unittest

from test_modular_system import PROJECT,FakeBrowser
from test_modular_evaluator_compatibility import parse_pair
from test_modular_empty_class_policy import policy,node,APPROVED
from card_migration_system.adapters.ssm import SSMExtractor
from card_migration_system.adapters.browser import BrowserEvaluator
from card_migration_system.adapters.legacy_checks import legacy_stage
from card_migration_system.config import load_settings
from card_migration_system.runtime import profile
from card_migration_system.stages.structure import tree_distance,ssm_template_tree,target_template_tree
from card_migration_system.stages.dom_comparison import compare_dom,compare_control_state
from card_migration_system.stages.evaluation import assess
from card_migration_system.prompts.repair_context import relevant_ssm,compact_issues

SOURCE='''<template><button @click="change">{{value}}</button></template><script>
module.exports={name:'GenericSetter',data(){return {value:0,other:0}},
created(){this.assignField('value',1)},methods:{
assignField(field,next){this[field]=next},change(){this.assignField('value',2)}}}
</script><style>button{color:rgb(20,40,60)}</style>'''
TARGET='''<template><button on-click="change">{{value}}</button></template><script>
const san=require('san');const DataTypes=san.DataTypes;module.exports=san.defineComponent({name:'GenericSetter',dataTypes:{},
initData(){return {value:0,other:0}},inited(){this.assignField('value',1)},
assignField(k,v){this.data.set(k,v)},change(){this.assignField('value',2)}})
</script><style>button{color:rgb(20,40,60)}</style>'''


def inspect(source=SOURCE,code=TARGET,repair=False):
    result=subprocess.run(['node',str(PROJECT/'engine/migration_pipeline/utils/bounded_semantics.cjs')],
        input=json.dumps({'vue':source,'code':code,'repair':repair}).encode(),capture_output=True,timeout=30)
    value=json.loads(result.stdout)
    if result.returncode or value.get('error'):raise AssertionError(value)
    return value


class SymmetricClassTests(unittest.TestCase):
    def compare(self,expression,target=None):
        source=SOURCE.replace('<button @click',f'<button :class="{expression}" @click')
        code=TARGET.replace('<button on-click',f'<button class="{{{{{target or expression}}}}}" on-click')
        pair=parse_pair(source,code)
        ssm=SSMExtractor(PROJECT/'engine').extract(source.encode(),'Generic.vue',sha256(source.encode()).hexdigest())['ssm']
        return pair,tree_distance(ssm_template_tree(ssm,pair['source']['class_bindings']),target_template_tree(pair['target']['tree']))

    def test_concatenation_ternary_array_and_object_have_symmetric_projections(self):
        for expression in ("'row ' + (value ? 'active' : '')", "value ? 'row on' : 'row off'",
                           "['row',value ? 'active' : '']", "{row:true,active:value}"):
            with self.subTest(expression=expression):
                pair,metric=self.compare(expression)
                self.assertEqual(metric['distance'],0,pair)
                self.assertEqual(pair['source']['class_bindings'][expression],['row'])

    def test_unseparated_unknown_fragment_is_not_a_guaranteed_class(self):
        expression="'row'+value"
        pair,metric=self.compare(expression)
        self.assertEqual(pair['source']['class_bindings'][expression],[])
        self.assertEqual(metric['distance'],0)
        self.assertNotIn('class=row',str(pair['target']))

    def test_missing_class_and_changed_literal_class_are_not_waived(self):
        for target in ("value ? 'active' : ''", "'other ' + (value ? 'active' : '')"):
            _,metric=self.compare("'row ' + (value ? 'active' : '')",target)
            self.assertGreater(metric['distance'],0)


class DOMClassificationTests(unittest.TestCase):
    def test_class_serialization_requires_approved_policy_and_keeps_raw(self):
        approved={**APPROVED,'version':'class_serialization_v2'}
        a,b=node({'class':'a b'}),node({'class':' b  a a '})
        original=deepcopy((a,b))
        result=compare_dom(a,b,approved)
        self.assertEqual(result['metric']['distance'],0)
        self.assertGreater(result['raw_metric']['distance'],0)
        self.assertEqual((a,b),original)
        self.assertEqual(result['representation_differences'][0]['kind'],'class_token_serialization')
        strict=compare_dom(a,b,{**approved,'approved':False})
        self.assertGreater(strict['metric']['distance'],0)
        self.assertFalse(strict['representation_differences'][0]['normalized'])
        self.assertGreater(compare_dom(node({'class':'a\u00a0b'}),node({'class':'a b'}),approved)['metric']['distance'],0)

    def test_attribute_observers_and_missing_tokens_remain_failures(self):
        source=SOURCE.replace('<style>','<style>button[class="a b"]{color:red}')
        self.assertFalse(policy(source,TARGET)['approved'])
        self.assertGreater(compare_dom(node({'class':'a b'}),node({'class':'a'}),
            {**APPROVED,'version':'class_serialization_v2'})['metric']['distance'],0)

    def test_wrapper_is_real_structure_not_representation(self):
        text={'label':'#text:Votes','children':[]}
        a={'label':'footer|','children':[text]}
        b={'label':'footer|','children':[{'label':'span|','children':[text]}]}
        result=compare_dom(a,b,{**APPROVED,'version':'class_serialization_v2'})
        self.assertGreater(result['metric']['distance'],0)
        self.assertFalse(result['representation_differences'])

    def test_path_only_change_is_not_reported_as_changed_value(self):
        a={'path':'root.0','tag':'button','value':'','checked':False}
        b={**a,'path':'root.1'}
        result=compare_control_state([a],[b])
        self.assertFalse(result['equal']);self.assertTrue(result['values_equal_in_order'])
        self.assertEqual(result['differences'][0]['kind'],'control_path_changed')
        data=FakeBrowser().evaluate('','',{},[])
        data['vue']['snapshots'][0]['styles']=[{**a,'styles':{}}]
        data['san']['snapshots'][0]['styles']=[{**b,'styles':{}}]
        report=assess({'validation_passed':True,'validation_errors':[]},data,[],{'structure':.95,'ui':.95,'pixel_difference':.05})
        self.assertEqual(report['dimensions']['structure'],'fail')
        self.assertIn('rendered_control_position_mismatch',[i['code'] for i in report['diagnostics']])
        self.assertNotIn('rendered_control_state_mismatch',[i['code'] for i in report['diagnostics']])

    def test_repair_receives_representation_evidence_and_position_uses_template_scope(self):
        issue={'code':'rendered_dom_mismatch','message':'diff',
            'representation_differences':[{'path':'root.1','kind':'empty_class_presence','normalized':False}]}
        self.assertEqual(compact_issues([issue])[0]['details']['representation_differences']['examples'][0]['path'],'root.1')
        selected,audit=relevant_ssm({'template':{'must':'retain'},'script':{'not_needed_for_position':True}},
            {'diagnostics':[{'code':'rendered_control_position_mismatch'}],'dimensions':{'visual':'pass'}})
        self.assertIn('template',selected);self.assertNotIn('script',selected)


class DynamicAssignmentProofTests(unittest.TestCase):
    def proof(self,source=SOURCE,code=TARGET):
        result=inspect(source,code)
        item=next(i for i in result['method_contracts'] if i.get('dynamic_assignment'))
        return result,item['dynamic_assignment']['scoped_proof']

    def test_method_and_parameter_names_do_not_select_the_rule(self):
        for name in ('assignField','setValue','updateAnything'):
            result,proof=self.proof(SOURCE.replace('assignField',name),TARGET.replace('assignField',name))
            self.assertEqual(proof['status'],'proven_for_source_internal_calls',proof)
            self.assertFalse(proof['arbitrary_key_semantics_proven'])
            self.assertNotIn('source_dynamic_assignment_unproven',[i['code'] for i in result['findings']])

    def test_constant_key_is_scope_resolved_and_reassigned_binding_is_refused(self):
        source=SOURCE.replace("this.assignField('value',2)","const field='value';this.assignField(field,2)")
        target=TARGET.replace("this.assignField('value',2)","const field='value';this.assignField(field,2)")
        self.assertEqual(self.proof(source,target)[1]['status'],'proven_for_source_internal_calls')
        source=source.replace("const field='value'","let field='value';field=unknown")
        self.assertEqual(self.proof(source,target)[1]['status'],'unproven')

    def test_unknown_dotted_symbol_namespace_props_and_computed_keys_are_refused(self):
        for expression in ('unknown',"'extra.key'","Symbol('x')","'data'","'assignField'","'missing'"):
            source=SOURCE.replace("'value',2",expression+',2')
            target=TARGET.replace("'value',2",expression+',2')
            with self.subTest(expression=expression):self.assertEqual(self.proof(source,target)[1]['status'],'unproven')
        for extra in ("props:{value:Number},", "computed:{value(){return 0}},"):
            source=SOURCE.replace("name:'GenericSetter',", "name:'GenericSetter',"+extra)
            self.assertEqual(self.proof(source,TARGET)[1]['status'],'unproven')

    def test_empty_returning_guarded_extra_effect_and_wrong_argument_setters_are_refused(self):
        for body in ('', 'return this.data.set(k,v)', 'this.data.set(v,k)',
                     "if(k==='value')this.data.set(k,v)", "this.data.set(k,v);this.fire('x')"):
            with self.subTest(body=body):self.assertEqual(self.proof(code=TARGET.replace('this.data.set(k,v)',body))[1]['status'],'unproven')

    def test_escaped_dynamic_unknown_template_and_changed_caller_keys_are_refused(self):
        for addition in ('const alias=this.assignField;', 'const self=this;', "this['assignField']('value',3);",
                         "this.data.set=function(){};"):
            target=TARGET.replace("this.assignField('value',2)",addition+"this.assignField('value',2)")
            with self.subTest(addition=addition):self.assertEqual(self.proof(code=target)[1]['status'],'unproven')
        self.assertEqual(self.proof(code=TARGET.replace("'value',2","'other',2"))[1]['status'],'unproven')
        self.assertEqual(self.proof(SOURCE.replace('@click="change"','@click="assignField(unknown,2)"'))[1]['status'],'unproven')

    def test_no_source_or_target_code_is_mutated_and_no_runtime_is_added(self):
        result=inspect(repair=True)
        self.assertEqual(result['code'],TARGET)
        self.assertNotIn('source_dynamic_assignment_unproven',[i['code'] for i in result['findings']])

    def test_source_matched_inlined_writes_are_proven_but_changed_values_order_or_guard_are_not(self):
        target=TARGET.replace("this.assignField('value',", "this.data.set('value',")
        result,proof=self.proof(code=target)
        self.assertEqual(proof['status'],'proven_for_source_internal_calls',proof)
        self.assertTrue(all(m['status']=='complete_caller_with_inlined_write' for m in proof['caller_mappings']))
        for wrong in (target.replace("'value',2","'value',99"),
                      target.replace("change(){this.data.set('value',2)}","change(){if(false)this.data.set('value',2)}"),
                      TARGET.replace("'value',2","'value',99")):
            self.assertEqual(self.proof(code=wrong)[1]['status'],'unproven')

    def test_real_san_state_and_reactive_render_follow_internal_calls(self):
        settings=load_settings(project_root=PROJECT,environ={})
        data=BrowserEvaluator(settings,profile(settings)).evaluate(SOURCE,TARGET,{},[{'name':'change','type':'click','selector':'button'}])
        self.assertFalse(data['vue']['errors']);self.assertFalse(data['san']['errors'])
        for a,b in zip(data['vue']['snapshots'],data['san']['snapshots']):
            self.assertEqual(tree_distance(a['dom'],b['dom'])['distance'],0)
        self.assertIn('2',str(data['san']['snapshots'][1]['dom']))
        ssm=SSMExtractor(PROJECT/'engine').extract(SOURCE.encode(),'GenericSetter.vue',sha256(SOURCE.encode()).hexdigest())['ssm']
        static=legacy_stage(PROJECT/'engine','validate',source=SOURCE,code=TARGET,ssm=ssm)
        contract=next(c for c in static['source_method_contracts'] if c.get('dynamic_assignment'))
        self.assertEqual(contract['status'],'proven_for_source_internal_calls')
        result=assess(static,data,[{'name':'change','type':'click','selector':'button'}],{'structure':.95,'ui':.95,'pixel_difference':.05},ssm)
        self.assertTrue(result['passed'],result['diagnostics'])


if __name__=='__main__':unittest.main()
