"""Literal-root record updates: source semantics, repair and independent guards."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from migration_pipeline.utils.bounded_semantics import inspect_semantics
from migration_pipeline.utils.repair_scheduler import candidate_gate
from migration_pipeline.utils.repair_prompt import RepairPromptInput, build_repair_prompt
from migration_pipeline.stages.repair import RepairStage, RepairStageInput
from migration_pipeline.repair_client import RepairResult

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data/experiments/analysis/formal_30_v4_record_update_v1_input_20261114'
ISSUE='source_record_update_not_landed'
CHANGE='restored_source_literal_record_update'
CLONE="""function clone(obj){
if(obj===null||typeof obj!=='object')return obj;
if(Array.isArray(obj))return obj.map(clone);
const result={};for(let key in obj){if(obj.hasOwnProperty(key)){result[key]=clone(obj[key]);}}
return result;}"""


def fixture():
    data="{record:{label:'old',count:1,nested:{tag:7}}}"
    value="field==='count' ? Number(event.target.value)||0 : event.target.value"
    vue='<template><section></section></template><script>module.exports={data(){return '+data+";},methods:{setValue(key,value){this[key]=value;},update(field,event){this.setValue('record',Object.assign({},this.record,{[field]:"+value+'}));}}};</script>'
    code='<template><section></section></template><script>const san=require("san");'+CLONE+"module.exports=san.defineComponent({initData(){return "+data+";},update(field,event){const record=this.data.get('record');const value="+value+";const next=clone(record);next[field]=value;this.data.set('record',next);}});</script><style>section{color:red}</style>"
    return code,vue


class SourceRecordUpdateClosureTests(unittest.TestCase):
    def apply(self, code, vue, repair=True):
        r=inspect_semantics(code,vue,repair=repair)
        self.assertNotIn('error',r,r)
        return r

    def findings(self,code,vue):
        return [f for f in self.apply(code,vue,False)['findings'] if f['code']==ISSUE]

    def test_literal_record_copy_is_derived_from_source_and_idempotent(self):
        code,vue=fixture();r=self.apply(code,vue)
        self.assertIn(CHANGE,r['changes'])
        self.assertIn('Object.assign({},this.data.get("record")',r['code'])
        self.assertEqual(len(self.findings(code,vue)),1)
        self.assertEqual(self.findings(r['code'],vue),[])
        self.assertEqual(self.apply(r['code'],vue)['code'],r['code'])
        self.assertTrue(self.apply(r['code'],vue)['record_update_contracts'][0]['landed'])

    def test_readonly_mode_only_reports_and_preserves_template_style_helper(self):
        code,vue=fixture();r=self.apply(code,vue,False)
        self.assertEqual(r['code'],code)
        fixed=self.apply(code,vue)['code']
        self.assertIn(CLONE,fixed)
        self.assertEqual(fixed.split('<script>')[0],code.split('<script>')[0])
        self.assertEqual(fixed.split('</script>')[1],code.split('</script>')[1])

    def test_names_and_literal_roots_are_not_component_specific(self):
        code,vue=fixture()
        for old,new in [('record','settings'),('update','edit'),('field','name'),('event','input'),('clone','copyValue')]:
            code=code.replace(old,new);vue=vue.replace(old,new)
        self.assertIn(CHANGE,self.apply(code,vue)['changes'])
        for name in ['_record','$record']:
            c,v=fixture();self.assertNotIn(CHANGE,self.apply(c.replace('record',name),v.replace('record',name))['changes'])

    def test_unknown_copy_helpers_and_identity_clones_are_not_guessed(self):
        code,vue=fixture()
        for changed in [code.replace(CLONE,'function clone(obj){return obj;}'),
                        code.replace('return result;', 'external(result);return result;'),
                        code.replace('const next=clone(record)', 'const next=unknown(record)'),
                        code.replace('module.exports=', 'clone=other;module.exports=')]:
            r=self.apply(changed,vue)
            self.assertNotIn(CHANGE,r['changes'])
            self.assertTrue(self.findings(changed,vue))

    def test_extra_effects_wrong_keys_wrong_commit_and_value_changes_refused(self):
        code,vue=fixture()
        for old,new in [("const record=",'sideEffect();const record='),
                        ('next[field]=value','next.other=value'),
                        ("this.data.set('record',next)","this.data.set('other',next)"),
                        ("field==='count'","field==='wrong'"),
                        ('const next=clone(record)','const next=record'),
                        ('next[field]=value','next.nested.tag=value')]:
            changed=code.replace(old,new);self.assertNotEqual(changed,code)
            self.assertNotIn(CHANGE,self.apply(changed,vue)['changes'])
            self.assertTrue(self.findings(changed,vue))

    def test_source_setter_effects_unknown_values_or_nonliteral_roots_not_admitted(self):
        code,vue=fixture()
        for old,new in [('this[key]=value;','this[key]=value;this.log();'),
                        ('Object.assign({},this.record','Object.assign(this.record,this.record'),
                        ("'record',Object.assign",'field,Object.assign'),
                        ('event.target.value','unknown(event)'),
                        ('this.record,{[field]','this.record,{literal'),
                        ('data(){return {record:', 'data(){return {recordSource:'),
                        ('update(field,event)', 'initData(field,event)')]:
            changed=vue.replace(old,new);self.assertNotEqual(changed,vue)
            self.assertNotIn(CHANGE,self.apply(code,changed)['changes'])

    def test_shadowed_globals_and_framework_overrides_keep_target_unproven(self):
        code,vue=fixture()
        for prefix in ['const Object=other;','const Number=other;', 'Object.assign=other;', 'san.defineComponent=other;']:
            changed=code.replace('module.exports=',prefix+'module.exports=')
            r=self.apply(changed,vue)
            self.assertNotIn(CHANGE,r['changes']);self.assertTrue(self.findings(changed,vue))
        self.assertNotIn(CHANGE,self.apply(code,vue.replace('module.exports=', 'const Object=other;module.exports='))['changes'])
        collision=code.replace('initData(){','computed:{record(){return null;}},initData(){')
        self.assertNotIn(CHANGE,self.apply(collision,vue)['changes'])

    def test_default_params_wrong_parameter_binding_and_different_target_shape_refused(self):
        code,vue=fixture()
        for changed in [code.replace('update(field,event)','update(field,input)'),
                        code.replace('update(field,event)','update(field,event={})'),
                        code.replace('update(field,event)','async update(field,event)'),
                        code.replace('const value=', 'let value='),
                        code.replace('const next=clone(record);', 'const next=clone(record);unknown(next);')]:
            self.assertNotIn(CHANGE,self.apply(changed,vue)['changes'])

    def test_independent_gate_accepts_fix_rejects_regression_and_forged_flags(self):
        code,vue=fixture();fixed=self.apply(code,vue)['code']
        state=lambda c:{'generated_code':c,'vue_source':vue,'ssm':{},'validation_errors':self.apply(c,vue,False)['findings']}
        self.assertFalse(candidate_gate(state(code),state(fixed))['should_stop'])
        self.assertTrue(candidate_gate(state(fixed),state(code))['should_stop'])
        forged={**state(code),'validation_errors':[],'validation_passed':True}
        gate=candidate_gate(state(fixed),forged)
        self.assertTrue(gate['should_stop']);self.assertTrue(gate['waived_source_record_update_findings'])
        hidden=code.replace('module.exports=', 'const Object=other;module.exports=')
        self.assertTrue(candidate_gate(state(fixed),{**state(hidden),'validation_errors':[]})['should_stop'])

    def test_missing_target_method_still_reports_contract(self):
        code,vue=fixture();a=code.index('update(field,event)');b=code.index('});</script>',a)
        changed=code[:a]+code[b:]
        self.assertTrue(self.findings(changed,vue))
        self.assertNotIn(CHANGE,self.apply(changed,vue)['changes'])

    def test_frozen_trip_restores_record_and_projection_not_mutation_exemption_or_setter(self):
        b=json.loads((BASE/'baseline.json').read_text(encoding='utf-8'))
        code=(ROOT/b['candidate']['path']).read_text(encoding='utf-8');vue=(ROOT/b['source']['path']).read_text(encoding='utf-8')
        r=self.apply(code,vue);self.assertEqual(r['changes'],[CHANGE,'restored_source_shared_swap_shallow_projection','restored_source_parent_shallow_initialization','restored_source_native_computed_collection','restored_source_native_filter_method'])
        self.assertIn('const rows=this.data.get("dayItems").slice();',r['code'])
        self.assertFalse(r['shared_record_contracts'][0]['nested_mutation_exemption'])
        self.assertIn('script.methods.setValue',[f['location'] for f in self.apply(r['code'],vue,False)['findings']])
        self.assertEqual(self.apply(r['code'],vue)['code'],r['code'])

    def test_prepass_and_simulated_response_postprocessing_use_identical_rule(self):
        code,vue=fixture()
        class Client:
            def repair(self,request):
                return RepairResult(source_file='fixture',ssm={},code=code,saved_file_path=request.output_file_path,provider='fixture',model='offline',usage={})
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'Source.vue';path.write_text(vue,encoding='utf-8')
            errors=self.apply(code,vue,False)['findings']
            fixed,steps=RepairStage._deterministic_repair_plan(code,errors,[],{},str(path))
            self.assertIn(('bounded_ast_semantics',CHANGE),steps)
            result=RepairStage(Client()).run(RepairStageInput(ssm={},generated_code=code,vue_file_path=str(path),
                output_file_path=str(Path(directory)/'candidate.san'),metadata={'skip_deterministic_prepass':True}))
            self.assertEqual(result.repaired_code,fixed+'\n')
            self.assertIn(CHANGE,result.raw_response['pipeline_postprocessing'])

    def test_prompt_requires_shallow_copy_literal_root_and_no_arbitrary_setter(self):
        prompt=build_repair_prompt(RepairPromptInput(ssm={},current_code='',validation_errors=[{'code':ISSUE}]))
        for phrase in ['shallow Object.assign','dotted record key','Unknown helper bodies']:
            self.assertIn(phrase,prompt)

    def native(self, mode):
        code,vue=fixture();fixed=self.apply(code,vue)['code']
        js=r'''
const fs=require('fs'),{parse}=require('@vue/compiler-sfc');
const x=JSON.parse(fs.readFileSync(0,'utf8')),Vue=require(x.runtime);
function source(){const m={exports:{}};Function('module',parse(x.vue).descriptor.script.content)(m);return new Vue(m.exports);}
function target(text){const m={exports:{}};Function('require','module',/<script>([\s\S]*?)<\/script>/.exec(text)[1])(require,m);return new m.exports();}
const run=(instance,isVue)=>{
 const read=()=>isVue?instance.record:instance.data.get('record'),old=read(),nested=old.nested,trace=[];
 if(x.mode==='order')Object.defineProperty(old,'label',{configurable:true,enumerable:true,get(){trace.push('record-copy');return 'old';}});
 const event={target:{}};Object.defineProperty(event.target,'value',{get(){trace.push('event-value');return x.mode==='numeric'?'4':'new';}});
 const field=x.mode==='numeric'?'count':x.mode==='dotted'?'a.b':'label';
 const result=instance.update(field,event),record=read();
 const output={record:JSON.parse(JSON.stringify(record)),newRoot:record!==old,sameNested:record.nested===nested,trace:[...trace],returnUndefined:result===undefined};
 if(isVue)instance.$destroy();else instance.dispose();return output;
};
process.stdout.write(JSON.stringify({source:run(source(),true),before:run(target(x.before),false),after:run(target(x.after),false)}));
'''
        p=subprocess.run(['node','-e',js],cwd=ROOT,input=json.dumps({'vue':vue,'before':code,'after':fixed,'mode':mode,
            'runtime':str(ROOT/'data/experiments/manual_followups/task_manager_async_scope_v7_prepared_20261113/vendor/vue-2.7.16.js')}),
            text=True,encoding='utf-8',capture_output=True,timeout=20)
        self.assertEqual(p.returncode,0,p.stderr);return json.loads(p.stdout)

    def test_native_frameworks_preserve_shallow_nested_alias_and_new_root(self):
        r=self.native('plain');self.assertEqual(r['source'],r['after'])
        self.assertTrue(r['after']['sameNested']);self.assertTrue(r['after']['newRoot'])
        self.assertFalse(r['before']['sameNested'])

    def test_native_getter_evaluation_order_matches_actual_source(self):
        r=self.native('order');self.assertEqual(r['source'],r['after'])
        # All Object.assign arguments, including the computed-property value,
        # are evaluated before Object.assign starts copying source properties.
        self.assertEqual(r['source']['trace'],['event-value','record-copy'])
        self.assertEqual(r['after']['trace'],['event-value','record-copy'])
        self.assertEqual(r['before']['trace'],['event-value','record-copy'])

    def test_native_dotted_record_key_is_literal_not_a_san_path(self):
        r=self.native('dotted');self.assertEqual(r['source'],r['after'])
        self.assertEqual(r['after']['record']['a.b'],'new');self.assertNotIn('a',r['after']['record'])

    def test_native_numeric_conversion_and_return_value_preserved(self):
        r=self.native('numeric');self.assertEqual(r['source'],r['after'])
        self.assertEqual(r['after']['record']['count'],4);self.assertTrue(r['after']['returnUndefined'])


if __name__=='__main__':unittest.main()
