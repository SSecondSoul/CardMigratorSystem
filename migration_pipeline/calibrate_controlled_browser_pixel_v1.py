"""Calibrate an opt-in evaluator, not migration success. No model/server dependency.

Run from the repository root:
python -m migration_pipeline.calibrate_controlled_browser_pixel_v1 --output-dir <NEW directory>
The runner starts its own ephemeral loopback server and isolated headless Edge.
It never uses the manual pages or marks any existing component/batch as passed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
VUE = ROOT / 'data/experiments/manual_followups/task_manager_async_scope_v7_prepared_20261113/vendor/vue-2.7.16.js'
SAN = ROOT / 'node_modules/san/dist/san.dev.js'
RUNTIME_SHA = {
    'vue': '36b10d3b4920592a4ec26c064c429e9a3dfb4689235fdfc91e1736b681c76786',
    'san': '4b1c4a3a918d91663c0f79a4f77358a9de3c0ee1fbc01dfc47897f8531543134',
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixtures(output_dir):
    for name, path in [('vue', VUE), ('san', SAN)]:
        if digest(path) != RUNTIME_SHA[name]:
            raise RuntimeError('Calibration runtime fingerprint differs: ' + name)
    css = ('html,body{margin:0;background:white;color:#172033;font-family:Arial;font-size:16px}'
           'main{box-sizing:border-box;margin:24px;padding:16px;width:280px;height:160px;'
           'background:#e0f0ff;border:2px solid #224466;border-radius:8px}'
           'h1{font-size:20px;line-height:24px;margin:0 0 12px}p{margin:0;line-height:20px}')
    markup = '<main id="card"><h1 id="title">Visual fixture</h1><p id="value">{{value}}</p></main>'
    value = "Date.now()+' / '+Math.random().toFixed(6)"

    def page(name, script, style=css, runtime=''):
        # Local trusted runtimes only, embedded without external asset requests.
        runtime = runtime.replace('</script', '<\\/script')
        return {'name': name, 'selectors': {'card': '#card', 'title': '#title', 'value': '#value'},
                'html': '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
                        '<link rel="icon" href="data:,"><style>' + style + '</style></head>'
                        '<body><div id="host"></div><script>' + runtime + '</script><script>' + script + '</script></body></html>'}

    plain = ("document.querySelector('#host').innerHTML=" + json.dumps(markup) + ";"
             "document.querySelector('#value').textContent=" + value + ';window.__visualReady=true;')
    pages = [page('baseline', plain), page('identical', plain),
             page('color', plain, css.replace('background:#e0f0ff', 'background:#ffdddd')),
             page('spacing', plain, css.replace('padding:16px', 'padding:24px')),
             page('vue_native', "new Vue({el:'#host',template:" + json.dumps(markup) + ',data(){return {value:' + value + '};}});Vue.nextTick(()=>{window.__visualReady=true;});', runtime=VUE.read_text(encoding='utf-8')),
             page('san_native', 'const C=san.defineComponent({template:' + json.dumps(markup) + ',initData(){return {value:' + value + '};}});new C().attach(document.querySelector(\'#host\'));san.nextTick(()=>{window.__visualReady=true;});', runtime=SAN.read_text(encoding='utf-8')),
             page('runtime_error', plain + 'setTimeout(()=>{throw Error("known calibration error");},0);'),
             page('blocked_network', plain + 'fetch("https://invalid.example/calibration").catch(()=>{});'),
             page('unstable', plain + 'setInterval(()=>{document.querySelector("#value").textContent=String(performance.now());},10);')]
    pairs = [{'source': 'baseline', 'target': name} for name in ['identical', 'color', 'spacing']]
    pairs += [{'source': 'vue_native', 'target': 'san_native'}]
    pairs += [{'source': name, 'target': name} for name in ['runtime_error', 'blocked_network', 'unstable']]
    return {'outputDir': str(Path(output_dir).resolve()), 'pages': pages, 'pairs': pairs,
            # Strict calibration controls, NOT selected production pass thresholds.
            'thresholds': {'pixelTolerance': 0, 'maxChangedPixelRatio': 0, 'minSSIM': 0.999999999}}


def calibrate(output_dir):
    output_dir = Path(output_dir).resolve()
    if output_dir.exists():
        raise FileExistsError('Never overwrite previous calibration evidence')
    payload = fixtures(output_dir)
    proc = subprocess.run(['node', str(ROOT / 'migration_pipeline/run_controlled_browser_pixel_v1.cjs')],
                          cwd=ROOT, input=json.dumps(payload), text=True, encoding='utf-8',
                          capture_output=True, timeout=180)
    result_path = output_dir / 'result.json'
    if not result_path.is_file():
        raise RuntimeError('Browser unavailable/failed, not a pass: ' + proc.stderr)
    result = json.loads(result_path.read_text(encoding='utf-8'))
    if proc.returncode not in [0, 2] or proc.stderr.strip() or 'comparisons' not in result:
        raise RuntimeError('Calibration execution blocked; inspect ' + str(result_path))
    pairs = result['comparisons']
    checks = {
        'identical_pages_exact_match': pairs[0]['passed'] and pairs[0]['metrics']['changedPixels'] == 0,
        'known_color_difference_rejected': pairs[1]['eligible'] and not pairs[1]['passed'] and pairs[1]['metrics']['changedPixels'] > 0,
        'known_spacing_difference_rejected': pairs[2]['eligible'] and not pairs[2]['passed'] and bool(pairs[2]['styleChanges']),
        'native_vue_san_fixture_exact_match': pairs[3]['passed'] and pairs[3]['metrics']['changedPixels'] == 0,
        'runtime_error_blocks_self_comparison': not pairs[4]['eligible'] and not pairs[4]['passed'],
        'network_denial_blocks_self_comparison': not pairs[5]['eligible'] and not pairs[5]['passed'],
        'unstable_page_blocks_self_comparison': not pairs[6]['eligible'] and not pairs[6]['passed'],
        'negative_controls_not_overall_pass': result['status'] == 'blocked' and not result['passed'],
        'all_screenshot_sizes_match': all(p['metrics']['totalPixels'] == 640 * 480 for p in pairs),
    }
    summary = {'calibrationPassed': all(checks.values()), 'checks': checks, 'runtimeSha256': RUNTIME_SHA,
               'pages': len(payload['pages']), 'pairs': len(pairs), 'productionThresholdsSelected': False,
               'componentPassClaimed': False, 'historicalBatchChanged': False, 'modelCalls': 0,
               'inputSha256': digest(output_dir / 'input.json'), 'resultSha256': digest(result_path)}
    with (output_dir / 'calibration.json').open('x', encoding='utf-8') as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
    return summary


def failure_modes(output_dir):
    """Exercise fail-closed launch/readiness/mapping/crop contracts, not just scores."""
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    rows = {}
    for name, message in [('not_ready', 'readiness timeout'),
                          ('missing_selector', 'Selector must match exactly one'),
                          ('overflow', 'outside viewport'),
                          ('missing_browser', 'ENOENT')]:
        payload = fixtures(output_dir / name)
        page = payload['pages'][0]
        payload['pages'] = [page]
        payload['pairs'] = [{'source': 'baseline', 'target': 'baseline'}]
        if name == 'not_ready':
            page['html'] = page['html'].replace('window.__visualReady=true', 'window.__visualReady=false')
        elif name == 'missing_selector':
            page['selectors']['card'] = '#not-present'
        elif name == 'overflow':
            page['html'] = page['html'].replace('width:280px', 'width:900px')
        else:
            payload['browserExecutable'] = str(output_dir / 'deliberately-missing-browser.exe')
        proc = subprocess.run(['node', str(ROOT / 'migration_pipeline/run_controlled_browser_pixel_v1.cjs')],
                              cwd=ROOT, input=json.dumps(payload), text=True, encoding='utf-8',
                              capture_output=True, timeout=60)
        result_path = output_dir / name / 'result.json'
        result = json.loads(result_path.read_text(encoding='utf-8')) if result_path.exists() else None
        rows[name] = {'exitCode': proc.returncode, 'stderr': proc.stderr, 'result': result,
                      'checkPassed': proc.returncode == 2 and message in (proc.stdout + proc.stderr)
                                     and (result is None or (result['status'] == 'blocked' and not result['passed']))}
    # The already existing first directory must not be reused or replaced.
    payload = fixtures(output_dir / 'not_ready')
    proc = subprocess.run(['node', str(ROOT / 'migration_pipeline/run_controlled_browser_pixel_v1.cjs')],
                          cwd=ROOT, input=json.dumps(payload), text=True, encoding='utf-8',
                          capture_output=True, timeout=30)
    rows['overwrite'] = {'exitCode': proc.returncode, 'stderr': proc.stderr,
                         'checkPassed': proc.returncode == 2 and 'never overwrite evidence' in proc.stderr}
    summary = {'checks': rows, 'allPassed': all(row['checkPassed'] for row in rows.values())}
    with (output_dir / 'failure_modes.json').open('x', encoding='utf-8') as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--failure-modes-only', action='store_true')
    args = parser.parse_args()
    outcome = failure_modes(args.output_dir) if args.failure_modes_only else calibrate(args.output_dir)
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    if not outcome.get('calibrationPassed', outcome.get('allPassed', False)):
        raise SystemExit(1)
