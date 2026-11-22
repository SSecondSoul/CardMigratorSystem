"""A Vue key becomes San trackby INSIDE s-for, not HTML attributes."""
import unittest
from test_modular_system import PROJECT
from card_migration_system.adapters.syntax import target_syntax
from card_migration_system.config import load_settings

SOURCE='''<template><main><span v-for="(row, i) in rows" :key="row.id">{{row.id}}</span></main></template><script>module.exports={data(){return {rows:[{id:1}]}}}</script>'''
TARGET='''<template><main><span s-for="row, i in rows" trackby row.id>{{row.id}}</span></main></template><script>const san=require('san');module.exports=san.defineComponent({initData(){return {rows:[{id:1}]}}})</script>'''


class ForKeyGrammarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.settings=load_settings(project_root=PROJECT,environ={})

    def norm(self,source,code):return target_syntax(self.settings,source,code,normalize=True)

    def test_source_key_moves_inside_binding_and_does_not_become_a_DOM_attribute(self):
        for key in ('row.id','i'):
            source=SOURCE.replace(':key="row.id"',':key="'+key+'"')
            code=TARGET.replace('trackby row.id','trackby '+key)
            result=self.norm(source,code)
            self.assertIn('source_matched_external_trackby_into_for_v1',str(result['changes']))
            self.assertIn('s-for="row, i in rows trackby '+key+'"',result['code'])
            self.assertNotIn('" trackby ',result['code'])
            self.assertEqual(result['after']['status'],'pass',result)
            self.assertEqual(self.norm(source,result['code'])['code'],result['code'])

    def test_SVG_loop_has_same_key_contract(self):
        source=SOURCE.replace('<main>','<svg>').replace('</main>','</svg>').replace('<span','<g').replace('</span>','</g>')
        code=TARGET.replace('<main>','<svg>').replace('</main>','</svg>').replace('<span','<g').replace('</span>','</g>')
        result=self.norm(source,code)
        self.assertEqual(result['after']['status'],'pass',result)
        self.assertIn('in rows trackby row.id"',result['code'])

    def test_wrong_key_collection_alias_and_real_source_attributes_are_not_erased(self):
        for source,code in (
            (SOURCE,TARGET.replace('trackby row.id','trackby row.other')),
            (SOURCE,TARGET.replace('in rows"','in otherRows"')),
            (SOURCE,TARGET.replace('row, i in','item, i in')),
            (SOURCE.replace(':key="row.id"',':key="row.id" trackby'),TARGET),
            (SOURCE,TARGET.replace('trackby row.id','trackby row.id trackby i')),
        ):
            result=self.norm(source,code)
            self.assertNotIn('source_matched_external_trackby_into_for_v1',str(result['changes']))


if __name__=='__main__':unittest.main()
