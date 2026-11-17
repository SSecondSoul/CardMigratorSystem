"""Generic separator, numeric style and watcher-phase closure; no model calls."""
import json
from pathlib import Path
import subprocess
import unittest

from migration_pipeline.utils.class_binding_semantics import class_binding_semantics
from migration_pipeline.utils.source_render_dependency_semantics import source_render_dependency_semantics
from migration_pipeline.utils.bounded_semantics import inspect_semantics

ROOT=Path(__file__).resolve().parents[1]


def style_fixture():
    vue='''<template><div><i class="bar" :style="{width: size(amount) + '%'}"></i></div></template>
<script>export default {data(){return {amount:5,limit:10}},methods:{size(amount){if(this.limit===0)return 0;return (amount/this.limit)*100;}}}</script>'''
    san='''<template><div><i class="bar" style="width: {{size(amount,limit)}}%"></i></div></template>
<script>const san=require('san');module.exports=san.defineComponent({initData(){return {amount:5,limit:10}},size(amount,limit){if(limit===0)return 0;return(amount/limit)*100;}})</script>'''
    return san,vue


def phase_fixture():
    vue='''<template><div/></template><script>export default {data(){return {rows:[]}},
watch:{rows:{handler(){this.save()},deep:true}},mounted(){this.load()},methods:{load(){},save(){}}}</script>'''
    san='''<template><div/></template><script>const san=require('san');module.exports=san.defineComponent({
initData(){return {rows:[]}},inited(){this.load()},attached(){this.watch('rows',()=>{this.save()})},load(){},save(){}})</script>'''
    return san,vue,{'script':{'options':{'data':[{'name':'rows'}]}}}


class StringClassBoundaryTests(unittest.TestCase):
    def fixture(self):
        return ('<template><div class="row{{tone}}"/></template><script>const san=require("san");module.exports=san.defineComponent({initData(){return {tone:"expense"}}})</script>',
                '<template><div class="row" :class="tone"/></template><script>export default {data(){return {tone:"expense"}}}</script>')

    def test_missing_separator_detected_and_repaired_without_changing_expression(self):
        code,vue=self.fixture();result=class_binding_semantics(code,vue,repair=True)
        self.assertNotIn('error',result,result)
        self.assertIn('source_class_binding_not_landed',[f['code'] for f in result['findings']])
        self.assertEqual(result['code'],code.replace('row{{tone}}','row {{tone}}'))
        self.assertIn('restored_source_class_token_separator',result['changes'])
        self.assertEqual(class_binding_semantics(result['code'],vue)['findings'],[])
        self.assertEqual(class_binding_semantics(result['code'],vue,repair=True)['code'],result['code'])

    def test_string_loop_member_binding_matches_scope(self):
        code,vue=self.fixture()
        code=code.replace('<div class','<div s-for="record in rows trackby record.id" class').replace('{{tone}}','{{record.type}}').replace('tone:"expense"','rows:[]')
        vue=vue.replace('<div class','<div v-for="record in rows" :key="record.id" class').replace(':class="tone"',':class="record.type"').replace('tone:"expense"','rows:[]')
        result=class_binding_semantics(code,vue,repair=True)
        self.assertIn('row {{record.type}}',result['code'])
        mismatched=code.replace('record in rows','other in rows')
        self.assertEqual(class_binding_semantics(mismatched,vue,repair=True)['code'],mismatched)

    def test_wrong_expression_static_prefix_path_or_unknown_field_not_guessed(self):
        code,vue=self.fixture()
        for changed in (code.replace('{{tone}}','{{other}}'),code.replace('row{{','wrong{{'),
                        code.replace('<div class','<aside class'),code.replace('tone:"expense"','other:"expense"')):
            with self.subTest(changed=changed):
                self.assertEqual(class_binding_semantics(changed,vue,repair=True)['code'],changed)

    def test_nonobject_source_call_and_string_literal_are_not_inferred(self):
        code,vue=self.fixture()
        for expression in ('makeTone().value',"'expense'"):
            changed=code.replace('{{tone}}','{{'+expression+'}}')
            source=vue.replace(':class="tone"',':class="'+expression+'"')
            self.assertEqual(class_binding_semantics(changed,source,repair=True)['code'],changed)

    def test_equivalent_concatenation_is_not_a_false_positive_and_missing_separator_can_be_repaired(self):
        code,vue=self.fixture()
        for value in ("{{'row ' + tone}}","{{'row' + ' ' + tone}}"):
            changed=code.replace('row{{tone}}',value)
            result=class_binding_semantics(changed,vue,repair=True)
            self.assertEqual(result['findings'],[]);self.assertEqual(result['code'],changed)
        changed=code.replace('row{{tone}}',"{{'row' + tone}}")
        self.assertIn('class="row {{tone}}"',class_binding_semantics(changed,vue,repair=True)['code'])

    def test_unknown_but_valid_class_representation_is_reviewed_not_declared_a_mismatch(self):
        code,vue=self.fixture();changed=code.replace('row{{tone}}',"{{['row', tone] | classNames}}")
        result=class_binding_semantics(changed,vue,repair=True)
        self.assertEqual(result['code'],changed);self.assertEqual(result['findings'],[])
        self.assertTrue(result['reviews'])


