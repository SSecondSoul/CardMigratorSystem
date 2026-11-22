"""Finite internal parameter flow; all callers/arguments, not method-name rules."""
import unittest
from test_internal_assignment_v3_followup import proof
from test_semantic_comparison_v1 import inspect

SOURCE='''<template><main>
 <input :value="start" @input="updateField('start',$event)"/>
 <input :value="end" @input="updateField('end',$event)"/>
</main></template><script>export default {data(){return {start:0,end:3}},methods:{
 assignField(k,v){this[k]=v},updateField(field,event){this.assignField(field,Number(event.target.value))}}}</script>'''
TARGET='''<template><main><input value="{{start}}" on-input="updateField('start',$event)"/><input value="{{end}}" on-input="updateField('end',$event)"/></main></template><script>const san=require('san');module.exports=san.defineComponent({initData(){return {start:0,end:3}},
 assignField(k,v){this.data.set(k,v)},updateField(field,event){this.assignField(field,Number(event.target.value))}})</script>'''


class InternalParameterFlowTests(unittest.TestCase):
    def test_all_template_call_keys_are_proven_without_assuming_external_arguments(self):
        for name in ('updateField','writeInput','renamedHandler'):
            _,contract=proof(SOURCE.replace('updateField',name),TARGET.replace('updateField',name))
            self.assertEqual(contract['status'],'proven_for_source_internal_calls',contract)
            self.assertEqual(set(contract['source_keys']),{'start','end'})
            self.assertFalse(contract['arbitrary_key_semantics_proven'])
            self.assertTrue(contract['parameter_flows'])

    def test_script_wrapper_arguments_and_entire_upstream_body_are_checked(self):
        source=SOURCE.replace('updateField(\'start\',$event)',"startInput($event)").replace('methods:{',"methods:{startInput(e){this.updateField('start',e)},")
        target=TARGET.replace('updateField(\'start\',$event)',"startInput($event)").replace('assignField(k,v)',"startInput(e){this.updateField('start',e)},assignField(k,v)")
        self.assertEqual(proof(source,target)[1]['status'],'proven_for_source_internal_calls')
        wrong=target.replace("this.updateField('start',e)","this.updateField('start',{target:{value:99}})")
        contract=proof(source,wrong)[1]
        self.assertEqual(contract['status'],'unproven')
        self.assertIn('caller_body_not_source_matched:startInput',contract['refusals'])

    def test_unknown_implicit_event_escaped_reassigned_and_recursive_parameters_refuse(self):
        for old,new in [("updateField('start',$event)",'updateField'),
                        ("updateField('start',$event)","updateField(runtimeKey,$event)"),
                        ('this.assignField(field,Number(event.target.value))',"field=event.key;this.assignField(field,Number(event.target.value))"),
                        ('this.assignField(field,Number(event.target.value))',"const escaped=this.updateField;this.assignField(field,Number(event.target.value))"),
                        ('this.assignField(field,Number(event.target.value))',"this.updateField(field,event);this.assignField(field,Number(event.target.value))")]:
            self.assertEqual(proof(SOURCE.replace(old,new),TARGET)[1]['status'],'unproven',(old,new))

    def test_every_template_argument_and_key_must_match_not_only_key_sets(self):
        for old,new in [("'start',$event","'start',otherEvent"),("'start',$event","'end',$event"),
                        ("'start',$event","'start',99"),("'start',$event","...args"),
                        ("'start',$event","'data',$event"),("'start',$event","'a.b',$event")]:
            self.assertEqual(proof(SOURCE,TARGET.replace(old,new))[1]['status'],'unproven',(old,new))

    def test_loop_alias_shadowing_and_implicit_text_method_references_refuse(self):
        for before,after in [('<main>','<main v-for="updateField in handlers">'),
                             ('</main>','{{updateField}}</main>')]:
            self.assertEqual(proof(SOURCE.replace(before,after),TARGET)[1]['status'],'unproven')


if __name__=='__main__':unittest.main()
