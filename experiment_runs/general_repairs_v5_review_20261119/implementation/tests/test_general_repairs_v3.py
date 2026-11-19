"""Universal repairs: real parsers/browser plus refusal controls; no paid calls."""
import base64
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import unittest

PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT/'src'))
from card_migration_system.adapters.syntax import target_syntax
from card_migration_system.adapters.browser import BrowserEvaluator
from card_migration_system.adapters.legacy_checks import legacy_stage
from card_migration_system.config import load_settings
from card_migration_system.runtime import profile
from card_migration_system.prompts.san_contract import CONSTRAINTS,repair_targets
from card_migration_system.prompts.migration import generation_messages
from card_migration_system.stages.syntax import syntax_repair_messages
from test_semantic_comparison_v1 import inspect,SOURCE as SETTER,TARGET as SAN_SETTER

SOURCE='''<template><div class="items" @dragover.prevent><button class="item" v-for="(item, index) in items" :key="item.id" :class="{active:chosen===item.id}" @click.stop="choose(item.id)">{{item.id}}</button></div></template>
<script>export default {data(){return {items:[{id:1}],chosen:1}},methods:{choose(id){this.chosen=id}}}</script>'''
TARGET='''<template><div class="items" on-dragover=""><button class="item" s-for="(item, index) in this.data.get('items') trackby item.id" class="{{chosen===item.id ? 'active' : ''}}" on-click.stop="choose(item.id)">{{item.id}}</button></div></template>
<script>const san=require('san');module.exports=san.defineComponent({initData(){return {items:[{id:1}],chosen:1}},choose(id){this.data.set('chosen',id)}})</script>'''
SVG='<svg width="16" height="16" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M0 0h16v16H0z" fill="WindowText"/></svg>'


class AttributeRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.settings=load_settings(project_root=PROJECT,environ={})
    def normalize(self,source=SOURCE,code=TARGET):return target_syntax(self.settings,source,code,normalize=True)

    def test_independent_attributes_and_duplicate_class_are_repaired_atomically(self):
        r=self.normalize()
        self.assertEqual(r['after']['status'],'pass',r)
        self.assertIn('s-for="item, index in items trackby item.id"',r['code'])
        self.assertIn('on-dragover="prevent:__migrationNoopEvent($event)"',r['code'])
        self.assertIn('on-click="stop:choose(item.id)"',r['code'])
        self.assertIn('item {{chosen',r['code'])
        self.assertIn('__migrationNoopEvent() {}',r['code'])
        self.assertEqual(self.normalize(code=r['code'])['changes'],[])
        self.assertIn("this.data.set('chosen',id)",r['code'])

    def test_all_fatal_attributes_have_exact_locations_not_template_start(self):
        code=TARGET.replace(' class="{{chosen===item.id ? \'active\' : \'\'}}"','')
        r=target_syntax(self.settings,SOURCE,code)
        attrs={x.get('attribute'):x for x in r['diagnostics']}
        for name in ('on-dragover','s-for','on-click.stop'):
            self.assertIn(name,attrs,r)
            self.assertEqual(attrs[name]['location_precision'],'exact')
            self.assertTrue(code[attrs[name]['location']['offset']:].startswith(name))

    def test_unknown_source_event_loop_key_or_class_is_not_guessed(self):
        for source in (SOURCE.replace('@dragover.prevent','@dragover="save"'),
                       SOURCE.replace(':key="item.id"',':key="index"'),
                       SOURCE.replace('in items','in otherItems'),
                       SOURCE.replace('{active:chosen===item.id}','{wrong:chosen===item.id}')):
            with self.subTest(source=source):self.assertEqual(self.normalize(source)['after']['status'],'fail')

    def test_inline_child_repairs_are_owned_and_ordinary_business_templates_ignored(self):
        src=SOURCE.replace('<script>export default','<script>const Child={name:"Child",template:`<div @dragover.prevent/>`};export default')
        target=TARGET.replace("const san=require('san');", "const san=require('san');const Child=san.defineComponent({name:'Child',template:`<div on-dragover="+'""'+"/>`});const data={name:'not-component',template:`<div on-click="+'""'+"/>`};")
        r=self.normalize(src,target)
        self.assertEqual(r['after']['status'],'pass',r)
        self.assertEqual(r['code'].count('() {}'),2)
        self.assertIn("name:'not-component',template:`<div on-click=\"\"/>`",r['code'])

    def test_interpolation_data_store_access_repaired_only_when_source_matches(self):
        src=SOURCE.replace('{{item.id}}','{{item.id}} {{chosen}}')
        target=TARGET.replace('{{item.id}}',"{{this.data.get('item').id}} {{this.data.get('chosen')}}")
        r=self.normalize(src,target)
        self.assertEqual(r['after']['status'],'pass',r)
        self.assertNotIn("get('item')",r['code'])
        wrong=self.normalize(src,target.replace("get('item').id","get('item').wrong"))
        self.assertIn("get('item').wrong",wrong['code'])
        # San's expression parser accepts prefixes; semantic validation must
        # still reject the unmodified getter access, even if parsing succeeds.
        validation=legacy_stage(self.settings.repository_root,'validate',source=src,code=wrong['code'],ssm={})
        self.assertIn('invalid_san_template_data_store_access',[e['code'] for e in validation['validation_errors']])

    def test_inline_vue_directives_are_located_instead_of_hidden_by_parent_success(self):
        code='<template><div/></template><script>const san=require("san");const Child=san.defineComponent({name:"Child",template:`<div @click="doIt"/>`});module.exports=san.defineComponent({})</script>'
        r=target_syntax(self.settings,SOURCE,code)
        item=next(d for d in r['diagnostics'] if d.get('attribute')=='@click')
        self.assertEqual(item['location']['offset'],code.index('@click'))
        self.assertEqual(r['status'],'fail')

    def test_else_if_is_checked_with_its_required_parser_context(self):
        code='<template><div><p s-if="flag">a</p><p s-elif="other">b</p><p s-else>c</p></div></template><script>const san=require("san");module.exports=san.defineComponent({})</script>'
        self.assertEqual(target_syntax(self.settings,SOURCE,code)['status'],'pass')


