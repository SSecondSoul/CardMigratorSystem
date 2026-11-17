"""General evaluator compatibility and negative controls; never invoke a model."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT/'src'))
from card_migration_system.adapters.ssm import SSMExtractor
from card_migration_system.adapters.legacy_checks import legacy_binding
from card_migration_system.stages.structure import ssm_template_tree,target_template_tree,tree_distance
from card_migration_system.adapters.browser import BrowserEvaluator
from card_migration_system.config import load_settings
from card_migration_system.runtime import profile

SOURCE='''<template><div class="panel" :class="{active:running}" @click="toggle"><p>{{running ? 'On' : 'Off'}}</p><p>{{count}} units</p></div></template>
<script>module.exports={name:'CompatibilityCard',data(){return {running:false,count:3}},methods:{toggle(){this.running=!this.running}}}</script><style>.panel{color:rgb(20,40,60)}.panel.active{color:rgb(80,40,20)}</style>'''
TARGET='''<template><div class="panel{{ running ? ' active' : '' }}" on-click="toggle"><p>{{running ? 'On' : 'Off'}}</p><p>{{count}} units</p></div></template>
<script>const san=require('san');const DataTypes=san.DataTypes;module.exports=san.defineComponent({name:'CompatibilityCard',dataTypes:{},initData(){return {running:false,count:3}},toggle(){this.data.set('running',!this.data.get('running'))}})</script><style>.panel{color:rgb(20,40,60)}.panel.active{color:rgb(80,40,20)}</style>'''


def parse_pair(source,code):
    request={'repository':str(PROJECT.parent),'project':str(PROJECT),'source':source,'code':code,'action':'parse'}
    p=subprocess.run(['node',str(PROJECT/'browser/evaluate.mjs')],input=json.dumps(request).encode(),capture_output=True,timeout=30)
    if p.returncode:raise AssertionError(p.stdout.decode()[:1000])
    return json.loads(p.stdout)


class ProjectionCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ssm=SSMExtractor(PROJECT.parent).extract(SOURCE.encode(),'CompatibilityCard.vue',sha256(SOURCE.encode()).hexdigest())['ssm']

    def compare(self,target):
        pair=parse_pair(SOURCE,target)
        return (tree_distance(pair['source']['tree'],pair['target']['tree']),
                tree_distance(ssm_template_tree(self.ssm),target_template_tree(pair['target']['tree'])))

    def test_ternary_interpolation_static_class_and_text_separator_match(self):
        for value in self.compare(TARGET):self.assertEqual(value['distance'],0,value)

    def test_concatenated_static_class_and_split_attributes_match(self):
        code=TARGET.replace("panel{{ running ? ' active' : '' }}","{{'panel ' + (running ? 'active' : '')}}")
        for value in self.compare(code):self.assertEqual(value['distance'],0,value)

    def test_dropped_static_classes_text_elements_and_event_still_differ(self):
        for code in (TARGET.replace('panel{{','other{{'),TARGET.replace(' units',' months'),
                     TARGET.replace('<p>{{count}} units</p>',''),TARGET.replace('on-click="toggle"',''),
                     TARGET.replace('<p>{{count}} units</p>','<aside>{{count}} units</aside>')):
            with self.subTest(code=code[:160]):
                for value in self.compare(code):self.assertGreater(value['distance'],0,value)

    def test_literal_ternary_branch_text_is_not_confused_with_an_interpolation(self):
        code=TARGET.replace("{{running ? 'On' : 'Off'}}",'OnOff')
        for value in self.compare(code):self.assertGreater(value['distance'],0,value)

    def test_legacy_dependency_fingerprint_includes_cjs_implementation(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'migration_pipeline').mkdir();(root/'SSM').mkdir()
            p=root/'migration_pipeline/rule.cjs';p.write_text('module.exports=1',encoding='utf-8')
            first=legacy_binding(root)
            self.assertIn('migration_pipeline/rule.cjs',first)
            p.write_text('module.exports=2',encoding='utf-8')
            self.assertNotEqual(first,legacy_binding(root))


class BrowserWhitespaceCompatibilityTests(unittest.TestCase):
    def test_indentation_is_not_a_style_element_identity(self):
        settings=load_settings(project_root=PROJECT,environ={})
        code=TARGET.replace('><','>\n  <')
        actions=[{'name':'start','type':'click','selector':'.panel'},{'name':'stop','type':'click','selector':'.panel'}]
        data=BrowserEvaluator(settings,profile(settings)).evaluate(SOURCE,code,{},actions)
        self.assertEqual(data['vue']['errors'],[]);self.assertEqual(data['san']['errors'],[])
        from card_migration_system.stages.structure import compare_styles
        for a,b in zip(data['vue']['snapshots'],data['san']['snapshots']):
            self.assertEqual(tree_distance(a['dom'],b['dom'])['distance'],0)
            self.assertEqual(compare_styles(a['styles'],b['styles'])['similarity'],1)


if __name__=='__main__':unittest.main()
