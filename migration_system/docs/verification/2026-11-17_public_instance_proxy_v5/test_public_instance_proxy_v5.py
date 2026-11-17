"""Finite root-owner research. No production admission or complete Vue tree claim."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import unittest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'src'))
from card_migration_system.runtime import browser_executable


def execute(name, payload=None):
    result = subprocess.run(['node', str(PROJECT / 'research/public_instance_v5' / name)], cwd=PROJECT,
                            input=json.dumps(payload).encode() if payload else None,
                            capture_output=True, timeout=90)
    if result.returncode:
        raise AssertionError(result.stderr.decode('utf-8', errors='replace'))
    return json.loads(result.stdout)


class RootOwnerNativeTests(unittest.TestCase):
    def test_original_non_dom_94_cases_and_private_graph_gap_remain(self):
        report = execute('compatibility.cjs')
        self.assertEqual(report['matched_cases'], 94)
        self.assertEqual(report['gaps'][0]['name'], 'private-instance-renderer-vnode-graph')
        self.assertTrue(report['node_render_barrier_is_test_double'])
        self.assertFalse(report['production_admission_eligible'])

    def test_native_writes_keep_all_five_cases_and_eight_controls(self):
        report = execute('native_writes.cjs')
        self.assertEqual(report['matched_cases'], 5)
        self.assertEqual(len(report['controls']), 8)
        self.assertTrue(all(report['controls'].values()))

    def test_owner_boundary_controls_are_real_checks_not_blanket_admission(self):
        report = execute('owner_controls.cjs')
        self.assertEqual(len(report['controls']), 10)
        self.assertTrue(all(report['controls'].values()))
        self.assertFalse(report['arbitrary_public_key_contract_complete'])

    def test_prior_evidence_and_production_baseline_are_unchanged(self):
        for version in ['v1','v2','v3','v4']:
            evidence = PROJECT / f'docs/verification/2026-11-17_public_instance_proxy_{version}'
            sums = json.loads((evidence / 'SHA256SUMS.json').read_bytes())
            for name, digest in sums.items():
                self.assertEqual(sha256((evidence / name).read_bytes()).hexdigest(), digest)
            self.assertEqual(sha256((PROJECT / f'research/public_instance_{version}/runtime.cjs').read_bytes()).hexdigest(), sums['runtime.cjs'])
        baseline = json.loads((PROJECT / 'docs/verification/2026-11-17_standalone_refactor/standalone.json').read_bytes())
        for name, digest in baseline['implementation_sha256'].items():
            self.assertEqual(sha256((PROJECT / name).read_bytes()).hexdigest(), digest, name)


class RootOwnerBrowserTests(unittest.TestCase):
    def test_native_owner_connection_fixes_six_finite_browser_cases(self):
        executable = browser_executable({})
        self.assertTrue(executable, 'Actual browser required')
        before = execute('browser_probe.cjs', {'executable': executable, 'version': 'v4'})
        after = execute('browser_probe.cjs', {'executable': executable, 'version': 'v5'})
        self.assertFalse(before['owner_connection_available'])
        self.assertEqual(before['matched_cases'], 0)
        self.assertTrue(after['owner_connection_available'])
        self.assertEqual(after['matched_cases'], 6)
        self.assertEqual(after['errors'], [])
        self.assertEqual(after['observations'][1]['runtime'], {'vue': False, 'kernel': True})
        rows = {row['name']: row['target'] for row in after['cases']}
        log = rows['root-hook-order-receiver-dom-and-flags']['log']
        self.assertEqual([entry['name'] for entry in log],
                         ['beforeMount','mounted','beforeUpdate','updated','beforeUpdate','updated','beforeUnmount','unmounted'])
        self.assertTrue(all(entry['receiver'] for entry in log))
        self.assertFalse(log[-1]['scopeActive'])
        self.assertFalse(log[-1]['unmounted'])
        self.assertTrue(rows['root-hook-order-receiver-dom-and-flags']['final']['unmounted'])
        self.assertEqual(rows['native-disposal-stops-owner-watch-and-cleans-once']['log'], [['watch',1,0],['cleanup',1]])
        self.assertEqual(rows['watch-created-in-mounted-belongs-to-owner']['log'], [1,2])
        self.assertFalse(after['production_admission_eligible'])

    def test_render_schedule_and_actual_controls_with_owner_connected(self):
        executable = browser_executable({})
        self.assertTrue(executable, 'Actual browser required')
        scheduling = execute('scheduling_browser_probe.cjs', {'executable': executable})
        self.assertEqual(scheduling['matched_cases'], 8)
        self.assertEqual(scheduling['errors'], [])
        controls = execute('controls_browser_probe.cjs', {'executable': executable})
        self.assertEqual(controls['errors'], [])
        self.assertEqual(controls['observations'][0]['states'], controls['observations'][1]['states'])
        self.assertEqual(len(controls['observations'][1]['watches']), 7)
        self.assertFalse(controls['production_admission_eligible'])


if __name__ == '__main__':
    unittest.main()
