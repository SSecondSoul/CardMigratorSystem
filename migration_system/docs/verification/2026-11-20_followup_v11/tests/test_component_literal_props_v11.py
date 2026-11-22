"""Source-bound typed component literals, never native HTML coercion guesses."""
import unittest
from test_modular_system import PROJECT
from card_migration_system.adapters.syntax import target_syntax
from card_migration_system.adapters.browser import BrowserEvaluator
from card_migration_system.config import load_settings
from card_migration_system.runtime import profile

SOURCE='''<template><section><tiny-meter :size="250" :active="false"/></section></template><script>const TinyMeter={template:'<b>{{size}}/{{active ? "on" : "off"}}</b>',props:{size:Number,active:Boolean}};module.exports={components:{TinyMeter}}</script><style>b{color:red}</style>'''
TARGET='''<template><section><tiny-meter size="250" active="false"/></section></template><script>const san=require('san');const DataTypes=san.DataTypes;const Meter=san.defineComponent({template:'<b>{{size}}/{{active ? "on" : "off"}}</b>',dataTypes:{size:DataTypes.number,active:DataTypes.bool},initData(){return {size:0,active:true}}});module.exports=san.defineComponent({components:{'tiny-meter':Meter}})</script><style>b{color:red}</style>'''
RULE='source_registered_component_typed_literal_binding_v1'


class ComponentLiteralTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.settings=load_settings(project_root=PROJECT,environ={})

    def norm(self,source=SOURCE,code=TARGET):return target_syntax(self.settings,source,code,normalize=True)

    def test_registered_numeric_and_boolean_literals_retain_actual_types(self):
        result=self.norm()
        self.assertIn('size="{{250}}" active="{{false}}"',result['code'])
        self.assertEqual(sum(c['rule']==RULE for c in result['changes']),2)
        self.assertEqual(self.norm(SOURCE,result['code'])['changes'],[])
        renamed=self.norm(SOURCE.replace('TinyMeter','ScalePanel').replace('tiny-meter','scale-panel'),
                          TARGET.replace('tiny-meter','scale-panel'))
        self.assertIn('size="{{250}}"',renamed['code'])

    def test_unknown_registration_capture_type_or_ambiguous_scope_does_not_get_proof(self):
        for source,code in (
            (SOURCE,TARGET.replace("'tiny-meter':Meter","'other-meter':Meter")),
            (SOURCE.replace('size:Number','size:String'),TARGET),
            (SOURCE.replace('size:Number','size:[Number,String]'),TARGET),
            (SOURCE.replace('const TinyMeter','const Number=unknown;const TinyMeter'),TARGET),
            (SOURCE,TARGET.replace('const DataTypes=san.DataTypes','const DataTypes=unknown')),
            (SOURCE.replace('<section>','<section v-bind="attrs">'),TARGET),
            (SOURCE.replace('<section>','<section v-if="shown">'),TARGET),
            (SOURCE.replace('components:{TinyMeter}','components:{...registry,TinyMeter}'),TARGET),
        ):
            with self.subTest(source=source,code=code):
                # Only size is the witness here; active is already correctly
                # typed so an independent valid Boolean fix is not prohibited.
                code=code.replace('active="false"','active="{{false}}"')
                self.assertFalse(any(c['rule']==RULE for c in self.norm(source,code)['changes']))

    def test_changed_value_unknown_expression_and_native_attributes_are_not_reinterpreted(self):
        for source,code in (
            (SOURCE.replace(':size="250"',':size="amount"'),TARGET.replace('active="false"','active="{{false}}"')),
            (SOURCE,TARGET.replace('size="250"','size="251"').replace('active="false"','active="{{false}}"')),
            (SOURCE.replace('tiny-meter','input'),TARGET.replace('tiny-meter','input')),
        ):
            self.assertFalse(any(c['rule']==RULE for c in self.norm(source,code)['changes']))

    def test_real_browser_type_failure_recovers_without_changing_source_or_threshold(self):
        browser=BrowserEvaluator(self.settings,profile(self.settings))
        before=browser.evaluate(SOURCE,TARGET,{},[])
        result=self.norm();after=browser.evaluate(SOURCE,result['code'],{},[])
        self.assertTrue(before['san']['errors'])
        self.assertFalse(after['san']['errors'],after['san']['errors'])
        self.assertEqual(after['vue']['snapshots'][0]['dom'],after['san']['snapshots'][0]['dom'])

    def test_source_captured_boolean_and_duplicate_attribute_remain_unmodified(self):
        for source,code in (
            (SOURCE.replace('const TinyMeter','const Boolean=unknown;const TinyMeter'),
             TARGET.replace('size="250"','size="{{250}}"')),
            (SOURCE,TARGET.replace('size="250"','size="250" size="250"').replace('active="false"','active="{{false}}"')),
            (SOURCE.replace(':size="250"',':size="250" size="250"'),TARGET.replace('active="false"','active="{{false}}"')),
        ):
            self.assertFalse(any(c['rule']==RULE for c in self.norm(source,code)['changes']))

    def test_unrecognized_loop_scope_on_both_sides_is_not_an_equivalence_proof(self):
        source=SOURCE.replace('<section>','<section v-for="(row,key,index) in rows">')
        code=TARGET.replace('<section>','<section s-for="row,key,index in rows">')
        self.assertFalse(any(c['rule']==RULE for c in self.norm(source,code)['changes']))


if __name__=='__main__':unittest.main()
