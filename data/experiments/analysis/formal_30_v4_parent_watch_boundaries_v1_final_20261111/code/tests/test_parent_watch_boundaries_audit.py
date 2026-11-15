"""Preserve actual normal-flow controls and demonstrate unproven boundaries without repairing source."""
import json
import unittest

from migration_pipeline.audit_formal_30_v4_parent_watch_boundaries_v1 import (
    runtime, summarize, BASE, SAN, VUE, VUE_RUNTIME, SAN_RUNTIME,
)
from migration_pipeline.analyze_formal_30_v4_full_regression import digest


class ParentWatchBoundariesAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = runtime()
        cls.rows = {(r['scenario'],r['variant']):r for r in cls.result['runs']}

    def row(self,name,variant='vue_source'):
        return self.rows[(name,variant)]

    def phase(self,name,phase,variant='vue_source'):
        return next(p for p in self.row(name,variant)['phases'] if p['name']==phase)

    def events(self,name,phase,kind,variant='vue_source'):
        return [e for e in self.phase(name,phase,variant)['events'] if e['kind']==kind]

    def test_nine_scenarios_eighteen_runs_180_snapshots_90_pairs(self):
        self.assertEqual(len(self.result['scenarios']),9)
        self.assertEqual(len(self.rows),18)
        self.assertEqual(sum(len(r['phases']) for r in self.rows.values()),180)
        self.assertEqual(len(self.result['pairs']),90)

    def test_real_pinned_frameworks_and_explicit_no_browser_boundary(self):
        for (_,variant),r in self.rows.items():
            self.assertEqual(r['frameworkVersion'],'2.7.16' if variant=='vue_source' else '3.15.6')
            b=r['boundary']
            self.assertTrue(b['nativePromiseQueues'] and b['hostImmediateUsedOnlyToObserve'])
            for key in ['sanFullAttach','browser','realStorage','realApplicationTimers',
                        'sourceBusinessCodeChanged','sanCodeChanged','exceptionBridgeInstalledInSan']:
                self.assertFalse(b[key],key)

    def test_declared_same_changed_and_restored_existing_key_controls_all_match(self):
        for name in ['declared_same_value','declared_changed_value','restored_extra_key']:
            pairs=[p for p in self.result['pairs'] if p['scenario']==name]
            self.assertEqual(len(pairs),10)
            self.assertTrue(all(p['stateEqual'] and p['businessEffectsEqual'] for p in pairs),name)

    def test_new_plain_key_does_not_notify_vue_but_clone_notifies_san(self):
        for phase in ['primary_tick','repeat_tick']:
            self.assertEqual(self.events('new_key',phase,'storage-write'),[])
            self.assertEqual(len(self.events('new_key',phase,'storage-write','san_frozen_normal_flow')),1)
            self.assertEqual(len(self.events('new_key',phase,'interval-start','san_frozen_normal_flow')),1)
        source=self.phase('new_key','primary_tick')['state']
        target=self.phase('new_key','primary_tick','san_frozen_normal_flow')['state']
        self.assertEqual(source['settings']['customFlag'],target['settings']['customFlag'])
        self.assertNotIn('customFlag',source['stored']['settings'])
        self.assertEqual(target['stored']['settings']['customFlag'],'first')

    def test_undefined_new_key_shape_is_not_hidden_by_json(self):
        source=self.phase('new_undefined_key','primary_sync')['state']
        target=self.phase('new_undefined_key','primary_sync','san_frozen_normal_flow')['state']
        self.assertEqual(source['settingsShape']['ownUndefined'],['extraUndefined'])
        self.assertEqual(target['settingsShape']['ownUndefined'],[])
        self.assertEqual(source['settings']['extraUndefined'],{'$type':'undefined'})
        self.assertNotIn('extraUndefined',target['settings'])
        pairs=[p for p in self.result['pairs'] if p['scenario']=='new_undefined_key']
        self.assertTrue(all(p['businessEffectsEqual'] for p in pairs))
        self.assertTrue(any(not p['stateEqual'] for p in pairs))

    def test_inherited_key_assignment_is_not_a_declared_reactive_setter(self):
        for variant in ['vue_source','san_frozen_normal_flow']:
            self.assertIn('toString',self.phase('inherited_key','primary_tick',variant)['state']['settingsShape']['ownEnumerableKeys'])
        self.assertEqual(self.events('inherited_key','primary_tick','storage-write'),[])
        self.assertEqual(len(self.events('inherited_key','primary_tick','storage-write','san_frozen_normal_flow')),1)

    def test_proto_key_is_local_prototype_change_vs_spread_own_property(self):
        a=self.phase('prototype_key','primary_sync')['state']['settingsShape']
        b=self.phase('prototype_key','primary_sync','san_frozen_normal_flow')['state']['settingsShape']
        self.assertFalse(a['standardPrototype']);self.assertEqual(a['inheritedMarker'],'first')
        self.assertFalse(a['hasOwnProto']);self.assertTrue(b['standardPrototype']);self.assertTrue(b['hasOwnProto'])
        self.assertIsNone(b['inheritedMarker'])

    def test_captured_storage_error_routes_differ_and_source_continues_next_watcher(self):
        name='write_failure_captured'
        a,b=self.row(name),self.row(name,'san_frozen_normal_flow')
        self.assertEqual([e['channel'] for e in a['errors']],['vue.config.errorHandler'])
        self.assertEqual(a['errors'][0]['info'],'callback for watcher "tasks"')
        self.assertEqual([e['channel'] for e in b['errors']],['process.unhandledRejection'])
        self.assertEqual([e['message'] for e in a['errors']],['BoundaryStorageWriteFailure'])
        self.assertEqual([e['message'] for e in b['errors']],['BoundaryStorageWriteFailure'])
        self.assertEqual(self.phase(name,'primary_tick')['state']['activeIntervalDelays'],[30000])
        self.assertEqual(self.phase(name,'primary_tick','san_frozen_normal_flow')['state']['activeIntervalDelays'],[])
        self.assertEqual([e['name'] for e in self.events(name,'primary_tick','call')],
            ['updateStatistics','saveToLocalStorage','saveToLocalStorage','updateSyncInterval'])
        self.assertEqual([e['name'] for e in self.events(name,'primary_tick','call','san_frozen_normal_flow')],
            ['updateStatistics','saveToLocalStorage'])

    def test_storage_failure_is_injected_once_without_changing_either_business_method(self):
        for name in ['write_failure_captured','write_failure_headless_default']:
            for variant in ['vue_source','san_frozen_normal_flow']:
                self.assertEqual(len(self.events(name,'primary_tick','storage-write-failure',variant)),1)
                total=sum(len([e for e in p['events'] if e['kind']=='storage-write-failure']) for p in self.row(name,variant)['phases'])
                self.assertEqual(total,1)

    def test_try_finally_recovers_san_queue_but_does_not_prove_error_policy_parity(self):
        name='write_failure_captured';variant='san_frozen_normal_flow'
        self.assertEqual(self.phase(name,'repeat_tick',variant)['state']['activeIntervalDelays'],[60000])
        self.assertEqual([e['name'] for e in self.events(name,'recovery_tick','call',variant)],
            ['updateStatistics','saveToLocalStorage','saveToLocalStorage','updateSyncInterval'])
        self.assertEqual(self.phase(name,'recovery_tick',variant)['state']['activeIntervalDelays'],[])

    def test_node_default_vue_error_policy_is_not_assumed_to_continue(self):
        name='write_failure_headless_default'
        for variant in ['vue_source','san_frozen_normal_flow']:
            self.assertEqual([e['channel'] for e in self.row(name,variant)['errors']],['process.unhandledRejection'])
        self.assertEqual(self.phase(name,'repeat_tick')['events'],[])
        self.assertEqual(self.phase(name,'recovery_tick')['events'],[])
        self.assertTrue(self.phase(name,'repeat_tick','san_frozen_normal_flow')['events'])
        self.assertTrue(self.phase(name,'recovery_tick','san_frozen_normal_flow')['events'])
        self.assertEqual(self.row(name)['errorPolicy'],'headless_default')

    def test_diagnostic_restores_host_listener_and_keeps_prototypes_clean(self):
        for key in ['hostPrototypeCleanBefore','hostPrototypeCleanAfter','rejectionListenerCountRestored']:
            self.assertTrue(self.result[key],key)
        for r in self.rows.values():
            self.assertTrue(all(p['state']['settingsShape']['realmObjectPrototypeClean'] for p in r['phases']))

    def test_destroy_runs_but_no_blanket_timeout_cleanup_claim(self):
        for r in self.rows.values():
            final=next(p for p in r['phases'] if p['name']=='destroy_tick')['state']
            self.assertTrue(final['disposed'])
            self.assertEqual(final['activeIntervalDelays'],[])
            self.assertGreater(final['pendingNotificationTimeouts'],0)

    def test_comparison_and_summary_retain_all_business_events_and_shape_differences(self):
        for p in self.result['pairs']:
            a=self.phase(p['scenario'],p['phase']);b=self.phase(p['scenario'],p['phase'],'san_frozen_normal_flow')
            self.assertEqual(p['stateEqual'],a['state']==b['state'])
            self.assertEqual(p['businessEffectsEqual'],a['events']==b['events'])
        summary=summarize(self.result)
        self.assertEqual(len(summary),9)
        self.assertEqual({r['scenario'] for r in summary if not r['state_mismatch_phases'] and not r['business_effect_mismatch_phases']},
            {'declared_same_value','declared_changed_value','restored_extra_key'})

    def test_frozen_inputs_and_382_inventory_record_without_future_live_lock(self):
        frozen_inventory=json.loads((BASE/'live_inventory.json').read_text(encoding='utf-8'))
        self.assertEqual(len(frozen_inventory),382)
        self.assertEqual(digest(SAN),'925ff96134dca5cb927fa9cd738561dfb59dc1eaccc844451e804eddb9b79e14')
        data=json.loads((BASE/'replay.json').read_text(encoding='utf-8'))
        task=next(r for r in data['retained_artifact_replays'] if r['id']=='TaskManager')
        self.assertEqual(digest(VUE),task['vue_sha256'])
        self.assertEqual(digest(VUE_RUNTIME),self.result['vueRuntimeSha256'])
        self.assertEqual(digest(SAN_RUNTIME),self.result['sanRuntimeSha256'])

    def test_repeat_audit_is_deterministic_without_model_or_rule_change(self):
        self.assertEqual(runtime(),self.result)
        self.assertEqual(self.result['modelRequests'],0)
        self.assertFalse(self.result['productionRuleChanged'])


if __name__=='__main__':
    unittest.main()
