"""Synthetic browser controls for the real-component page adapter/full-page path."""
import argparse
import json
from pathlib import Path
import subprocess

from migration_pipeline.prepare_frozen_component_browser_v1 import ROOT, RUNTIMES, readonly_baseline


def controls(output_dir):
    readonly_baseline()
    output = Path(output_dir).resolve()
    if output.exists():
        raise FileExistsError('Never overwrite controls')
    pages, manifests = [], {}
    root_template = '<main class="parent"><p class="inside own">own</p><leaf-box/></main>'
    leaf_template = '<aside class="leaf"><span class="inside">child default</span></aside>'
    for framework in ['vue', 'san']:
        ext = '.vue' if framework == 'vue' else '.san'
        if framework == 'vue':
            root_script = "const Leaf=require('./Leaf.vue');module.exports={components:{'leaf-box':Leaf}};"
            leaf_script = 'module.exports={};'
            leaf_style = '<style scoped>.inside{color:rgb(0,0,255)}</style>'
            root_style = '<style scoped>.inside{color:rgb(255,0,0)}.leaf{padding:10px;border:1px solid black}</style>'
        else:
            root_script = "const san=require('san'),Leaf=require('./Leaf.san');module.exports=san.defineComponent({components:{'leaf-box':Leaf}});"
            leaf_script = "const san=require('san');module.exports=san.defineComponent({});"
            leaf_style = '<style>.leaf .inside{color:rgb(0,0,255)}</style>'
            root_style = '<style>.own{color:rgb(255,0,0)}.leaf{padding:10px;border:1px solid black}</style>'
        spec = {'framework': framework, 'main': 'Root' + ext,
                # Leaf styles are emitted FIRST. Dropping parent scoping would make the child RED.
                'modules': [{'id': 'Leaf' + ext, 'source': '<template>' + leaf_template + '</template><script>' + leaf_script + '</script>' + leaf_style, 'dependencies': {}},
                            {'id': 'Root' + ext, 'source': '<template>' + root_template + '</template><script>' + root_script + '</script>' + root_style,
                             'dependencies': {'./Leaf' + ext: 'Leaf' + ext}}],
                'props': {}, 'ready': {'fields': [], 'equals': {}, 'minLengths': {}}}
        proc = subprocess.run(['node', str(ROOT / 'migration_pipeline/utils/component_page_adapter_v1.cjs')], cwd=ROOT,
                              input=json.dumps({'spec': spec, 'runtime': (ROOT / RUNTIMES[framework][0]).read_text(encoding='utf-8')}),
                              capture_output=True, text=True, encoding='utf-8', timeout=30, check=True)
        built = json.loads(proc.stdout)
        name = 'module_' + framework
        pages.append({'name': name, 'html': built['html'], 'selectors': {'root': '.parent', 'own': '.own', 'child': '.leaf .inside', 'leaf': '.leaf'}})
        manifests[name] = {'spec': spec, 'manifest': built['manifest']}

    def tall(name, width, height):
        return {'name': name, 'html': '<!doctype html><link rel="icon" href="data:,"><style>body{margin:0}main{position:relative;background:#ddeeff;width:' + str(width) + 'px;height:' + str(height) + 'px}footer{position:absolute;bottom:0;height:40px;width:100px;background:red}</style><main><footer>bottom</footer></main><script>window.__visualReady=true;</script>',
                'selectors': {'root': 'main', 'bottom': 'footer'}}

    pages += [tall('tall_a', 1200, 1200), tall('tall_b', 1200, 1300),
              tall('too_many_pixels', 1200, 4000), tall('horizontal_overflow', 2000, 1200)]
    pairs = [{'source': 'module_' + f, 'target': 'module_' + f} for f in ['vue', 'san']]
    pairs += [{'source': 'tall_a', 'target': 'tall_a'}, {'source': 'tall_a', 'target': 'tall_b'},
              {'source': 'too_many_pixels', 'target': 'too_many_pixels'}, {'source': 'horizontal_overflow', 'target': 'horizontal_overflow'}]
    payload = {'outputDir': str(output), 'pages': pages, 'pairs': pairs, 'viewport': {'width': 1280, 'height': 800},
               'capturePolicy': 'full-page', 'thresholds': {'pixelTolerance': 0, 'maxChangedPixelRatio': 0, 'minSSIM': .999999999}}
    proc = subprocess.run(['node', str(ROOT / 'migration_pipeline/run_controlled_browser_pixel_v2.cjs')], cwd=ROOT,
                          input=json.dumps(payload), capture_output=True, text=True, encoding='utf-8', timeout=180)
    if proc.returncode != 2 or proc.stderr:
        raise RuntimeError('Expected negative controls blocked; inspect ' + str(output) + ': ' + proc.stderr)
    result = json.loads(proc.stdout)
    c, p = result['captures'], result['comparisons']
    checks = {
        'vue_declared_sfc_dependency_mounted': p[0]['passed'] and c['module_vue']['componentEvidence']['childComponentCount'] == 1,
        'san_declared_sfc_dependency_mounted': p[1]['passed'] and c['module_san']['componentEvidence']['childComponentCount'] == 1,
        'vue_scoped_parent_does_not_pierce_child': c['module_vue']['styles']['own']['color'] == 'rgb(255, 0, 0)' and c['module_vue']['styles']['child']['color'] == 'rgb(0, 0, 255)',
        'vue_scoped_parent_applies_to_child_root': c['module_vue']['styles']['leaf']['padding-top'] == '10px',
        'full_page_below_fold_captured': p[2]['passed'] and c['tall_a']['extent']['height'] == 1200 and c['tall_a']['styles']['bottom']['rect']['y'] > 800,
        'height_mismatch_not_resized_or_given_fake_ssim': p[3]['eligible'] and not p[3]['passed'] and p[3]['metrics'] is None and p[3]['diff'] is None,
        'full_page_pixel_budget_blocks': c['too_many_pixels']['status'] == 'blocked' and 'pixel budget' in c['too_many_pixels']['error'],
        'horizontal_overflow_blocks': c['horizontal_overflow']['status'] == 'blocked' and 'Horizontal overflow' in c['horizontal_overflow']['error'],
        'negative_page_does_not_erase_other_pages': len(c) == 6 and len(p) == 6 and p[0]['passed'] and p[1]['passed'],
    }
    with (output / 'adapter_controls.json').open('x', encoding='utf-8') as stream:
        json.dump({'checks': checks, 'allPassed': all(checks.values()), 'moduleManifests': manifests}, stream, ensure_ascii=False, indent=2)
    return checks


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    checks = controls(args.output_dir)
    print(json.dumps(checks, indent=2))
    if not all(checks.values()):
        raise SystemExit(1)
