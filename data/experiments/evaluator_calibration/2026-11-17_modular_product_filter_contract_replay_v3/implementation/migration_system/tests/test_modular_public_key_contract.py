"""Retained arbitrary-key contract fails early; live values never waive DOM attributes."""
from copy import deepcopy
from hashlib import sha256
import json
import subprocess
import unittest

from test_modular_system import ModularFixture,PROJECT,FakeBrowser
from card_migration_system.adapters.browser import BrowserEvaluator,SourceContractError
from card_migration_system.config import load_settings
from card_migration_system.runtime import profile
from card_migration_system.stages.evaluation import assess
from card_migration_system.stages.dom_comparison import compare_control_state

FROZEN=PROJECT.parent/'data/experiments/evaluator_calibration/2026-11-17_modular_product_filter_failure_frozen_v1'
SOURCE='<template><div><input></div></template><script>module.exports={methods:{setValue(key,value){this[key]=value}}}</script>'


def contracts(source):
    result=subprocess.run(['node',str(PROJECT/'browser/evaluate.mjs')],input=json.dumps({
        'repository':str(PROJECT.parent),'project':str(PROJECT),'source':source,'action':'source-contracts'}).encode(),
        capture_output=True,timeout=30)
    return result.returncode,json.loads(result.stdout)


class PublicKeyContractTests(unittest.TestCase):
    def test_generic_exact_setter_is_detected_without_component_name_or_fixed_keys(self):
        for source in (SOURCE,SOURCE.replace('module.exports=','export default '),
                       SOURCE.replace('setValue(key,value){this[key]=value}',
                                      'assignAnything(other,next){this[other]=next}')):
            code,data=contracts(source)
            self.assertEqual(code,2,data)
            self.assertEqual(data['error'],'source_dynamic_key_contract_unsupported')
            self.assertEqual(data['diagnostics'][0]['location_precision'],'exact')

    def test_constant_function_alias_uses_same_shared_recognition_as_validator(self):
        source=SOURCE.replace('module.exports=', 'function assign(k,v){this[k]=v};module.exports=')
        source=source.replace('setValue(key,value){this[key]=value}','setValue:assign')
        self.assertEqual(contracts(source)[1]['error'],'source_dynamic_key_contract_unsupported')

    def test_literal_state_writes_and_non_method_decoys_are_not_blocked(self):
        for source in (SOURCE.replace('this[key]=value','this.query=value'),
                       SOURCE.replace('methods:{setValue(key,value){this[key]=value}}',
                                      'data(){return {text:"this[key]=value"}}'),
                       SOURCE.replace('module.exports=', 'const helper={methods:{setValue(k,v){this[k]=v}}};module.exports=').replace(
                           'methods:{setValue(key,value){this[key]=value}}','data(){return {query:""}}')):
            self.assertEqual(contracts(source)[0],0)

    def test_check_does_not_execute_source_and_plain_syntax_preflight_still_succeeds(self):
        source=SOURCE.replace('module.exports=', 'throw Error("MUST_NOT_EXECUTE");module.exports=')
        self.assertEqual(contracts(source)[1]['error'],'source_dynamic_key_contract_unsupported')
        settings=load_settings(project_root=PROJECT,environ={})
        browser=BrowserEvaluator(settings,profile(settings))
        self.assertEqual(browser.preflight(source)['status'],'completed')
        with self.assertRaises(SourceContractError) as error:browser.source_contracts(source)
        self.assertIn('源代码合法',error.exception.diagnostics[0]['message'])

    def test_frozen_product_source_identity_and_exact_contract_block(self):
        source=(FROZEN/'frozen/source.vue').read_bytes()
        self.assertEqual(sha256(source).hexdigest(),'aed0d49a2bab60b3103e50beb0236320d35f7fb9d8bd2341db36a65be65e817a')
        result=contracts(source.decode())[1]
        self.assertEqual(result['error'],'source_dynamic_key_contract_unsupported')
        self.assertIn('setValue',result['diagnostics'][0]['message'])

    def test_real_san_path_setter_is_not_arbitrary_literal_key_assignment(self):
        script="""const san=require('san');const C=san.defineComponent({initData(){return {query:''}}});
        const c=new C(),source={query:''};source['extra.key']=7;c.data.set('extra.key',7);
        source.query='ok';c.data.set('query','ok');const symbol=Symbol('example');source[symbol]=3;
        console.log(JSON.stringify({literal:source['extra.key'],nested:c.data.get('extra').key,
        targetLiteral:Object.prototype.hasOwnProperty.call(c.data.raw,'extra.key'),
        ordinary:source.query===c.data.get('query'),symbol:source[symbol]}));"""
        p=subprocess.run(['node','-e',script],cwd=PROJECT.parent,capture_output=True,timeout=15)
        self.assertEqual(p.returncode,0,p.stderr.decode())
        result=json.loads(p.stdout)
        self.assertEqual(result,{'literal':7,'nested':7,'targetLiteral':False,'ordinary':True,'symbol':3})


