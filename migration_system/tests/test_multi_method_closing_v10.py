"""Multiple independently source-matched method closures commit atomically."""
import unittest
from test_modular_system import PROJECT
from card_migration_system.config import load_settings
from card_migration_system.adapters.syntax import target_syntax

SOURCE='''<template><b>{{n}}</b></template><script>module.exports={data(){return {n:1,items:[{v:1}],active:true}},methods:{
 adjust(delta){this.n=Math.max(0.7,Number((this.n+delta).toFixed(1)))},
 refresh(){if(!this.active)return;const n=this.n;this.items=this.items.map(item=>Object.assign({},item,{v:n}));this.done(n)},done(n){return n}}}</script>'''
GOOD='''<template><b>{{n}}</b></template><script>const san=require('san');module.exports=san.defineComponent({initData(){return {n:1,items:[{v:1}],active:true}},
 adjust(delta){this.data.set("n",Math.max(0.7,Number((this.data.get("n")+delta).toFixed(1))))},
 refresh(){if(!this.data.get("active"))return;const n=this.data.get("n");this.data.set("items",this.data.get("items").map(item=>Object.assign({},item,{v:n})));this.done(n)},done(n){return n}})</script>'''
BROKEN=GOOD.replace('.toFixed(1))))','.toFixed(1)))').replace('item,{v:n})))','item,{v:n}))')


class MultiMethodClosingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.settings=load_settings(project_root=PROJECT,environ={})

    def test_all_independent_source_method_closes_restore_exact_complete_program(self):
        result=target_syntax(self.settings,SOURCE,BROKEN,normalize=True)
        self.assertEqual(result['after']['status'],'pass',result)
        self.assertEqual(result['code'],GOOD)
        self.assertEqual(sum(c['replacement']==')' for c in result['changes']),2)

    def test_changed_business_value_and_shadowed_native_capture_are_not_patched(self):
        for source,code in (
            (SOURCE,BROKEN.replace('item,{v:n}','item,{v:99}')),
            (SOURCE.replace('Object.assign({},item','outside({},item'),BROKEN),
            (SOURCE,BROKEN.replace("const san=","const Object=outside;const san=")),
        ):
            result=target_syntax(self.settings,source,code,normalize=True)
            self.assertEqual(result['after']['status'],'fail')
            self.assertNotIn('source_complete_method_closing_tokens_v1',str(result['changes']))


if __name__=='__main__':unittest.main()
