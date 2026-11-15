"""Private async capability guards; never certifies application callback purity."""
import json
import unittest

from test_source_error_context_v6 import payloads, node, ROOT, PRIOR as BROWSER, V5, ALIAS
from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
from migration_pipeline.utils.repair_scheduler import PARENT_WATCH_REVIEW_CODES, candidate_gate

ADAPTER = ROOT / 'migration_pipeline/probe_async_watcher_scope_adapter_v7.cjs'
RUNTIME = ROOT / 'migration_pipeline/audit_async_watcher_scope_v7_runtime.cjs'
POLICY = 'private-async-parent-watch-source-context'


def adapt(code, vue, **kw):
    return node(ADAPTER, {'code': code, 'vue': vue, 'experimental': True, 'error_context_policy': POLICY, **kw})


STRUCTURE = r'''
const fs=require('fs'),parser=require('@babel/parser'),i=JSON.parse(fs.readFileSync(0,'utf8'));
const {parentOf}=require('./migration_pipeline/utils/inline_identifier_recovery.cjs');
const {one,same}=require('./migration_pipeline/utils/source_render_call_semantics.cjs');
const parse=s=>parser.parse(/<script\b[^>]*>([\s\S]*?)<\/script>/.exec(s)[1],{sourceType:'unambiguous'});
const before=parse(i.before),after=parse(i.after),parent=parentOf(after),init=one(parent,'inited');
let factories=0,catches=0,schedules=0;
after.program.body=after.program.body.filter(n=>{
 if(n.type==='VariableDeclaration'&&['__sourceErrorContext_v6Create','__watcherScope_v7Create'].includes(n.declarations[0].id.name)){factories++;return false;}return true;
});
const privateStatements=init.body.body.splice(0,2).concat(init.body.body.splice(-2));
function walk(n){if(!n||typeof n!=='object')return;
 if(n.type==='CatchClause'&&n.param.name==='__parentWatchError_v5Error'){
  n.body=n.body.body[0].consequent;catches++;return;
 }
 for(const [k,v] of Object.entries(n)){
  if(['loc','start','end','extra'].includes(k))continue;
  if(v?.type==='CallExpression'&&v.callee?.object?.name==='__watcherScope_v7Local'&&v.callee?.property?.name==='schedule'){
   n[k]=parser.parseExpression('Promise.resolve().then(flush)');schedules++;
  }else Array.isArray(v)?v.forEach(walk):walk(v);
 }
}walk(after);
process.stdout.write(JSON.stringify({factories,catches,schedules,privateStatements:privateStatements.length,rest_of_script_unchanged:same(before,after)}));
'''

