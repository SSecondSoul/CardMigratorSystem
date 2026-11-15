"""Bounded packaging contracts plus separately recorded browser evidence.
Never launch browsers or mutate frozen components during test discovery.
"""
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'data/experiments/analysis/frozen_component_browser_v1_20261115'


def node(code):
    proc = subprocess.run(['node', '-'], cwd=ROOT, input=code, text=True,
                          encoding='utf-8', capture_output=True, timeout=30)
    if proc.returncode:
        raise AssertionError(proc.stderr)
    return json.loads(proc.stdout)


class ComponentPackagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.values = node(r"""
const a=require('./migration_pipeline/utils/component_page_adapter_v1.cjs');
const sfc=(script='module.exports={};',style='<style scoped>.root{color:red}</style>')=>'<template><main class="root"><span>{{ value }}</span></main></template><script>'+script+'</script>'+style;
const base=()=>({framework:'vue',main:'Root.vue',modules:[{id:'Root.vue',source:sfc(),dependencies:{}}]});
const reject=fn=>{try{fn();return null;}catch(e){return e.message;}};
const check=change=>{const s=base();change(s);return reject(()=>a.prepareModules(s));};
const positive=a.prepareModules(base());
const local=base();local.modules[0]={id:'Root.vue',source:sfc("const Leaf=require('./Leaf');module.exports={components:{Leaf}};"),dependencies:{'./Leaf':'Leaf.vue'}};local.modules.push({id:'Leaf.vue',source:sfc(),dependencies:{}});
const script='const sourceBody="unchanged";module.exports={data(){return {value:sourceBody};}};';
const copy=base();copy.modules[0].source=sfc(script);const unchanged=a.prepareModules(copy);
const errors={
 setup:check(s=>s.modules[0].source='<template><main/></template><script setup>const x=1;</script>'),
 esm:check(s=>s.modules[0].source=sfc('export default {};')),
 src:check(s=>s.modules[0].source='<template src="./t.html"></template><script>module.exports={};</script>'),
 preprocess:check(s=>s.modules[0].source=sfc().replace('<style scoped>','<style scoped lang="scss">')),
 module:check(s=>s.modules[0].source=sfc().replace('<style scoped>','<style module>')),
 deep:check(s=>s.modules[0].source=sfc('module.exports={};','<style scoped>:deep(.x){color:red}</style>')),
 bind:check(s=>s.modules[0].source=sfc('module.exports={};','<style scoped>.x{color:v-bind(color)}</style>')),
 cssImport:check(s=>s.modules[0].source=sfc('module.exports={};','<style>@import "https://invalid.example/x.css";</style>')),
 url:check(s=>s.modules[0].source=sfc('module.exports={};','<style>.x{background:url(./photo.png)}</style>')),
 dynamicRequire:check(s=>s.modules[0].source=sfc('module.exports=require(name);')),
 external:check(s=>s.modules[0].source=sfc("module.exports=require('external-package');")),
 undeclared:check(s=>s.modules[0].source=sfc("module.exports=require('./Leaf');")),
 missingSource:check(s=>{s.modules[0].source=sfc("module.exports=require('./Leaf');");s.modules[0].dependencies={'./Leaf':'Leaf.vue'};}),
 unused:check(s=>s.modules[0].dependencies={'./Leaf':'Leaf.vue'}),
 duplicate:check(s=>s.modules.push(s.modules[0])),
 unreachable:check(s=>s.modules.push({id:'Other.vue',source:sfc(),dependencies:{}})),
 traversal:check(s=>s.modules[0].id='../Root.vue'),
 sanScoped:check(s=>{s.framework='san';s.main='Root.san';s.modules[0].id='Root.san';}),
 circular:reject(()=>{const x=structuredClone(local);x.modules[1].source=sfc("module.exports=require('./Root');");x.modules[1].dependencies={'./Root':'Root.vue'};a.prepareModules(x);})
};
console.log(JSON.stringify({errors,scope:positive.manifest[0].scopeId,compiledCSS:positive.styles[0].css,localModules:a.prepareModules(local).manifest.length,
 unchanged:unchanged.modules['Root.vue'].script.trim()===script,template:positive.modules['Root.vue'].template,
 sanRuntime:require('san').version}));
""")

    def test_ordinary_scoped_css_not_removed(self):
        self.assertTrue(self.values['scope'].startswith('data-v-'))
        self.assertIn('[' + self.values['scope'] + ']', self.values['compiledCSS'])

    def test_business_script_not_rewritten(self):
        self.assertTrue(self.values['unchanged'])

    def test_full_root_template_preserved(self):
        self.assertEqual(self.values['template'], '<main class="root"><span>{{ value }}</span></main>')

    def test_declared_dependency_sources_present(self):
        self.assertEqual(self.values['localModules'], 2)

    def test_pinned_san_runtime(self):
        self.assertEqual(self.values['sanRuntime'], '3.15.6')

    def test_script_setup_rejected(self): self.assertTrue(self.values['errors']['setup'])
    def test_esm_rejected(self): self.assertTrue(self.values['errors']['esm'])
    def test_external_block_not_silently_ignored(self): self.assertTrue(self.values['errors']['src'])
    def test_preprocessor_rejected(self): self.assertTrue(self.values['errors']['preprocess'])
    def test_css_module_rejected(self): self.assertTrue(self.values['errors']['module'])
    def test_deep_scope_not_approximated(self): self.assertTrue(self.values['errors']['deep'])
    def test_css_dynamic_bind_rejected(self): self.assertTrue(self.values['errors']['bind'])
    def test_css_import_rejected(self): self.assertTrue(self.values['errors']['cssImport'])
    def test_external_asset_not_mocked(self): self.assertTrue(self.values['errors']['url'])
    def test_dynamic_dependency_rejected(self): self.assertTrue(self.values['errors']['dynamicRequire'])
    def test_external_package_rejected(self): self.assertTrue(self.values['errors']['external'])
    def test_undeclared_dependency_rejected(self): self.assertTrue(self.values['errors']['undeclared'])
    def test_missing_dependency_source_rejected(self): self.assertTrue(self.values['errors']['missingSource'])
    def test_unused_mapping_rejected(self): self.assertTrue(self.values['errors']['unused'])
    def test_duplicate_module_rejected(self): self.assertTrue(self.values['errors']['duplicate'])
    def test_unreachable_source_rejected(self): self.assertTrue(self.values['errors']['unreachable'])
    def test_path_traversal_rejected(self): self.assertTrue(self.values['errors']['traversal'])
    def test_san_scoped_not_faked(self): self.assertTrue(self.values['errors']['sanScoped'])
    def test_circular_graph_not_partially_loaded(self): self.assertTrue(self.values['errors']['circular'])


class RecordedPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((BASE / 'prepared/manifest.json').read_text(encoding='utf-8'))

    def test_first_per_stratum_not_result_selected(self):
        self.assertEqual([r['component'] for r in self.manifest['selection']],
                         ['VolumeControl', 'BatchRenamer', 'AnalyticsDashboard'])

    def test_ten_pages_and_five_declared_scenarios(self):
        self.assertEqual(len(self.manifest['pages']), 10)
        self.assertEqual(len(self.manifest['scenarios']), 5)

    def test_no_default_props_injected(self):
        for name, page in self.manifest['pages'].items():
            if '_default_' in name:
                self.assertEqual(page['props'], {})
            self.assertTrue(page['boundary']['defaultPropsNotInjected'])
            self.assertTrue(page['boundary']['businessBodiesUnmodified'])

    def test_local_runtime_no_cdn(self):
        for page in self.manifest['pages'].values():
            self.assertTrue((ROOT / page['runtime']['path']).is_file())

    def test_no_model_batch_or_score_claim(self):
        self.assertFalse(self.manifest['productionThresholdsSelected'])
        self.assertFalse(self.manifest['historicalScoresChanged'])
        self.assertEqual(self.manifest['modelCalls'], 0)


class RecordedFullComponentBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = json.loads((BASE / 'corrected_run/result.json').read_text(encoding='utf-8'))
        cls.repeat = json.loads((BASE / 'repeat/result.json').read_text(encoding='utf-8'))
        cls.captures = cls.result['captures']

    def test_all_ten_full_pages_mounted_and_stable(self):
        self.assertEqual(len(self.captures), 10)
        self.assertTrue(all(c['status'] == 'captured' and c['stable'] for c in self.captures.values()))

    def test_four_simple_medium_scenes_exactly_match(self):
        for pair in self.result['comparisons'][:4]:
            self.assertTrue(pair['eligible'] and pair['passed'])
            self.assertEqual(pair['metrics']['changedPixels'], 0)
            self.assertEqual(pair['styleChanges'], [])

    def test_volume_source_default_and_explicit_props(self):
        for suffix in ['vue', 'san']:
            for scenario, value in [('volume_default_', 45), ('volume_prop_', 60)]:
                fields = self.captures[scenario + suffix]['componentEvidence']['fields']
                self.assertEqual(fields['volume'], value)
                self.assertEqual(fields['volumeLabel'], str(value) + '%')

    def test_rename_source_default_and_explicit_props(self):
        for suffix in ['vue', 'san']:
            for scenario, count in [('rename_default_', 3), ('rename_prop_', 2)]:
                fields = self.captures[scenario + suffix]['componentEvidence']['fields']
                self.assertEqual(len(fields['currentFiles']), count)
                self.assertEqual(len(fields['previews']), count)

    def test_analytics_complete_child_tree_and_loaded_business_data(self):
        source = self.captures['analytics_default_vue']['componentEvidence']
        target = self.captures['analytics_default_san']['componentEvidence']
        self.assertEqual(source['childComponentCount'], 7)
        self.assertEqual(target['childComponentCount'], 7)
        self.assertEqual(source['fields'], target['fields'])
        self.assertEqual(len(source['fields']['chartData']), 30)
        self.assertEqual(len(source['fields']['activities']), 15)

    def test_source_warning_not_called_target_migration_failure_or_pass(self):
        self.assertFalse(self.captures['analytics_default_vue']['clean'])
        self.assertTrue(self.captures['analytics_default_san']['clean'])
        self.assertEqual(len(self.result['exceptions']), 0)
        self.assertEqual(len(self.result['consoleErrors']), 10)
        for record in self.result['consoleErrors']:
            self.assertEqual(record['args'][0]['value'], 'Vue component warning')
            self.assertIn('Duplicate keys detected:', record['args'][1]['value'])
        self.assertFalse(self.result['passed'])

    def test_actual_full_page_height_mismatch_not_cropped_or_scored_as_ssim(self):
        pair = self.result['comparisons'][-1]
        self.assertEqual(pair['dimensions'], {'source': [1280, 1326], 'target': [1280, 1625]})
        self.assertIsNone(pair['metrics'])
        self.assertIsNone(pair['diff'])
        self.assertFalse(pair['passed'])
        self.assertEqual(len(pair['styleChanges']), 7)

    def test_independent_repeat_all_screenshots_and_observations_identical(self):
        self.assertEqual(self.result['browser'], self.repeat['browser'])
        for name, capture in self.captures.items():
            other = self.repeat['captures'][name]
            self.assertEqual(capture['screenshotSha256'], other['screenshotSha256'])
            self.assertEqual(capture['componentEvidence'], other['componentEvidence'])
            self.assertEqual(capture['styles'], other['styles'])

    def test_nine_synthetic_adapter_capture_controls(self):
        controls = json.loads((BASE / 'controls/adapter_controls.json').read_text(encoding='utf-8'))
        self.assertTrue(controls['allPassed'])
        self.assertEqual(len(controls['checks']), 9)
        self.assertTrue(all(controls['checks'].values()))

    def test_scrollbar_counterfactual_explains_harness_instability(self):
        counter = json.loads((BASE / 'gutter_counterfactual/result.json').read_text(encoding='utf-8'))
        for name, capture in counter['captures'].items():
            self.assertFalse(capture['stable'])
            self.assertEqual(capture['repeatChangedPixels'], 0)
            self.assertEqual(set(capture['changedObservationKeys']), {'styles', 'extent'})
            self.assertEqual(capture['extent']['width'], 1265)
            self.assertEqual(capture['repeatObservation']['extent']['width'], 1280)
            self.assertTrue(self.captures[name]['stable'])
        initial = json.loads((BASE / 'run/result.json').read_text(encoding='utf-8'))
        self.assertFalse(initial['captures']['analytics_default_vue']['stable'])


if __name__ == '__main__':
    unittest.main()
