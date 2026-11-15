"""Explicit reporting-only error contract; default/throwing routes remain negative evidence."""
import json
from pathlib import Path
import unittest

from test_parent_dynamic_key_adapter_probe import node
from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
from migration_pipeline.utils.repair_scheduler import PARENT_WATCH_REVIEW_CODES,candidate_gate

ROOT=Path(__file__).resolve().parents[1]
PRIOR=ROOT/'data/experiments/analysis/formal_30_v4_parent_alias_observer_v4_20261112'
OLD_ALIAS=ROOT/'data/experiments/analysis/formal_30_v4_parent_alias_child_audit_v1_20261112'
BOUNDARY=ROOT/'data/experiments/analysis/formal_30_v4_parent_watch_boundaries_v1_final_20261111'
ADAPTER=ROOT/'migration_pipeline/probe_parent_watch_error_router_v5.cjs'
RUNTIME=ROOT/'migration_pipeline/audit_parent_watch_error_router_v5_runtime.cjs'
POLICY='explicit-returning-application-reporter'


def adapt(code,vue,**kw):
    return node(ADAPTER,{'code':code,'vue':vue,'experimental':True,'error_policy':POLICY,**kw})


def payloads():
    old=json.loads((PRIOR/'audit.json').read_text(encoding='utf-8'))
    paths=old['source_inputs']
    base={k:(ROOT/next(p for p in paths if p.endswith(end))).read_text(encoding='utf-8')
          for k,end in [('code','.san'),('vue','.vue')]}
    common={k:(ROOT/next(p for p in paths if p.endswith(end))).read_bytes().decode('utf-8')
            for k,end in [('vueRuntime','vue.runtime.common.dev.js'),('sanRuntime','san.dev.js')]}
    candidate=adapt(**base)
    return old,base,common,candidate


STRUCTURE=r"""
const fs=require('fs'),parser=require('@babel/parser');const i=JSON.parse(fs.readFileSync(0,'utf8'));
const {parentOf}=require('./migration_pipeline/utils/inline_identifier_recovery.cjs');
const {same}=require('./migration_pipeline/utils/source_render_call_semantics.cjs');
const parse=s=>parser.parse(/<script\b[^>]*>([\s\S]*?)<\/script>/.exec(s)[1],{sourceType:'unambiguous'});
const before=parse(i.before),after=parse(i.after),parent=parentOf(after);let configure=0,catches=0;
parent.properties=parent.properties.filter(p=>{if(p.key.name==='__parentWatchError_v5Configure'){configure++;return false;}return true;});
function visit(n){if(!n||typeof n!=='object')return;
 for(const [key,value] of Object.entries(n)){if(['loc','start','end','extra'].includes(key))continue;
  if(Array.isArray(value))for(let j=0;j<value.length;j++){
   const v=value[j];if(v?.type==='TryStatement'&&v.handler?.param.name==='__parentWatchError_v5Error'){
    value[j]=v.block.body[0];catches++;
   }else visit(v);
  }else visit(value);
 }
}visit(after);
process.stdout.write(JSON.stringify({configure,catches,rest_of_script_unchanged:same(before,after)}));
"""


