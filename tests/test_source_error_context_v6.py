"""Mapped browser error context; application bindings are explicit, never inferred."""
import json
from pathlib import Path
import unittest

from test_parent_dynamic_key_adapter_probe import node
from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
from migration_pipeline.utils.repair_scheduler import PARENT_WATCH_REVIEW_CODES,candidate_gate

ROOT=Path(__file__).resolve().parents[1]
PRIOR=ROOT/'data/experiments/analysis/formal_30_v4_browser_error_chain_audit_v1_20261113'
V5=ROOT/'data/experiments/analysis/formal_30_v4_watch_error_router_v5_20261113'
ALIAS=ROOT/'data/experiments/analysis/formal_30_v4_parent_alias_child_audit_v1_20261112'
ADAPTER=ROOT/'migration_pipeline/probe_source_error_context_adapter_v6.cjs'
RUNTIME=ROOT/'migration_pipeline/audit_source_error_context_v6_runtime.cjs'
POLICY='mapped-browser-reporting-only-source-error-context'


def adapt(code,vue,**kw):return node(ADAPTER,{'code':code,'vue':vue,'experimental':True,'error_context_policy':POLICY,**kw})


def payloads():
    old=json.loads((PRIOR/'audit.json').read_text(encoding='utf-8'))
    v5=json.loads((V5/'audit.json').read_text(encoding='utf-8'));paths=v5['source_inputs']
    base={k:(ROOT/next(p for p in paths if p.endswith(end))).read_text(encoding='utf-8') for k,end in [('code','.san'),('vue','.vue')]}
    common={k:(ROOT/next(p for p in paths if p.endswith(end))).read_bytes().decode('utf-8')
            for k,end in [('vueRuntime','vue.runtime.common.dev.js'),('sanRuntime','san.dev.js')]}
    candidate=adapt(**base)
    payload={**common,'vue':base['vue'],'san_v5':v5['candidate']['code'],'san_v6':candidate['code'],
             'domModule':str(ALIAS/'code/migration_pipeline/audit_parent_alias_child_runtime.cjs')}
    return old,v5,base,common,candidate,payload


STRUCTURE=r"""
const fs=require('fs'),parser=require('@babel/parser'),i=JSON.parse(fs.readFileSync(0,'utf8'));
const {parentOf}=require('./migration_pipeline/utils/inline_identifier_recovery.cjs');
const {same}=require('./migration_pipeline/utils/source_render_call_semantics.cjs');
const parse=s=>parser.parse(/<script\b[^>]*>([\s\S]*?)<\/script>/.exec(s)[1],{sourceType:'unambiguous'});
const before=parse(i.before),after=parse(i.after),parent=parentOf(after);let factory=0,configure=0,dispatch=0;
after.program.body=after.program.body.filter(s=>{
 if(s.type==='VariableDeclaration'&&s.declarations.length===1&&s.declarations[0].id.name==='__sourceErrorContext_v6Create'){factory++;return false;}return true;
});
parent.properties=parent.properties.filter(p=>{if(p.key.name==='__sourceErrorContext_v6Configure'){configure++;return false;}return true;});
function walk(n){if(!n||typeof n!=='object')return;
 if(n.type==='CatchClause'&&n.param.name==='__parentWatchError_v5Error'){
  const wrapper=n.body.body[0];n.body=wrapper.alternate;dispatch++;return;
 }
 for(const [k,v] of Object.entries(n))if(!['loc','start','end','extra'].includes(k))Array.isArray(v)?v.forEach(walk):walk(v);
}walk(after);
process.stdout.write(JSON.stringify({factory,configure,dispatch,rest_of_script_unchanged:same(before,after)}));
"""


