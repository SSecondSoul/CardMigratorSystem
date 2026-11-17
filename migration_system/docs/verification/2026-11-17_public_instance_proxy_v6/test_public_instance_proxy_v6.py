"""Finite owner trees: assert closed cases AND preserve the native keyed gap."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import unittest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT/'src'))
from card_migration_system.runtime import browser_executable


def execute(name,payload=None):
    result=subprocess.run(['node',str(PROJECT/'research/public_instance_v6'/name)],cwd=PROJECT,
                          input=json.dumps(payload).encode() if payload else None,capture_output=True,timeout=100)
    if result.returncode:
        raise AssertionError(result.stderr.decode('utf-8',errors='replace'))
    return json.loads(result.stdout)


class OwnerTreeNativeTests(unittest.TestCase):
    def test_non_dom_public_keys_and_writes_remain_compatible(self):
        native=execute('compatibility.cjs')
        self.assertEqual(native['matched_cases'],94)
        self.assertEqual(native['gaps'][0]['name'],'private-instance-renderer-vnode-graph')
        self.assertTrue(native['node_render_barrier_is_test_double'])
        writes=execute('native_writes.cjs')
        self.assertEqual(writes['matched_cases'],5)
        self.assertEqual(len(writes['controls']),8)
        self.assertTrue(all(writes['controls'].values()))

    def test_root_guards_still_reject_unknown_parents_and_transitions(self):
        report=execute('owner_controls.cjs')
        self.assertEqual(len(report['controls']),10)
        self.assertTrue(all(report['controls'].values()))
        self.assertFalse(report['production_admission_eligible'])

    def test_old_seals_and_production_are_unchanged(self):
        for version in ['v1','v2','v3','v4','v5']:
            directory=PROJECT/f'docs/verification/2026-11-17_public_instance_proxy_{version}'
            sums=json.loads((directory/'SHA256SUMS.json').read_bytes())
            for name,digest in sums.items():
                self.assertEqual(sha256((directory/name).read_bytes()).hexdigest(),digest)
            self.assertEqual(sha256((PROJECT/f'research/public_instance_{version}/runtime.cjs').read_bytes()).hexdigest(),sums['runtime.cjs'])
        baseline=json.loads((PROJECT/'docs/verification/2026-11-17_standalone_refactor/standalone.json').read_bytes())
        for name,digest in baseline['implementation_sha256'].items():
            self.assertEqual(sha256((PROJECT/name).read_bytes()).hexdigest(),digest,name)


class OwnerTreeBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.executable=browser_executable({})
        if not cls.executable:
            raise AssertionError('A real browser is required')
        cls.before=execute('browser_probe.cjs',{'executable':cls.executable,'version':'v5'})
        cls.after=execute('browser_probe.cjs',{'executable':cls.executable,'version':'v6'})
        cls.rows={row['name']:row for row in cls.after['cases']}

    def test_three_tree_cases_close_with_real_links_dom_and_cleanup(self):
        self.assertEqual(self.before['matched_cases'],0)
        self.assertEqual(self.after['matched_cases'],3)
        self.assertEqual(self.after['errors'],[])
        for name,row in self.rows.items():
            if not name.startswith('keyed-'):
                self.assertTrue(row['equal'],name)
        row=self.rows['parent-child-native-mount-unmount-order-and-links']['target']
        self.assertTrue(all(link['parent'] and link['root'] and link['scope'] for link in row['links']))
        self.assertTrue(row['inactive'])
        self.assertEqual(self.after['observations'][1]['runtime'],{'vue':False,'kernel':True})

    def test_native_keyed_gap_is_preserved_not_reclassified_as_pass(self):
        row=self.rows['keyed-reorder-remove-reinsert-keeps-independent-scopes']
        self.assertFalse(row['equal'])
        self.assertTrue(row['source']['removed']['bSame'])
        self.assertFalse(row['target']['removed']['bSame'])
        control=self.after['observations'][1]['nativeKeyControl']
        self.assertEqual(control,{'bSame':False,'cSame':True,'bDisposed':True,'dom':['c:1','b:0']})
        self.assertFalse(self.after['production_admission_eligible'])
        self.assertFalse(self.after['arbitrary_public_key_contract_complete'])
        self.assertFalse(self.after['dynamic_child_prop_updates_verified'])

    def test_previous_root_schedule_and_controls_still_hold(self):
        root=execute('root_browser_probe.cjs',{'executable':self.executable})
        self.assertEqual(root['matched_cases'],6)
        self.assertEqual(root['errors'],[])
        scheduling=execute('scheduling_browser_probe.cjs',{'executable':self.executable})
        self.assertEqual(scheduling['matched_cases'],8)
        self.assertEqual(scheduling['errors'],[])
        controls=execute('controls_browser_probe.cjs',{'executable':self.executable})
        self.assertEqual(controls['errors'],[])
        self.assertEqual(len(controls['observations'][1]['watches']),7)


if __name__=='__main__':
    unittest.main()
