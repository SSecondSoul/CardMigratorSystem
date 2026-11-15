"""Native mounted browser-branch/ancestor audit, not a real browser or repaired candidate."""
import json
from pathlib import Path
import unittest

from test_parent_dynamic_key_adapter_probe import node
from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
from migration_pipeline.utils.repair_scheduler import PARENT_WATCH_REVIEW_CODES

ROOT=Path(__file__).resolve().parents[1]
PRIOR=ROOT/'data/experiments/analysis/formal_30_v4_watch_error_router_v5_20261113'
ALIAS=ROOT/'data/experiments/analysis/formal_30_v4_parent_alias_child_audit_v1_20261112'
RUNTIME=ROOT/'migration_pipeline/audit_browser_error_chain_v1_runtime.cjs'


def payload():
    old=json.loads((PRIOR/'audit.json').read_text(encoding='utf-8'));paths=old['source_inputs']
    common={k:(ROOT/next(p for p in paths if p.endswith(end))).read_bytes().decode('utf-8')
            for k,end in [('vueRuntime','vue.runtime.common.dev.js'),('sanRuntime','san.dev.js')]}
    return old,{'vue':(ROOT/next(p for p in paths if p.endswith('.vue'))).read_text(encoding='utf-8'),
                'san_v5':old['candidate']['code'],
                'domModule':str(ALIAS/'code/migration_pipeline/audit_parent_alias_child_runtime.cjs'),**common}


