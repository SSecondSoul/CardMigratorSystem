"""Dynamic assignment proof gate; no claim to repair arbitrary instance APIs."""
import json
import subprocess
import tempfile
import unittest
from functools import lru_cache
from pathlib import Path

from migration_pipeline.utils.bounded_semantics import inspect_semantics
from migration_pipeline.utils.repair_scheduler import candidate_gate
from migration_pipeline.utils.repair_prompt import RepairPromptInput,build_repair_prompt
from migration_pipeline.stages.validate import ValidateStage,ValidateStageInput
from migration_pipeline.stages.repair import RepairStage,RepairStageInput
from migration_pipeline.repair_client import RepairResult

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data/experiments/analysis/formal_30_v4_dynamic_setter_guard_v1_input_20261115'
ISSUE='source_dynamic_assignment_unproven'


def fixture():
    b=json.loads((BASE/'baseline.json').read_text(encoding='utf-8'))
    return tuple((ROOT/b[k]['path']).read_text(encoding='utf-8') for k in ['candidate','source'])


@lru_cache(maxsize=1)
def variants():
    js=r'''const fs=require('fs'),p=require('./migration_pipeline/probe_source_dynamic_setter_v1.cjs');process.stdout.write(JSON.stringify(p.variants(JSON.parse(fs.readFileSync(0,'utf8')))));'''
    p=subprocess.run(['node','-e',js],cwd=ROOT,input=json.dumps(fixture()[0]),capture_output=True,text=True,encoding='utf-8',check=True,timeout=20)
    return json.loads(p.stdout)


@lru_cache(maxsize=1)
def native():
    c,v=fixture();p=subprocess.run(['node','migration_pipeline/probe_source_dynamic_setter_v1.cjs'],cwd=ROOT,
        input=json.dumps({'code':c,'vue':v,'runtime':str(ROOT/'data/experiments/manual_followups/task_manager_async_scope_v7_prepared_20261113/vendor/vue-2.7.16.js')}),
        capture_output=True,text=True,encoding='utf-8',check=True,timeout=40)
    return json.loads(p.stdout)


