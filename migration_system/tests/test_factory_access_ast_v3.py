"""Factory access is syntax, not text: no cloud calls or validator waivers."""
import json
import subprocess
import unittest
from test_modular_system import PROJECT
from card_migration_system.adapters.legacy_checks import legacy_stage


def target(body,extra='',factory=None):
    script="const san=require('san');"+extra+"module.exports=san.defineComponent({"+(factory or 'initData(){'+body+'}')+'})'
    return '<template><div></div></template><script>'+script+'</script>'


def inspect(code):
    source='<template><div></div></template><script>export default {}</script>'
    return legacy_stage(PROJECT/'engine','validate',source=source,code=code,ssm={})


class FactoryAccessASTTests(unittest.TestCase):
    def codes(self,code):return [e['code'] for e in inspect(code)['validation_errors']]
    def test_strings_comments_and_template_literal_text_are_not_code_access(self):
        for body in ("return {options:['this.data.get','this.data.set']}",
                     "/* this.data.get('x') */return {text:'ok'}",
                     "return {text:`Example: this.data.get('x')`}",
                     "return {text:`${'this.data.get'}`} "):
            with self.subTest(body=body):
                codes=self.codes(target(body))
                self.assertNotIn('invalid_san_init_data_store_access',codes)
                self.assertNotIn('init_data_store_analysis_unavailable',codes)
    def test_actual_dot_computed_optional_and_local_alias_reads_still_fail(self):
        for body in ("return {x:this.data.get('x')}","return {x:this['data'].get('x')}",
                     "return {x:this.data?.get('x')}","const self=this;return {x:self.data.get('x')}",
                     "return {text:`${this.data.get('x')}`} "):
            with self.subTest(body=body):self.assertIn('invalid_san_init_data_store_access',self.codes(target(body)))
    def test_function_valued_alias_factory_and_inline_child_are_checked(self):
        for code in (target('',factory="initData:function(){return {x:this.data.get('x')}}"),
                     target('',extra="const defaults=function(){return {x:this.data.get('x')}};",factory='initData:defaults'),
                     target('return {}',extra="const Child=san.defineComponent({initData(){return {x:this.data.get('x')}}});")):
            with self.subTest(code=code):self.assertIn('invalid_san_init_data_store_access',self.codes(code))
    def test_ordinary_object_named_initdata_is_not_a_san_factory(self):
        code=target('return {}',extra="const data={initData(){return this.data}};")
        self.assertNotIn('invalid_san_init_data_store_access',self.codes(code))
    def test_unresolved_factory_fails_closed_instead_of_falling_back_to_text(self):
        self.assertIn('init_data_store_analysis_unavailable',self.codes(target('',factory='initData:makeUnknownFactory()')))


if __name__=='__main__':unittest.main()
