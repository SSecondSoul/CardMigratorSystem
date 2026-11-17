"""Authorized namespace prototype: native differential tests, no production waiver."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'src'))
from card_migration_system.adapters.engine import verify_engine
from card_migration_system.runtime import browser_executable


class PublicInstancePrototypeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result = subprocess.run(['node', str(PROJECT / 'research/public_instance_v1/compatibility.cjs')],
                                capture_output=True, timeout=40, cwd=PROJECT)
        if result.returncode:
            raise AssertionError(result.stderr.decode('utf-8', errors='replace'))
        cls.result = json.loads(result.stdout)

    def test_native_differential_cases_are_real_and_not_a_key_whitelist(self):
        self.assertEqual(self.result['versions'], {'vue': '3.5.45', 'san': '3.15.6'})
        self.assertEqual(self.result['matched_cases'], 73)
        self.assertTrue(all(row['equal'] for row in self.result['cases']))
        names = {row['name'] for row in self.result['cases']}
        self.assertTrue({'symbol-key', 'coercion-to-symbol', 'dotted-literal',
                         'native-namespace-data-null', 'coerced-native-data',
                         'captured-setter-survives-self-replacement'}.issubset(names))
        rows = {row['name']: row for row in self.result['cases']}
        self.assertTrue(rows['undefined-key']['target']['matches'])
        self.assertEqual(rows['declared-root-key-coercion']['target']['conversions'], ['string'])
        self.assertEqual(rows['coercion-to-symbol']['target']['conversions'], ['string'])
        self.assertEqual(rows['throwing-key']['target']['error'], 'RangeError')
        self.assertEqual(rows['invalid-primitive-conversion']['target']['error'], 'TypeError')

    def test_namespace_writes_do_not_destroy_the_native_data_pointer(self):
        for row in self.result['cases']:
            if row['name'].startswith('native-namespace-'):
                self.assertTrue(row['target']['dataPointerIntact'], row['name'])
                self.assertTrue(row['target']['matches'], row['name'])
                self.assertIsNone(row['target']['businessError'], row['name'])
                self.assertIsNone(row['target']['watchError'], row['name'])

    def test_object_reactivity_and_framework_api_gaps_are_not_reclassified_as_pass(self):
        self.assertEqual({row['name'] for row in self.result['gaps']}, {
            'declared-state-object-reactive-identity', 'private-instance-reflection',
            'dollar-key-write-and-public-read', 'public-watch-api'})
        self.assertTrue(all(row['status'] == 'unresolved_not_waived' for row in self.result['gaps']))
        self.assertFalse(self.result['production_admission_eligible'])
        self.assertFalse(self.result['arbitrary_public_key_contract_complete'])

    def test_original_engine_and_production_block_are_unchanged(self):
        self.assertEqual(verify_engine(PROJECT / 'engine')['files'], 98)
        value = {'repository': str(PROJECT / 'engine'), 'project': str(PROJECT),
                 'source': '<template><div/></template><script>module.exports={methods:{setValue(k,v){this[k]=v}}}</script>',
                 'action': 'source-contracts'}
        result = subprocess.run(['node', str(PROJECT / 'browser/evaluate.mjs')],
                                input=json.dumps(value).encode(), capture_output=True, timeout=25)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)['error'], 'source_dynamic_key_contract_unsupported')
        self.assertEqual(self.result['model_calls'], 0)
        self.assertEqual(self.result['live_database_writes'], 0)


class PublicInstanceBrowserPrototypeTests(unittest.TestCase):
    def test_native_clicks_still_render_after_public_data_and_watch_are_overwritten(self):
        executable = browser_executable({})
        self.assertTrue(executable, 'A real local browser is required; no fake DOM result')
        result = subprocess.run(['node', str(PROJECT / 'research/public_instance_v1/browser_probe.cjs')],
                                input=json.dumps({'executable': executable}).encode(),
                                capture_output=True, timeout=80, cwd=PROJECT)
        self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', errors='replace'))
        value = json.loads(result.stdout)
        self.assertEqual(value['rendered_texts'], ['0', '1', '11'])
        self.assertTrue(value['target_has_no_vue_runtime'])
        self.assertFalse(value['production_admission_eligible'])
        self.assertFalse(value['generated_SFC_loaders_changed'])
        self.assertEqual(value['errors'], [])


if __name__ == '__main__':
    unittest.main()
