"""Native SELECT timing: actual DOM/control checks, no extra user scenarios."""
import unittest
from test_modular_system import PROJECT
from card_migration_system.adapters.syntax import target_syntax
from card_migration_system.adapters.browser import BrowserEvaluator
from card_migration_system.config import load_settings
from card_migration_system.runtime import profile
from card_migration_system.stages.structure import tree_distance
from card_migration_system.stages.dom_comparison import compare_control_state
from test_modular_empty_class_policy import policy
from test_internal_assignment_v3_followup import proof
from test_semantic_comparison_v1 import inspect

SOURCE='''<template><main><select :value="value" @change="choose"><option v-for="item in options" :value="item">{{item}}</option></select><button @click="zero">zero</button><button @click="changeOptions">options</button><button @click="clear">clear</button></main></template><script>export default {data(){return {value:null,options:['a','b','0']}},methods:{choose(e){this.value=e.target.value},zero(){this.value=0},changeOptions(){this.options=['x','y']},clear(){this.value=null}}}</script>'''
TARGET='''<template><main><select value="{{value}}" on-change="choose"><option s-for="item in options" value="{{item}}">{{item}}</option></select><button on-click="zero">zero</button><button on-click="changeOptions">options</button><button on-click="clear">clear</button></main></template><script>const san=require('san');module.exports=san.defineComponent({initData(){return {value:null,options:['a','b','0']}},choose(e){this.data.set('value',e.target.value)},zero(){this.data.set('value',0)},changeOptions(){this.data.set('options',['x','y'])},clear(){this.data.set('value',null)}})</script>'''


class NativeSelectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.settings=load_settings(project_root=PROJECT,environ={})

    def normalize(self,source=SOURCE,code=TARGET):return target_syntax(self.settings,source,code,normalize=True)

    def test_adds_internal_public_ref_hooks_no_wrapper_and_idempotent(self):
        result=self.normalize()
        self.assertIn('source_native_select_post_option_value_v1',str(result['changes']))
        self.assertIn('s-ref="__migrationNativeSelect0"',result['code'])
        self.assertIn('VALUE="{{value}}"',result['code'])
        self.assertEqual(result['after']['status'],'pass',result)
        self.assertEqual(self.normalize(code=result['code'])['code'],result['code'])

    def test_real_null_selection_user_choice_numeric_zero_dynamic_options_and_clear(self):
        code=self.normalize()['code']
        raw=BrowserEvaluator(self.settings,profile(self.settings)).evaluate(SOURCE,code,{},[
            {'name':'choose','type':'select','selector':'select','value':'b'},
            {'name':'zero','type':'click','selector':'button'},
            {'name':'options','type':'click','selector':'button:nth-of-type(2)'},
            {'name':'clear','type':'click','selector':'button:nth-of-type(3)'}])
        self.assertEqual(raw['vue']['errors'],[]);self.assertEqual(raw['san']['errors'],[])
        self.assertEqual(tree_distance(raw['source_ast']['tree'],raw['target_ast']['tree'])['distance'],0)
        for a,b in zip(raw['vue']['snapshots'],raw['san']['snapshots']):
            self.assertEqual(tree_distance(a['dom'],b['dom'])['distance'],0,a['name'])
            self.assertTrue(compare_control_state(a['styles'],b['styles'])['equal'],a['name'])

    def test_root_select_and_conditional_native_select_lifecycle(self):
        source='<template><select :value="value"><option value="a">A</option><option value="b">B</option></select></template><script>export default {props:{value:{type:String,default:null}}}</script>'
        code='<template><select value="{{value}}"><option value="a">A</option><option value="b">B</option></select></template><script>const san=require("san");module.exports=san.defineComponent({initData(){return {value:null}}})</script>'
        result=self.normalize(source,code)
        for props in ({},{'value':'b'},{'value':'missing'}):
            raw=BrowserEvaluator(self.settings,profile(self.settings)).evaluate(source,result['code'],props,[])
            self.assertEqual(raw['san']['errors'],[])
            self.assertTrue(compare_control_state(raw['vue']['snapshots'][0]['styles'],raw['san']['snapshots'][0]['styles'])['equal'],props)
        src=SOURCE.replace('<select ','<select v-if="shown" ').replace('value:null,','shown:false,value:null,').replace('zero(){','zero(){this.shown=true;')
        tgt=TARGET.replace('<select ','<select s-if="shown" ').replace('value:null,','shown:false,value:null,').replace('zero(){','zero(){this.data.set("shown",true);')
        result=self.normalize(src,tgt)
        raw=BrowserEvaluator(self.settings,profile(self.settings)).evaluate(src,result['code'],{},[{'name':'show','type':'click','selector':'button'}])
        self.assertEqual(raw['san']['errors'],[])
        self.assertTrue(compare_control_state(raw['vue']['snapshots'][-1]['styles'],raw['san']['snapshots'][-1]['styles'])['equal'])

    def test_vmodel_loop_owned_ref_wrong_expression_and_conflicting_helper_refuse(self):
        for source,code in [
            (SOURCE.replace(':value="value"','v-model="value"'),TARGET),
            (SOURCE.replace('<main>','<main v-for="value in list">'),TARGET),
            (SOURCE,TARGET.replace('<select ','<select s-ref="businessSelect" ')),
            (SOURCE,TARGET.replace('value="{{value}}"','value="{{other}}"',1)),
            (SOURCE,TARGET.replace('initData(){','__migrationSyncSelectValues(){return 99},initData(){')),
        ]:
            self.assertNotIn('source_native_select_post_option_value_v1',str(self.normalize(source,code)['changes']))

    def test_only_exact_generated_value_helper_is_excluded_from_class_observer_analysis(self):
        source=SOURCE.replace('@change="choose"','').replace('choose(e){this.value=e.target.value},','')
        target=TARGET.replace('on-change="choose"','').replace("choose(e){this.data.set('value',e.target.value)},",'')
        code=self.normalize(source,target)['code']
        self.assertTrue(policy(source,code)['approved'])
        for tampered in (code.replace('.value =','.className ='),code.replace('this.ref(', 'document.querySelector(')):
            self.assertFalse(policy(source,tampered)['approved'])
        self.assertFalse(policy(source+'<style>select[class]{color:red}</style>',code)['approved'])

    def test_source_mounted_contract_ignores_only_proven_native_prefix_and_repairs_preserve_it(self):
        source=SOURCE.replace('methods:{','mounted(){this.setValue(\'value\',\'b\')},methods:{setValue(k,v){this[k]=v},').replace('this.value=e.target.value',"this.setValue('value',e.target.value)").replace('this.value=0',"this.setValue('value',0)").replace("this.options=['x','y']","this.setValue('options',['x','y'])").replace('this.value=null',"this.setValue('value',null)")
        target=TARGET.replace('choose(e){',"attached(){this.setValue('value','b')},setValue(k,v){this.data.set(k,v)},choose(e){").replace("this.data.set('value',e.target.value)","this.setValue('value',e.target.value)").replace("this.data.set('value',0)","this.setValue('value',0)").replace("this.data.set('options',['x','y'])","this.setValue('options',['x','y'])").replace("this.data.set('value',null)","this.setValue('value',null)")
        code=self.normalize(source,target)['code']
        self.assertEqual(proof(source,code)[1]['status'],'proven_for_source_internal_calls')
        changed=code.replace("this.setValue('value','b')","this.setValue('value','a')")
        result=inspect(source,changed,True)
        self.assertIn('restored_source_internal_setter_caller_bodies',result['changes'])
        self.assertEqual(proof(source,result['code'])[1]['status'],'proven_for_source_internal_calls')
        self.assertIn('__migrationSyncSelectValues();',result['code'])
        self.assertEqual(self.normalize(source,result['code'])['code'],result['code'])


if __name__=='__main__':unittest.main()
