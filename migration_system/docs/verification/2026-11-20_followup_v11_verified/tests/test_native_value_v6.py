"""Native value attributes are actually repaired, never ignored in DOM TED."""
import unittest
from test_modular_system import PROJECT
from card_migration_system.adapters.syntax import target_syntax
from card_migration_system.adapters.browser import BrowserEvaluator
from card_migration_system.config import load_settings
from card_migration_system.runtime import profile
from card_migration_system.stages.structure import tree_distance

SRC='''<template><div><input :value="amount" @input="update"/><button @click="clear">clear</button></div></template>
<script>export default {data(){return {amount:'start'}},methods:{setValue(k,v){this[k]=v},
update(event){this.setValue('amount',event.target.value)},clear(){this.setValue('amount','')}}}</script>'''
SAN='''<template><div><input value="{{amount}}" on-input="update"/><button on-click="clear">clear</button></div></template>
<script>const san=require('san');module.exports=san.defineComponent({initData(){return {amount:'start'}},
setValue(k,v){this.data.set(k,v)},update(event){this.setValue('amount',event.target.value)},clear(){this.setValue('amount','')}})</script>'''


class NativeValueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.settings=load_settings(project_root=PROJECT,environ={})

    def normalize(self,src=SRC,code=SAN):return target_syntax(self.settings,src,code,normalize=True)

    def test_source_proven_attribute_binding_is_added_and_idempotent(self):
        result=self.normalize()
        self.assertIn('defaultValue="{{amount}}"',result['code'])
        self.assertEqual(self.normalize(code=result['code'])['code'],result['code'])

    def test_actual_initial_input_and_clear_dom_and_live_value_match(self):
        result=self.normalize()
        raw=BrowserEvaluator(self.settings,profile(self.settings)).evaluate(SRC,result['code'],{},[
            {'name':'type','type':'input','selector':'input','value':'changed'},
            {'name':'clear','type':'click','selector':'button'}])
        self.assertEqual(raw['san']['errors'],[])
        self.assertEqual(tree_distance(raw['source_ast']['tree'],raw['target_ast']['tree'])['distance'],0)
        for a,b in zip(raw['vue']['snapshots'],raw['san']['snapshots']):
            self.assertEqual(tree_distance(a['dom'],b['dom'])['distance'],0)
            self.assertEqual([s['value'] for s in a['styles']],[s['value'] for s in b['styles']])

    def test_unknown_nullable_or_external_key_values_are_not_repaired(self):
        for old,new in (("amount:'start'","amount:null"),
                        ("'amount',''","'amount',null"),
                        ("'amount',''","'amount',external()"),
                        ("'amount',event.target.value","key,event.target.value"),
                        ("'amount',event.target.value","'amount',event.detail.value")):
            self.assertNotIn('defaultValue=',self.normalize(SRC.replace(old,new))['code'])

    def test_props_vmodel_loops_wrong_binding_and_existing_default_are_not_overwritten(self):
        cases=[(SRC.replace("data(){return {amount:'start'}}","props:{amount:String}"),SAN),
               (SRC.replace(':value="amount"','v-model="amount"'),SAN),
               (SRC.replace('<input ','<input v-for="amount in items" '),SAN),
               (SRC,SAN.replace('{{amount}}','{{other}}')),
               (SRC,SAN.replace('<input ','<input defaultValue="custom" '))]
        for src,code in cases:
            self.assertNotIn('source_nonnullable_native_value_attribute_reflection_v1',str(self.normalize(src,code)['changes']))

    def test_file_checkbox_radio_and_unknown_type_are_not_given_text_value_semantics(self):
        for kind in ('file','checkbox','radio'):
            self.assertNotIn('defaultValue=',self.normalize(SRC.replace('<input ',f'<input type="{kind}" '),SAN.replace('<input ',f'<input type="{kind}" '))['code'])

    def test_empty_string_class_attribute_is_really_present_even_with_attribute_css(self):
        src='''<template><div><button :class="{active:flag}" @click="toggle">toggle</button></div></template>
<script>export default {data(){return {flag:false}},methods:{toggle(){this.flag=!this.flag}}}</script>
<style>button[class]{color:red}</style>'''
        code='''<template><div><button class="{{flag?'active':''}}" on-click="toggle">toggle</button></div></template>
<script>const san=require('san');module.exports=san.defineComponent({initData(){return {flag:false}},toggle(){this.data.set('flag',!this.data.get('flag'))}})</script>
<style>button[class]{color:red}</style>'''
        result=self.normalize(src,code)
        self.assertIn('className=',result['code'])
        raw=BrowserEvaluator(self.settings,profile(self.settings)).evaluate(src,result['code'],{},[
            {'name':'on','type':'click','selector':'button'},{'name':'off','type':'click','selector':'button'}])
        self.assertEqual(raw['san']['errors'],[])
        self.assertFalse(raw['comparison_policy']['approved']) # no CSS observer waiver
        self.assertEqual(tree_distance(raw['source_ast']['tree'],raw['target_ast']['tree'])['distance'],0)
        for a,b in zip(raw['vue']['snapshots'],raw['san']['snapshots']):
            self.assertEqual(tree_distance(a['dom'],b['dom'])['distance'],0)

    def test_unknown_class_objects_svg_and_wrong_conditional_are_not_reflected(self):
        for src,code in (
            ('<button :class="value"/>','<button class="{{value}}"/>'),
            ('<svg><a :class="flag?\'on\':\'\'"/></svg>','<svg><a class="{{flag?\'on\':\'\'}}"/></svg>'),
            ('<button :class="flag?\'on\':\'\'"/>','<button class="{{other?\'on\':\'\'}}"/>')):
            self.assertNotIn('className=',self.normalize('<template>'+src+'</template><script>export default {}</script>',
                '<template>'+code+'</template><script>const san=require("san");module.exports=san.defineComponent({})</script>')['code'])


if __name__=='__main__':unittest.main()
