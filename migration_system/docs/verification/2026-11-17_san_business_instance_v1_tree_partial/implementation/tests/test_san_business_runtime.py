"""Real San business receiver/emitter; these tests do not enable the main Worker."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import unittest
import importlib.util
from copy import deepcopy
import tempfile

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'src'))
from card_migration_system.runtime import browser_executable


def cli(payload):
    result = subprocess.run(['node', str(PROJECT / 'runtime/san_business_v1/cli.cjs')],
                            input=json.dumps(payload).encode(), cwd=PROJECT, capture_output=True, timeout=30)
    return result.returncode, json.loads(result.stdout)


def probe(name, payload=None):
    result = subprocess.run(['node', str(PROJECT / 'runtime/san_business_v1' / name)],
                            input=json.dumps(payload).encode() if payload else None,
                            cwd=PROJECT, capture_output=True, timeout=100)
    if result.returncode:
        raise AssertionError(result.stderr.decode('utf-8', errors='replace'))
    return json.loads(result.stdout)


SOURCE = '<template><button @click="inc">{{count}}</button></template><script>export default {data(){return {count:0}},methods:{inc(){this.count++},setValue(k,v){this[k]=v}}}</script>'
TARGET = '<template><button on-click="inc">{{count}}</button></template><script>module.exports={};</script>'


class SanBusinessCompilerTests(unittest.TestCase):
    def test_source_metadata_and_portable_export_are_automatic_and_bound(self):
        code, result = cli({'action': 'compile', 'source': SOURCE, 'code': TARGET})
        self.assertEqual(code, 0, result)
        self.assertEqual(result['manifest']['contract_id'], 'san-business-instance-v1')
        self.assertEqual(result['manifest']['source_sha256'], sha256(SOURCE.encode()).hexdigest())
        self.assertEqual(result['manifest']['code_sha256'], sha256(result['code'].encode()).hexdigest())
        self.assertFalse(result['manifest']['vue_renderer_used'])
        self.assertFalse(result['manifest']['vue_component_runtime_used'])
        self.assertTrue(result['manifest']['standalone_reactivity_kernel_used'])
        self.assertNotIn('research/public_instance', result['code'])
        self.assertIn('setValue(k,v){this[k]=v}', result['code'])
        manifest = dict(reversed(list(result['manifest'].items())))
        self.assertEqual(cli({'action': 'verify', 'source': SOURCE, 'code': result['code'], 'manifest': manifest})[1]['status'], 'completed')

    def test_tampered_code_manifest_and_source_are_rejected(self):
        _, result = cli({'action': 'compile', 'source': SOURCE, 'code': TARGET})
        for code, source, manifest in [
            (result['code'].replace('count:0', 'count:7'), SOURCE, result['manifest']),
            (result['code'], SOURCE.replace('count:0', 'count:7'), result['manifest']),
            (result['code'], SOURCE, {**result['manifest'], 'source_sha256': '0' * 64}),
        ]:
            self.assertEqual(cli({'action': 'verify', 'source': source, 'code': code, 'manifest': manifest})[1]['status'], 'fail')

    def test_private_reads_this_escapes_eval_and_unimplemented_options_block_explicitly(self):
        cases = [
            SOURCE.replace('this.count++', 'return this.$.vnode'),
            SOURCE.replace('this.count++', 'return this["_"]'),
            SOURCE.replace('this.count++', 'return this[key]'),
            SOURCE.replace('this.count++', 'return this'),
            SOURCE.replace('this.count++', 'return Vue.createApp({})'),
            SOURCE.replace('this.count++', 'return new Function("return 3")()'),
            SOURCE.replace('data(){', 'mixins:[],data(){'),
        ]
        for source in cases:
            code, report = cli({'action': 'inspect', 'source': source})
            self.assertEqual(code, 2, report)
            self.assertEqual(report['status'], 'blocked')
        # Function as a declared prop type is not executing the Function constructor.
        self.assertEqual(cli({'action': 'inspect', 'source': SOURCE.replace('data(){', 'props:{callback:Function},data(){')})[0], 0)

    def test_unknown_generated_handlers_are_not_silently_accepted(self):
        code, report = cli({'action': 'compile', 'source': SOURCE, 'code': TARGET.replace('on-click="inc"', 'on-click="invented"')})
        self.assertEqual(code, 2, report)
        self.assertEqual(report['error'], 'business_target_unknown_event_handler')

    def test_automatic_tree_rejects_missing_children_and_private_child_dependencies(self):
        for script, expected in [
            ('export default {components:{Child:Missing}}', 'business_component_definition_not_static'),
            ('const Child={template:"<b>child</b>",mounted(){return this.$.vnode}};export default {components:{Child}}', 'source_private_runtime_dependency_unsupported'),
            ('const Child={};export default {components:{Child}}', 'business_inline_component_template_required'),
        ]:
            source = '<template><child/></template><script>' + script + '</script>'
            code, report = cli({'action': 'inspect', 'source': source})
            self.assertEqual(code, 2, report)
            self.assertEqual(report['error'], expected)

    def test_identity_projection_requires_exact_verified_keys_and_keeps_raw_evidence(self):
        source = SOURCE.replace('<button @click="inc">', '<button v-for="item in items" :key="item.id" @click="inc">')
        target = TARGET.replace('<button on-click="inc">', '<button s-for="item in items trackBy item.id" on-click="inc">')
        _, result = cli({'action': 'compile', 'source': source, 'code': target})
        self.assertEqual(result['status'], 'completed', result)
        for broken in [target.replace('trackBy item.id', ''), target.replace('trackBy item.id', 'trackBy item.name')]:
            self.assertEqual(cli({'action': 'compile', 'source': source, 'code': broken})[1]['error'], 'business_loop_key_mismatch')
        spec = importlib.util.spec_from_file_location('projection', PROJECT / 'runtime/san_business_v1/identity_projection.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        raw = {'label': '#root', 'children': [{'label': 'button|binding:key|directive:for', 'children': []}]}
        before = deepcopy(raw)
        canonical, changes = module.project_tree(raw, result['manifest']['element_policies'], source=True)
        self.assertEqual(raw, before)
        self.assertEqual(canonical['children'][0]['label'], 'button|directive:for|identity:item.id')
        self.assertEqual(len(changes), 1)

    def test_ninety_two_business_cases_and_private_exclusions_are_separate(self):
        report = probe('legacy_business_cases.cjs')
        self.assertEqual(report['matched_cases'], 92)
        self.assertEqual(len(report['excluded']), 2)
        self.assertTrue(all(case['equal'] for case in report['cases']))
        self.assertFalse(report['arbitrary_public_key_contract_complete'])
        self.assertFalse(report['production_admission_eligible'])

    def test_shared_kernel_and_unsupported_renderer_callbacks_have_explicit_guards(self):
        report = probe('controls.cjs')
        self.assertEqual(report['status'], 'finite_controls_match')
        self.assertEqual(len(report['cases']), 4)
        self.assertTrue(all(row['equal'] for row in report['cases']))
        self.assertFalse(report['production_admission_eligible'])

    def test_offline_export_preserves_exact_utf8_bytes_on_windows(self):
        spec = importlib.util.spec_from_file_location('replay', PROJECT / 'scripts/replay_san_business.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        (PROJECT / 'var').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=PROJECT / 'var') as temporary:
            source = SOURCE.replace('</template>', '</template>\r\n')
            output = Path(temporary) / 'export'
            result = module.replay(source, TARGET, output)
            manifest = json.loads((output / 'manifest.json').read_bytes())
            self.assertEqual(manifest['source_sha256'], sha256((output / 'source.vue').read_bytes()).hexdigest())
            self.assertEqual(manifest['code_sha256'], sha256((output / 'target.san').read_bytes()).hexdigest())
            self.assertEqual((output / 'source.vue').read_bytes(), source.encode())
            self.assertFalse(result['production_admission_eligible'])


class SanBusinessBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        executable = browser_executable({})
        if not executable:
            raise AssertionError('Real local browser is required')
        cls.compiled = probe('browser_probe.cjs', {'executable': executable})
        cls.public = probe('public_api_probe.cjs', {'executable': executable})
        cls.values = probe('value_probe.cjs', {'executable': executable})
        cls.tree = probe('tree_probe.cjs', {'executable': executable})

    def test_compiled_source_not_manual_state_metadata_matches_real_vue_controls(self):
        report = self.compiled
        self.assertTrue(report['equal'], report)
        self.assertEqual(report['errors'], [])
        self.assertTrue(report['metadata_from_actual_source'])
        target = report['observations'][1]
        self.assertTrue(target['rawIdentity'])
        self.assertTrue(all(target['keys']))
        self.assertEqual(target['conversions'], ['string'])
        self.assertEqual(target['typed'], 'typed')
        self.assertNotEqual(target['beforeForce'], target['afterForce'])
        self.assertFalse(target['runtime']['vue'])
        self.assertEqual(target['attributes'], [
            {'class': '', 'value': 'initial', 'checked': None},
            {'class': 'chosen', 'value': 'typed', 'checked': ''}])
        self.assertIn(['set', 'unused', 6], target['reads'])
        self.assertFalse(report['production_admission_eligible'])

    def test_events_and_real_parent_props_include_observable_watch_hook_dom_order(self):
        report = self.public
        self.assertEqual(report['status'], 'finite_public_api_cases_match')
        self.assertEqual(len(report['cases']), 6)
        self.assertTrue(all(case['equal'] for case in report['cases']), report)
        self.assertEqual(report['errors'], [])
        row = report['cases'][1]['target']
        self.assertEqual([item['dom'] for item in row['seen']], ['old:0:1', 'old:0:1', 'new:0:1', 'new:0:1', 'new:0:2'])
        self.assertTrue(row['parentSame'] and row['rootSame'] and row['itemSame'])
        self.assertEqual(report['cases'][2]['target'], {'registrationError': None, 'calls': [], 'count': 3, 'empty': True})
        self.assertEqual(report['cases'][4]['target']['attrs'], ['data-note', 'onClick', 'onlower'])
        self.assertEqual(report['cases'][4]['target']['name'], 'hyphenated')
        self.assertFalse(report['compiled_source_proof'])
        self.assertFalse(report['observations'][1]['runtime']['vue'])

    def test_compiled_interpolation_and_input_preserve_non_string_values(self):
        report = self.values
        self.assertEqual(report['status'], 'finite_value_cases_match', report)
        self.assertEqual(len(report['cases']), 13)
        self.assertEqual(report['errors'], [])
        self.assertTrue(all(row['equal'] for row in report['cases']), report)
        self.assertFalse(report['observations'][1]['runtime']['vue'])
        self.assertFalse(report['production_admission_eligible'])

    def test_automatic_source_tree_events_once_refs_and_ancestor_errors(self):
        report = self.tree
        self.assertEqual(report['status'], 'compiled_source_tree_matches', report)
        self.assertEqual(report['errors'], [])
        self.assertTrue(report['manifest']['source_component_tree_compiled'])
        self.assertTrue(report['source_component_tree_automatic'])
        target = report['observations'][1]
        self.assertEqual(target['count'], 4)
        self.assertEqual(target['log'], ['1:old', 'once:1', '2:old', '3:new', 'captured'])
        self.assertEqual(target['attrs'], {'data-note': 'second'})
        self.assertTrue(target['optionsSame'])
        self.assertTrue(target['parent'] and target['root'] and target['empty'])
        self.assertIn(['capture', 'RangeError', 'child failure', 'new', 'native event handler'], target['trace'])
        self.assertEqual(target['trace'].count(['replacement', True]), 1)
        self.assertIn(['new-handler', 4, 'replacement', True], target['trace'])
        self.assertFalse(target['runtime']['vue'])
        self.assertFalse(report['production_admission_eligible'])


if __name__ == '__main__':
    unittest.main()