UNIT = r'''
'use strict';const vm=require('vm');
const {createAsyncWatcherScope}=require('./migration_pipeline/probe_async_watcher_scope_v7.cjs');
const {createSourceErrorContext}=require('./migration_pipeline/probe_source_error_context_v6.cjs');
const c=vm.createContext({window:{document:{}},Promise});
vm.runInContext('globalThis.build=('+createAsyncWatcherScope.toString()+');globalThis.source=('+createSourceErrorContext.toString()+');',c);
(async()=>{
 const errors={},trace=[],error=new Error('original'),subject={parent:null},fields=['tasks','settings'];let sourceCalls=0;
 const source=b=>{sourceCalls++;return c.source(b);};
 const binding=()=>({channel:'async-parent-watch',environment:'browser',trackingPolicy:'no-reactive-reads-or-writes',
  parentOf:n=>n.parent,hooksOf:()=>[],globalHandler:()=>null,
  logError:(e,s,info)=>trace.push({type:'log',original:e===error,subject:s===subject,info})});
 const reject=(name,fn)=>{try{fn();errors[name]=null;}catch(e){errors[name]=e.code||e.message;}};
 const scope=c.build(source,subject,fields);fields[0]='mutated';
 reject('outside_before',()=>scope.route(error,0));
 for(const [name,changes] of Object.entries({wrongChannel:{channel:'event'},ssr:{environment:'ssr'},stateful:{trackingPolicy:'reactive'},missing:{logError:null}})){
  reject(name,()=>scope.configure({...binding(),...changes}));
 }
 const callsAfterRejectedConfig=sourceCalls;
 const b=binding();scope.configure(b);b.logError=()=>{throw Error('Mutated capability must not run');};
 const foreign=c.build(source,subject,['tasks']);foreign.configure(binding());
 const pending=scope.schedule(()=>{
  trace.push({type:'flush'});
  scope.route(error,0);
  reject('invalid_index',()=>scope.route(error,99));
  reject('invalid_fraction',()=>scope.route(error,0.5));
  reject('foreign_scope',()=>foreign.route(error,0));
  reject('nested_schedule',()=>scope.schedule(()=>{}));
 });
 trace.push({type:'sync'});
 reject('late_before_tick',()=>scope.configure(binding()));
 reject('duplicate_pending',()=>scope.schedule(()=>{}));
 await pending;
 reject('outside_after',()=>scope.route(error,0));
 reject('late_after_tick',()=>scope.configure(binding()));
 const unconfigured=c.build(source,subject,['tasks']);let noContextResult;
 await unconfigured.schedule(()=>{noContextResult=unconfigured.route(error,0);});
 const throwing=c.build(source,subject,['tasks']);let throwIdentity=false;
 try{await throwing.schedule(()=>{throw error;});}catch(e){throwIdentity=e===error;}
 reject('outside_after_throw',()=>throwing.route(error,0));
 let recovered=false;await throwing.schedule(()=>{recovered=true;});
 const cancel=c.build(source,subject,['tasks']);let cancellationReset=false;
 const waiting=cancel.schedule(()=>{cancellationReset=true;});cancel.dispose();await waiting;
 scope.dispose();
 reject('disposed_configure',()=>scope.configure(binding()));
 reject('disposed_schedule',()=>scope.schedule(()=>{}));
 reject('disposed_route',()=>scope.route(error,0));
 reject('invalid_fields',()=>c.build(source,subject,['tasks','tasks']));
 reject('invalid_flush',()=>c.build(source,subject,['tasks']).schedule(null));
 const headless=vm.createContext({Promise});vm.runInContext('globalThis.build=('+createAsyncWatcherScope.toString()+')',headless);
 reject('headless',()=>headless.build(source,subject,['tasks']).configure(binding()));
 const nullWindow=vm.createContext({Promise,window:null});vm.runInContext('globalThis.build=('+createAsyncWatcherScope.toString()+')',nullWindow);
 reject('null_window',()=>nullWindow.build(source,subject,['tasks']).configure(binding()));
 process.stdout.write(JSON.stringify({errors,trace,callsAfterRejectedConfig,noContextResult,throwIdentity,recovered,cancellationReset,
  scopeFrozen:Object.isFrozen(scope),publicMethods:Object.keys(scope)}));
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''


class AsyncWatcherScopeV7Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.browser, cls.v5, cls.base, cls.common, cls.v6, cls.old_payload = payloads()
        cls.candidate = adapt(**cls.base)
        cls.payload = {**cls.old_payload, 'san_v7': cls.candidate['code']}
        cls.observed = node(RUNTIME, cls.payload)
        cls.unit = node(UNIT, {})

    def test_explicit_policy_experimental_opt_in_and_no_production_eligibility(self):
        for kw in [{'experimental': False}, {'error_context_policy': None}]:
            result = adapt(**self.base, **kw)
            self.assertEqual(result['code'], self.base['code']); self.assertFalse(result['changes'])
        self.assertTrue(self.candidate['changes']); self.assertFalse(self.candidate['production_eligible'])

    def test_duplicate_application_and_frozen_v6_candidate_refused(self):
        for code in [self.candidate['code'], self.v6['code']]:
            result = adapt(code, self.base['vue'])
            self.assertFalse(result['changes']); self.assertEqual(result['code'], code)

    def test_exact_ast_scope_and_arrays_are_not_compared_as_nodes(self):
        self.assertEqual(node(STRUCTURE, {'before': self.v5['candidate']['code'], 'after': self.candidate['code']}),
            {'factories': 2, 'catches': 1, 'schedules': 1, 'privateStatements': 4, 'rest_of_script_unchanged': True})

    def test_33_runs_330_snapshots_and_110_v7_full_matches(self):
        self.assertEqual(len(self.observed['runs']), 33)
        self.assertEqual(sum(len(r['phases']) for r in self.observed['runs']), 330)
        rows = [r for r in self.observed['pairs'] if r['variant'] == 'san_v7']
        self.assertEqual(len(rows), 110)
        self.assertTrue(all(all(r[k] for k in ['stateEqual', 'eventsEqual', 'rawConsoleEqual', 'unhandledRejectionsEqual']) for r in rows))

    def test_entire_frozen_source_v5_control_runs_and_nine_failures_unchanged(self):
        self.assertEqual([r for r in self.observed['runs'] if r['variant'] != 'san_v7'], self.browser['native_observations']['runs'])
        rows = [{k: v for k, v in r.items() if k != 'variant'} for r in self.observed['pairs'] if r['variant'] == 'san_v5']
        self.assertEqual(rows, self.browser['native_observations']['pairs'])
        self.assertEqual(len(self.browser['negative_route_scenarios']), 9)

    def test_native_component_exposes_configure_not_context_or_dispatch_capability(self):
        for run in self.observed['runs']:
            if run['variant'] == 'san_v7': self.assertTrue(run['scopeControls']['configureOnly'])
        self.assertNotIn('__sourceErrorContext_v6Configure', self.candidate['code'])
        self.assertNotIn('__sourceErrorContext_v6Active', self.candidate['code'])

    def test_all_native_late_and_disposed_configuration_attempts_refused(self):
        for run in self.observed['runs']:
            if run['variant'] == 'san_v7':
                self.assertEqual(run['scopeControls']['lateConfiguration'], 'CONFIGURATION_LOCKED')
                self.assertEqual(run['scopeControls']['disposedConfiguration'], 'DISPOSED')

    def test_actual_entry_is_async_and_field_and_capability_slots_are_snapshotted(self):
        self.assertEqual(self.unit['trace'], [{'type': 'sync'}, {'type': 'flush'},
            {'type': 'log', 'original': True, 'subject': True, 'info': 'callback for watcher "tasks"'}])

    def test_outside_and_foreign_scope_route_refused(self):
        for name in ['outside_before', 'outside_after', 'outside_after_throw', 'foreign_scope']:
            self.assertEqual(self.unit['errors'][name], 'OUTSIDE_ASYNC_DISPATCH')

    def test_invalid_watcher_indices_refused_within_real_async_entry(self):
        for name in ['invalid_index', 'invalid_fraction']: self.assertEqual(self.unit['errors'][name], 'INVALID_WATCHER_INDEX')

    def test_nested_and_duplicate_pending_schedule_refused(self):
        for name in ['nested_schedule', 'duplicate_pending']: self.assertEqual(self.unit['errors'][name], 'REENTRANT_SCHEDULE')

    def test_configuration_locked_at_schedule_before_tick_and_after_tick(self):
        for name in ['late_before_tick', 'late_after_tick']: self.assertEqual(self.unit['errors'][name], 'CONFIGURATION_LOCKED')

    def test_unsupported_declared_profiles_and_missing_capability_rejected_before_core_creation(self):
        for name in ['wrongChannel', 'ssr', 'stateful']: self.assertEqual(self.unit['errors'][name], 'UNSUPPORTED_PROFILE')
        self.assertEqual(self.unit['errors']['missing'], 'MISSING_CAPABILITY')
        self.assertEqual(self.unit['callsAfterRejectedConfig'], 0)

    def test_headless_and_null_window_are_rejected_explicitly(self):
        for name in ['headless', 'null_window']: self.assertEqual(self.unit['errors'][name], 'BROWSER_REQUIRED')

    def test_disposed_scope_rejects_future_use_and_pending_queue_keeps_cancellation_reset(self):
        for name in ['disposed_configure', 'disposed_schedule', 'disposed_route']: self.assertEqual(self.unit['errors'][name], 'DISPOSED')
        self.assertTrue(self.unit['cancellationReset'])

    def test_flush_throw_preserves_identity_restores_scope_and_later_schedule_recovers(self):
        self.assertTrue(self.unit['throwIdentity'] and self.unit['recovered'])
        self.assertFalse(self.unit['noContextResult'])

    def test_invalid_factory_and_flush_refused_and_no_general_run_or_handle_export(self):
        self.assertEqual(self.unit['errors']['invalid_fields'], 'INVALID_SCOPE')
        self.assertEqual(self.unit['errors']['invalid_flush'], 'INVALID_FLUSH')
        self.assertEqual(self.unit['publicMethods'], ['configure', 'schedule', 'route', 'dispose'])
        self.assertTrue(self.unit['scopeFrozen'])

    def test_unconfigured_candidate_preserves_frozen_browser_failures(self):
        result = node(BROWSER / 'code/migration_pipeline/audit_browser_error_chain_v1_runtime.cjs',
                      {**self.old_payload, 'san_v5': self.candidate['code']})
        self.assertEqual(result, self.browser['native_observations'])

    def test_unconfigured_candidate_preserves_headless_reporter_and_native_child_observations(self):
        v4 = json.loads((ROOT / 'data/experiments/analysis/formal_30_v4_parent_alias_observer_v4_20261112/audit.json').read_text(encoding='utf-8'))
        observed = node(V5 / 'code/migration_pipeline/audit_parent_watch_error_router_v5_runtime.cjs',
            {**self.common, 'vue': self.base['vue'], 'san_v4': v4['candidate']['code'], 'san_v5': self.candidate['code']})
        self.assertEqual(observed, self.v5['explicit_policy_observations'])
        f = v4['mounted_fixture']; generic = adapt(f['normal'], f['vue'])
        mounted = node(ALIAS / 'code/migration_pipeline/audit_parent_alias_child_runtime.cjs', {**self.common, **f, 'v3': generic['code']})
        self.assertEqual(mounted, v4['mounted_observations'])

    def test_native_san_nearest_hook_and_original_parent_chain_unchanged(self):
        for run in self.observed['runs']:
            self.assertTrue(run['nativeAncestorChain'])
            if run['variant'] != 'vue_source':
                self.assertEqual(run['nativeSanControl']['received'], [{'ancestor': 'near', 'originalError': True, 'subjectIsChild': True, 'info': 'watch:value'}])

    def test_callback_purity_and_general_dependency_pause_not_claimed(self):
        self.assertTrue(any('NOT enforced' in s for s in self.candidate['limitations']))
        self.assertTrue(any('dependency suspension' in s for s in self.candidate['limitations']))

    def test_independent_diagnostics_and_forged_pass_stop_remain(self):
        diagnostics = source_parent_watch_semantics(self.candidate['code'], self.base['vue'])
        self.assertEqual({r['code'] for r in diagnostics['blocked_boundaries']}, PARENT_WATCH_REVIEW_CODES)
        before = {'generated_code': self.base['code'], 'vue_source': self.base['vue'],
                  'validation_errors': source_parent_watch_semantics(self.base['code'], self.base['vue'])['findings']}
        gate = candidate_gate(before, {**before, 'generated_code': self.candidate['code'], 'validation_errors': [], 'validation_passed': True})
        self.assertTrue(gate['should_stop']); self.assertEqual(len(gate['waived_source_parent_watch_boundaries']), 2)

    def test_repeated_native_observations_are_deterministic(self):
        self.assertEqual(node(RUNTIME, self.payload), self.observed)


if __name__ == '__main__': unittest.main()
