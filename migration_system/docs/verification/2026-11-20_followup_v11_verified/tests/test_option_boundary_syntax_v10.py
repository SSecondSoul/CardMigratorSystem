"""Object-boundary syntax recovery; no model, no whole-component generation."""
import unittest
from pathlib import Path
from test_modular_system import PROJECT
from card_migration_system.config import load_settings
from card_migration_system.adapters.syntax import target_syntax

SOURCE='''<template><b>{{label}}</b></template><script>module.exports={data(){return {n:0}},computed:{label(){return this.n?'on':'off'}},methods:{bump(){this.n++}}}</script>'''
GOOD='''<template><b>{{label}}</b></template><script>const san=require('san');module.exports=san.defineComponent({initData(){return {n:0}},computed:{label(){return this.data.get('n')?'on':'off'}},bump(){this.data.set('n',this.data.get('n')+1)}})</script>'''
BROKEN=GOOD.replace("?'on':'off'}},bump", "?'on':'off'}}},bump")
CHILD_SOURCE='''<template><main><tiny-card/></main></template><script>const TinyCard={template:'<b>{{n}}</b>',data(){return {n:1}},methods:{bump(){this.n++}}};module.exports={components:{TinyCard}}</script>'''
CHILD_GOOD='''<template><main><tiny-card/></main></template><script>const san=require('san');const child=san.defineComponent({template:'<b>{{n}}</b>',initData(){return {n:1}},methods:{bump(){this.data.set('n',this.data.get('n')+1)}}});module.exports=san.defineComponent({components:{'tiny-card':child}})</script>'''
CHILD_BROKEN=CHILD_GOOD.replace('return {n:1}},methods','return {n:1}}},methods')


class OptionBoundarySyntaxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.settings=load_settings(project_root=PROJECT,environ={})

    def norm(self,source,code):return target_syntax(self.settings,source,code,normalize=True)

    def test_parent_computed_extra_object_close_restores_exact_unchanged_code(self):
        result=self.norm(SOURCE,BROKEN)
        self.assertEqual(result['before']['status'],'fail')
        self.assertEqual(result['after']['status'],'pass',result)
        self.assertEqual(result['code'],GOOD)
        self.assertEqual(result['changes'][0]['rule'],'source_component_option_boundary_extra_brace_v1')
        self.assertEqual(self.norm(SOURCE,GOOD)['changes'],[])

    def test_registered_inline_child_boundary_uses_source_component_graph(self):
        for name in ('TinyCard','MetricBox'):
            source=CHILD_SOURCE.replace('TinyCard',name).replace('tiny-card','metric-box' if name=='MetricBox' else 'tiny-card')
            good=CHILD_GOOD.replace('tiny-card','metric-box' if name=='MetricBox' else 'tiny-card')
            broken=good.replace('return {n:1}},methods','return {n:1}}},methods')
            result=self.norm(source,broken)
            self.assertEqual(result['after']['status'],'pass',result)
            self.assertEqual(result['code'],good)

    def test_unknown_registration_or_source_container_shape_is_not_guessed(self):
        for source,code in (
            (SOURCE.replace('computed:{label','computed:{other'),BROKEN),
            (CHILD_SOURCE.replace('components:{TinyCard}','components:{other:Unknown}'),CHILD_BROKEN),
            (CHILD_SOURCE,CHILD_BROKEN.replace("'tiny-card':child","'tiny-card':unknown")),
            (CHILD_SOURCE,CHILD_BROKEN.replace("const san=require('san');","const san=other;")),
        ):
            result=self.norm(source,code)
            self.assertNotIn('source_component_option_boundary_extra_brace_v1',str(result['changes']))
            self.assertEqual(result['after']['status'],'fail')

    def test_business_function_body_and_string_comment_decoys_are_not_delimiters(self):
        for code in (
            GOOD.replace("this.data.set('n',this.data.get('n')+1)","if(true) this.data.set('n',this.data.get('n')+1)}}"),
            GOOD.replace("const san=", "const text='}}},computed:{x(){}}';/* }}} */const san="),
        ):
            result=self.norm(SOURCE,code)
            self.assertNotIn('source_component_option_boundary_extra_brace_v1',str(result['changes']))


if __name__=='__main__':unittest.main()
