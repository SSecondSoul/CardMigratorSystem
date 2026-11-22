"""Restore actual source DOM, not a broad tree-comparison equivalence waiver."""
import unittest
from test_modular_system import PROJECT
from card_migration_system.adapters.browser import BrowserEvaluator
from card_migration_system.adapters.syntax import target_syntax
from card_migration_system.adapters.legacy_checks import legacy_stage
from card_migration_system.config import load_settings
from card_migration_system.runtime import profile
from card_migration_system.stages.normalization import normalize_proposal
from card_migration_system.stages.structure import tree_distance
from card_migration_system.stages.dom_comparison import compare_control_state

SRC='''<template><main><label>Title<input :value="name" @input="update"></label><footer>{{count}} items<button @click="inc">+</button></footer><button type="button" @click="inc">guard</button></main></template><script>export default {data(){return {name:'A',count:1}},methods:{update(e){this.name=e.target.value},inc(){this.count++}}}</script><style>footer span{color:red}</style>'''
TGT='''<template><main aria-label="extra"><label><span>Title</span><input type="text" value="{{name}}" on-input="update"></label><footer><span>{{count}} items</span><button on-click="inc">+</button></footer><button on-click="inc">guard</button></main></template><script>const san=require('san');const DataTypes=san.DataTypes;module.exports=san.defineComponent({dataTypes:{},initData(){return {name:'A',count:1}},update(e){this.data.set('name',e.target.value)},inc(){this.data.set('count',this.data.get('count')+1)}})</script><style>footer span{color:red}</style>'''


class TemplateFidelityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings=load_settings(project_root=PROJECT,environ={});cls.runtime=profile(cls.settings)

    def normalize(self,source=SRC,code=TGT):
        return normalize_proposal(self.settings,legacy_stage,BrowserEvaluator(self.settings,self.runtime),source,code,{},
            {'dimensions':{'compile_runtime':'pass'},'syntax':{'status':'pass'},
             'diagnostics':[{'code':'rendered_dom_mismatch'},{'code':'template_structure_mismatch'}]})

    def test_source_owned_text_spans_attributes_and_control_binding_are_composed(self):
        result=self.normalize();code=result['code']
        self.assertIn('source_text_only_span_unwrap_v1',str(result['changes']))
        self.assertIn('source_native_static_attribute_fidelity_v1',str(result['changes']))
        self.assertNotIn('<span>',code);self.assertNotIn('aria-label="extra"',code)
        self.assertNotIn('type="text"',code);self.assertIn('type="button"',code)
        self.assertEqual(self.normalize(code=code)['code'],code)
        raw=BrowserEvaluator(self.settings,self.runtime).evaluate(SRC,code,{},[
            {'name':'type','type':'input','selector':'input','value':'next'},
            {'name':'inc','type':'click','selector':'footer button'}])
        self.assertEqual(raw['vue']['errors'],[]);self.assertEqual(raw['san']['errors'],[])
        self.assertEqual(tree_distance(raw['source_ast']['tree'],raw['target_ast']['tree'])['distance'],0)
        for a,b in zip(raw['vue']['snapshots'],raw['san']['snapshots']):
            self.assertEqual(tree_distance(a['dom'],b['dom'])['distance'],0,a['name'])
            self.assertTrue(compare_control_state(a['styles'],b['styles'])['equal'])

    def test_meaningful_attributes_mismatched_text_loop_scope_and_source_owned_spans_refuse(self):
        for source,code in (
            (SRC,TGT.replace('<span>Title</span>','<span class="note">Title</span>')),
            (SRC,TGT.replace('<span>Title</span>','<span>Wrong</span>')),
            (SRC.replace('<label>','<label v-for="x in rows">'),TGT.replace('<label>','<label s-for="y in rows">')),
            (SRC.replace('Title<input','<span>Title</span><input'),TGT),
            (SRC,TGT.replace('dataTypes:{},','components:{span:UnknownChild},dataTypes:{},')),
            (SRC.replace('data(){','components:{main:UnknownChild},data(){'),TGT),
            (SRC.replace('<main>','<main v-html="html">'),TGT),
        ):
            result=target_syntax(self.settings,source,code,normalize=True)
            self.assertIn('<span',result['code'])

    def test_case_insensitive_source_native_attributes_and_dynamic_spreads_are_not_removed(self):
        source=SRC.replace('<main>','<main ARIA-LABEL="source">').replace('<input ', '<input TYPE="text" ')
        code=TGT.replace('aria-label="extra"','aria-label="source"')
        normalized=target_syntax(self.settings,source,code,normalize=True)['code']
        self.assertIn('aria-label="source"',normalized);self.assertIn('type="text"',normalized)
        source=SRC.replace('<main>','<main v-bind="attrs">')
        self.assertIn('aria-label="extra"',target_syntax(self.settings,source,TGT,normalize=True)['code'])
        source=SRC.replace('data(){','components:{main:External},data(){')
        self.assertIn('aria-label="extra"',target_syntax(self.settings,source,TGT,normalize=True)['code'])
        source=SRC.replace('<main>','<main v-html="html">')
        self.assertIn('type="text"',target_syntax(self.settings,source,TGT,normalize=True)['code'])

    def test_literal_option_binding_is_restored_without_changing_real_selection(self):
        source='''<template><main><select :value="size" @change="change"><option :value="4">four</option><option :value="6">six</option></select><b>{{size}}</b></main></template><script>export default {data(){return {size:4}},methods:{change(e){this.size=Number(e.target.value)}}}</script>'''
        target='''<template><main><select value="{{size}}" on-change="change"><option value="4">four</option><option value="6">six</option></select><b>{{size}}</b></main></template><script>const san=require('san');const DataTypes=san.DataTypes;module.exports=san.defineComponent({dataTypes:{},initData(){return {size:4}},change(e){this.data.set('size',Number(e.target.value))}})</script>'''
        result=self.normalize(source,target)
        self.assertIn('source_native_literal_option_binding_v1',str(result['changes']))
        raw=BrowserEvaluator(self.settings,self.runtime).evaluate(source,result['code'],{},[
            {'name':'six','type':'select','selector':'select','value':'6'}])
        self.assertEqual(raw['vue']['errors'],[]);self.assertEqual(raw['san']['errors'],[])
        self.assertEqual(tree_distance(raw['source_ast']['tree'],raw['target_ast']['tree'])['distance'],0)
        for a,b in zip(raw['vue']['snapshots'],raw['san']['snapshots']):
            self.assertEqual(tree_distance(a['dom'],b['dom'])['distance'],0)
            self.assertTrue(compare_control_state(a['styles'],b['styles'])['equal'])

    def test_commonjs_source_gets_same_actual_template_repairs(self):
        source=SRC.replace('export default','module.exports =')
        result=target_syntax(self.settings,source,TGT,normalize=True)
        self.assertIn('source_text_only_span_unwrap_v1',str(result['changes']))
        self.assertIn('source_native_static_attribute_fidelity_v1',str(result['changes']))
        self.assertNotIn('<span>',result['code']);self.assertNotIn('aria-label="extra"',result['code'])
        raw=BrowserEvaluator(self.settings,self.runtime).evaluate(source,result['code'],{},[
            {'name':'type','type':'input','selector':'input','value':'next'},
            {'name':'inc','type':'click','selector':'footer button'}])
        self.assertEqual(raw['vue']['errors'],[]);self.assertEqual(raw['san']['errors'],[])
        self.assertEqual(tree_distance(raw['source_ast']['tree'],raw['target_ast']['tree'])['distance'],0)
        for a,b in zip(raw['vue']['snapshots'],raw['san']['snapshots']):
            self.assertEqual(tree_distance(a['dom'],b['dom'])['distance'],0,a['name'])
            self.assertTrue(compare_control_state(a['styles'],b['styles'])['equal'])

    def test_ambiguous_shadowed_nested_and_opaque_commonjs_exports_do_not_prove_ownership(self):
        common=SRC.replace('export default','module.exports =')
        for source in (
            common.replace('<script>','<script>const module={exports:null};'),
            common.replace('</script>',';module.exports = {};</script>'),
            common.replace('<script>','<script>function notTheComponent(){').replace('</script>','}</script>'),
            common.replace('module.exports','module[\'exports\']'),
            common.replace('data(){','...unknownOptions,data(){'),
        ):
            changes=target_syntax(self.settings,source,TGT,normalize=True)['changes']
            self.assertNotIn('source_native_static_attribute_fidelity_v1',str(changes))
            self.assertNotIn('source_text_only_span_unwrap_v1',str(changes))


if __name__=='__main__':unittest.main()
