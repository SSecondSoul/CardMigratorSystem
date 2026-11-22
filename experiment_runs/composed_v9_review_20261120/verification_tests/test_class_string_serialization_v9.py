"""Actual Vue string trim fidelity with strict DOM/CSS observer checks."""
import unittest
from test_modular_system import PROJECT
from card_migration_system.adapters.browser import BrowserEvaluator
from card_migration_system.adapters.syntax import target_syntax
from card_migration_system.adapters.legacy_checks import legacy_stage
from card_migration_system.config import load_settings
from card_migration_system.runtime import profile
from card_migration_system.stages.structure import tree_distance,compare_styles

SRC='''<template><div :class="'zone ' + (busy ? 'busy' : '')"><button @click="toggle">toggle</button></div></template><script>export default {data(){return {busy:false}},methods:{toggle(){this.busy=!this.busy}}}</script><style>.zone[class$=" "]{color:red}[class=""]{color:blue}</style>'''
TGT='''<template><div class="zone {{busy ? 'busy' : ''}}"><button on-click="toggle">toggle</button></div></template><script>const san=require('san');const DataTypes=san.DataTypes;module.exports=san.defineComponent({dataTypes:{},initData(){return {busy:false}},toggle(){this.data.set('busy',!this.data.get('busy'))}})</script><style>.zone[class$=" "]{color:red}[class=""]{color:blue}</style>'''


class StringClassSerializationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.settings=load_settings(project_root=PROJECT,environ={})

    def test_finite_string_class_is_repaired_in_actual_dom_not_comparison_policy(self):
        for prefix,export in (('zone ','export default'),(' ','export default'),('zone ','module.exports ='),(' ','module.exports =')):
            source=SRC.replace("'zone '",repr(prefix)).replace('export default',export);target=TGT.replace('class="zone {{','class="'+prefix+'{{')
            result=target_syntax(self.settings,source,target,normalize=True)
            self.assertIn('source_string_class_trim_v1',str(result['changes']))
            self.assertEqual(target_syntax(self.settings,source,result['code'],normalize=True)['code'],result['code'])
            raw=BrowserEvaluator(self.settings,profile(self.settings)).evaluate(source,result['code'],{},[
                {'name':'on','type':'click','selector':'button'},{'name':'off','type':'click','selector':'button'}])
            self.assertFalse(raw['comparison_policy']['approved']) # CSS observes exact class bytes.
            self.assertEqual(raw['san']['errors'],[])
            for a,b in zip(raw['vue']['snapshots'],raw['san']['snapshots']):
                self.assertEqual(tree_distance(a['dom'],b['dom'])['distance'],0,a['name'])
                self.assertEqual(compare_styles(a['styles'],b['styles'])['similarity'],1)
            checked=legacy_stage(PROJECT/'engine','validate',source=source,code=result['code'],ssm={})
            self.assertNotIn('source_class_binding_not_landed',[e['code'] for e in checked['validation_errors']])

    def test_calls_unknown_fields_mismatched_tokens_loops_and_existing_alias_are_not_guessed(self):
        for source,target in (
            (SRC.replace('busy ?', 'predicate() ?'),TGT.replace('busy ?', 'predicate() ?')),
            (SRC.replace('busy ?','unknown ?'),TGT.replace('busy ?','unknown ?')),
            (SRC,TGT.replace("'busy'", "'other'")),
            (SRC.replace('<div ', '<div v-for="busy in rows" '),TGT.replace('<div ','<div s-for="busy in rows" ')),
            (SRC,TGT.replace('<div ', '<div className="business" ')),
        ):
            result=target_syntax(self.settings,source,target,normalize=True)
            self.assertNotIn('source_string_class_trim_v1',str(result['changes']))


if __name__=='__main__':unittest.main()
