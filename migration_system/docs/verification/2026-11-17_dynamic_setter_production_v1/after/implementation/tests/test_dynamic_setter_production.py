"""Actual complex source and native San, not a six-key setter waiver."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import unittest

PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT/'src'))
from card_migration_system.adapters.browser import BrowserEvaluator
from card_migration_system.config import load_settings
from card_migration_system.runtime import profile,browser_executable
from card_migration_system.stages.evaluation import assess
from dataclasses import replace
from test_modular_system import ModularFixture
from card_migration_system.adapters.ssm import SSMExtractor

MODE='dynamic-setter-single-component-v1'
SOURCE=(PROJECT/'tests/fixtures/CapacityPlanningBoard.vue').read_bytes().decode('utf-8')
ACTIONS=json.loads((PROJECT/'configs/diagnostics/capacity-planning-actions.json').read_bytes())

def cli(payload):
    process=subprocess.run(['node',str(PROJECT/'runtime/san_business_v1/cli.cjs')],
        input=json.dumps(payload).encode(),capture_output=True,cwd=PROJECT,timeout=40)
    return json.loads(process.stdout)


class ProductionCompilerTests(unittest.TestCase):
    def test_complex_source_compiles_without_rewriting_setter_and_is_independently_bound(self):
        result=cli({'action':'compile','source':SOURCE,'code':SOURCE,'mode':MODE})
        self.assertEqual(result['status'],'completed',result)
        self.assertEqual(result['manifest']['source_sha256'],sha256(SOURCE.encode()).hexdigest())
        self.assertIn('setValue(key, value) { this[key] = value; }',result['code'])
        self.assertEqual(result['manifest']['production_profile'],MODE)
        self.assertEqual(cli({'action':'verify','source':SOURCE,'code':result['code'],'manifest':result['manifest']})['status'],'completed')
        self.assertEqual(cli({'action':'verify','source':SOURCE,'code':result['code'].replace('this[key] = value','this[key] = 0'),'manifest':result['manifest']})['status'],'fail')

    def test_actual_production_export_preserves_external_literal_symbol_collision_and_coercion_keys(self):
        result=cli({'action':'compile','source':SOURCE,'code':SOURCE,'mode':MODE})
        process=subprocess.run(['node',str(PROJECT/'tests/probe_dynamic_setter.cjs')],input=json.dumps({
            'source':SOURCE,'code':result['code'],'actions':[],
            'executable':browser_executable({})}).encode(),capture_output=True,timeout=60)
        self.assertEqual(process.returncode,0,process.stderr.decode(errors='replace'))
        observations=json.loads(process.stdout)
        self.assertEqual(observations[0]['publicKeys'],observations[1]['publicKeys'])
        self.assertTrue(all(observations[1]['publicKeys'].values()),observations)

    def test_complex_initial_and_nine_actions_use_real_browser(self):
        result=cli({'action':'compile','source':SOURCE,'code':SOURCE,'mode':MODE})
        self.assertEqual(result['status'],'completed',result)
        settings=load_settings(project_root=PROJECT,environ={})
        raw=BrowserEvaluator(settings,profile(settings)).evaluate(SOURCE,result['code'],{},ACTIONS)
        self.assertFalse(raw['vue']['errors'],raw['vue']['errors'])
        self.assertFalse(raw['san']['errors'],raw['san']['errors'])
        self.assertFalse(raw['san']['warnings'],raw['san']['warnings'])
        # Compare actual DOM attributes too; don't substitute the source tree
        # for the target AST and don't waive implicit option/class differences.
        from card_migration_system.stages.dom_comparison import compare_dom,compare_control_state
        from card_migration_system.stages.structure import compare_styles
        differences=[]
        for first,second in zip(raw['vue']['snapshots'],raw['san']['snapshots']):
            dom=compare_dom(first['dom'],second['dom'],raw.get('comparison_policy'))
            if dom['differences']:differences.append({'action':first['name'],'differences':dom['differences']})
        if differences:
            process=subprocess.run(['node',str(PROJECT/'tests/probe_dynamic_setter.cjs')],
                input=json.dumps({'source':SOURCE,'code':result['code'],'actions':ACTIONS,
                    'executable':browser_executable(profile(settings)['browser'])}).encode(),capture_output=True,timeout=60)
            self.fail(json.dumps({'differences':differences,'states':json.loads(process.stdout)},ensure_ascii=True))
        assessment=assess({'validation_passed':True,'validation_errors':[]},raw,ACTIONS,
            {'structure':.95,'ui':.95,'pixel_difference':.05})
        self.assertEqual(assessment['dimensions']['compile_runtime'],'pass',assessment['diagnostics'])
        self.assertEqual(assessment['dimensions']['interaction'],'pass',assessment['diagnostics'])
        self.assertEqual(assessment['dimensions']['visual'],'pass',assessment['diagnostics'])


class ProductionGraphTests(ModularFixture,unittest.TestCase):
    def setUp(self):
        super().setUp()
        # Real installed compiler/browser/engine; business DB, graph DB and all
        # uploaded source/artifacts remain exclusively in the temporary fixture.
        self.service.settings=replace(self.settings,project_root=PROJECT,repository_root=PROJECT/'engine')
        self.service.browser=BrowserEvaluator(self.service.settings,profile(self.service.settings))
        self.service.extractor=SSMExtractor(PROJECT/'engine')

    def test_real_complex_graph_finishes_nine_actions_without_model_or_source_changes(self):
        self.source=self.base.create_input({'filename':'CapacityPlanningBoard.vue','source':SOURCE})
        def forbidden(*args):raise AssertionError('Rule route must not preflight or call a model')
        self.model.preflight=forbidden;self.model.exchange=forbidden
        key=self.enqueue(confirm_model_calls=True,actions=ACTIONS)
        report=self.run_graph(key)
        self.assertEqual(report['status'],'finished',{'reason':report['stop_reason'],'assessment':report['assessment']})
        self.assertEqual(report['generation_origin'],'source_ast_rule_generation')
        self.assertEqual(report['model_calls_started'],0);self.assertEqual(report['usage']['known_total_tokens'],0)
        self.assertTrue(all(value=='pass' for value in report['assessment']['dimensions'].values()))
        self.assertEqual(len(report['assessment']['interaction']),9)
        self.assertEqual(self.service.source(key),SOURCE)
        self.assertIsNotNone(self.service.cached(key,'revisions/0.business.json'))
        original=self.service.cached(key,'revisions/0.json')
        tampered={**original,'code':original['code'].replace('this[key] = value','this[key] = 0')}
        from card_migration_system.stages.business import validate
        validation=validate(self.service,key,tampered,self.service.extract(key)['ssm'])
        self.assertFalse(validation['validation_passed'])
        from card_migration_system.stages.evaluation import candidate_decision
        failed={**report['assessment'],'dimensions':{**report['assessment']['dimensions'],'static':'fail'},
            'diagnostics':validation['validation_errors'],'passed':False}
        self.assertFalse(candidate_decision(report['assessment'],failed)['accepted'])

    def test_unimplemented_private_dependency_keeps_zero_call_block(self):
        source=SOURCE.replace('return this.selectedWorkId === id','return this.$.vnode')
        self.source=self.base.create_input({'filename':'Unsupported.vue','source':source})
        key=self.enqueue(confirm_model_calls=True)
        report=self.run_graph(key)
        self.assertEqual(report['status'],'blocked')
        self.assertEqual(report['model_calls_started'],0)
        self.assertIn('source_private_runtime_dependency_unsupported',report['state']['failure_diagnostics'][0]['message'])


if __name__=='__main__':unittest.main()
