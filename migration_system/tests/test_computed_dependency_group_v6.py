"""Atomic source-computed groups, not method-name exceptions. No model calls."""
import unittest
from test_computed_options_v5 import analyze, source, target
from test_modular_system import PROJECT
from card_migration_system.adapters.browser import BrowserEvaluator
from card_migration_system.config import load_settings
from card_migration_system.runtime import profile
from card_migration_system.stages.structure import tree_distance


SRC = '''<template><div><b>{{double}}</b><i>{{counts.a}}</i><button @click="add">add</button></div></template>
<script>export default {data(){return {items:[{status:'a'}],count:2}},computed:{
amount(){return this.count*2},double(){return this.amount*2},
counts(){return this.items.reduce((out,item)=>{out[item.status]+=1;return out},{a:0,b:0})}},
methods:{add(){if(this.double>0)this.count++}}}</script>'''
SAN = '''<template><div><b>{{double}}</b><i>{{counts.a}}</i><button on-click="add">add</button></div></template>
<script>const san=require('san');module.exports=san.defineComponent({initData(){return {items:[{status:'a'}],count:2}},
amount(){return this.data.get('count')*2},double(){return this.amount()*2},
counts(){return this.data.get('items').reduce((out,item)=>{out[item.status]+=1;return out},{a:0,b:0})},
add(){if(this.double()>0)this.data.set('count',this.data.get('count')+1)}})</script>'''


class ComputedDependencyGroupTests(unittest.TestCase):
    def test_relocates_dependency_chain_and_repairs_known_source_consumers_together(self):
        result = analyze(SRC, SAN, True)
        self.assertIn('restored_source_matched_computed_option_shape', result['changes'])
        self.assertNotIn('this.amount()', result['code'])
        self.assertNotIn('this.double()', result['code'])
        self.assertFalse(any(d['code']=='source_computed_option_not_landed' for d in analyze(SRC,result['code'])['findings']))
        self.assertEqual(analyze(SRC,result['code'],True)['code'], result['code'])

    def test_reduce_only_mutates_fresh_local_accumulator_not_state_or_items(self):
        result = analyze(SRC, SAN, True)
        self.assertIn('counts(){', result['code'].split('computed:{')[1])
        for old,new in (("{a:0,b:0})", "this.items)"),
                        ("out[item.status]+=1", "item.status='b'")):
            src = SRC.replace(old,new)
            code = SAN.replace(old,new.replace('this.items',"this.data.get('items')"))
            result = analyze(src, code, True)
            finding=next(d for d in result['findings'] if d.get('location')=='script.computed.counts')
            self.assertFalse(finding['details']['source_matched_relocation_eligible'])

    def test_unknown_callers_argument_calls_and_computed_writes_remain_unproven(self):
        for extra in ('other(){return this.amount()},','add(){return this.amount(2)},',
                      'add(){this.amount++},','add(){return function(){return this.amount()}},'):
            code=SAN.replace("add(){if(this.double()>0)this.data.set('count',this.data.get('count')+1)}",extra.rstrip(','))
            result=analyze(SRC,code,True)
            self.assertIn('amount(){', result['code'].split('computed:{')[0] if 'computed:{' in result['code'] else result['code'])

    def test_missing_or_changed_dependency_is_not_invented(self):
        code=SAN.replace("amount(){return this.data.get('count')*2}","amount(){return 99}")
        result=analyze(SRC,code,True)
        self.assertIn('double(){return this.amount()*2}',result['code'])
        self.assertIn('amount(){return 99}',result['code'])

    def test_browser_initial_and_click_recompute_match_vue(self):
        result=analyze(SRC,SAN,True);settings=load_settings(project_root=PROJECT,environ={})
        raw=BrowserEvaluator(settings,profile(settings)).evaluate(SRC,result['code'],{},[{'name':'add','type':'click','selector':'button'}])
        self.assertEqual(raw['san']['errors'],[])
        for a,b in zip(raw['vue']['snapshots'],raw['san']['snapshots']):
            self.assertEqual(tree_distance(a['dom'],b['dom'])['distance'],0)
        self.assertNotEqual(raw['san']['snapshots'][0]['dom'],raw['san']['snapshots'][1]['dom'])


if __name__=='__main__':unittest.main()