HELPER_UNIT=r"""
'use strict';const vm=require('vm');
const {createSourceErrorContext}=require('./migration_pipeline/probe_source_error_context_v6.cjs');
const c=vm.createContext({window:{document:{}}});vm.runInContext('globalThis.build=('+createSourceErrorContext.toString()+')',c);
const far={tag:'far',parent:null},near={tag:'near',parent:far},subject={tag:'subject',parent:near};
const original=new Error('Original');let trace=[],current=null;
const binding=()=>({environment:'browser',trackingPolicy:'no-reactive-reads-or-writes',parentOf:n=>n.parent,
 hooksOf:n=>n.hooks||[],globalHandler:()=>current,
 logError:(e,vm,info)=>trace.push(['log',e===original?'original':e.message,vm?.tag||null,info])});
subject.hooks=[()=>{throw Error('self hook must not run');}];
near.hooks=[function(){trace.push(['near',this===near]);return 0;}];
far.hooks=[function(){trace.push(['far',this===far]);return false;}];
c.build(binding()).handle(original,subject,'watch');const falseOnly=trace;
trace=[];near.hooks=[()=>{current=(e,vm,info)=>trace.push(['fresh',e===original,vm===subject,info]);}];far.hooks=[];current=()=>{throw Error('stale handler');};
c.build(binding()).handle(original,subject,'watch');const freshGlobal=trace;
trace=[];near.hooks=[];current=e=>{throw e;};c.build(binding()).handle(original,subject,'watch');const rethrowOnce=trace;
trace=[];current=()=>{throw new Error('Secondary');};c.build(binding()).handle(original,subject,'watch');const secondaryThenOriginal=trace;
const errors={};
function reject(name,fn){try{fn();errors[name]=null;}catch(e){errors[name]=e.message;}}
reject('headless',()=>createSourceErrorContext(binding()));
reject('ssr',()=>c.build({...binding(),environment:'ssr'}));
reject('stateful',()=>c.build({...binding(),trackingPolicy:'reactive'}));
reject('missing',()=>c.build({...binding(),parentOf:null}));
current=null;near.hooks=[];const cyclic={tag:'cycle'};cyclic.parent=cyclic;
reject('cyclic',()=>c.build(binding()).handle(original,cyclic,'watch'));
near.hooks=[1];reject('badHooks',()=>c.build(binding()).handle(original,subject,'watch'));
near.hooks=[];current=42;reject('badGlobal',()=>c.build(binding()).handle(original,subject,'watch'));
current=null;reject('sinkThrows',()=>c.build({...binding(),logError(){throw new Error('DiagnosticSinkFailure');}}).handle(original,subject,'watch'));
process.stdout.write(JSON.stringify({falseOnly,freshGlobal,rethrowOnce,secondaryThenOriginal,errors}));
"""