class ParentWatchErrorRouterV5Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old,cls.base,cls.common,cls.candidate=payloads()
        cls.payload={'vue':cls.base['vue'],'san_v4':cls.old['candidate']['code'],
                     'san_v5':cls.candidate['code'],**cls.common}
        cls.observed=node(RUNTIME,cls.payload)

    def run_of(self,scenario,variant='san_v5'):
        return next(r for r in self.observed['runs'] if r['scenario']==scenario and r['variant']==variant)

    def phase(self,scenario,name,variant='san_v5'):
        return next(p for p in self.run_of(scenario,variant)['phases'] if p['name']==name)

    def reports(self,scenario,name='primary_tick'):
        return [e for e in self.phase(scenario,name)['events'] if e['kind']=='application-error-report']

    def test_requires_explicit_policy_and_experimental_opt_in(self):
        for extra in [{'error_policy':None},{'error_policy':'browser-default'},{'experimental':False}]:
            r=adapt(**self.base,**extra)
            self.assertFalse(r['changes']);self.assertEqual(r['code'],self.base['code'])
        self.assertTrue(self.candidate['changes']);self.assertFalse(self.candidate['production_eligible'])

    def test_existing_marker_refuses_duplicate_application_without_changes(self):
        r=adapt(self.candidate['code'],self.base['vue'])
        self.assertFalse(r['changes']);self.assertEqual(r['code'],self.candidate['code'])

    def test_only_per_callback_catch_and_reporter_configuration_added(self):
        r=node(STRUCTURE,{'before':self.old['candidate']['code'],'after':self.candidate['code']})
        self.assertEqual(r,{'configure':1,'catches':1,'rest_of_script_unchanged':True})

    def test_native_runtime_dimensions_and_no_host_listener_leak(self):
        self.assertEqual(len(self.observed['runs']),27)
        self.assertEqual(sum(len(r['phases']) for r in self.observed['runs']),270)
        self.assertEqual(len(self.observed['pairs']),180)
        self.assertTrue(self.observed['rejectionListenerRestored'])
        self.assertEqual(self.observed['modelRequests'],0)

    def test_all_60_positive_contract_pairs_match_state_business_and_error_reports(self):
        rows=[p for p in self.observed['pairs'] if p['positiveContract'] and p['variant']=='san_v5']
        self.assertEqual(len(rows),60)
        self.assertTrue(all(p['stateEqual'] and p['businessAndApplicationErrorEventsEqual'] and p['warningsEqual'] for p in rows))

    def test_old_control_still_exposes_error_contract_mismatch(self):
        rows=[p for p in self.observed['pairs'] if p['positiveContract'] and p['variant']=='san_v4']
        self.assertTrue(any(not p['businessAndApplicationErrorEventsEqual'] for p in rows))

    def test_tasks_failure_reports_original_error_and_later_settings_watcher_runs(self):
        reports=self.reports('tasks_failure_once')
        self.assertEqual(len(reports),1);self.assertEqual(reports[0]['info'],'callback for watcher "tasks"')
        self.assertTrue(reports[0]['originalError'] and reports[0]['subjectIsInstance'] and reports[0]['thisIsNull'])
        self.assertEqual(self.phase('tasks_failure_once','primary_tick')['state']['activeIntervals'],[30000])

    def test_settings_failure_does_not_resume_tail_of_failed_callback(self):
        self.assertEqual(self.phase('settings_failure_once','primary_tick')['state']['activeIntervals'],[])
        self.assertEqual(self.phase('settings_failure_once','repeat_tick')['state']['activeIntervals'],[60000])
        self.assertEqual([r['info'] for r in self.reports('settings_failure_once')],['callback for watcher "settings"'])

    def test_two_callbacks_fail_independently_and_are_each_reported_once(self):
        reports=self.reports('two_watcher_failures')
        self.assertEqual([r['info'] for r in reports],['callback for watcher "tasks"','callback for watcher "settings"'])
        self.assertTrue(all(r['originalError'] for r in reports))
        self.assertEqual(self.phase('two_watcher_failures','primary_tick')['state']['activeIntervals'],[])

    def test_later_failure_keeps_prior_interval_until_source_recovery(self):
        self.assertEqual(self.phase('repeat_settings_failure','repeat_tick')['state']['activeIntervals'],[30000])
        self.assertEqual(self.phase('repeat_settings_failure','recovery_tick')['state']['activeIntervals'],[])

    def test_false_reporter_return_is_not_misinterpreted_as_queue_abort(self):
        self.assertEqual(self.phase('reporter_returns_false','primary_tick')['state']['activeIntervals'],[30000])
        self.assertEqual(len(self.reports('reporter_returns_false')),1)

    def test_success_does_not_invoke_reporter(self):
        self.assertFalse(self.run_of('normal')['rawErrors'])
        self.assertTrue(all(not any(e['kind']=='application-error-report' for e in p['events']) for p in self.run_of('normal')['phases']))

    def test_no_unhandled_rejection_in_returning_reporter_positive_contract(self):
        for r in self.observed['runs']:
            if r['positiveContract'] and r['variant']=='san_v5':
                self.assertTrue(all(e['channel']=='san.instance.explicitReporter' for e in r['rawErrors']))
                self.assertEqual(r['warnings'],[])

    def test_raw_framework_channels_preserved_not_falsely_identified_as_equal(self):
        self.assertFalse(self.observed['rawErrorRoutesComparedAsIdentical'])
        a=self.run_of('tasks_failure_once','vue_source')['rawErrors']
        b=self.run_of('tasks_failure_once')['rawErrors']
        self.assertEqual(a[0]['channel'],'vue.config.errorHandler')
        self.assertEqual(b[0]['channel'],'san.instance.explicitReporter')

    def test_missing_reporter_preserves_v4_failure_without_silent_console_fallback(self):
        for scenario in ['headless_default_not_closed','missing_target_reporter_not_closed']:
            a=self.run_of(scenario,'san_v4');b=self.run_of(scenario)
            self.assertEqual(a['phases'],b['phases']);self.assertEqual(a['rawErrors'],b['rawErrors'])
            self.assertTrue(any(e['channel']=='process.unhandledRejection' for e in b['rawErrors']))

    def test_throwing_reporter_not_swallowed_or_claimed_equivalent(self):
        r=self.run_of('throwing_reporter_not_closed')
        self.assertTrue(any(e['channel']=='process.unhandledRejection' and e['message']=='ApplicationReporterFailure' for e in r['rawErrors']))
        rows=[p for p in self.observed['pairs'] if p['variant']=='san_v5' and p['scenario']=='throwing_reporter_not_closed']
        self.assertTrue(any(not p['businessAndApplicationErrorEventsEqual'] or not p['warningsEqual'] for p in rows))

    def test_all_three_out_of_contract_groups_remain_negative(self):
        for name in ['headless_default_not_closed','missing_target_reporter_not_closed','throwing_reporter_not_closed']:
            rows=[p for p in self.observed['pairs'] if p['variant']=='san_v5' and p['scenario']==name]
            self.assertEqual(len(rows),10)
            self.assertTrue(any(not all(p[k] for k in ['stateEqual','businessAndApplicationErrorEventsEqual','warningsEqual']) for p in rows))

    def test_unmodified_old_boundary_oracle_without_reporter_is_identical_to_v4(self):
        r=node(BOUNDARY/'code/migration_pipeline/audit_formal_30_v4_parent_watch_boundaries_v1.cjs',
               {'code':self.candidate['code'],'vue':self.base['vue'],**self.common})
        self.assertEqual(r,self.old['boundary_observations'])

    def test_v4_native_child_fix_is_retained_without_reporter_on_nonthrowing_path(self):
        f=self.old['mounted_fixture'];generic=adapt(f['normal'],f['vue'])
        r=node(OLD_ALIAS/'code/migration_pipeline/audit_parent_alias_child_runtime.cjs',
               {**f,'v3':generic['code'],**self.common})
        self.assertEqual(r,self.old['mounted_observations'])

    def test_production_boundary_and_forged_pass_guard_remain(self):
        d=source_parent_watch_semantics(self.candidate['code'],self.base['vue'])
        self.assertEqual({b['code'] for b in d['blocked_boundaries']},PARENT_WATCH_REVIEW_CODES)
        before={'generated_code':self.base['code'],'vue_source':self.base['vue'],
                'validation_errors':source_parent_watch_semantics(self.base['code'],self.base['vue'])['findings']}
        gate=candidate_gate(before,{**before,'generated_code':self.candidate['code'],'validation_errors':[],'validation_passed':True})
        self.assertTrue(gate['should_stop']);self.assertEqual(len(gate['waived_source_parent_watch_boundaries']),2)


if __name__=='__main__':unittest.main()