class NumericStyleTests(unittest.TestCase):
    def apply(self,code,vue,repair=True):
        result=source_render_dependency_semantics(code,vue,repair=repair)
        self.assertNotIn('error',result,result);return result

    def test_matching_CSS_envelope_recovers_public_signature_and_private_dependencies(self):
        code,vue=style_fixture();result=self.apply(code,vue)
        self.assertTrue(result['changes']);self.assertTrue(result['proofs'][0]['public_signature_restored'])
        self.assertIn('size(amount)',result['code']);self.assertIn('__sourceDependency_size(amount,limit)',result['code'])
        again=self.apply(result['code'],vue)
        self.assertEqual(again['code'],result['code']);self.assertEqual(again['findings'],[])

    def test_whole_interpolation_CSS_envelope_and_original_public_signature(self):
        code,vue=style_fixture()
        code=code.replace('width: {{size(amount,limit)}}%',"{{'width: ' + size(amount) + '%'}}")
        code=code.replace('size(amount,limit){if(limit===0)return 0;return(amount/limit)*100;}',
                          'size(amount){if(this.data.get("limit")===0)return 0;return(amount/this.data.get("limit"))*100;}')
        result=self.apply(code,vue)
        self.assertTrue(result['changes'],result)
        self.assertIn('__sourceDependency_size(amount,limit)',result['code'])
        self.assertEqual(self.apply(result['code'],vue)['findings'],[])
        self.assertEqual(self.apply(result['code'],vue)['code'],result['code'])
        for changed in (code.replace("+ '%'","+ 'px'"),code.replace("'width: '","'height: '"),
                        code.replace("+ '%'","+ '%;color:red'"),code.replace('size(amount)','size(2)',1)):
            self.assertEqual(self.apply(changed,vue)['code'],changed)

    def test_installed_San_public_and_render_follow_dependency_updates(self):
        code,vue=style_fixture();fixed=self.apply(code,vue)['code']
        js=r'''const fs=require('fs'),san=require('san'),m={exports:{}};
const code=JSON.parse(fs.readFileSync(0,'utf8'));
new Function('require','module',/<script>([\s\S]*?)<\/script>/.exec(code)[1])(require,m);
m.exports.prototype.template=/<template>([\s\S]*?)<\/template>/.exec(code)[1];const c=new m.exports();
const find=n=>n.tagName==='i'?n:(n.children||[]).map(find).find(Boolean);
const expr=find(c.aNode).props.find(p=>p.name==='style').expr;
const read=()=>({public:c.size(5),render:san.evalExpr(expr,c.data,c)});const a=read();c.data.set('limit',20);const b=read();c.data.set('limit',0);console.log(JSON.stringify([a,b,read()]));'''
        process=subprocess.run(['node','-e',js],input=json.dumps(fixed).encode(),capture_output=True,cwd=ROOT,timeout=15)
        self.assertEqual(process.returncode,0,process.stderr.decode())
        values=json.loads(process.stdout)
        self.assertEqual([v['public'] for v in values],[50,25,0])
        self.assertEqual([v['render'] for v in values],['width: 50%','width: 25%','width: 0%'])

    def test_wrong_units_extra_CSS_properties_or_other_operand_refuse(self):
        code,vue=style_fixture()
        for changed in (code.replace('}}%','}}px'),code.replace('}}%','}}%;color:red'),
                        code.replace('{{size(amount,limit)}}','{{size(2,limit)}}'),code.replace('style="width:','style="height:')):
            self.assertEqual(self.apply(changed,vue)['code'],changed)

    def test_nonnumeric_return_effects_and_unknown_calls_refuse(self):
        code,vue=style_fixture()
        for old,new in [('return (amount/this.limit)*100',"return 'wide'"),
                        ('if(this.limit===0)','this.limit=2;if(this.limit===0)'),
                        ('return (amount/this.limit)*100','return this.unknown(amount)')]:
            source=vue.replace(old,new)
            self.assertEqual(self.apply(code,source)['code'],code)

    def test_other_script_or_event_callers_and_multiple_template_roots_refuse(self):
        code,vue=style_fixture()
        for changed in (code.replace('initData(){','other(){return this.size(1)},initData(){'),
                        code.replace('<i class','<i on-click="size" class'),
                        code.replace('</i>','</i><b>{{size(amount,limit)}}</b>')):
            self.assertEqual(self.apply(changed,vue)['code'],changed)

    def test_body_change_unknown_scope_and_missing_dependency_not_overwritten(self):
        code,vue=style_fixture()
        for changed in (code.replace('*100','*99'),code.replace('<i class','<i s-if="amount" class'),
                        code.replace('size(amount,limit)}}','size(amount)}}')):
            self.assertEqual(self.apply(changed,vue)['code'],changed)


