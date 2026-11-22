"""Source-bound fixes, real browser observations and negative gate controls."""
from copy import deepcopy
import json
import subprocess
import unittest
from test_modular_system import PROJECT
from test_closed_loop_v2 import COMPUTED_SOURCE,COMPUTED_TARGET,inspect
from card_migration_system.adapters.browser import BrowserEvaluator
from card_migration_system.adapters.syntax import target_syntax
from card_migration_system.config import load_settings
from card_migration_system.runtime import profile
from card_migration_system.stages.structure import tree_distance
from card_migration_system.stages.evaluation import assess,candidate_decision
from card_migration_system.stages.dom_comparison import proven_default_runtime_recovery


class ComputedValueCallTests(unittest.TestCase):
    def test_readonly_collection_calls_are_value_reads_not_getter_invocations(self):
        for operation in ('filter(x=>x>0)','map(x=>x*2)','find(x=>x===2)','slice(0,1)',"join(',')"):
            code=COMPUTED_TARGET.replace('this.computed.total*10','this.computed.total.'+operation)
            result=inspect(COMPUTED_SOURCE,code,True)
            self.assertIn('source_declared_computed_namespace_value_read',result['changes'])
            self.assertNotIn('this.computed.total',result['code'])
            self.assertEqual(inspect(COMPUTED_SOURCE,result['code'],True)['code'],result['code'])

    def test_mutation_dynamic_call_optional_constructor_and_escape_are_not_inferred(self):
        for expression in ('this.computed.total()','this.computed.total.push(2)',
                           'this.computed.total.sort()','this.computed.total[method]()',
                           'this.computed.total.filter.call(null)',
                           'new this.computed.total()', 'consume(this.computed.total)',
                           'this.computed.total?.map(x=>x)','this.computed.total[0]=2'):
            code=COMPUTED_TARGET.replace('this.computed.total*10',expression)
            self.assertEqual(inspect(COMPUTED_SOURCE,code,True)['code'],code,expression)

    def test_real_computed_filter_reactivity_initial_and_click(self):
        source='''<template><div><b>{{visible.length}}</b><button @click="add">add</button></div></template>
<script>export default {data(){return {items:[1,2]}},computed:{rows(){return this.items},visible(){return this.rows.filter(x=>x>1)}},methods:{add(){this.items.push(3)}}}</script>'''
        code='''<template><div><b>{{visible.length}}</b><button on-click="add">add</button></div></template>
<script>const san=require('san');module.exports=san.defineComponent({initData(){return {items:[1,2]}},computed:{rows(){return this.data.get('items')},visible(){return this.computed.rows.filter(x=>x>1)}},add(){this.data.push('items',3)}})</script>'''
        result=inspect(source,code,True);settings=load_settings(project_root=PROJECT,environ={})
        raw=BrowserEvaluator(settings,profile(settings)).evaluate(source,result['code'],{},[{'name':'add','type':'click','selector':'button'}])
        self.assertEqual(raw['san']['errors'],[])
        for a,b in zip(raw['vue']['snapshots'],raw['san']['snapshots']):self.assertEqual(tree_distance(a['dom'],b['dom'])['distance'],0)
        self.assertNotEqual(raw['san']['snapshots'][0]['dom'],raw['san']['snapshots'][1]['dom'])


class NullableNativeValueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.settings=load_settings(project_root=PROJECT,environ={})

    def pair(self,tag='input',two_way=False):
        src='<input :value="value" @input="update"/>' if tag=='input' else '<textarea :value="value" @input="update"></textarea>'
        v='{=value=}' if two_way else '{{value}}'
        tgt=f'<input value="{v}" on-input="update"/>' if tag=='input' else f'<textarea value="{v}" on-input="update"></textarea>'
        source='<template><form>'+src+'<button type="button" @click="change">next</button><button type="button" @click="clear">clear</button><button type="reset">reset</button></form></template><script>export default {data(){return {value:null}},methods:{update(e){this.value=e.target.value},change(){this.value="b"},clear(){this.value=null}}}</script>'
        code='<template><form>'+tgt+'<button type="button" on-click="change">next</button><button type="button" on-click="clear">clear</button><button type="reset">reset</button></form></template><script>const san=require("san");module.exports=san.defineComponent({initData(){return {value:null}},update(e){this.data.set("value",e.target.value)},change(){this.data.set("value","b")},clear(){this.data.set("value",null)}})</script>'
        return source,code

    def test_nullable_and_two_way_native_values_actual_dom_live_controls_and_reset(self):
        for tag,two_way in [('input',False),('input',True),('textarea',False),('textarea',True)]:
            with self.subTest(tag=tag,two_way=two_way):
                source,code=self.pair(tag,two_way)
                normalized=target_syntax(self.settings,source,code,normalize=True)
                self.assertIn(' VALUE="{{value}}"',normalized['code'])
                self.assertEqual(target_syntax(self.settings,source,normalized['code'],normalize=True)['code'],normalized['code'])
                raw=BrowserEvaluator(self.settings,profile(self.settings)).evaluate(source,normalized['code'],{},[
                    {'name':'type','type':'input','selector':tag,'value':'changed'},
                    {'name':'reset','type':'click','selector':'button[type=reset]'},
                    {'name':'next','type':'click','selector':'button'},
                    {'name':'clear','type':'click','selector':'button:nth-of-type(2)'}])
                self.assertEqual(raw['san']['errors'],[])
                self.assertEqual(tree_distance(raw['source_ast']['tree'],raw['target_ast']['tree'])['distance'],0)
                for a,b in zip(raw['vue']['snapshots'],raw['san']['snapshots']):
                    self.assertEqual(tree_distance(a['dom'],b['dom'])['distance'],0,(tag,two_way,a['name']))
                    self.assertEqual([(s['value'],s['checked']) for s in a['styles']],[(s['value'],s['checked']) for s in b['styles']])

    def test_select_vmodel_prop_modifier_calls_dynamic_type_and_mismatched_values_are_not_repaired(self):
        source,code=self.pair()
        for src,tgt in [(source.replace(':value=',':value.prop='),code),
                        (source.replace(':value="value"','v-model="value"'),code),
                        (source.replace(':value="value"',':value="nextValue()"'),code),
                        (source.replace('<input ','<input :type="kind" '),code),
                        (source,code.replace('{{value}}','{{other}}')),
                        (source.replace('<input ','<input type="checkbox" '),code.replace('<input ','<input type="checkbox" ')),
                        (source.replace('<input ','<select ').replace('@input="update"/>','@input="update"></select>'),code.replace('<input ','<select ').replace('on-input="update"/>','on-input="update"></select>')),
                        (source,code.replace('<input ','<input VALUE="custom" '))]:
            result=target_syntax(self.settings,src,tgt,normalize=True)
            self.assertNotIn('source_native_nullable_value_attribute_reflection_v2',str(result['changes']))


class RuntimeRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings=load_settings(project_root=PROJECT,environ={});cls.browser=BrowserEvaluator(cls.settings,profile(cls.settings))
        cls.source='''<template><main><input value="a"/><b>{{rows.length}}</b></main></template><script>export default {props:{items:{type:Array,default:()=>[1,2]}},data(){return {rows:[]}},created(){this.rows=this.items.slice()}}</script>'''
        cls.code='''<template><main><div><input value="a"/><b>{{rows.length}}</b></div></main></template><script>const san=require('san');const DataTypes=san.DataTypes;module.exports=san.defineComponent({dataTypes:{items:DataTypes.array},initData(){return {rows:[]}},inited(){this.data.set('rows',this.data.get('items').slice())}})</script>'''
        proc=subprocess.run(['node',str(PROJECT/'engine/migration_pipeline/utils/parent_prop_semantics.cjs')],input=json.dumps({'vue':cls.source,'code':cls.code,'repair':True}),capture_output=True,encoding='utf-8',check=True)
        cls.repaired=json.loads(proc.stdout)['code'];cls.raw=[];cls.reports=[]
        for text in (cls.code,cls.repaired):
            raw=cls.browser.evaluate(cls.source,text,{},[]);cls.raw.append(raw)
            cls.reports.append(assess({'validation_passed':True,'validation_errors':[]},raw,[],{'structure':.95,'ui':.95,'pixel_difference':.05}))

    def test_real_missing_default_runtime_recovery_can_progress_but_not_pass_structure(self):
        before,after=self.reports
        self.assertTrue(proven_default_runtime_recovery(before,after))
        decision=candidate_decision(before,after)
        self.assertTrue(decision['accepted'],decision);self.assertFalse(after['passed'])
        self.assertEqual(after['dimensions']['structure'],'fail')
        self.assertIn('rendered_control_position_mismatch',[d['code'] for d in after['diagnostics']])

    def test_old_incomplete_changed_input_or_runtime_evidence_never_refines(self):
        for field,value in [('complete',False),('input_sha256','changed'),('runtime_sha256','changed'),('code_sha256','changed'),('normalized_sha256','changed')]:
            before,after=deepcopy(self.reports);after['default_recovery_binding'][field]=value
            self.assertFalse(proven_default_runtime_recovery(before,after),field)
            self.assertFalse(candidate_decision(before,after)['accepted'],field)
        before,after=deepcopy(self.reports);after.pop('default_recovery_binding')
        self.assertFalse(candidate_decision(before,after)['accepted'])

    def test_changed_binding_wrapper_method_or_style_is_not_same_repair(self):
        for old,new in [('<div>','<section>'),('{{rows.length}}','{{rows[0]}}'),(".slice()",'.map(x=>x*2)'),('</script>','</script><style>input{color:red}</style>')]:
            candidate=self.repaired.replace(old,new).replace('</div>','</section>') if old=='<div>' else self.repaired.replace(old,new)
            raw=self.browser.evaluate(self.source,candidate,{},[])
            after=assess({'validation_passed':True,'validation_errors':[]},raw,[],{'structure':.95,'ui':.95,'pixel_difference':.05})
            self.assertFalse(proven_default_runtime_recovery(self.reports[0],after),(old,new))

    def test_new_diagnostics_and_previous_pass_loss_still_reject(self):
        for change in ('diagnostic','dimension','no_progress','bad_controls'):
            before,after=deepcopy(self.reports)
            if change=='diagnostic':after['diagnostics'].append({'code':'new_semantic_defect'})
            elif change=='dimension':after['dimensions']['static']='fail'
            elif change=='no_progress':after['dom_ted']=before['dom_ted']
            else:after['initial_control_state']['values_equal_in_order']=False
            self.assertFalse(candidate_decision(before,after)['accepted'],change)


if __name__=='__main__':unittest.main()