class SourceDynamicAssignmentGuardTests(unittest.TestCase):
    def inspect(self,c,v=None):
        r=inspect_semantics(c,fixture()[1] if v is None else v);self.assertNotIn('error',r,r);return r

    def state(self,c):return {'generated_code':c,'vue_source':fixture()[1],'ssm':{},'validation_errors':self.inspect(c)['findings']}

    def test_current_missing_interface_remains_blocked_not_auto_restored(self):
        c,v=fixture();r=self.inspect(c);s=next(x for x in r['method_contracts'] if x['name']=='setValue')
        self.assertEqual(s['dynamic_assignment']['target_status'],'missing');self.assertFalse(s['dynamic_assignment']['automatic_restore'])
        self.assertTrue(any(x['code']=='source_method_interface_not_landed' for x in r['findings']))
        self.assertFalse(any(x['code']==ISSUE for x in r['findings']))
        self.assertEqual(inspect_semantics(c,v,repair=True)['code'],c)

    def test_all_five_merely_callable_proposals_get_unproven_finding(self):
        for name,c in variants().items():
            if name=='missing':continue
            with self.subTest(variant=name):
                r=self.inspect(c);self.assertTrue(any(x['code']==ISSUE and x['location']=='script.methods.setValue' for x in r['findings']))
                self.assertEqual(inspect_semantics(c,fixture()[1],repair=True)['code'],c)

    def test_rejects_reported_bad_callable_and_forged_cleared_diagnostics(self):
        before=self.state(fixture()[0]);self.assertFalse(candidate_gate(before,before)['should_stop'])
        for name,c in variants().items():
            after=self.state(c)
            if name!='missing':self.assertTrue(candidate_gate(before,after)['should_stop'])
            gate=candidate_gate(before,{**after,'validation_errors':[],'validation_passed':True})
            self.assertTrue(gate['should_stop']);self.assertEqual(len(gate['waived_source_dynamic_assignment_findings']),1)

    def test_unknown_target_scope_cannot_erase_source_contract(self):
        c,v=fixture();bad=c.replace('module.exports = san.defineComponent({','module.exports = san.defineComponent({...unknown,')
        gate=candidate_gate(self.state(c),{**self.state(bad),'validation_errors':[]})
        self.assertTrue(gate['should_stop']);self.assertEqual(gate['lost_source_dynamic_assignment_contracts'],['setValue'])

    def test_helper_and_parameter_names_not_allowlisted(self):
        c,v=fixture();v=v.replace('setValue','putRoot')
        v=v.replace('putRoot(key, value) { this[key] = value; }','putRoot(field, payload) { this[field] = payload; }')
        c=c.replace('module.exports = san.defineComponent({','module.exports = san.defineComponent({putRoot(field,payload){this.data.set(field,payload);},')
        r=self.inspect(c,v);contract=next(x for x in r['method_contracts'] if x['name']=='putRoot')
        self.assertEqual(contract['dynamic_assignment']['key_parameter'],'field');self.assertTrue(any(x['code']==ISSUE for x in r['findings']))

    def test_function_expression_and_constant_source_function_reference_supported(self):
        c,v=fixture();wrong=variants()['path']
        for changed in [v.replace('setValue(key, value) { this[key] = value; }','setValue:function(key,value){this[key]=value;}'),
                        v.replace('module.exports = {','function put(key,value){this[key]=value;}\nmodule.exports = {').replace('setValue(key, value) { this[key] = value; }','setValue:put')]:
            self.assertNotEqual(changed,v);self.assertTrue(any(x['code']==ISSUE for x in self.inspect(wrong,changed)['findings']))

    def test_extra_source_effect_or_arrow_this_not_misclassified(self):
        c,v=fixture()
        for changed in [v.replace('this[key] = value;','this[key] = value; this.extra();'),
                        v.replace('setValue(key, value) { this[key] = value; }','setValue:(key,value)=>{this[key]=value;}')]:
            r=self.inspect(variants()['path'],changed)
            self.assertFalse(any(x.get('dynamic_assignment') for x in r['method_contracts']));self.assertFalse(any(x['code']==ISSUE for x in r['findings']))
        self.assertFalse(self.inspect(c,'').get('method_contracts'))

    def test_static_check_never_executes_generated_method(self):
        wrong=variants()['instance'].replace('setValue(key,value){this[key]=value;}','setValue(key,value){throw new Error(\'must not run\');}')
        self.assertTrue(any(x['code']==ISSUE for x in self.inspect(wrong)['findings']))

    def test_native_declared_root_subset_does_not_prove_arbitrary_key_api(self):
        r=native();self.assertEqual(len(r['cases']),15);self.assertEqual(len(r['variants']),6)
        for name in ['finite_fallback','coerced_finite_fallback']:
            for field in ['items','activeDayId','draft','budgetLimit','saved','nextId']:
                self.assertTrue(r['variants'][name]['root:'+field]['mappedProjectionEqual'])
            self.assertFalse(r['variants'][name]['runtime-data-collision']['mappedProjectionEqual'])
            self.assertFalse(r['variants'][name]['runtime-data-collision']['target']['frameworkStorePointerIntact'])
        self.assertFalse(r['production_adapter_installed'])

    def test_native_dotted_extra_symbol_and_key_coercion_counterexamples(self):
        r=native()['variants']
        self.assertFalse(r['instance']['root:saved']['mappedProjectionEqual'])
        for case in ['dotted-literal','late-instance','symbol-literal']:
            self.assertTrue(r['instance'][case]['mappedProjectionEqual']);self.assertFalse(r['path'][case]['mappedProjectionEqual'])
        self.assertFalse(r['finite_fallback']['coerced-root']['mappedProjectionEqual'])
        self.assertTrue(r['coerced_finite_fallback']['coerced-root']['mappedProjectionEqual'])
        self.assertEqual(r['coerced_finite_fallback']['coerced-root']['target']['coercions'],['string'])
        self.assertEqual(r['path']['dotted-literal']['source']['state']['draft']['start'],'09:00')
        self.assertEqual(r['path']['dotted-literal']['target']['state']['draft']['start'],'literal')

    def test_prompt_preserves_unproven_scope_and_no_compatibility_feature(self):
        p=build_repair_prompt(RepairPromptInput(ssm={},current_code='',validation_errors=[{'code':ISSUE}]))
        for term in ['callable presence','literal dotted keys','ToPropertyKey','finite-key guard','collisions','new caller protocol']:self.assertIn(term,p)

    def test_real_validator_prepass_and_stub_return_do_not_claim_repair(self):
        c,v=fixture();b=json.loads((BASE/'baseline.json').read_text(encoding='utf-8'))
        state=json.loads((ROOT/'data/experiments/snapshots/formal_30_v4_full_regression_v2_results_20261104_214821/repair_reports/complex/TripItineraryPlanner_repair_history.json').read_text(encoding='utf-8'))['state']
        wrong=variants()['path']
        r=ValidateStage().run(ValidateStageInput(generated_code=wrong,ssm=state['ssm'],vue_file_path=str(ROOT/b['source']['path'])))
        self.assertEqual({e['code'] for e in r.validation_errors},{'nested_state_mutation',ISSUE});self.assertFalse(r.validation_passed)
        class Client:
            def repair(self,request):return RepairResult(code=wrong,saved_file_path=request.output_file_path,source_file='',ssm={},provider='stub',model='stub',raw_response={})
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'source.vue';path.write_text(v,encoding='utf-8')
            unchanged,steps=RepairStage._deterministic_repair_plan(wrong,[{'code':ISSUE}],[],{},str(path));self.assertEqual(unchanged,wrong);self.assertEqual(steps,[])
            out=RepairStage(Client()).run(RepairStageInput(ssm={},generated_code=c,vue_file_path=str(path),output_file_path=str(Path(tmp)/'out.san'),metadata={'skip_deterministic_prepass':True}))
            self.assertEqual(out.repaired_code.rstrip(),wrong.rstrip());self.assertTrue(candidate_gate(self.state(c),self.state(out.repaired_code))['should_stop'])


if __name__=='__main__':unittest.main()