class ScopedSetterRepairTests(unittest.TestCase):
    def test_minified_method_wrappers_on_parent_and_children_flatten_without_touching_data(self):
        code=SAN_SETTER.replace("assignField(k,v){this.data.set(k,v)},change(){this.assignField('value',2)}", "methods:{assignField(k,v){this.data.set(k,v)},change(){this.assignField('value',2)}}")
        r=inspect(SETTER,code,True)
        self.assertIn('flattened_parsed_component_method_options',r['changes'])
        self.assertNotIn('methods:{',r['code']);self.assertIn('initData()',r['code'])
        self.assertEqual(inspect(SETTER,r['code'],True)['code'],r['code'])
        # A real option/method collision is not resolved by overwriting either.
        collision=code.replace('methods:{','change(){return 5},methods:{')
        self.assertEqual(inspect(SETTER,collision,True)['code'],collision)
    def test_wrong_complete_caller_is_restored_and_then_proven_for_different_method_names(self):
        for name in ('assignField','writeState','setValue'):
            source=SETTER.replace('assignField',name)
            code=SAN_SETTER.replace('assignField',name).replace("'value',2","'value',99")
            before=inspect(source,code)
            self.assertIn('source_dynamic_assignment_unproven',[e['code'] for e in before['findings']])
            repaired=inspect(source,code,True)
            self.assertIn('restored_source_internal_setter_caller_bodies',repaired['changes'])
            self.assertNotIn('source_dynamic_assignment_unproven',[e['code'] for e in inspect(source,repaired['code'])['findings']])
            self.assertEqual(inspect(source,repaired['code'],True)['code'],repaired['code'])

    def test_unsafe_key_escape_or_capture_never_acquires_caller_repair(self):
        for source,code in (
            (SETTER.replace("'value',2","'bad.key',2"),SAN_SETTER.replace("'value',2","'bad.key',99")),
            (SETTER.replace("'value',2","unknown,2"),SAN_SETTER.replace("'value',2","unknown,99")),
            (SETTER.replace("'value',2","'value',outside()"),SAN_SETTER.replace("'value',2","'value',99")),
            (SETTER,SAN_SETTER.replace("'value',2","'bad.key',99")),
        ):
            with self.subTest(source=source):
                r=inspect(source,code,True)
                self.assertNotIn('restored_source_internal_setter_caller_bodies',r['changes'])
                self.assertIn('source_dynamic_assignment_unproven',[e['code'] for e in r['findings']])

    def test_verified_emit_passthrough_inlining_not_mistaken_for_changed_caller(self):
        source=SETTER.replace('methods:{',"methods:{emitChange(n,v){this.$emit(n,v)},").replace("this.assignField('value',2)","this.assignField('value',2);this.emitChange('change',2)")
        target=SAN_SETTER.replace("assignField(k,v)","emitChange(n,v){this.fire(n,v)},assignField(k,v)").replace("this.assignField('value',2)","this.data.set('value',2);this.fire('change',2)")
        self.assertNotIn('source_dynamic_assignment_unproven',[e['code'] for e in inspect(source,target)['findings']])
        for wrong in (target.replace("this.fire('change',2)","this.fire('wrong',2)"),target.replace("this.fire(n,v)","this.fire(v,n)")):
            self.assertIn('source_dynamic_assignment_unproven',[e['code'] for e in inspect(source,wrong)['findings']])


class ResourcePolicyTests(unittest.TestCase):
    def run_policy(self,entries):
        js="import {inlineImage} from './browser/resource-policy.mjs';let s='';for await(const c of process.stdin)s+=c;console.log(JSON.stringify(JSON.parse(s).map(x=>Boolean(inlineImage(...x)))));"
        p=subprocess.run(['node','--input-type=module','-e',js],cwd=PROJECT,input=json.dumps(entries).encode(),capture_output=True,timeout=15)
        self.assertEqual(p.returncode,0,p.stderr);return json.loads(p.stdout)
    def uri(self,text):return 'data:image/svg+xml;base64,'+base64.b64encode(text.encode()).decode()
    def test_passive_clock_svg_and_resource_type_boundary(self):
        url=self.uri(SVG)
        self.assertEqual(self.run_policy([(url,'image'),(url,'document'),(url,'image','POST'),('https://example.com/a.svg','image')]),[True,False,False,False])
    def test_active_external_malformed_oversized_and_mislabeled_data_are_blocked(self):
        variants=[SVG.replace('<path','<script'),SVG.replace('<path','<foreignObject'),SVG.replace('<path','<image href="https://example.com/"'),
                  SVG.replace('fill="none"','onload="alert(1)"'),SVG.replace('fill="none"','fill="url(#x)"'),
                  SVG.replace('WindowText','&x;'),SVG.replace('</svg>','</g>'),SVG+'<svg/>',SVG+' ' * 20000]
        entries=[(self.uri(s),'image') for s in variants]
        entries.extend([('data:text/html;base64,PGgxPng8L2gxPg==','image'),('data:image/png;base64,PHNjcmlwdD4=','image')])
        self.assertFalse(any(self.run_policy(entries)))


class BrowserCapacityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings=load_settings(project_root=PROJECT,environ={});cls.browser=BrowserEvaluator(cls.settings,profile(cls.settings))
    def test_more_than_300_elements_have_complete_dom_and_style_evidence(self):
        body='<div>'+''.join('<span>'+str(i)+'</span>' for i in range(340))+'</div>'
        source='<template>'+body+'</template><script>export default {}</script>'
        code='<template>'+body+'</template><script>const san=require("san");module.exports=san.defineComponent({})</script>'
        r=self.browser.evaluate(source,code,{},[])
        for side in ('vue','san'):
            self.assertGreater(len(r[side]['snapshots'][0]['styles']),340)
            self.assertTrue(r[side]['evidence_limits']['complete'])
    def test_true_node_capacity_is_still_blocked(self):
        body='<div>'+'<i></i>'*3001+'</div>'
        source='<template>'+body+'</template><script>export default {}</script>'
        code='<template>'+body+'</template><script>const san=require("san");module.exports=san.defineComponent({})</script>'
        with self.assertRaisesRegex(Exception,'dom_node_limit'):self.browser.evaluate(source,code,{},[])
    def test_native_time_control_data_image_no_longer_blocks_source(self):
        body='<div><input type="time"/><img src="'+self.uri(SVG)+'"/></div>'
        source='<template>'+body+'</template><script>export default {}</script>'
        code='<template>'+body+'</template><script>const san=require("san");module.exports=san.defineComponent({})</script>'
        r=self.browser.evaluate(source,code,{},[])
        for side in ('vue','san'):self.assertEqual(r[side]['blocked_requests'],[])
    uri=ResourcePolicyTests.uri


class SharedConstraintTests(unittest.TestCase):
    def test_generation_and_both_repair_paths_share_contract_without_changing_base_builder(self):
        settings=load_settings(project_root=PROJECT,environ={})
        messages,audit=generation_messages(settings,{'template':{},'script':{}},[])
        self.assertIn(CONSTRAINTS,messages[0]['content'])
        self.assertEqual(audit['generation_context']['shared_san_contract']['sha256'],sha256(CONSTRAINTS.encode()).hexdigest())
        self.assertIn(CONSTRAINTS,syntax_repair_messages('','',{'diagnostics':[],'diagnostic_count':0})[0]['content'])
        errors=[{'code':c} for c in ['rendered_dom_mismatch','missing_prop_defaults','source_dynamic_assignment_unproven','target_template_syntax_error','hidden_template_reactive_dependency']]
        self.assertEqual(len(repair_targets(errors)),5)


class ClassArrayProofTests(unittest.TestCase):
    def test_data_array_index_reads_do_not_disable_class_serialization_proof(self):
        from test_modular_empty_class_policy import policy,SOURCE as A,TARGET as B
        source=A.replace('flag:false','flag:false,index:0,items:[1,2]').replace('methods:{','computed:{chosen(){const items=this.items;return items[this.index]}},methods:{')
        code=B.replace('flag:false','flag:false,index:0,items:[1,2]').replace('toggle(){',"computed:{chosen(){const items=this.data.get('items');return items[this.data.get('index')]}},toggle(){")
        self.assertTrue(policy(source,code)['approved'])
        for a,b in ((source.replace('items:[1,2]','items:{}'),code.replace('items:[1,2]','items:{}')),
                    (source.replace('return items[this.index]','return other[this.index]'),code),
                    (source.replace('return items[this.index]','items[this.index]=5;return 1'),code),
                    (source.replace('<style>','<style>button[class]{color:red}'),code)):
            with self.subTest(source=a):self.assertFalse(policy(a,b)['approved'])

    def test_value_attribute_stays_strict_even_with_approved_class_policy(self):
        from card_migration_system.stages.dom_comparison import compare_dom
        a={'tag':'input','attributes':{'type':'number','value':'3'},'label':'input|type=number|value=3','children':[]}
        b={'tag':'input','attributes':{'type':'number'},'label':'input|type=number','children':[]}
        r=compare_dom(a,b,{'version':'class_serialization_v2','approved':True})
        self.assertEqual(r['raw_metric']['distance'],1);self.assertEqual(r['metric']['distance'],1)




if __name__=='__main__':unittest.main()
