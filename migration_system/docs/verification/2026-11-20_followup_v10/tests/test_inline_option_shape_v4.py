"""Source-bound inline option repair, not component-name or model-output fixtures."""
from hashlib import sha256
from functools import lru_cache
import json
import subprocess
import unittest
from test_modular_system import PROJECT
from card_migration_system.adapters.ssm import SSMExtractor
from card_migration_system.adapters.legacy_checks import legacy_stage
from card_migration_system.adapters.browser import BrowserEvaluator
from card_migration_system.config import load_settings
from card_migration_system.runtime import profile
from card_migration_system.stages.structure import tree_distance


def source(options="props:['rows'],data(){return {selected:null}}"):
    return '<template><arbitrary-widget :rows="rows"/></template><script>const Widget={'+options+",template:'<span>{{rows.length}}:{{selected}}</span>'};export default {data(){return {rows:[1,2]}},components:{ArbitraryWidget:Widget}}</script>"


def target(options="props:['rows'],data:function(){return {selected:null}}"):
    return '<template><arbitrary-widget rows="{{rows}}"/></template><script>const san=require("san");const Child=san.defineComponent({'+options+",template:'<span>{{rows.length}}:{{selected}}</span>'});module.exports=san.defineComponent({initData(){return {rows:[1,2]}},components:{'arbitrary-widget':Child}})</script>"


@lru_cache(maxsize=32)
def extract(src):
    return SSMExtractor(PROJECT/'engine').extract(src.encode(),'Any.vue',sha256(src.encode()).hexdigest())['ssm']


def normalize(src,code):
    ssm=extract(src)
    proc=subprocess.run(['node',str(PROJECT/'engine/migration_pipeline/utils/residual_semantics.cjs')],
        input=json.dumps({'code':code,'ssm':ssm,'repair':True}),encoding='utf-8',capture_output=True,check=True)
    result=json.loads(proc.stdout)
    if result.get('error'):raise AssertionError(result)
    return result,ssm


class InlineShapeTests(unittest.TestCase):
    def test_array_props_and_minified_function_factory_restored_once(self):
        a,_=normalize(source(),target())
        self.assertIn('dataTypes:',a['code']);self.assertIn('initData:function()',a['code'])
        self.assertNotIn("props:['rows']",a['code'])
        self.assertEqual(set(a['changes']),{'normalized_source_matched_inline_array_props','restored_inline_source_literal_factory_option'})
        self.assertEqual(normalize(source(),a['code'])[0]['changes'],[])

    def test_names_and_literal_shape_are_not_component_specific(self):
        for field in ('chosen','hoverIndex','expanded'):
            with self.subTest(field=field):
                body='return {'+field+':null,flags:[true,false],config:{n:-2,text:"hello"}}'
                a,_=normalize(source("props:['rows'],data(){"+body+'}'),target("props:['rows'],data(){"+body+'}'))
                self.assertIn('initData(){'+body+'}',a['code'])

    def test_different_or_defaulted_props_are_not_overwritten(self):
        for opt in ("props:['missing']","props:{rows:{type:Array,default(){return []}}}","props:['rows','rows']",
                    "props:['rows'],dataTypes:{rows:san.DataTypes.array}","props:['rows'],propTypes:{}"):
            with self.subTest(opt=opt):
                a,_=normalize(source(),target(opt))
                self.assertNotIn('normalized_source_matched_inline_array_props',a['changes'])
                self.assertIn(opt,a['code'])

    def test_factory_unknown_or_different_behavior_is_not_replaced(self):
        for body in ('return {selected:1}','return {selected:this.rows[0]}','return {selected:makeValue()}',
                     'return {...defaults}','return {get selected(){return 1}}',"return {__proto__:{x:1}}",
                     'log();return {selected:null}'):
            with self.subTest(body=body):
                a,_=normalize(source(),target("props:['rows'],data(){"+body+'}'))
                self.assertNotIn('restored_inline_source_literal_factory_option',a['changes'])
                self.assertIn('data(){'+body+'}',a['code'])

    def test_existing_initdata_prop_overlap_and_wrong_registry_are_preserved(self):
        for src,code in (
            (source("props:['selected'],data(){return {selected:null}}"),target("props:['selected'],data(){return {selected:null}}")),
            (source(),target().replace("'arbitrary-widget':Child","'other-widget':Child")),
            (source(),target().replace('data:function()', 'initData(){return {other:1}},data:function()'))):
            with self.subTest(code=code):
                a,_=normalize(src,code)
                self.assertNotIn('restored_inline_source_literal_factory_option',a['changes'])

    def test_does_not_rewrite_an_untrusted_runtime(self):
        for code in (target().replace('require("san")','unknownRuntime'),target().replace('const Child=', 'san.DataTypes=unknown;const Child=')):
            a,_=normalize(source(),code)
            self.assertNotIn('normalized_source_matched_inline_array_props',a['changes'])
            self.assertNotIn('restored_inline_source_literal_factory_option',a['changes'])

    def test_production_rules_use_the_same_repair(self):
        src=source();_,ssm=normalize(src,target())
        result=legacy_stage(PROJECT/'engine','rules',source=src,code=target(),ssm=ssm,
                            errors=[{'code':'vue_props_not_migrated'}])
        self.assertIn('dataTypes:',result['code']);self.assertIn('initData:function()',result['code'])

    def test_real_san_child_receives_props_and_factory_defaults(self):
        src=source();result,_=normalize(src,target());settings=load_settings(project_root=PROJECT,environ={})
        raw=BrowserEvaluator(settings,profile(settings)).evaluate(src,result['code'],{},[])
        self.assertEqual(raw['status'],'completed',raw)
        self.assertFalse(raw['san'].get('errors'),raw['san'].get('errors'))
        for a,b in zip(raw['vue']['snapshots'],raw['san']['snapshots']):
            self.assertEqual(tree_distance(a['dom'],b['dom'])['distance'],0)


if __name__=='__main__':unittest.main()
