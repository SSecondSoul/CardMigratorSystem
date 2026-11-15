"""Native observable dependency checks, not certification of reactive hooks."""
import json
import unittest

from test_source_error_context_v6 import payloads, node, ROOT
from migration_pipeline.audit_formal_30_v4_error_context_reactivity_v1 import (
    NAMES, PRIOR, STATIC, application_audit, inventory, summarize,
)
from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
from migration_pipeline.utils.repair_scheduler import PARENT_WATCH_REVIEW_CODES, candidate_gate


class ErrorContextReactivityAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old, cls.v5, cls.base, cls.common, cls.candidate, cls.payload = payloads()
        cls.result = node(ROOT / NAMES[0], cls.payload)
        cls.prior = json.loads((PRIOR / 'audit.json').read_text(encoding='utf-8'))

    def run_for(self, scenario, variant):
        return next(r for r in self.result['runs'] if r['scenario'] == scenario and r['variant'] == variant)

    def frame(self, scenario, variant, name):
        return next(p for p in self.run_for(scenario, variant)['phases'] if p['name'] == name)

    def test_native_dimensions_and_rejection_listener_restored(self):
        self.assertEqual(len(self.result['runs']), 18)
        self.assertEqual(sum(len(r['phases']) for r in self.result['runs']), 216)
        self.assertEqual(len(self.result['pairs']), 108)
        self.assertTrue(self.result['rejectionListenerRestored'])

    def test_all_108_complete_events_raw_console_and_rejection_pairs_match(self):
        for row in self.result['pairs']:
            for key in ['eventsEqual', 'rawConsoleEqual', 'unhandledRejectionsEqual']:
                self.assertTrue(row[key], (row['scenario'], row['phase'], key))

    def test_raw_state_not_falsely_marked_equal_and_differences_are_preserved(self):
        self.assertTrue(any(not row['stateEqual'] for row in self.result['pairs']))
        differences = summarize(self.result)
        self.assertTrue(differences)
        self.assertTrue(all(set(row['fields']) <= {'auditComputedRuns', 'domText'} for row in differences))

    def test_normal_control_already_has_sync_computed_timing_difference(self):
        a = self.frame('normal', 'vue_source', 'primary_sync')['state']['auditComputedRuns']
        b = self.frame('normal', 'san_v6', 'primary_sync')['state']['auditComputedRuns']
        self.assertEqual((a, b), (2, 3))
        self.assertEqual(self.frame('normal', 'vue_source', 'primary_tick')['state'],
                         self.frame('normal', 'san_v6', 'primary_tick')['state'])

    def test_normal_control_retains_native_destroy_dom_difference(self):
        self.assertEqual(self.frame('normal', 'vue_source', 'destroy_tick')['state']['domText'], '0')
        self.assertEqual(self.frame('normal', 'san_v6', 'destroy_tick')['state']['domText'], '')

    def test_reads_do_not_create_observed_unrelated_dependency_in_async_dispatch(self):
        for name in ['capture_reads_subject', 'global_reads_subject']:
            for variant in ['vue_source', 'san_v6']:
                a = self.frame(name, variant, 'recovery_tick')['state']['auditComputedRuns']
                b = self.frame(name, variant, 'unrelated_tick')['state']['auditComputedRuns']
                self.assertEqual(b - a, 0)

    def test_unrelated_hook_writes_apply_without_repeated_computed_evaluation(self):
        for name in ['capture_writes_unrelated', 'global_writes_unrelated']:
            for variant in ['vue_source', 'san_v6']:
                self.assertEqual(self.frame(name, variant, 'primary_tick')['state']['auditSentinel'], 1)
                self.assertEqual(self.frame(name, variant, 'unrelated_tick')['state']['auditSentinel'], 2)
                self.assertEqual(self.frame(name, variant, 'primary_tick')['state']['auditComputedRuns'], 3)

    def test_settings_reentry_preserves_business_output_but_not_evaluation_count(self):
        a = self.frame('capture_reenters_settings', 'vue_source', 'primary_tick')['state']
        b = self.frame('capture_reenters_settings', 'san_v6', 'primary_tick')['state']
        self.assertEqual(a['settings']['syncInterval'], 15)
        self.assertEqual(a['intervalDelays'], [15000])
        self.assertEqual(a['domText'], b['domText'])
        self.assertEqual((a['auditComputedRuns'], b['auditComputedRuns']), (3, 4))

    def test_no_error_double_update_control_reproduces_same_extra_evaluation(self):
        for variant in ['vue_source', 'san_v6']:
            error = self.frame('capture_reenters_settings', variant, 'primary_tick')['state']
            control = self.frame('normal_two_updates', variant, 'primary_tick')['state']
            self.assertEqual(error['auditComputedRuns'], control['auditComputedRuns'])
            self.assertEqual(error['domText'], control['domText'])

    def test_task_reentry_preserves_source_order_and_recovers_without_unhandled_rejection(self):
        for variant in ['vue_source', 'san_v6']:
            frame = self.frame('global_reenters_tasks', variant, 'primary_tick')
            self.assertEqual(frame['state']['tasks'][0]['title'], 'from-error-hook')
            self.assertEqual(frame['unhandledRejections'], [])
            writes = [e for e in frame['events'] if e['kind'] == 'storage-write']
            self.assertGreaterEqual(len(writes), 2)

    def test_positive_control_observes_a_real_added_dependency_and_updates_dom(self):
        for variant in ['vue_source', 'san_v6']:
            a = self.frame('positive_computed_dependency', variant, 'recovery_tick')['state']
            b = self.frame('positive_computed_dependency', variant, 'unrelated_tick')['state']
            self.assertEqual(b['auditComputedRuns'] - a['auditComputedRuns'], 1)
            self.assertEqual((a['domText'], b['domText']), ('0', '1'))

    def test_reactive_hook_calls_occur_on_real_primary_tick_not_forced_collector(self):
        for run in self.result['runs']:
            reads = [e for p in run['phases'] for e in p['events'] if e['kind'] == 'reactive-error-read']
            self.assertTrue(all(e['phase'] == 'primary_tick' for e in reads))
        self.assertTrue(self.result['realCandidateDispatchUsed'])
        self.assertFalse(self.result['dependencySuspensionImplemented'])

    def test_native_parent_identity_and_san_nearest_hook_semantics_unchanged(self):
        for run in self.result['runs']:
            self.assertTrue(run['nativeAncestorChain'])
            if run['variant'] == 'san_v6':
                c = run['nativeSanControl']
                self.assertTrue(c['nativeChildParentLink'] and c['nearReturnedTrue'])
                self.assertEqual(c['received'], [{'ancestor': 'near', 'originalError': True,
                    'subjectIsChild': True, 'info': 'watch:value'}])

    def test_unchanged_v6_profile_and_entire_prior_observations_replay(self):
        self.assertEqual(self.candidate, self.prior['candidate'])
        self.assertFalse(self.candidate['production_eligible'])
        self.assertTrue(self.result['reactiveHooksIntentionallyOutsideDeclaredV6Profile'])
        old = node(PRIOR / 'code/migration_pipeline/audit_source_error_context_v6_runtime.cjs', self.payload)
        self.assertEqual(old, self.prior['native_observations'])

    def test_application_mapping_checks_executable_scripts_not_stale_comment(self):
        from migration_pipeline.audit_formal_30_v4_error_context_reactivity_v1 import fixture
        app = application_audit(fixture(), self.base)
        self.assertEqual(app['current_component'], 'RuleBuilder')
        self.assertFalse(app['TaskManager_is_current_manual_subject'])
        self.assertFalse(app['v6_application_binding_deployed'])
        self.assertFalse(app['remote_loader_or_global_config_proven'])
        for name in ['vue_page', 'frozen_TaskManager_source']:
            self.assertEqual(app['syntax'][name]['errorCapturedKeys'], 0)
            self.assertEqual(app['syntax'][name]['mixinOrExtendsKeys'], 0)
        self.assertEqual(app['syntax']['vue_page']['globalHandlerAssignments'], 0)
        self.assertEqual(app['syntax']['san_page']['v6ConfigureCalls'], 0)
        self.assertTrue(all('RuleBuilder' in p for p in app['selected_files_sha256']))

    def test_static_audit_does_not_match_hooks_hidden_in_comments_or_external_scripts(self):
        result = node(STATIC, {'fixture': {'html': True, 'text':
            '<!-- errorCaptured --> <script src="remote.js">Vue.config.errorHandler=x;</script>'
            '<script>/* errorCaptured(){} */ new Vue({el:"#app"});</script>'}})['fixture']
        self.assertEqual(result['errorCapturedKeys'], 0)
        self.assertEqual(result['globalHandlerAssignments'], 0)
        self.assertEqual(result['vueRoots'], [['el']])

    def test_production_diagnostics_and_forged_pass_stop_remain_independent(self):
        diagnostics = source_parent_watch_semantics(self.candidate['code'], self.base['vue'])
        self.assertEqual({e['code'] for e in diagnostics['blocked_boundaries']}, PARENT_WATCH_REVIEW_CODES)
        before = {'generated_code': self.base['code'], 'vue_source': self.base['vue'],
                  'validation_errors': source_parent_watch_semantics(self.base['code'], self.base['vue'])['findings']}
        gate = candidate_gate(before, {**before, 'generated_code': self.candidate['code'], 'validation_errors': [], 'validation_passed': True})
        self.assertTrue(gate['should_stop'])
        self.assertEqual(len(gate['waived_source_parent_watch_boundaries']), 2)

    def test_repeat_is_deterministic_and_prior_421_live_files_unchanged(self):
        self.assertEqual(node(ROOT / NAMES[0], self.payload), self.result)
        self.assertEqual(len(inventory()), 424)


if __name__ == '__main__':
    unittest.main()