class WatcherMountedTests(unittest.TestCase):
    def apply(self,code,vue,ssm):
        result=inspect_semantics(code,vue,repair=True,ssm=ssm)
        self.assertNotIn('error',result,result);return result

    def test_misplaced_mounted_call_moves_after_matching_source_watcher(self):
        code,vue,ssm=phase_fixture();result=self.apply(code,vue,ssm)
        self.assertIn('restored_source_mounted_after_proven_watchers',result['changes'])
        self.assertIn('inited(){}',result['code']);self.assertLess(result['code'].index("this.watch('rows'"),result['code'].index('this.load()'))
        self.assertEqual(self.apply(result['code'],vue,ssm)['code'],result['code'])

    def test_source_proven_watcher_option_becomes_registration_before_mounted(self):
        code,vue,ssm=phase_fixture()
        code=code.replace("attached(){this.watch('rows',()=>{this.save()})}","watcher:{rows(){this.save()}}")
        result=self.apply(code,vue,ssm)
        self.assertIn('registered_source_proven_watcher_option_before_mounted',result['changes'],result)
        self.assertNotIn('watcher:',result['code'])
        self.assertIn('inited(){this.watch("rows",()=>{this.save();});}',result['code'])
        self.assertIn('attached(){this.load();}',result['code'])
        self.assertEqual(self.apply(result['code'],vue,ssm)['code'],result['code'])
        for changed,source in ((code.replace('this.save()','this.extra()'),vue),
                               (code.replace('inited(){','inited(){this.extra();'),vue),
                               (code.replace('watcher:{','other(){return this.watcher},watcher:{'),vue),
                               (code,vue.replace('deep:true','deep:true,immediate:true')),
                               (code,vue.replace('mounted(){','created(){this.extra()},mounted(){'))):
            self.assertEqual(self.apply(changed,source,ssm)['code'],changed)

    def test_registered_source_deep_watcher_observes_nested_native_San_update(self):
        code,vue,ssm=phase_fixture()
        code=code.replace("attached(){this.watch('rows',()=>{this.save()})}","watcher:{rows(){this.save()}}")
        code=code.replace('rows:[]','rows:[{value:1}],events:[]').replace('save(){}',"save(){this.data.push('events','save')}")
        vue=vue.replace('rows:[]','rows:[{value:1}],events:[]').replace('save(){}',"save(){this.events.push('save')}")
        ssm['script']['options']['data'].append({'name':'events'})
        fixed=self.apply(code,vue,ssm)['code']
        js=r'''const fs=require('fs'),san=require('san'),m={exports:{}};
const code=JSON.parse(fs.readFileSync(0,'utf8'));
new Function('require','module',/<script>([\s\S]*?)<\/script>/.exec(code)[1])(require,m);
const c=new m.exports();c.data.set('rows[0].value',2);
san.nextTick(()=>process.stdout.write(JSON.stringify(c.data.get('events')),()=>process.exit(0)));'''
        process=subprocess.run(['node','-e',js],input=json.dumps(fixed).encode(),capture_output=True,cwd=ROOT,timeout=15)
        self.assertEqual(process.returncode,0,process.stderr.decode())
        self.assertEqual(json.loads(process.stdout),['save'])

    def test_unknown_hook_effects_wrong_watch_body_and_early_source_hook_refuse(self):
        code,vue,ssm=phase_fixture()
        for changed,source in ((code.replace('inited(){','inited(){this.extra();'),vue),
                               (code.replace('this.save()','this.extra()'),vue),
                               (code,vue.replace('mounted(){','created(){this.extra()},mounted(){')),
                               (code,vue.replace('deep:true','deep:true,immediate:true'))):
            self.assertEqual(self.apply(changed,source,ssm)['code'],changed)

    def test_unregistered_or_duplicate_watchers_are_not_moved_across(self):
        code,vue,ssm=phase_fixture()
        for changed in (code.replace("watch('rows'","watch('unknown'"),
                        code.replace("this.watch('rows',()=>{this.save()})","this.watch('rows',()=>{this.save()});this.watch('rows',()=>{this.save()})")):
            self.assertEqual(self.apply(changed,vue,ssm)['code'],changed)

    def test_installed_San_registers_watcher_before_loading_once(self):
        code,vue,ssm=phase_fixture()
        vue=vue.replace('rows:[]','rows:[],events:[]').replace('load(){}',"load(){this.events.push('load');this.rows=[1]}").replace('save(){}',"save(){this.events.push('save')}")
        code=code.replace('rows:[]','rows:[],events:[]').replace('load(){}',"load(){this.data.push('events','load');this.data.set('rows',[1])}").replace('save(){}',"save(){this.data.push('events','save')}")
        ssm['script']['options']['data'].append({'name':'events'})
        fixed=self.apply(code,vue,ssm)['code']
        js=r'''const fs=require('fs'),san=require('san'),m={exports:{}};
const code=JSON.parse(fs.readFileSync(0,'utf8'));
new Function('require','module',/<script>([\s\S]*?)<\/script>/.exec(code)[1])(require,m);
const c=new m.exports();c.attached();san.nextTick(()=>process.stdout.write(JSON.stringify(c.data.get('events')),()=>process.exit(0)));'''
        process=subprocess.run(['node','-e',js],input=json.dumps(fixed).encode(),capture_output=True,cwd=ROOT,timeout=15)
        self.assertEqual(process.returncode,0,process.stderr.decode())
        self.assertEqual(json.loads(process.stdout),['load','save'])


if __name__=='__main__':unittest.main()