class BrowserErrorChainAuditV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.old,cls.payload=payload();cls.observed=node(RUNTIME,cls.payload)

    def run_of(self,scenario,variant='vue_source'):
        return next(r for r in self.observed['runs'] if r['scenario']==scenario and r['variant']==variant)

    def frame(self,scenario,variant='vue_source',phase='primary_tick'):
        return next(p for p in self.run_of(scenario,variant)['phases'] if p['name']==phase)

    def hooks(self,scenario,variant='vue_source'):
        return [e for e in self.frame(scenario,variant)['events'] if e['kind'] in ['capture-hook','global-handler','san-native-error-hook']]

    def console_errors(self,scenario,variant='vue_source'):
        return [a for r in self.frame(scenario,variant)['consoleRecords'] for a in r['args'] if a['kind']=='error']

    def test_dimensions_and_host_rejection_listener_restored(self):
        self.assertEqual(len(self.observed['runs']),22)
        self.assertEqual(sum(len(r['phases']) for r in self.observed['runs']),220)
        self.assertEqual(len(self.observed['pairs']),110)
        self.assertTrue(self.observed['rejectionListenerRestored'])
        self.assertEqual(self.observed['modelRequests'],0);self.assertFalse(self.observed['adapterChanged'])

    def test_native_mounted_ancestor_chain_and_explicit_limited_dom_boundary(self):
        for r in self.observed['runs']:
            self.assertTrue(r['nativeAncestorChain'] and r['boundary']['nativeComponentsMounted'])
            self.assertTrue(r['boundary']['limitedDOM']);self.assertFalse(r['boundary']['realBrowser'])
            self.assertFalse(r['boundary']['subjectBusinessBodyChanged'])
            self.assertFalse(r['boundary']['privateFrameworkErrorFunctionInvokedByHarness'])

    def test_no_failure_and_explicit_returning_handler_controls_all_20_phases_match(self):
        rows=[p for p in self.observed['pairs'] if p['scenario'] in ['normal','global_handler_returns']]
        self.assertEqual(len(rows),20)
        self.assertTrue(all(all(p[k] for k in ['stateEqual','eventsEqual','rawConsoleEqual','unhandledRejectionsEqual']) for p in rows))

    def test_native_vue_browser_default_logs_original_and_continues_next_watcher(self):
        f=self.frame('browser_default')
        self.assertEqual(f['state']['intervalDelays'],[30000]);self.assertEqual(f['unhandledRejections'],[])
        self.assertEqual([e['identity'] for e in self.console_errors('browser_default')],['original'])

    def test_unchanged_v5_missing_reporter_rejects_and_skips_settings_this_turn(self):
        f=self.frame('browser_default','san_v5')
        self.assertEqual(f['state']['intervalDelays'],[])
        self.assertEqual([e['identity'] for e in f['unhandledRejections']],['original'])
        self.assertEqual(self.hooks('browser_default','san_v5'),[])

    def test_native_san_watch_positive_control_reaches_ancestor_with_original_error(self):
        for r in self.observed['runs']:
            if r['variant']!='san_v5':continue
            c=r['nativeSanControl'];self.assertTrue(c['nativeChildParentLink'])
            self.assertEqual(c['received'],[{'ancestor':'near','originalError':True,'subjectIsChild':True,'info':'watch:value'}])
            self.assertTrue(c['nearReturnedTrue'])  # Native San still stops at the nearest error hook.

    def test_near_capture_false_stops_far_and_global_but_not_next_watcher(self):
        self.assertEqual([(e['ancestor'],e['behavior']) for e in self.hooks('near_capture_false')],[('near','false')])
        self.assertEqual(self.console_errors('near_capture_false'),[])
        self.assertEqual(self.frame('near_capture_false')['state']['intervalDelays'],[30000])

    def test_capture_bubbles_near_to_far_preserving_receiver_and_original_subject(self):
        h=self.hooks('near_bubble_far_false')
        self.assertEqual([e['ancestor'] for e in h],['near','far'])
        self.assertTrue(all(e['receiver']==e['ancestor'] and e['subject']=='subject' and e['identity']=='original' for e in h))

    def test_multiple_hooks_declaration_order_and_false_short_circuit(self):
        h=self.hooks('near_two_hooks_false')
        self.assertEqual([(e['ancestor'],e['index'],e['behavior']) for e in h],[('near',0,'true'),('near',1,'false')])

    def test_true_is_bubble_not_capture_then_global_runs(self):
        h=self.hooks('capture_returns_true_global')
        self.assertEqual([e['kind'] for e in h],['capture-hook','capture-hook','global-handler'])
        self.assertEqual([e['ancestor'] for e in h[:-1]],['near','far'])
        self.assertTrue(h[-1]['thisIsNull']);self.assertEqual(h[-1]['info'],'callback for watcher "tasks"')

    def test_throwing_capture_logs_secondary_then_far_still_captures_original(self):
        self.assertEqual([e['identity'] for e in self.console_errors('near_throw_far_false')],['capture-error'])
        h=self.hooks('near_throw_far_false')
        self.assertEqual([(e['ancestor'],e['identity']) for e in h],[('near','original'),('far','original')])
        self.assertEqual(self.frame('near_throw_far_false')['unhandledRejections'],[])

    def test_throwing_global_logs_new_then_original_and_continues_in_browser_branch(self):
        self.assertEqual([e['identity'] for e in self.console_errors('global_handler_throws_different')],['reporter-error','original'])
        self.assertEqual(self.frame('global_handler_throws_different')['state']['intervalDelays'],[30000])
        self.assertEqual(self.frame('global_handler_throws_different')['unhandledRejections'],[])

    def test_rethrow_original_is_not_logged_twice_by_source(self):
        self.assertEqual([e['identity'] for e in self.console_errors('global_handler_rethrows_original')],['original'])
        self.assertEqual(self.frame('global_handler_rethrows_original')['state']['intervalDelays'],[30000])

    def test_capture_error_global_attribution_is_ancestor_then_original_subject(self):
        h=[e for e in self.hooks('near_throw_global_returns') if e['kind']=='global-handler']
        self.assertEqual([(e['identity'],e['subject'],e['info']) for e in h],
                         [('capture-error','near','errorCaptured hook'),('original','subject','callback for watcher "tasks"')])

    def test_same_business_state_can_still_have_wrong_error_routing(self):
        for scenario in ['capture_returns_true_global','near_throw_global_returns']:
            rows=[p for p in self.observed['pairs'] if p['scenario']==scenario]
            self.assertTrue(all(p['stateEqual'] for p in rows))
            self.assertTrue(any(not p['eventsEqual'] for p in rows))

    def test_all_nine_unsupported_route_groups_remain_negative(self):
        names=[s['name'] for s in self.observed['scenarios'] if s['name'] not in ['normal','global_handler_returns']]
        self.assertEqual(len(names),9)
        for name in names:
            self.assertTrue(any(not all(p[k] for k in ['stateEqual','eventsEqual','rawConsoleEqual','unhandledRejectionsEqual'])
                                for p in self.observed['pairs'] if p['scenario']==name))

    def test_raw_vue_warning_trace_and_error_objects_are_both_preserved(self):
        records=self.frame('browser_default')['consoleRecords']
        self.assertTrue(any(a['kind']=='value' and '[Vue warn]' in a['text'] and 'ErrorAuditSubject' in a['text'] for r in records for a in r['args']))
        self.assertTrue(any(a['kind']=='error' and a['identity']=='original' for r in records for a in r['args']))

    def test_native_ancestor_error_hooks_exist_but_custom_promise_queue_bypasses_them(self):
        for scenario in ['near_capture_false','near_bubble_far_false','near_throw_far_false']:
            self.assertTrue(self.run_of(scenario,'san_v5')['boundary']['sanAncestorErrorHooksInstalled'])
            self.assertEqual(self.hooks(scenario,'san_v5'),[])

    def test_production_guard_and_unmodified_v5_candidate_remain(self):
        self.assertFalse(self.old['candidate']['production_eligible'])
        d=source_parent_watch_semantics(self.payload['san_v5'],self.payload['vue'])
        self.assertEqual({b['code'] for b in d['blocked_boundaries']},PARENT_WATCH_REVIEW_CODES)
        self.assertFalse(self.old['source_default_exception_contract_closed'])

    def test_repeated_native_audit_is_deterministic(self):
        self.assertEqual(node(RUNTIME,self.payload),self.observed)


if __name__=='__main__':unittest.main()
