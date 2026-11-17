"""Research candidate only: pinned upstream stays unchanged, known failures stay sealed."""
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
    result = subprocess.run(['node', str(PROJECT / 'research/public_instance_v7' / name)], cwd=PROJECT,
                            input=json.dumps(payload).encode() if payload else None,
                            capture_output=True, timeout=100)
    if result.returncode:
        raise AssertionError(result.stderr.decode('utf-8', errors='replace'))
    return json.loads(result.stdout)


class KeyedCandidateTests(unittest.TestCase):
    def test_transform_rejects_unknown_source_and_version_and_is_deterministic(self):
        script = r"""
const assert=require('node:assert/strict'), fs=require('node:fs');
const candidate=require('./research/public_instance_v7/san_candidate.cjs');
const upstream=fs.readFileSync('./engine/node_modules/san/dist/san.dev.js','utf8');
const a=candidate.buildCandidate(upstream),b=candidate.buildCandidate(upstream);
assert.equal(a.content,b.content);assert.equal(a.candidate_sha256,b.candidate_sha256);
assert.notEqual(a.candidate_sha256,a.upstream_sha256);
assert.throws(()=>candidate.buildCandidate(upstream+' '),/fingerprint_mismatch/);
assert.throws(()=>candidate.buildCandidate(upstream,'3.15.7'),/fingerprint_mismatch/);
assert.equal(candidate.loadCandidate().candidate_sha256,a.candidate_sha256);
console.log(JSON.stringify({deterministic:true,upstream:a.upstream_sha256}));
"""
        result = subprocess.run(['node', '-e', script], cwd=PROJECT, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertTrue(json.loads(result.stdout)['deterministic'])

    def test_old_seals_and_185_production_files_are_unchanged(self):
        for version in ['v1', 'v2', 'v3', 'v4', 'v5', 'v6']:
            directory = PROJECT / f'docs/verification/2026-11-17_public_instance_proxy_{version}'
            sums = json.loads((directory / 'SHA256SUMS.json').read_bytes())
            for name, digest in sums.items():
                self.assertEqual(sha256((directory / name).read_bytes()).hexdigest(), digest)
                if name.endswith(('.cjs', '.py')):
                    current = PROJECT / ('tests' if name.endswith('.py') else f'research/public_instance_{version}') / name
                    self.assertEqual(sha256(current.read_bytes()).hexdigest(), digest, str(current))
        baseline = json.loads((PROJECT / 'docs/verification/2026-11-17_standalone_refactor/standalone.json').read_bytes())
        self.assertEqual(len(baseline['implementation_sha256']), 185)
        for name, digest in baseline['implementation_sha256'].items():
            self.assertEqual(sha256((PROJECT / name).read_bytes()).hexdigest(), digest, name)

    def test_non_dom_compatibility_and_existing_guards_are_preserved(self):
        report = execute('compatibility.cjs')
        self.assertEqual(report['matched_cases'], 94)
        self.assertEqual(report['gaps'][0]['name'], 'private-instance-renderer-vnode-graph')
        self.assertTrue(report['node_render_barrier_is_test_double'])
        writes = execute('native_writes.cjs')
        self.assertEqual(writes['matched_cases'], 5)
        self.assertEqual(len(writes['controls']), 8)
        self.assertTrue(all(writes['controls'].values()))
        guards = execute('owner_controls.cjs')
        self.assertEqual(len(guards['controls']), 10)
        self.assertTrue(all(guards['controls'].values()))


class KeyedCandidateBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.executable = browser_executable({})
        if not cls.executable:
            raise AssertionError('A real browser is required')
        cls.before = execute('../public_instance_v6/browser_probe.cjs', {'executable': cls.executable})
        cls.after = execute('browser_probe.cjs', {'executable': cls.executable})
        cls.native = execute('keyed_browser_probe.cjs', {'executable': cls.executable})

    def test_keyed_tree_gap_closes_in_proxy_and_native_control(self):
        self.assertEqual(self.before['matched_cases'], 3)
        self.assertEqual(self.after['matched_cases'], 4)
        self.assertTrue(all(row['equal'] for row in self.after['cases']))
        self.assertEqual(self.after['errors'], [])
        self.assertEqual(self.before['observations'][1]['nativeKeyControl'],
                         {'bSame': False, 'cSame': True, 'bDisposed': True, 'dom': ['c:1', 'b:0']})
        self.assertEqual(self.after['observations'][1]['nativeKeyControl'],
                         {'bSame': True, 'cSame': True, 'bDisposed': False, 'dom': ['c:1', 'b:1']})
        self.assertFalse(self.after['production_admission_eligible'])
        self.assertFalse(self.after['arbitrary_public_key_contract_complete'])
        self.assertFalse(self.after['dynamic_child_prop_updates_verified'])

    def test_native_thirteen_updates_preserve_identity_state_props_index_and_listener(self):
        self.assertEqual(self.native['matched_cases'], 2)
        self.assertEqual(self.native['errors'], [])
        self.assertFalse(self.native['cases'][0]['before_equal'])
        self.assertTrue(self.native['cases'][1]['before_equal'])
        steps = self.native['cases'][0]['candidate']['steps']
        self.assertEqual(len(steps), 13)
        self.assertTrue(all(row['same'] for step in steps for row in step['retained']))
        self.assertEqual(self.native['observations'][2]['runtime'], {'vue': False, 'kernel': False})
        self.assertFalse(self.native['dynamic_proxy_child_props_verified'])
        # Raw San still disposes a parent subtree in a different final order. The
        # v6 owner bridge, not this native keyed patch, handles that separate gap.
        self.assertFalse(self.native['native_disposal_order']['equal'])
        self.assertEqual(self.native['native_disposal_order']['upstream'],
                         self.native['native_disposal_order']['candidate'])

    def test_unsafe_shapes_and_keys_decline_before_native_dom_or_instance_changes(self):
        controls = self.native['observations'][2]['controls']
        self.assertEqual(len(controls), 9)
        for row in controls:
            self.assertIn(row['message'], ['research_keyed_component_shape_unsupported',
                                           'research_keyed_component_key_unsupported'], row)
            self.assertTrue(row['domUnchanged'], row)
            self.assertTrue(row['instancesUnchanged'], row)

    def test_candidate_also_passes_existing_root_schedule_and_real_controls(self):
        root = execute('root_browser_probe.cjs', {'executable': self.executable})
        scheduling = execute('scheduling_browser_probe.cjs', {'executable': self.executable})
        controls = execute('controls_browser_probe.cjs', {'executable': self.executable})
        self.assertEqual(root['matched_cases'], 6)
        self.assertEqual(scheduling['matched_cases'], 8)
        self.assertEqual(len(controls['observations'][1]['watches']), 7)
        for report in [root, scheduling, controls]:
            self.assertEqual(report['errors'], [])
            self.assertEqual(report['san_candidate']['candidate_sha256'],
                             self.after['san_candidate']['candidate_sha256'])


if __name__ == '__main__':
    unittest.main()
