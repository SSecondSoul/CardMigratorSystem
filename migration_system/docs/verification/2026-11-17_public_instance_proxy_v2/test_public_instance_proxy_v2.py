"""Reactive prototype regressions; successful research is NOT production admission."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import unittest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'src'))
from card_migration_system.adapters.engine import verify_engine
from card_migration_system.runtime import browser_executable


class ReactivePublicInstanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result = subprocess.run(['node', str(PROJECT / 'research/public_instance_v2/compatibility.cjs')],
                                capture_output=True, timeout=40, cwd=PROJECT)
        if result.returncode:
            raise AssertionError(result.stderr.decode('utf-8', errors='replace'))
        cls.result = json.loads(result.stdout)
        cls.rows = {row['name']: row for row in cls.result['cases']}

    def test_all_94_native_cases_match_without_a_key_whitelist(self):
        self.assertEqual(self.result['matched_cases'], 94)
        self.assertTrue(all(row['equal'] for row in self.rows.values()))
        self.assertTrue(self.result['standalone_reactivity_kernel_used'])
        self.assertEqual(self.rows['coercion-to-symbol']['target']['conversions'], ['string'])

    def test_objects_refs_aliases_and_computed_cache_are_not_just_type_checks(self):
        value = self.rows['object-array-map-cycle-and-alias-identity']['target']
        self.assertTrue(value['aliases'] and value['cycle'] and value['reactive'])
        self.assertTrue(value['originalUnchanged'] and value['rawSame'])
        self.assertFalse(value['sameRaw'])
        self.assertTrue(self.rows['root-data-self-identity']['target']['same'])
        self.assertEqual(self.rows['escaped-ref-native-state-mirror']['target'], {'publicCount': 6, 'nativeState': 6})
        self.assertEqual(self.rows['computed-caches-and-invalidates']['target']['final'], 2)
        self.assertEqual(self.rows['no-eager-or-duplicate-root-getter-read']['target'], {'before': 0, 'value': 0, 'after': 1})
        self.assertEqual(self.rows['native-consumer-does-not-evaluate-nested-getter-twice']['target'], {'value': 7, 'reads': 1})

    def test_watchers_execute_batch_cleanup_pause_resume_and_dispose(self):
        value = self.rows['watch-default-batches-pause-resume-cleanup-stop']['target']
        self.assertEqual(value['beforeTick'], 0)
        self.assertGreater(len(value['calls']), 3)
        self.assertTrue(self.rows['watch-getter-public-receiver-and-nextTick-callback']['target']['callbackThis'])
        self.assertEqual(self.rows['watch-disposal-cancels-pending-callback']['target'], {'calls': []})
        self.assertEqual(self.rows['watch-numeric-deep-and-handler-object']['target']['afterNested'], 0)

    def test_watcher_error_handler_return_is_not_a_getter_result(self):
        value = self.rows['watch-getter-error-policy']['target']
        self.assertEqual(value['calls'], [[1, None]])
        self.assertEqual(value['errors'][0]['phase'], 'watcher getter')
        callback = self.rows['watch-callback-cleanup-error-policy']['target']
        self.assertEqual(callback['calls'], ['later-cleanup'])
        self.assertEqual([error['phase'] for error in callback['errors']], ['watcher callback', 'watcher cleanup function'])
        self.assertEqual(self.rows['watch-async-rejection-recording-policy']['target']['errors'][0]['phase'], 'watcher callback')

    def test_logical_instance_record_is_not_a_fabricated_vue_renderer_graph(self):
        value = self.rows['logical-instance-record-and-aliases']['target']
        self.assertTrue(value['proxySame'] and value['dataSame'] and value['contextSame'])
        self.assertEqual(self.result['gaps'][0]['name'], 'private-instance-renderer-vnode-graph')
        self.assertFalse(self.result['production_admission_eligible'])
        self.assertFalse(self.result['arbitrary_public_key_contract_complete'])

    def test_native_receiver_notifications_restore_and_kernel_guards(self):
        result = subprocess.run(['node', str(PROJECT / 'research/public_instance_v2/controls.cjs')],
                                capture_output=True, timeout=25, cwd=PROJECT)
        self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', errors='replace'))
        value = json.loads(result.stdout)
        self.assertEqual(len(value['controls']), 8)
        self.assertTrue(all(value['controls'].values()))

    def test_v1_evidence_engine_and_old_production_block_are_unchanged(self):
        evidence = PROJECT / 'docs/verification/2026-11-17_public_instance_proxy_v1'
        sums = json.loads((evidence / 'SHA256SUMS.json').read_bytes())
        for name, digest in sums.items():
            self.assertEqual(sha256((evidence / name).read_bytes()).hexdigest(), digest)
        self.assertEqual(sha256((PROJECT / 'research/public_instance_v1/runtime.cjs').read_bytes()).hexdigest(), sums['runtime.cjs'])
        self.assertEqual(verify_engine(PROJECT / 'engine')['files'], 98)
        value = {'repository': str(PROJECT / 'engine'), 'project': str(PROJECT),
                 'source': '<template><div/></template><script>module.exports={methods:{setValue(k,v){this[k]=v}}}</script>',
                 'action': 'source-contracts'}
        result = subprocess.run(['node', str(PROJECT / 'browser/evaluate.mjs')],
                                input=json.dumps(value).encode(), capture_output=True, timeout=25)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)['error'], 'source_dynamic_key_contract_unsupported')


class ReactivePublicInstanceBrowserTests(unittest.TestCase):
    def test_real_dom_ref_nested_alias_and_pre_post_watchers(self):
        executable = browser_executable({})
        self.assertTrue(executable, 'A real browser is required; no synthetic DOM verdict')
        result = subprocess.run(['node', str(PROJECT / 'research/public_instance_v2/browser_probe.cjs')],
                                input=json.dumps({'executable': executable}).encode(),
                                capture_output=True, timeout=90, cwd=PROJECT)
        self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', errors='replace'))
        value = json.loads(result.stdout)
        self.assertEqual(value['page_count'], 4)
        self.assertTrue(value['nested_alias_render_verified'] and value['escaped_ref_render_verified'])
        targets = [item for item in value['observations'] if item['kind'] == 'target']
        self.assertEqual(len(targets), 2)
        for item in targets:
            self.assertEqual(item['nested'], {'publicValue': 9, 'dom': '9'})
            self.assertEqual(len(item['watches']), 8 if item['scenario'] == 'ref' else 6)
            self.assertTrue(all(not state['vuePresent'] and state['standaloneKernelPresent'] for state in item['states']))
        self.assertEqual(value['errors'], [])
        self.assertFalse(value['production_admission_eligible'])


if __name__ == '__main__':
    unittest.main()