class PublicKeyGraphTests(ModularFixture,unittest.TestCase):
    def test_retained_unsupported_contract_blocks_before_model_preflight_and_ssm(self):
        self.source=self.base.create_input({'filename':'Generic.vue','source':SOURCE})
        settings=load_settings(project_root=PROJECT,environ={})
        self.service.browser=BrowserEvaluator(settings,profile(settings))
        def forbidden():raise AssertionError('Model preflight must not run')
        self.model.preflight=forbidden
        key=self.enqueue();result=self.run_graph(key)
        self.assertEqual(result['status'],'blocked')
        self.assertEqual(result['stop_reason'],'source_dynamic_key_contract_unsupported')
        self.assertEqual(result['model_calls_started'],0);self.assertEqual(self.model.calls,0)
        self.assertEqual(result['usage']['known_total_tokens'],0)
        self.assertIsNone(result['assessment']);self.assertIsNone(self.service.cached(key,'ssm.json'))
        finding=result['state']['failure_diagnostics'][0]
        self.assertEqual(finding['code'],result['stop_reason'])
        self.assertIn('this[key]',finding['excerpt'])
        failure=next(f for f in result['files'] if f['kind']=='failure')
        details=self.service.cached(key,failure['relative_path'].split(key+'/')[1])
        self.assertEqual(details['source_sha256'],sha256(SOURCE.encode()).hexdigest())
        self.assertNotIn('excerpt',json.dumps(details['trace']))


def control(value='a',checked=False,selected=None):
    return {'path':'root.0','tag':'input','value':value,'checked':checked,'selected_values':selected,'styles':{}}


class ControlStateTests(unittest.TestCase):
    def assessment(self,first,second):
        data=FakeBrowser().evaluate('','',{},[])
        data['vue']['snapshots'][0]['styles']=first
        data['san']['snapshots'][0]['styles']=second
        result=assess({'validation_passed':True,'validation_errors':[]},data,[],
                      {'structure':.95,'ui':.95,'pixel_difference':.05})
        return result,data

    def test_initial_value_mismatch_fails_even_with_identical_DOM_and_pixels(self):
        result,_=self.assessment([control('a')],[control('b')])
        self.assertFalse(result['passed']);self.assertEqual(result['dimensions']['structure'],'fail')
        self.assertIn('rendered_control_state_mismatch',[i['code'] for i in result['diagnostics']])
        self.assertEqual(result['ssim'],1)

    def test_checkbox_and_multi_select_differences_are_observed(self):
        self.assertFalse(compare_control_state([control(checked=False)],[control(checked=True)])['equal'])
        a={**control(selected=['a','b']),'tag':'select'}
        b={**a,'selected_values':['a']}
        self.assertFalse(compare_control_state([a],[b])['equal'])

    def test_equal_live_values_do_not_waive_value_or_class_attribute_presence(self):
        data=FakeBrowser().evaluate('','',{},[])
        for side in ('vue','san'):data[side]['snapshots'][0]['styles']=[control()]
        data['vue']['snapshots'][0]['dom']={'label':'input|value=a|class=','children':[]}
        data['san']['snapshots'][0]['dom']={'label':'input|','children':[]}
        original=deepcopy(data)
        result=assess({'validation_passed':True,'validation_errors':[]},data,[],
                      {'structure':.95,'ui':.95,'pixel_difference':.05})
        self.assertTrue(result['initial_control_state']['equal'])
        self.assertEqual(result['dimensions']['structure'],'fail');self.assertEqual(data,original)
        self.assertTrue(next(d for d in result['diagnostics'] if d['code']=='rendered_dom_mismatch')['live_control_state']['equal'])

    def test_empty_state_remains_compatible_and_wrong_control_after_action_is_rejected(self):
        self.assertTrue(self.assessment([],[])[0]['passed'])
        action={'name':'type','type':'input','selector':'input','value':'new'}
        data=FakeBrowser().evaluate('','',{},[action])
        data['vue']['snapshots'][1]['styles']=[control('new')]
        data['san']['snapshots'][1]['styles']=[control('old')]
        result=assess({'validation_passed':True,'validation_errors':[]},data,[action],
                      {'structure':.95,'ui':.95,'pixel_difference':.05})
        self.assertEqual(result['dimensions']['interaction'],'fail')
        self.assertTrue(result['interaction'][0]['control_state_differences'])


if __name__=='__main__':unittest.main()
