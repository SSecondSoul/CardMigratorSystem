"""Recovery proposal ordering through the real persistent service/graph gate."""
import unittest
from types import SimpleNamespace
from test_modular_system import PROJECT,ModularFixture
import test_remaining_repairs_v7 as v7
from card_migration_system.stages.normalization import normalize_proposal
from card_migration_system.adapters.browser import BrowserEvaluator
from card_migration_system.adapters.legacy_checks import legacy_stage
from card_migration_system.adapters.ssm import SSMExtractor
from card_migration_system.config import load_settings
from card_migration_system.runtime import profile


class RecoveryOrderingTests(unittest.TestCase):
    def test_minimal_recovery_is_not_mixed_with_unrelated_template_changes(self):
        actions=[]
        def checks(_,action,**kw):
            actions.append(action)
            if action=='prop_defaults':return {'code':'default_only','changes':['restored_source_parent_prop_defaults']}
            self.fail('broad rules must wait for recovery retest')
        class Browser:
            def syntax(*a,**kw):raise AssertionError('unrelated syntax normalization ran')
        result=normalize_proposal(SimpleNamespace(repository_root='unused'),checks,Browser(),'source','old',{},
            {'dimensions':{'compile_runtime':'fail'},'syntax':{'status':'pass'},'diagnostics':[{'code':'missing_prop_defaults'}]})
        self.assertEqual(result['code'],'default_only');self.assertEqual(actions,['prop_defaults'])
        self.assertEqual(result['stop'],'source_defaults_runtime_recovery_first')

    def test_model_output_and_rejected_recovery_can_use_full_normalization(self):
        def checks(_,action,**kw):
            self.assertNotEqual(action,'prop_defaults')
            return {'validation_errors':[]} if action=='validate' else {'code':'full','changes':[]}
        result=normalize_proposal(SimpleNamespace(repository_root='unused'),checks,object(),'source','old',{},
            {'dimensions':{'compile_runtime':'fail'},'diagnostics':[{'code':'missing_prop_defaults'}]},prefer_runtime_recovery=False)
        self.assertEqual(result['code'],'full')


class RecoveryGraphTests(ModularFixture,unittest.TestCase):
    def test_real_browser_and_existing_rule_reach_candidate_gate_without_second_model_call(self):
        source='''<template><main><input value="a"/><b>{{rows.length}}</b></main></template><script>export default {props:{items:{type:Array,default:()=>[1,2]}},data(){return {rows:[]}},created(){this.rows=this.items.slice()}}</script>'''
        code='''<template><main><div><input value="a"/><b>{{rows.length}}</b></div></main></template><script>const san=require('san');const DataTypes=san.DataTypes;module.exports=san.defineComponent({dataTypes:{items:DataTypes.array},initData(){return {rows:[]}},inited(){this.data.set('rows',this.data.get('items').slice())}})</script>'''
        self.source=self.base.create_input({'filename':'RuntimeRecovery.vue','source':source})
        self.model.codes=[code+'<style></style>']
        self.service.checks=lambda _,action,**value:legacy_stage(PROJECT/'engine',action,**value)
        self.service.extractor=SSMExtractor(PROJECT/'engine')
        settings=load_settings(project_root=PROJECT,environ={})
        self.service.browser=BrowserEvaluator(settings,profile(settings))
        key=self.enqueue(max_repair_rounds=1);report=self.run_graph(key)
        self.assertEqual(self.model.calls,1) # Explicit injected generation double only.
        self.assertEqual(report['actual_cloud_model_calls'],0)
        self.assertIn('decisions',report['state'],report.get('stop_reason'))
        self.assertTrue(report['state']['decisions'][0]['accepted'],report['state']['decisions'])
        self.assertEqual(report['assessment']['dimensions']['compile_runtime'],'pass')
        self.assertEqual(report['assessment']['dimensions']['structure'],'fail')
        self.assertEqual(self.service.cached(key,'normalizations/1.json')['stop'],'source_defaults_runtime_recovery_first')
        self.assertEqual(report['status'],'failed') # Never relabel the remaining wrapper defect.


if __name__=='__main__':unittest.main()
