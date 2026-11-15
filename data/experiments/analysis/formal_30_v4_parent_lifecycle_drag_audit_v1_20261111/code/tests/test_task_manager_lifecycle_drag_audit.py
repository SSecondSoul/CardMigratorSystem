"""Pin diagnostic observations; these passing tests do NOT mean the defects are fixed."""
import unittest

from migration_pipeline.audit_formal_30_v4_task_manager_lifecycle_drag_v1 import runtime, inventory, SAN
from migration_pipeline.analyze_formal_30_v4_full_regression import digest


class TaskManagerLifecycleDragAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = runtime()
        cls.lifecycle = {r['scenario']: r for r in cls.result['lifecycle']}
        cls.drag = {r['operation']: r for r in cls.result['drag']}

    def test_runtime_version_and_explicit_no_browser_boundary(self):
        self.assertEqual(self.result['sanVersion'], '3.15.6')
        boundary = self.result['boundary']
        self.assertTrue(boundary['hookInvokedDirectly'])
        for key in ['browserUsed', 'realTimersUsed', 'realStorageUsed', 'nativeDragGestureExecuted',
                    'fullSanAttachExecuted', 'productionCodeChanged', 'newBatchOrManualAcceptance']:
            self.assertFalse(boundary[key])
        self.assertFalse(self.result['sourceLifecycle']['vueRuntimeExecuted'])

    def test_four_storage_branches_restore_tasks_and_statistics(self):
        self.assertEqual(set(self.lifecycle), {'empty', 'saved', 'saved-autosave-off', 'malformed'})
        for name, row in self.lifecycle.items():
            expected = 1 if name.startswith('saved') else 3
            self.assertEqual(row['initial']['taskCount'], expected)
            self.assertEqual(row['initial']['statisticsTotal'], expected)
            self.assertEqual(row['initial']['activeIntervals'], 0 if name.startswith('saved') else 1)

    def test_missed_startup_observation_is_reproduced_not_claimed_fixed(self):
        for row in self.lifecycle.values():
            initial = row['initial']
            self.assertEqual(initial['watchCallbacks'], 0)
            self.assertEqual(initial['saves'], 0)
            registrations = initial['registrations']
            self.assertEqual([r['field'] for r in registrations], ['tasks', 'settings'])
            self.assertTrue(all(r['afterLoad'] and r['taskCount'] == initial['taskCount'] for r in registrations))
            self.assertTrue(all(r['ignoredThirdOptions'] == {'deep': True, 'immediate': False} for r in registrations))

    def test_source_watch_contract_is_static_not_vue_runtime_result(self):
        source = self.result['sourceLifecycle']
        self.assertEqual(source['watcherKeys'], ['tasks', 'settings'])
        self.assertEqual(source['deepWatchers'], ['tasks', 'settings'])
        self.assertIn('this.loadInitialData()', source['mounted'])
        self.assertIn('this.startAutoSync()', source['mounted'])
        self.assertIn('this.saveToLocalStorage()', source['beforeDestroy'])
        self.assertFalse(source['vueRuntimeExecuted'])

    def test_nested_task_edit_is_observed_after_registration(self):
        for name, row in self.lifecycle.items():
            events = row['afterEdit']['events']
            self.assertEqual([e['field'] for e in events if e['kind'] == 'watch-callback'], ['tasks', 'settings'])
            self.assertIn({'kind': 'call', 'name': 'updateStatistics'}, events)
            writes = [e for e in events if e['kind'] == 'storage-write']
            self.assertEqual(len(writes), 0 if name == 'saved-autosave-off' else 2)

    def test_setting_interval_zero_cancels_mock_interval_without_real_timer(self):
        for row in self.lifecycle.values():
            self.assertEqual(row['afterEdit']['activeIntervals'], 0)
            self.assertIn({'kind': 'call', 'name': 'updateSyncInterval'}, row['afterEdit']['events'])

    def test_disposed_hook_saves_even_if_source_autosave_is_off(self):
        for row in self.lifecycle.values():
            self.assertEqual(row['afterDisposed']['activeIntervals'], 0)
            writes = [e for e in row['afterDisposed']['events'] if e['kind'] == 'storage-write']
            self.assertEqual(len(writes), 1)

    def test_deep_immediate_option_does_not_supply_vue_watch_semantics(self):
        watch = self.result['watcher']
        self.assertEqual(watch['formalArgumentCount'], 2)
        self.assertEqual(watch['immediateCount'], 0)
        self.assertEqual(watch['nestedCount'], 1)
        self.assertEqual(watch['directMutationCount'], 1)
        self.assertEqual(watch['sameReferenceCount'], 1)
        self.assertEqual(watch['spliceCount'], 2)
        self.assertTrue(watch['directMutationNotObserved'])

    def test_parsed_event_chain_order_matches_source_six_filtered_cases(self):
        self.assertEqual(len(self.drag), 6)
        for row in self.drag.values():
            self.assertEqual(row['order'], row['sourceExpectedOrder'])
            self.assertTrue(row['oldArrayUnchanged'])
            self.assertTrue(row['elementIdentitiesPreserved'])
            self.assertIsNone(row['finalDragIndex'])
        self.assertEqual(self.drag['onto-down']['order'], list('acdbefg'))
        self.assertEqual(self.drag['onto-up']['order'], list('adbcefg'))
        self.assertEqual(self.drag['list-end']['order'], list('acdefbg'))

    def test_native_prevent_and_stop_declarations_are_actually_executed(self):
        for name in ['onto-down', 'onto-up', 'self']:
            self.assertTrue(self.drag[name]['bubblePrevented'])
            self.assertEqual(self.drag[name]['calls'], [{'kind': 'prevent'}, {'kind': 'stop'}])
        self.assertEqual(self.drag['list-end']['calls'], [{'kind': 'prevent'}])

    def test_source_transfer_effects_missing_in_target_are_reproduced(self):
        source = self.result['sourceDragStart']
        self.assertEqual(source['setData'], [['text/plain', 0]])
        self.assertEqual(source['effectAllowed'], 'move')
        self.assertEqual(source['emitted'], [['drag-start', 0]])
        for row in self.drag.values():
            self.assertIsNone(row['dataTransferEffectAllowed'])
            self.assertFalse(any(c['kind'] == 'setData' for c in row['calls']))

    def test_disabled_cancel_self_do_not_move_or_notify(self):
        self.assertEqual(self.result['sourceDragStart']['disabledEmitted'], [])
        for name in ['disabled', 'cancel', 'self']:
            self.assertEqual(self.drag[name]['order'], list('abcdefg'))
            self.assertEqual(self.drag[name]['notes'], [])
        self.assertIsNone(self.drag['disabled']['startIndex'])
        self.assertEqual(self.drag['cancel']['startIndex'], 0)

    def test_zero_index_payload_is_not_dropped(self):
        self.assertEqual(self.drag['onto-down']['startIndex'], 0)
        self.assertEqual(self.drag['onto-up']['startIndex'], 1)

    def test_production_inventory_and_frozen_candidate_are_unchanged(self):
        self.assertEqual(len(inventory()), 363)
        self.assertEqual(digest(SAN), 'a55eded4764f5f049df8c27940dffda52907f5dd0b877c15fbabb10e8f4feb61')


if __name__ == '__main__':
    unittest.main()
