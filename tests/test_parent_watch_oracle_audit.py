"""Pin actual source queue observations, not a production watcher fix or UI acceptance."""
import json
import unittest

from migration_pipeline.audit_formal_30_v4_parent_watch_oracle_v1 import (
    runtime, verify_vendor, phase, metrics, BASE, SAN,
)
from migration_pipeline.analyze_formal_30_v4_full_regression import digest


class ParentWatchOracleAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vendor = verify_vendor()
        cls.result = runtime()
        cls.rows = {(r['scenario'], r['variant']): r for r in cls.result['runs']}

    def row(self, scenario, variant):
        return self.rows[(scenario, variant)]

    def test_fifteen_runs_270_snapshots_and_versions(self):
        self.assertEqual(len(self.rows), 15)
        self.assertEqual(sum(len(r['phases']) for r in self.rows.values()), 270)
        for (_, variant), row in self.rows.items():
            self.assertEqual(row['frameworkVersion'], '2.7.16' if variant == 'vue_source' else '3.15.6')

    def test_real_vue_queue_not_a_hand_written_or_browser_emulation_claim(self):
        for (_, variant), row in self.rows.items():
            boundary = row['boundary']
            self.assertEqual(boundary['vueRealRootMount'], variant == 'vue_source')
            self.assertEqual(boundary['sanFrameworkDisposeExecuted'], variant != 'vue_source')
            for key in ['sanFullAttach', 'realApplicationTimers', 'realStorage', 'browser',
                        'notificationTimeoutCallbacksExecuted', 'naiveEarlyIsProductionFix']:
                self.assertFalse(boundary[key])

    def test_source_and_counterfactual_register_before_mount_current_san_does_not(self):
        for (scenario, variant), row in self.rows.items():
            registered = [e for e in row['constructionEvents'] if e['kind'] == 'watch-register']
            self.assertEqual([e['field'] for e in registered], [] if variant == 'san_current' else ['tasks', 'settings'])
            self.assertTrue(all(e['taskCount'] == 0 and e['autoSave'] for e in registered))

    def test_source_startup_effects_deferred_current_san_omits_them(self):
        for name in self.result['scenarios']:
            source = self.row(name, 'vue_source'); current = self.row(name, 'san_current')
            self.assertEqual(metrics(source, 'mount_sync')['watch_callbacks'], [])
            expected = ['tasks'] if name in ['empty', 'malformed'] else ['tasks', 'settings']
            self.assertEqual(metrics(source, 'mount_tick')['watch_callbacks'], expected)
            self.assertEqual(metrics(current, 'mount_sync', 'mount_tick')['watch_callbacks'], [])
            self.assertEqual(metrics(current, 'mount_sync', 'mount_tick')['writes'], [])

    def test_source_startup_save_counts(self):
        expected = {'empty': 1, 'malformed': 1, 'saved_manual': 2, 'saved_interval_30': 2, 'saved_autosave_off': 0}
        for name, count in expected.items():
            self.assertEqual(len(metrics(self.row(name, 'vue_source'), 'mount_sync', 'mount_tick')['writes']), count)

    def test_naive_move_overwrites_disabled_autosave_with_default_settings(self):
        source = self.row('saved_autosave_off', 'vue_source')
        naive = self.row('saved_autosave_off', 'san_naive_early')
        writes = metrics(naive, 'mount_sync', 'mount_tick')['writes']
        self.assertEqual(len(writes), 1)
        self.assertTrue(writes[0]['settings']['autoSave'])
        self.assertEqual(writes[0]['settings']['syncInterval'], 60)
        self.assertFalse(phase(naive, 'mount_tick')['state']['settings']['autoSave'])
        self.assertTrue(phase(naive, 'mount_tick')['state']['stored']['settings']['autoSave'])
        self.assertFalse(phase(source, 'mount_tick')['state']['stored']['settings']['autoSave'])

    def test_saved_interval_first_payload_uses_restored_value_only_in_source(self):
        source = metrics(self.row('saved_interval_30', 'vue_source'), 'mount_sync', 'mount_tick')['writes']
        naive = metrics(self.row('saved_interval_30', 'san_naive_early'), 'mount_sync', 'mount_tick')['writes']
        self.assertEqual([w['settings']['syncInterval'] for w in source], [30, 30])
        self.assertEqual([w['settings']['syncInterval'] for w in naive], [60, 30])

    def test_two_nested_changes_are_coalesced_once_in_actual_vue(self):
        for name in self.result['scenarios']:
            source = self.row(name, 'vue_source')
            self.assertEqual(metrics(source, 'nested_twice_sync')['watch_callbacks'], [])
            self.assertEqual(metrics(source, 'nested_twice_tick')['watch_callbacks'], ['tasks'])
            for variant in ['san_current', 'san_naive_early']:
                self.assertEqual(metrics(self.row(name, variant), 'nested_twice_sync')['watch_callbacks'], ['tasks', 'tasks'])

    def test_registration_order_not_mutation_order_controls_source_queue(self):
        for name in self.result['scenarios']:
            source = self.row(name, 'vue_source')
            self.assertEqual(metrics(source, 'settings_before_tasks_tick')['watch_callbacks'], ['tasks', 'settings'])
            for variant in ['san_current', 'san_naive_early']:
                self.assertEqual(metrics(self.row(name, variant), 'settings_before_tasks_sync')['watch_callbacks'], ['settings', 'settings', 'tasks'])

    def test_autosave_off_on_and_splice_effects(self):
        for name in self.result['scenarios']:
            source = self.row(name, 'vue_source')
            self.assertEqual(metrics(source, 'autosave_off_sync', 'autosave_off_tick')['writes'], [])
            self.assertEqual(len(metrics(source, 'autosave_on_sync', 'autosave_on_tick')['writes']), 2)
            self.assertEqual(metrics(source, 'splice_tick')['watch_callbacks'], ['tasks'])
            for variant in ['san_current', 'san_naive_early']:
                row = self.row(name, variant)
                self.assertEqual(metrics(row, 'autosave_off_sync', 'autosave_off_tick')['writes'], [])
                self.assertEqual(len(metrics(row, 'autosave_on_sync', 'autosave_on_tick')['writes']), 3)
                self.assertEqual(metrics(row, 'splice_sync')['watch_callbacks'], ['tasks'])

    def test_source_timer_restart_counts_preserved_not_optimized_away(self):
        source = metrics(self.row('saved_interval_30', 'vue_source'), 'mount_sync', 'mount_tick')
        current = metrics(self.row('saved_interval_30', 'san_current'), 'mount_sync', 'mount_tick')
        self.assertEqual(source['interval_starts'], [30000, 30000]); self.assertEqual(source['interval_clears'], 1)
        self.assertEqual(current['interval_starts'], [30000]); self.assertEqual(current['interval_clears'], 0)
        for row in self.rows.values():
            self.assertEqual(phase(row, 'manual_interval_tick')['state']['activeIntervalDelays'], [])

    def test_destroy_cancels_source_pending_watch_and_native_teardown_stops_listeners(self):
        for name in self.result['scenarios']:
            source = metrics(self.row(name, 'vue_source'), 'destroy_before_flush_sync', 'destroy_before_flush_tick')
            self.assertEqual(source['watch_callbacks'], []); self.assertEqual(len(source['writes']), 1)
            self.assertEqual(source['interval_starts'], [])
            for variant in ['san_current', 'san_naive_early']:
                current = metrics(self.row(name, variant), 'destroy_before_flush_sync', 'destroy_before_flush_tick')
                self.assertEqual(current['watch_callbacks'], ['settings']); self.assertEqual(len(current['writes']), 2)
                self.assertEqual(current['interval_starts'], [30000])
        for row in self.rows.values():
            final = phase(row, 'post_destroy_change_tick')['state']
            self.assertTrue(final['frameworkDisposed']); self.assertEqual(final['activeIntervalDelays'], [])
            later = metrics(row, 'post_destroy_change_sync', 'post_destroy_change_tick')
            self.assertEqual(later['watch_callbacks'], []); self.assertEqual(later['writes'], [])
            self.assertGreater(final['pendingNotificationTimeouts'], 0)  # Source does not clear these; no blanket cleanup claim.

    def test_business_state_matches_after_each_tick_despite_different_effect_histories(self):
        for name in self.result['scenarios']:
            source = self.row(name, 'vue_source')
            for expected in source['phases']:
                if not expected['name'].endswith('_tick'):
                    continue
                for variant in ['san_current', 'san_naive_early']:
                    actual = phase(self.row(name, variant), expected['name'])
                    for field in ['tasks', 'settings', 'statistics']:
                        self.assertEqual(actual['state'][field], expected['state'][field], (name, variant, expected['name'], field))

    def test_pinned_vendor_frozen_candidate_and_runtime_determinism(self):
        self.assertEqual(len(self.vendor), 5)
        self.assertEqual(digest(SAN), 'c22596d8a59a72f02bed8bffe04a9844e0584ad47a73e93e5ea50d69deaefea0')
        frozen_inventory = json.loads((BASE/'live_inventory.json').read_text(encoding='utf-8'))
        self.assertEqual(len(frozen_inventory), 370)  # Do not lock future production files to old live bytes.
        self.assertEqual(runtime(), self.result)


if __name__ == '__main__':
    unittest.main()
