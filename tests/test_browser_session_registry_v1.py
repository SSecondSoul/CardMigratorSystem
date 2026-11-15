"""Pure registry controls; no browser/model starts during test discovery."""
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        code = r"""
const {SessionRegistry}=require('./migration_pipeline/utils/browser_session_registry_v1.cjs');
const pages=[{name:'vue'},{name:'san'}],pairs=[{source:'vue',target:'san'}],pin='a'.repeat(64);
const base=()=>new SessionRegistry('run-1','http://127.0.0.1:12345',pages,pairs);
const reg=(r,i)=>r.register(i,'context-'+i,'target-'+i,'session-'+i,pin);
const verify=(r,e,patch={},framePatch={})=>r.verify(e,{type:'page',targetId:e.targetId,browserContextId:e.contextId,url:e.url,...patch},{id:'frame-'+e.index,url:e.url,...framePatch});
const rejects=fn=>{try{fn();return false;}catch(e){return true;}};
const r=base(),s=reg(r,0),t=reg(r,1);verify(r,s);verify(r,t);
r.contextCreated(s.sessionId,{id:2,origin:r.origin,auxData:{frameId:'frame-0',isDefault:true}});
const misleading=r.diagnostic('console_error',s.sessionId,{executionContextId:2,args:[{value:'San target failed!'}]});
const target=r.diagnostic('console_error',t.sessionId,{args:[{value:'Vue source failed!'}]});
const unknown=r.diagnostic('console_error','stale-session',{stackTrace:{callFrames:[{url:t.url}]}});
const conflict=r.diagnostic('runtime_exception',s.sessionId,{url:t.url});
const context=r.diagnostic('runtime_exception',s.sessionId,{executionContextId:99});
const activeRequests=[r.allows(t.sessionId,{url:t.url,method:'GET'}),r.allows(t.sessionId,{url:s.url,method:'GET'}),r.allows(t.sessionId,{url:t.url.replace('12345','12346'),method:'GET'})];
const before=r.snapshot();r.disposed(s);r.disposed(t);const after=r.snapshot();
const late=r.diagnostic('console_error',s.sessionId,{});
const clean=base(),a=reg(clean,0),b=reg(clean,1);verify(clean,a);verify(clean,b);clean.disposed(a);clean.disposed(b);
const bad=patch=>{const x=base(),e=reg(x,0);return rejects(()=>verify(x,e,patch));};
const dup=method=>{const x=base();reg(x,0);return rejects(()=>x.register(1,...method,pin));};
const invalid=base();invalid.contextCreated('absent',{id:1});
console.log(JSON.stringify({
 roles:[s.roles,t.roles],misleading,target,unknown,conflict,context,late,activeRequests,nativeObservations:s.nativeObservations,
 before:before.identitiesComplete,after:after.identitiesComplete,complete:clean.snapshot().complete,
 cleanSource:clean.clean(a),sourceNotClean:r.clean(s),cleanTargetAfterSource:clean.clean(b),
 nativeRequests:[clean.allows(b.sessionId,{url:b.url,method:'GET'}),r.allows(t.sessionId,{url:t.url,method:'GET'}),clean.allows(b.sessionId,{url:a.url,method:'GET'})],
 requestChecks:['POST','GET'].map(method=>{const x=base(),e=reg(x,0);return [x.allows(e.sessionId,{url:e.url,method}),x.allows(e.sessionId,{url:e.url+'?x',method:'GET'}),x.allows('unknown',{url:e.url,method:'GET'})];}),
 bad:[bad({type:'worker'}),bad({targetId:'other'}),bad({browserContextId:'other'}),bad({url:s.url+'?redirect'}),(()=>{const x=base(),e=reg(x,0);return rejects(()=>verify(x,e,{}, {parentId:'parent'}));})()],
 duplicates:[dup(['context-0','new-target','new-session']),dup(['new-context','target-0','new-session']),dup(['new-context','new-target','session-0'])],
 incomplete:base().snapshot().complete,invalidContext:invalid.snapshot().integrityErrors.length,
 invalidPin:rejects(()=>base().register(0,'c','t','s','g'.repeat(64))),
 textDoesNotMutateOwner:misleading.owner.page==='vue',inputPageName:s.page,
}));
"""
        proc = subprocess.run(['node', '-'], cwd=ROOT, input=code, encoding='utf-8',
                              text=True, capture_output=True, timeout=30, check=True)
        cls.v = json.loads(proc.stdout)

    def test_source_role_from_declared_pair(self): self.assertEqual(self.v['roles'][0], [{'pair': 0, 'role': 'source'}])
    def test_target_role_from_declared_pair(self): self.assertEqual(self.v['roles'][1], [{'pair': 0, 'role': 'target'}])
    def test_misleading_san_text_stays_source(self): self.assertEqual(self.v['misleading']['owner']['page'], 'vue')
    def test_misleading_vue_text_stays_target(self): self.assertEqual(self.v['target']['owner']['page'], 'san')
    def test_stack_cannot_assign_unknown_session(self): self.assertIsNone(self.v['unknown']['owner'])
    def test_unknown_session_blocks(self): self.assertEqual(self.v['unknown']['attribution'], 'unverified')
    def test_conflicting_url_not_reassigned(self): self.assertEqual(self.v['conflict']['owner']['page'], 'vue')
    def test_conflicting_url_requires_review(self): self.assertIn('foreign_document_url', self.v['conflict']['reasons'])
    def test_unknown_context_requires_review(self): self.assertIn('unknown_execution_context', self.v['context']['reasons'])
    def test_late_event_keeps_original_page(self): self.assertEqual(self.v['late']['owner']['page'], 'vue')
    def test_late_event_blocks(self): self.assertIn('event_after_context_disposal', self.v['late']['reasons'])
    def test_disposal_required(self): self.assertFalse(self.v['before'])
    def test_all_identities_complete_after_disposal(self): self.assertTrue(self.v['after'])
    def test_clean_registry_complete(self): self.assertTrue(self.v['complete'])
    def test_registered_clean_source(self): self.assertTrue(self.v['cleanSource'])
    def test_diagnostics_not_silenced(self): self.assertFalse(self.v['sourceNotClean'])
    def test_clean_peer_not_global_slice(self): self.assertTrue(self.v['cleanTargetAfterSource'])
    def test_post_not_allowed(self): self.assertFalse(self.v['requestChecks'][0][0])
    def test_exact_get_allowed(self): self.assertTrue(self.v['requestChecks'][1][0])
    def test_query_not_allowed(self): self.assertFalse(self.v['requestChecks'][1][1])
    def test_unknown_request_owner_not_allowed(self): self.assertFalse(self.v['requestChecks'][1][2])
    def test_disposed_context_no_requests(self): self.assertFalse(any(self.v['nativeRequests']))
    def test_own_live_document_route_allowed(self): self.assertTrue(self.v['activeRequests'][0])
    def test_other_live_page_route_denied(self): self.assertFalse(self.v['activeRequests'][1])
    def test_wrong_actual_server_port_denied(self): self.assertFalse(self.v['activeRequests'][2])
    def test_raw_native_observations_retained(self): self.assertEqual(self.v['nativeObservations'][0]['targetInfo']['browserContextId'], 'context-0')
    def test_wrong_target_type_blocks(self): self.assertTrue(self.v['bad'][0])
    def test_wrong_target_identity_blocks(self): self.assertTrue(self.v['bad'][1])
    def test_wrong_context_identity_blocks(self): self.assertTrue(self.v['bad'][2])
    def test_wrong_origin_or_url_blocks(self): self.assertTrue(self.v['bad'][3])
    def test_subframe_cannot_be_main(self): self.assertTrue(self.v['bad'][4])
    def test_shared_context_rejected(self): self.assertTrue(self.v['duplicates'][0])
    def test_duplicate_target_rejected(self): self.assertTrue(self.v['duplicates'][1])
    def test_duplicate_session_rejected(self): self.assertTrue(self.v['duplicates'][2])
    def test_incomplete_registry_not_pass(self): self.assertFalse(self.v['incomplete'])
    def test_unknown_execution_context_owner_recorded(self): self.assertEqual(self.v['invalidContext'], 1)
    def test_invalid_html_hash_rejected(self): self.assertTrue(self.v['invalidPin'])


class RecordedIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base=ROOT/'data/experiments/analysis/browser_session_isolation_v1_20261115'
        read=lambda p: json.loads(p.read_text(encoding='utf-8'))
        cls.controls=read(base/'controls_verified/result.json')
        cls.checks=read(base/'controls_verified/calibration.json')
        cls.previous=read(base/'controls_final/result.json')
        cls.real=read(base/'frozen_components/result.json')
        cls.replay=read(base/'frozen_components/replay_checks.json')

    def test_all_fifteen_browser_controls_pass(self):
        self.assertEqual(len(self.checks['checks']), 15)
        self.assertTrue(self.checks['allPassed'])

    def test_initial_five_stores_empty_in_both_contexts(self):
        for n in ['storage_source','storage_target']:
            v=self.controls['captures'][n]['componentEvidence']['initialEmpty']
            self.assertEqual(set(v), {'local','session','cookie','indexedDB','cache'})
            self.assertTrue(all(v.values()))

    def test_same_page_reload_preserves_five_stores(self):
        for n in ['storage_source','storage_target']:
            self.assertTrue(all(self.controls['captures'][n]['componentEvidence']['samePageReloadPersisted'].values()))

    def test_control_screenshots_reproduce_across_new_launches(self):
        for name,c in self.controls['captures'].items():
            self.assertEqual(c['screenshotSha256'], self.previous['captures'][name]['screenshotSha256'])

    def test_run_ids_are_not_reused(self):
        self.assertNotEqual(self.controls['nativeRegistry']['runId'], self.previous['nativeRegistry']['runId'])

    def test_control_foreign_document_not_eligible(self):
        self.assertFalse(self.controls['nativeRegistry']['complete'])
        self.assertFalse(self.controls['passed'])

    def test_all_thirteen_frozen_replay_checks_pass(self):
        self.assertEqual(len(self.replay['checks']), 13)
        self.assertTrue(self.replay['allPassed'])

    def test_real_ten_unique_contexts_and_sessions(self):
        entries=self.real['nativeRegistry']['entries']
        self.assertEqual(len(entries),10)
        for k in ['contextId','sessionId','targetId']:
            self.assertEqual(len({e[k] for e in entries}),10)

    def test_real_native_urls_bind_actual_origin(self):
        registry=self.real['nativeRegistry']
        for e in registry['entries']:
            self.assertEqual(e['url'], registry['origin']+'/page/'+str(e['index']))
            self.assertEqual(len(e['nativeObservations']),2)
            for observed in e['nativeObservations']:
                self.assertEqual(observed['targetInfo']['url'],e['url'])
                self.assertEqual(observed['targetInfo']['browserContextId'],e['contextId'])
                self.assertEqual(observed['targetInfo']['targetId'],e['targetId'])
                self.assertEqual(observed['mainFrame']['url'],e['url'])

    def test_real_no_orphan_diagnostics(self):
        self.assertTrue(self.real['nativeRegistry']['complete'])
        self.assertEqual(self.real['nativeRegistry']['integrityErrors'],[])

    def test_real_source_warnings_not_sent_to_target(self):
        events=self.real['nativeRegistry']['events']
        self.assertEqual(len(events),10)
        self.assertTrue(all(e['owner']['page']=='analytics_default_vue' for e in events))
        self.assertTrue(self.real['captures']['analytics_default_san']['clean'])

    def test_real_all_contexts_disposed(self):
        self.assertTrue(all(e['contextDisposed'] for e in self.real['nativeRegistry']['entries']))
        trace=self.real['browserProcess']['protocolTrace']
        disposals=[e for e in trace if e.get('method')=='Target.disposeBrowserContext']
        self.assertEqual(len(disposals),10)
        for call in disposals:
            self.assertTrue(any(e['phase']=='response' and e['id']==call['id'] and e['error'] is None for e in trace))

    def test_four_static_matches_not_five_component_passes(self):
        self.assertTrue(all(p['passed'] for p in self.real['comparisons'][:4]))
        self.assertFalse(self.real['comparisons'][-1]['passed'])
        self.assertFalse(self.real['passed'])

    def test_no_resize_to_hide_height_difference(self):
        p=self.real['comparisons'][-1]
        self.assertIsNone(p['metrics'])
        self.assertEqual(p['dimensions'],{'source':[1280,1326],'target':[1280,1625]})

    def test_browser_versions_and_binary_pins_same(self):
        self.assertEqual(self.real['browser']['executableSha256'],self.controls['browser']['executableSha256'])
        self.assertEqual(self.real['browser']['product'],self.controls['browser']['product'])

    def test_model_production_and_historical_scores_untouched(self):
        self.assertEqual(self.real['boundary']['modelCalls'],0)
        self.assertFalse(self.real['boundary']['productionIntegrated'])
        self.assertFalse(self.real['boundary']['historicalScoresChanged'])


if __name__ == '__main__':
    unittest.main()
