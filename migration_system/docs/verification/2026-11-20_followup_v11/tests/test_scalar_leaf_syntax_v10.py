"""Source-exact scalar assignment closing tokens, no guessed business rewrite."""
import unittest
from test_modular_system import PROJECT
from card_migration_system.config import load_settings
from card_migration_system.adapters.syntax import target_syntax

SRC='''<template><b>{{scale}}</b></template><script>module.exports={data(){return {scale:1}},methods:{adjust(delta){this.scale=Math.max(0.7,Math.min(1.3,Number((this.scale+delta).toFixed(1))))},next(){return 1}}}</script>'''
GOOD='''<template><b>{{scale}}</b></template><script>const san=require('san');module.exports=san.defineComponent({initData(){return {scale:1}},adjust(delta){this.data.set("scale",Math.max(0.7,Math.min(1.3,Number((this.data.get("scale")+delta).toFixed(1)))))},next(){return 1}})</script>'''
BROKEN=GOOD.replace('.toFixed(1)))))','.toFixed(1))))')


class ScalarLeafSyntaxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.settings=load_settings(project_root=PROJECT,environ={})

    def test_complete_scalar_expression_is_restored_by_only_its_missing_close(self):
        for name in ('scale','factor'):
            source=SRC.replace('scale',name);code=BROKEN.replace('scale',name)
            result=target_syntax(self.settings,source,code,normalize=True)
            self.assertEqual(result['after']['status'],'pass',result)
            self.assertEqual(result['code'],GOOD.replace('scale',name))
            self.assertEqual(result['changes'][0]['rule'],'source_proven_leaf_closing_tokens_v1')

    def test_changed_operator_value_key_and_unknown_capture_do_not_get_source_proof(self):
        for source,code in (
            (SRC,BROKEN.replace('+delta','-delta')),
            (SRC,BROKEN.replace('0.7','0.8')),
            (SRC,BROKEN.replace('set("scale"','set("other"')),
            (SRC.replace('this.scale+delta','this.scale+outside'),BROKEN),
            (SRC.replace('this.scale=',"this['scale']="),BROKEN),
        ):
            result=target_syntax(self.settings,source,code,normalize=True)
            self.assertNotIn('source_proven_leaf_closing_tokens_v1',str(result['changes']))

    def test_assignment_return_value_is_not_replaced_by_void_San_set(self):
        source=SRC.replace('adjust(delta){this.scale=','adjust(delta){return this.scale=')
        result=target_syntax(self.settings,source,BROKEN,normalize=True)
        self.assertNotIn('source_proven_leaf_closing_tokens_v1',str(result['changes']))

    def test_native_names_and_component_namespace_must_not_be_shadowed(self):
        for source,code in (
            (SRC.replace('module.exports=', 'const Math=outside;module.exports='),BROKEN),
            (SRC,BROKEN.replace('const san=', 'const Math=outside;const san=')),
            (SRC.replace('module.exports=', 'const module={};module.exports='),BROKEN),
            (SRC,BROKEN.replace('module.exports=', 'const module={};module.exports=')),
            (SRC,BROKEN.replace("const san=require('san')",'const san=outside')),
        ):
            result=target_syntax(self.settings,source,code,normalize=True)
            self.assertEqual(result['after']['status'],'fail')
            self.assertNotIn('source_proven_leaf_closing_tokens_v1',str(result['changes']))


if __name__=='__main__':unittest.main()
