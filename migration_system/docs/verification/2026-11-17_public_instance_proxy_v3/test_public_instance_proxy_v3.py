"""Research boundary tests; no production admission or real model/database writes."""
import json
from hashlib import sha256
from pathlib import Path
import subprocess
import sys
import unittest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'src'))
from card_migration_system.runtime import browser_executable


class NativeControlPublicInstanceTests(unittest.TestCase):
    def node(self, name):
        result = subprocess.run(['node', str(PROJECT / 'research/public_instance_v3' / name)],
                                cwd=PROJECT, capture_output=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', errors='replace'))
        return json.loads(result.stdout)

    def test_original_94_cases_still_match_and_private_graph_gap_remains(self):
        result = self.node('compatibility.cjs')
        self.assertEqual(result['matched_cases'], 94)
        self.assertTrue(all(row['equal'] for row in result['cases']))
        self.assertEqual(result['gaps'][0]['name'], 'private-instance-renderer-vnode-graph')
        self.assertFalse(result['arbitrary_public_key_contract_complete'])
        self.assertFalse(result['production_admission_eligible'])

    def test_nested_writes_keep_aliases_refs_and_dynamic_paths(self):
        result = self.node('native_writes.cjs')
        self.assertEqual(result['matched_cases'], 5)
        self.assertTrue(all(row['equal'] for row in result['cases']))
        self.assertTrue(all(result['controls'].values()))
        self.assertEqual(len(result['controls']), 8)
        self.assertFalse(result['production_admission_eligible'])

    def test_v1_v2_sealed_sources_remain_unchanged(self):
        for version in ['v1', 'v2']:
            directory = PROJECT / f'docs/verification/2026-11-17_public_instance_proxy_{version}'
            sums = json.loads((directory / 'SHA256SUMS.json').read_bytes())
            for name, digest in sums.items():
                self.assertEqual(sha256((directory / name).read_bytes()).hexdigest(), digest)
            for name in ['runtime.cjs', 'compatibility.cjs', 'browser_probe.cjs']:
                self.assertEqual(sha256((PROJECT / f'research/public_instance_{version}' / name).read_bytes()).hexdigest(), sums[name])


class NativeControlBrowserTests(unittest.TestCase):
    def test_actual_input_checkbox_select_and_literal_dot_bindings(self):
        executable = browser_executable({})
        self.assertTrue(executable, 'A real installed browser is required')
        result = subprocess.run(['node', str(PROJECT / 'research/public_instance_v3/browser_probe.cjs')],
                                cwd=PROJECT, input=json.dumps({'executable': executable}).encode(),
                                capture_output=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', errors='replace'))
        report = json.loads(result.stdout)
        self.assertEqual(report['page_count'], 2)
        self.assertEqual(report['errors'], [])
        self.assertEqual(report['observations'][0]['states'], report['observations'][1]['states'])
        self.assertEqual(len(report['observations'][1]['watches']), 7)
        self.assertEqual(report['observations'][1]['runtime'], {'vue': False, 'kernel': True})
        self.assertFalse(report['production_admission_eligible'])


if __name__ == '__main__':
    unittest.main()
