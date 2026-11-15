"""Check persisted live-browser evidence; does not launch a browser per test."""
import json
import os
from pathlib import Path
import subprocess
import unittest

from migration_pipeline.audit_formal_30_v4_async_watcher_browser_v1 import ROOT, OUTPUT, PRIOR, inventory


class AsyncWatcherBrowserV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(os.environ.get('CARDMIG_BROWSER_AUDIT_EVIDENCE', str(OUTPUT / 'audit.json')))
        cls.data = json.loads(source.read_text(encoding='utf-8'))
        cls.live = cls.data['browser_run']; cls.observed = cls.live['observations']

    def frame(self, scenario, variant, phase='primary_tick'):
        return next(p for r in self.observed['runs'] if r['scenario'] == scenario and r['variant'] == variant
                    for p in r['phases'] if p['name'] == phase)

    def test_real_browser_identity_and_executable_hash_recorded(self):
        browser = self.live['browser']
        self.assertTrue(browser['product'].startswith('Edg/'))
        self.assertEqual(len(browser['executable_sha256']), 64)
        self.assertTrue(browser['profile_isolated'] and browser['headless'] and browser['executable_unchanged_during_run'])

    def test_framework_runtime_versions_pinned_and_no_CDN(self):
        self.assertEqual(self.data['evidence_boundary']['frameworks_pinned'], {'vue': '2.7.16', 'san': '3.15.6'})
        self.assertFalse(self.data['evidence_boundary']['CDN_or_model_used'])
        self.assertFalse(self.data['evidence_boundary']['browser_binary_vendored'])

    def test_native_real_DOM_not_miniDOM_all_33_runs(self):
        self.assertEqual(len(self.observed['runs']), 33)
        for run in self.observed['runs']:
            self.assertTrue(run['boundary']['realBrowser'] and run['nativeAncestorChain'])
            self.assertFalse(run['boundary']['limitedDOM'])

    def test_dimensions_and_all_110_candidate_pairs_match(self):
        self.assertEqual(sum(len(r['phases']) for r in self.observed['runs']), 330)
        self.assertEqual(len(self.observed['pairs']), 220)
        rows = [p for p in self.observed['pairs'] if p['variant'] == 'san_v7']
        self.assertEqual(len(rows), 110)
        self.assertTrue(all(all(p[k] for k in ['stateEqual', 'eventsEqual', 'rawConsoleEqual', 'unhandledRejectionsEqual']) for p in rows))

    def test_repeat_separate_browser_observations_identical(self):
        self.assertTrue(self.data['repeat_native_observations_equal'])
        self.assertEqual(self.observed, self.data['repeat_browser_run']['observations'])
        self.assertEqual(self.live['browser'], self.data['repeat_browser_run']['browser'])

    def test_nine_v5_negative_groups_and_51_mismatch_phases_preserved(self):
        scenarios = self.data['v5_negative_control_scenarios']
        self.assertEqual(len(scenarios), 9)
        self.assertEqual(sum(len(s['mismatch_phases']) for s in scenarios), 51)

    def test_browser_default_continues_settings_for_source_and_v7_not_v5(self):
        for variant in ['vue_source', 'san_v7']:
            frame = self.frame('browser_default', variant)
            self.assertEqual(frame['state']['intervalDelays'], [30000])
            self.assertEqual(frame['unhandledRejections'], [])
        self.assertEqual(self.frame('browser_default', 'san_v5')['state']['intervalDelays'], [])

    def test_strict_false_capture_and_throwing_global_error_identity_order(self):
        near = self.frame('near_capture_false', 'san_v7')
        hooks = [e for e in near['events'] if e['kind'] == 'capture-hook']
        self.assertEqual([e['ancestor'] for e in hooks], ['near'])
        frame = self.frame('global_handler_throws_different', 'san_v7')
        ids = [a['identity'] for r in frame['consoleRecords'] for a in r['args'] if a['kind'] == 'error']
        self.assertEqual(ids, ['reporter-error', 'original'])

    def test_raw_CDP_exceptions_retained_and_match_v5_rejections_not_hidden(self):
        for result in [self.live, self.data['repeat_browser_run']]:
            rejects = sum(len(r['phases'][-1]['unhandledRejections']) for r in result['observations']['runs'])
            self.assertEqual(rejects, 7)
            self.assertEqual(len(result['browser_exceptions']), rejects)
            self.assertTrue(all('BoundaryStorageWriteFailure' in e['description'] or 'ApplicationReporterFailure' in e['description']
                                for e in result['browser_exceptions']))

    def test_v7_scope_surface_configuration_lock_and_disposed_refusal(self):
        for run in self.observed['runs']:
            if run['variant'] == 'san_v7':
                self.assertEqual(run['scopeControls'], {'configureOnly': True, 'lateConfiguration': 'CONFIGURATION_LOCKED', 'disposedConfiguration': 'DISPOSED'})

    def test_native_san_nearest_error_semantics_preserved(self):
        for run in self.observed['runs']:
            if run['variant'] != 'vue_source':
                self.assertEqual(run['nativeSanControl']['received'], [{'ancestor': 'near', 'originalError': True, 'subjectIsChild': True, 'info': 'watch:value'}])

    def test_all_iframe_realms_removed(self):
        self.assertEqual(self.observed['realmCountAfter'], 0)
        self.assertEqual(self.data['repeat_browser_run']['observations']['realmCountAfter'], 0)

    def test_transport_routes_are_local_allowlist_not_repo_directory_server(self):
        transport = self.live['transport']
        self.assertTrue(transport['loopback_only'] and transport['port_ephemeral'])
        self.assertEqual(transport['served_routes'], ['/', '/realm.html', '/fixture.js', '/payload.json'])
        self.assertTrue(all(r['method'] == 'GET' and r['path'] in [*transport['served_routes'], '/favicon.ico'] for r in transport['requests']))
        self.assertEqual(transport['blockedRequests'], []); self.assertEqual(transport['protocolErrors'], [])

    def test_no_general_UI_storage_timer_or_user_mapping_claim(self):
        boundary = self.data['evidence_boundary']
        for name in ['real_localStorage_or_business_timer_execution_tested', 'full_TaskManager_UI_or_CSS_tested',
                     'real_user_application_mapping_certified', 'SSR_async_hooks_or_general_dependency_pause_proven']:
            self.assertFalse(boundary[name])
        self.assertTrue(boundary['subject_render_replaced_with_minimal_node'] and boundary['trusted_binding_not_purity_sandbox'])

    def test_original_score_no_model_no_production_no_manual_acceptance_change(self):
        a = self.data['original_aggregate']
        self.assertEqual((a['passed'], a['failed'], a['execution_errors'], a['total_tokens']), (24, 6, 0, 1821544))
        self.assertEqual(self.data['model_requests'], 0)
        for flag in ['production_integration_enabled', 'production_rules_or_prompt_modified', 'existing_pages_or_candidate_modified',
                     'original_score_modified', 'manual_acceptance_added', 'full_suite_reexecuted']:
            self.assertFalse(self.data[flag])

    def test_production_boundary_and_forged_pass_still_blocked_as_prior_reference(self):
        prior = json.loads((PRIOR / 'audit.json').read_text(encoding='utf-8'))
        self.assertEqual(self.data['production_diagnostics_reference'], prior['production_diagnostics'])
        self.assertEqual(self.data['forged_pass_gate_reference'], prior['forged_pass_gate'])
        self.assertTrue(self.data['forged_pass_gate_reference']['should_stop'])
        self.assertFalse(self.data['production_validation_reference']['production_validation_passed'])
        self.assertFalse(self.data['production_validation_reference']['new_compile_run_claimed'])

    def test_failed_startup_retained_without_fabricated_cause_or_component_defect(self):
        failed = self.data['failed_startup']
        self.assertEqual(failed['status'], 'no_observations_returned')
        self.assertIn('undetermined', failed['cause'])
        self.assertFalse(failed['temporary_profile_remaining'])
        self.assertTrue(failed['not_a_canonical_component_defect'])

    def test_browser_fixture_and_driver_syntax_valid(self):
        for name in ['audit_async_watcher_browser_v1.js', 'run_async_watcher_browser_v1.cjs']:
            proc = subprocess.run(['node', '--check', str(ROOT / 'migration_pipeline' / name)], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_prior_429_files_pages_candidate_and_old_notebook_prefix_unchanged(self):
        self.assertEqual(len(inventory()), 433)
        self.assertEqual(self.data['previous_inventory_unchanged'], 429)
        self.assertEqual(self.data['production_runtime_inventory_unchanged'], 387)

    def test_browser_runner_uses_private_profile_and_scoped_cleanup_without_user_profile(self):
        code = (ROOT / 'migration_pipeline/run_async_watcher_browser_v1.cjs').read_text(encoding='utf-8')
        self.assertIn("fs.mkdtempSync(path.join(os.tmpdir(),'cardmig-browser-audit-'))", code)
        self.assertIn('windowsHide:true', code)
        self.assertIn('Refusing unsafe profile cleanup', code)
        self.assertNotIn('--no-sandbox', code)


if __name__ == '__main__': unittest.main()