class SourceErrorContextV6Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old,cls.v5,cls.base,cls.common,cls.candidate,cls.payload=payloads()
        cls.observed=node(RUNTIME,cls.payload);cls.unit=node(HELPER_UNIT,{})

    def frame(self,scenario,variant='san_v6',phase='primary_tick'):
        return next(p for r in self.observed['runs'] if r['scenario']==scenario and r['variant']==variant for p in r['phases'] if p['name']==phase)

    def hooks(self,scenario):return [e for e in self.frame(scenario)['events'] if e['kind'] in ['capture-hook','global-handler']]
    def errors(self,scenario):return [a for e in self.frame(scenario)['consoleRecords'] for a in e['args'] if a['kind']=='error']

    def test_explicit_opt_in_context_policy_and_no_production_eligibility(self):
        for kw in [{'experimental':False},{'error_context_policy':None},{'error_context_policy':'auto'}]:
            r=adapt(**self.base,**kw);self.assertFalse(r['changes']);self.assertEqual(r['code'],self.base['code'])
        self.assertTrue(self.candidate['changes']);self.assertFalse(self.candidate['production_eligible'])

    def test_marker_collision_duplicate_application_does_not_change_code(self):
        r=adapt(self.candidate['code'],self.base['vue']);self.assertFalse(r['changes']);self.assertEqual(r['code'],self.candidate['code'])

    def test_ast_scope_only_factory_context_config_and_dispatch_branch(self):
        r=node(STRUCTURE,{'before':self.v5['candidate']['code'],'after':self.candidate['code']})
        self.assertEqual(r,{'factory':1,'configure':1,'dispatch':1,'rest_of_script_unchanged':True})

    def test_runtime_dimensions_and_listener_cleanup(self):
        self.assertEqual(len(self.observed['runs']),33)
        self.assertEqual(sum(len(r['phases']) for r in self.observed['runs']),330)
        self.assertEqual(len(self.observed['pairs']),220);self.assertTrue(self.observed['rejectionListenerRestored'])

    def test_all_110_source_mapped_candidate_phases_match_including_raw_console(self):
        rows=[r for r in self.observed['pairs'] if r['variant']=='san_v6'];self.assertEqual(len(rows),110)
        self.assertTrue(all(all(r[k] for k in ['stateEqual','eventsEqual','rawConsoleEqual','unhandledRejectionsEqual']) for r in rows))

    def test_frozen_source_and_v5_complete_control_runs_are_unchanged(self):
        self.assertEqual([r for r in self.observed['runs'] if r['variant']!='san_v6'],self.old['native_observations']['runs'])

    def test_nine_old_negative_scenarios_remain_preserved_as_v5_control(self):
        rows=[{k:v for k,v in r.items() if k!='variant'} for r in self.observed['pairs'] if r['variant']=='san_v5']
        self.assertEqual(rows,self.old['native_observations']['pairs'])
        self.assertEqual(len(self.old['negative_route_scenarios']),9)

    def test_browser_default_logs_original_without_rejection_and_next_watcher_runs(self):
        self.assertEqual([e['identity'] for e in self.errors('browser_default')],['original'])
        self.assertEqual(self.frame('browser_default')['unhandledRejections'],[])
        self.assertEqual(self.frame('browser_default')['state']['intervalDelays'],[30000])

    def test_near_false_short_circuits_far_and_global(self):
        self.assertEqual([(e['ancestor'],e['behavior']) for e in self.hooks('near_capture_false')],[('near','false')])
        self.assertEqual(self.errors('near_capture_false'),[])

    def test_true_bubbles_in_order_and_multiple_hook_false_stops(self):
        self.assertEqual([e['ancestor'] for e in self.hooks('near_bubble_far_false')],['near','far'])
        self.assertEqual([(e['ancestor'],e['index']) for e in self.hooks('near_two_hooks_false')],[('near',0),('near',1)])

    def test_capture_secondary_error_retains_ancestor_and_original_subject_attribution(self):
        h=[e for e in self.hooks('near_throw_global_returns') if e['kind']=='global-handler']
        self.assertEqual([(e['identity'],e['subject'],e['info']) for e in h],
                         [('capture-error','near','errorCaptured hook'),('original','subject','callback for watcher "tasks"')])

    def test_global_secondary_then_original_order_and_rethrow_original_only_once(self):
        self.assertEqual([e['identity'] for e in self.errors('global_handler_throws_different')],['reporter-error','original'])
        self.assertEqual([e['identity'] for e in self.errors('global_handler_rethrows_original')],['original'])

    def test_global_receiver_and_capture_receivers_are_preserved(self):
        for name in ['capture_returns_true_global','near_throw_global_returns']:
            for e in self.hooks(name):
                if e['kind']=='global-handler':self.assertTrue(e['thisIsNull'])
                else:self.assertEqual(e['receiver'],e['ancestor']);self.assertEqual(e['subject'],'subject')

    def test_native_san_control_still_nearest_error_and_no_global_patch(self):
        for r in self.observed['runs']:
            if r['variant']=='vue_source':continue
            self.assertEqual(r['nativeSanControl']['received'],[{'ancestor':'near','originalError':True,'subjectIsChild':True,'info':'watch:value'}])
            self.assertTrue(r['nativeSanControl']['nearReturnedTrue'])

    def test_unconfigured_v6_preserves_entire_old_browser_negative_audit(self):
        payload={**self.payload,'san_v5':self.candidate['code']}
        result=node(PRIOR/'code/migration_pipeline/audit_browser_error_chain_v1_runtime.cjs',payload)
        self.assertEqual(result,self.old['native_observations'])

    def test_unconfigured_v6_preserves_old_headless_explicit_reporter_audit(self):
        result=node(V5/'code/migration_pipeline/audit_parent_watch_error_router_v5_runtime.cjs',
                    {**self.common,'vue':self.base['vue'],'san_v4':json.loads((ROOT/'data/experiments/analysis/formal_30_v4_parent_alias_observer_v4_20261112/audit.json').read_text(encoding='utf-8'))['candidate']['code'],
                     'san_v5':self.candidate['code']})
        self.assertEqual(result,self.v5['explicit_policy_observations'])

    def test_unconfigured_v6_retains_nonthrowing_native_child_observations(self):
        v4=json.loads((ROOT/'data/experiments/analysis/formal_30_v4_parent_alias_observer_v4_20261112/audit.json').read_text(encoding='utf-8'))
        f=v4['mounted_fixture'];generic=adapt(f['normal'],f['vue'])
        result=node(ALIAS/'code/migration_pipeline/audit_parent_alias_child_runtime.cjs',
                    {**self.common,**f,'v3':generic['code']})
        self.assertEqual(result,v4['mounted_observations'])

    def test_helper_only_false_captures_zero_does_not_and_self_hook_is_skipped(self):
        self.assertEqual(self.unit['falseOnly'],[['near',True],['far',True]])

    def test_helper_reads_global_handler_fresh_after_capture_hook(self):
        self.assertEqual(self.unit['freshGlobal'],[['fresh',True,True,'watch']])

    def test_helper_error_identity_deduplicates_original_not_different_error(self):
        self.assertEqual(self.unit['rethrowOnce'],[['log','original','subject','watch']])
        self.assertEqual(self.unit['secondaryThenOriginal'],[['log','Secondary',None,'config.errorHandler'],['log','original','subject','watch']])

    def test_invalid_context_profiles_missing_bindings_and_headless_refuse(self):
        for name in ['headless','ssr','stateful','missing']:
            self.assertTrue(self.unit['errors'][name].startswith('Source v6 probe:'))

    def test_invalid_cycles_hook_lists_and_handler_do_not_hang_or_silently_pass(self):
        self.assertEqual(self.unit['errors']['cyclic'],'Source v6 probe: cyclic ancestor mapping')
        self.assertEqual(self.unit['errors']['badHooks'],'Source v6 probe: unsupported capture mapping')
        self.assertEqual(self.unit['errors']['badGlobal'],'Source v6 probe: unsupported global handler')
        self.assertEqual(self.unit['errors']['sinkThrows'],'DiagnosticSinkFailure')

    def test_production_boundaries_and_forged_pass_guard_remain(self):
        d=source_parent_watch_semantics(self.candidate['code'],self.base['vue'])
        self.assertEqual({b['code'] for b in d['blocked_boundaries']},PARENT_WATCH_REVIEW_CODES)
        before={'generated_code':self.base['code'],'vue_source':self.base['vue'],
                'validation_errors':source_parent_watch_semantics(self.base['code'],self.base['vue'])['findings']}
        gate=candidate_gate(before,{**before,'generated_code':self.candidate['code'],'validation_errors':[],'validation_passed':True})
        self.assertTrue(gate['should_stop']);self.assertEqual(len(gate['waived_source_parent_watch_boundaries']),2)

    def test_repeat_native_observations_deterministic_and_bindings_not_inferred(self):
        self.assertEqual(node(RUNTIME,self.payload),self.observed)
        self.assertTrue(self.observed['explicitApplicationMappings'] and self.observed['boundedDiagnosticSinkIsHarnessCode'])


if __name__=='__main__':unittest.main()
