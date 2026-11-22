"""Pure source initialization recovery must reach the real unchanged gate."""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from test_initialization_phase_v8 import SOURCE,TARGET
from test_modular_system import PROJECT,ModularFixture
from card_migration_system.adapters.browser import BrowserEvaluator
from card_migration_system.adapters.legacy_checks import legacy_stage
from card_migration_system.adapters.ssm import SSMExtractor
from card_migration_system.config import load_settings
from card_migration_system.runtime import profile
from card_migration_system.stages.normalization import normalize_proposal
from card_migration_system.stages.evaluation import assess,candidate_decision
from card_migration_system.stages.dom_comparison import proven_initialization_runtime_recovery

SRC=SOURCE.replace('<main>','<main><input value="a"/>')+'<style></style>'
TGT=TARGET.replace('<main>','<main><div><input value="a"/>').replace('</main>','</div></main>')+'<style></style>'
THRESHOLDS={'structure':.95,'ui':.95,'pixel_difference':.05}


class InitializationOrderingTests(unittest.TestCase):
    def test_minimal_initialization_runs_before_any_class_or_template_normalizer(self):
        calls=[]
        def checks(_,action,**kw):
            calls.append(action)
            if action!='data_initialization':self.fail(action)
            return {'code':'pure-init','changes':['restored_source_pure_prop_data_initialization_phase']}
        class Browser:
            def syntax(*a,**kw):raise AssertionError('unrelated normalization must wait')
        result=normalize_proposal(SimpleNamespace(repository_root='unused'),checks,Browser(),'source','old',{},
            {'dimensions':{'compile_runtime':'fail'},'syntax':{'status':'pass'},
             'diagnostics':[{'code':'source_data_initialization_phase_not_landed'}]})
        self.assertEqual(calls,['data_initialization'])
        self.assertEqual(result['stop'],'source_data_initialization_runtime_recovery_first')
        self.assertEqual(result['code'],'pure-init')


class InitializationGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings=load_settings(project_root=PROJECT,environ={})
        cls.browser=BrowserEvaluator(cls.settings,profile(cls.settings))
        cls.rule=legacy_stage(PROJECT/'engine','data_initialization',source=SRC,code=TGT,ssm={})
        cls.repaired=cls.rule['code']
        cls.reports=[]
        for code in (TGT,cls.repaired):
            raw=cls.browser.evaluate(SRC,code,{},[])
            static=legacy_stage(PROJECT/'engine','validate',source=SRC,code=code,ssm={})
            cls.reports.append(assess(static,raw,[],THRESHOLDS))

    def test_actual_runtime_recovers_but_wrapper_and_structure_failure_remain(self):
        before,after=self.reports
        self.assertEqual(before['dimensions']['compile_runtime'],'fail')
        self.assertEqual(after['dimensions']['compile_runtime'],'pass')
        self.assertTrue(proven_initialization_runtime_recovery(before,after))
        decision=candidate_decision(before,after)
        self.assertTrue(decision['accepted'],decision)
        self.assertIn('source_pure_initialization_runtime_recovery_revealed_position_defect',decision['diagnostic_refinements'])
        self.assertFalse(after['passed']);self.assertEqual(after['dimensions']['structure'],'fail')
        self.assertIn('rendered_control_position_mismatch',[d['code'] for d in after['diagnostics']])

    def test_incomplete_old_changed_or_extra_edit_witness_is_not_recovery(self):
        for field,value in [('complete',False),('input_sha256','changed'),('runtime_sha256','changed'),
                            ('normalized_sha256','changed'),('code_sha256','changed'),('contract','unknown')]:
            before,after=deepcopy(self.reports)
            after['initialization_recovery_binding'][field]=value
            self.assertFalse(proven_initialization_runtime_recovery(before,after),field)
            self.assertFalse(candidate_decision(before,after)['accepted'],field)
        before,after=deepcopy(self.reports);after.pop('initialization_recovery_binding')
        self.assertFalse(candidate_decision(before,after)['accepted'])

    def test_new_semantic_error_or_previous_pass_loss_is_still_rejected(self):
        for change in ('new_error','dimension','no_dom_progress','wrong_controls'):
            before,after=deepcopy(self.reports)
            if change=='new_error':after['diagnostics'].append({'code':'new_business_defect'})
            elif change=='dimension':after['dimensions']['source_baseline']='fail'
            elif change=='no_dom_progress':after['dom_ted']=before['dom_ted']
            else:after['initial_control_state']['values_equal_in_order']=False
            self.assertFalse(candidate_decision(before,after)['accepted'],change)

    def test_real_extra_css_edit_cannot_share_the_exact_source_init_witness(self):
        changed=self.repaired.replace('<style>','<style>input{background:black}')
        raw=self.browser.evaluate(SRC,changed,{},[])
        static=legacy_stage(PROJECT/'engine','validate',source=SRC,code=changed,ssm={})
        after=assess(static,raw,[],THRESHOLDS)
        self.assertFalse(proven_initialization_runtime_recovery(self.reports[0],after))
        self.assertFalse(candidate_decision(self.reports[0],after)['accepted'])


class InitializationGraphTests(ModularFixture,unittest.TestCase):
    def test_persistent_graph_accepts_only_minimal_initializer_without_another_model_call(self):
        self.source=self.base.create_input({'filename':'PureInitialization.vue','source':SRC})
        self.model.codes=[TGT]
        self.service.checks=lambda _,action,**value:legacy_stage(PROJECT/'engine',action,**value)
        self.service.extractor=SSMExtractor(PROJECT/'engine')
        settings=load_settings(project_root=PROJECT,environ={})
        self.service.browser=BrowserEvaluator(settings,profile(settings))
        key=self.enqueue(max_repair_rounds=1);report=self.run_graph(key)
        self.assertEqual(self.model.calls,1) # Explicit injected generation double.
        self.assertEqual(report['actual_cloud_model_calls'],0)
        self.assertTrue(report['state']['decisions'][0]['accepted'],report['state']['decisions'])
        self.assertEqual(report['assessment']['dimensions']['compile_runtime'],'pass')
        self.assertEqual(report['assessment']['dimensions']['structure'],'fail')
        self.assertEqual(self.service.cached(key,'normalizations/1.json')['stop'],
                         'source_data_initialization_runtime_recovery_first')
        self.assertEqual(report['status'],'failed')


if __name__=='__main__':unittest.main()
