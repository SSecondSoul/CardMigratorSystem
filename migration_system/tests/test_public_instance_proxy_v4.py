"""Render-aware research scheduling: before/after actual browser observations."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import unittest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'src'))
from card_migration_system.runtime import browser_executable
from historical_lineage import assert_production_lineage


def execute(name, payload=None):
    result = subprocess.run(['node', str(PROJECT / 'research/public_instance_v4' / name)], cwd=PROJECT,
                            input=json.dumps(payload).encode() if payload else None,
                            capture_output=True, timeout=90)
    if result.returncode:
        raise AssertionError(result.stderr.decode('utf-8', errors='replace'))
    return json.loads(result.stdout)


class RenderScheduleNativeTests(unittest.TestCase):
    def test_original_94_non_dom_cases_with_explicit_render_double(self):
        report = execute('compatibility.cjs')
        self.assertEqual(report['matched_cases'], 94)
        self.assertTrue(all(case['equal'] for case in report['cases']))
        self.assertTrue(report['node_render_barrier_is_test_double'])
        self.assertEqual(report['gaps'][0]['name'], 'private-instance-renderer-vnode-graph')
        self.assertFalse(report['production_admission_eligible'])

    def test_native_write_cases_and_controls_still_hold(self):
        report = execute('native_writes.cjs')
        self.assertEqual(report['matched_cases'], 5)
        self.assertEqual(len(report['controls']), 8)
        self.assertTrue(all(report['controls'].values()))
        self.assertTrue(report['node_render_barrier_is_test_double'])

    def test_prior_seals_and_production_runtime_remain_unchanged(self):
        for version in ['v1', 'v2', 'v3']:
            directory = PROJECT / f'docs/verification/2026-11-17_public_instance_proxy_{version}'
            sums = json.loads((directory / 'SHA256SUMS.json').read_bytes())
            for name, digest in sums.items():
                self.assertEqual(sha256((directory / name).read_bytes()).hexdigest(), digest)
            self.assertEqual(sha256((PROJECT / f'research/public_instance_{version}/runtime.cjs').read_bytes()).hexdigest(), sums['runtime.cjs'])
        assert_production_lineage(self)


class RenderScheduleBrowserTests(unittest.TestCase):
    def test_v3_failure_is_preserved_and_v4_eight_actual_schedule_cases_match(self):
        executable = browser_executable({})
        self.assertTrue(executable, 'Real browser required')
        old = execute('browser_probe.cjs', {'executable': executable, 'version': 'v3'})
        new = execute('browser_probe.cjs', {'executable': executable, 'version': 'v4'})
        self.assertEqual(old['matched_cases'], 3)
        self.assertEqual(sum(not case['equal'] for case in old['cases']), 5)
        self.assertEqual(new['matched_cases'], 8)
        self.assertTrue(all(case['equal'] for case in new['cases']))
        for report in [old, new]:
            self.assertEqual(report['errors'], [])
            self.assertEqual(report['page_count'], 2)
            self.assertEqual(report['observations'][1]['runtime'], {'vue': False, 'kernel': True})
            self.assertFalse(report['arbitrary_public_key_contract_complete'])
        cases = {case['name']: case for case in new['cases']}
        self.assertEqual(cases['no-watcher-nextTick-observes-render']['target'], {'state': 1, 'dom': '1'})
        self.assertEqual(cases['post-watcher-sidewrite-is-drained-before-nextTick']['target'][-1], ['tick', 2, '2'])
        self.assertEqual(cases['idle-nextTick-does-not-invent-a-render-turn']['target'], ['tick', 'microtask'])
        self.assertEqual(cases['unmount-cancels-watches-but-not-existing-tick-callback']['target'], [['tick', None, True]])

    def test_actual_nested_controls_still_work_with_v4_scheduler(self):
        executable = browser_executable({})
        self.assertTrue(executable, 'Real browser required')
        report = execute('controls_browser_probe.cjs', {'executable': executable})
        self.assertEqual(report['errors'], [])
        self.assertEqual(report['observations'][0]['states'], report['observations'][1]['states'])
        self.assertEqual(len(report['observations'][1]['watches']), 7)
        self.assertFalse(report['production_admission_eligible'])


if __name__ == '__main__':
    unittest.main()
