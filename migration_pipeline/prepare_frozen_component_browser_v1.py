"""Prepare real, immutable component pages for S2 development calibration.
Not a model batch or a replacement for the historical summary.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'data/experiments/analysis/frozen_component_browser_v1_20261115'
RUNTIMES = {
    'vue': ('data/experiments/manual_followups/task_manager_async_scope_v7_prepared_20261113/vendor/vue-2.7.16.js',
            '36b10d3b4920592a4ec26c064c429e9a3dfb4689235fdfc91e1736b681c76786'),
    'san': ('node_modules/san/dist/san.dev.js',
            '4b1c4a3a918d91663c0f79a4f77358a9de3c0ee1fbc01dfc47897f8531543134'),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def readonly_baseline():
    baseline = json.loads((BASE / 'baseline.json').read_text(encoding='utf-8'))
    for p, digest in {**baseline['protected'], **baseline['manual']}.items():
        if sha(ROOT / p) != digest:
            raise RuntimeError('Prior implementation/manual drift: ' + p)
    for item in baseline['selection']:
        for field in ['source', 'target']:
            if sha(ROOT / item[field]['path']) != item[field]['sha256']:
                raise RuntimeError('Frozen component differs: ' + item['component'])
    for p, digest in RUNTIMES.values():
        if sha(ROOT / p) != digest:
            raise RuntimeError('Runtime differs: ' + p)
    return baseline


def scenarios():
    return [
        {'component': 'VolumeControl', 'name': 'volume_default', 'props': {},
         'ready': {'fields': ['initialVolume', 'volume', 'lastVolume', 'volumeLabel'], 'equals': {}, 'minLengths': {}},
         'selectors': {'root': '.volume-control', 'title': 'h2', 'range': '.volume-slider', 'action': 'button.primary'}},
        {'component': 'VolumeControl', 'name': 'volume_prop', 'props': {'initialVolume': 60},
         'ready': {'fields': ['initialVolume', 'volume', 'lastVolume', 'volumeLabel'], 'equals': {}, 'minLengths': {}},
         'selectors': {'root': '.volume-control', 'title': 'h2', 'range': '.volume-slider', 'action': 'button.primary'}},
        {'component': 'BatchRenamer', 'name': 'rename_default', 'props': {},
         'ready': {'fields': ['files', 'currentFiles', 'prefix', 'startAt', 'previewVisible', 'previews'], 'equals': {}, 'minLengths': {'currentFiles': 1}},
         'selectors': {'root': '.batch-renamer', 'title': 'h2', 'rules': '.rename-rules', 'table': 'table', 'newname': 'tbody tr:first-child td:nth-child(2)', 'action': 'button.primary'}},
        {'component': 'BatchRenamer', 'name': 'rename_prop', 'props': {'files': ['sample.png', 'draft.txt']},
         'ready': {'fields': ['files', 'currentFiles', 'prefix', 'startAt', 'previewVisible', 'previews'], 'equals': {}, 'minLengths': {'currentFiles': 1}},
         'selectors': {'root': '.batch-renamer', 'title': 'h2', 'rules': '.rename-rules', 'table': 'table', 'newname': 'tbody tr:first-child td:nth-child(2)', 'action': 'button.primary'}},
        {'component': 'AnalyticsDashboard', 'name': 'analytics_default', 'props': {},
         'ready': {'fields': ['isLoading', 'statistics', 'chartData', 'insights', 'activities', 'selectedPeriod', 'isDarkMode'],
                   'equals': {'isLoading': False}, 'minLengths': {'statistics': 1, 'chartData': 1, 'insights': 1, 'activities': 1}},
         'selectors': {'root': '.analytics-dashboard', 'title': '.logo-text', 'stats': '.stats-grid', 'firstcard': '.stats-grid .stat-card:first-child',
                       'chart': '.trend-chart', 'insights': '.insight-list', 'activity': '.activity-section', 'lastrow': '.activity-section tbody tr:last-child'}},
    ]


def prepare(output_dir):
    baseline = readonly_baseline()
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=False)
    manifest = {'selection': baseline['selection'], 'scenarios': scenarios(), 'pages': {},
                'productionThresholdsSelected': False, 'modelCalls': 0, 'historicalScoresChanged': False}
    pages, pairs = [], []
    for scenario in scenarios():
        selected = next(s for s in baseline['selection'] if s['component'] == scenario['component'])
        for framework, field in [('vue', 'source'), ('san', 'target')]:
            file = ROOT / selected[field]['path']
            spec = {'framework': framework, 'main': file.name,
                    'modules': [{'id': file.name, 'source': file.read_text(encoding='utf-8'), 'dependencies': {}}],
                    'props': scenario['props'], 'ready': scenario['ready']}
            proc = subprocess.run(['node', str(ROOT / 'migration_pipeline/utils/component_page_adapter_v1.cjs')],
                                  cwd=ROOT, input=json.dumps({'spec': spec, 'runtime': (ROOT / RUNTIMES[framework][0]).read_text(encoding='utf-8')}),
                                  text=True, encoding='utf-8', capture_output=True, timeout=30)
            if proc.returncode or proc.stderr:
                with (output / 'preparation_failure.json').open('x', encoding='utf-8') as stream:
                    json.dump({'scenario': scenario['name'], 'framework': framework, 'stderr': proc.stderr}, stream)
                raise RuntimeError('Page preparation failed; retain failed directory: ' + proc.stderr)
            built = json.loads(proc.stdout)
            name = scenario['name'] + '_' + framework
            with (output / (name + '.html')).open('x', encoding='utf-8', newline='\n') as stream:
                stream.write(built['html'])
            pages.append({'name': name, 'html': built['html'], 'selectors': scenario['selectors']})
            manifest['pages'][name] = {'input': selected[field], 'runtime': {'path': RUNTIMES[framework][0], 'sha256': RUNTIMES[framework][1]},
                                      'htmlSha256': sha(output / (name + '.html')), 'moduleManifest': built['manifest'],
                                      'styleManifest': built['styles'], 'boundary': built['boundary'], 'props': scenario['props']}
        pairs.append({'source': scenario['name'] + '_vue', 'target': scenario['name'] + '_san'})
    payload = {'pages': pages, 'pairs': pairs, 'viewport': {'width': 1280, 'height': 800}, 'capturePolicy': 'full-page',
               'thresholds': {'pixelTolerance': 0, 'maxChangedPixelRatio': 0, 'minSSIM': .999999999}}
    for name, data in [('manifest.json', manifest), ('payload.json', payload)]:
        with (output / name).open('x', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
    readonly_baseline()
    return {'preparedPages': len(pages), 'comparisonPairs': len(pairs), 'outputDir': str(output), 'browserStarted': False}


def execute(prepared_dir, output_dir):
    readonly_baseline()
    prepared = Path(prepared_dir).resolve()
    manifest = json.loads((prepared / 'manifest.json').read_text(encoding='utf-8'))
    payload = json.loads((prepared / 'payload.json').read_text(encoding='utf-8'))
    for page in payload['pages']:
        if sha(prepared / (page['name'] + '.html')) != manifest['pages'][page['name']]['htmlSha256']:
            raise RuntimeError('Prepared HTML differs')
        if hashlib.sha256(page['html'].encode()).hexdigest() != manifest['pages'][page['name']]['htmlSha256']:
            raise RuntimeError('Payload HTML differs')
    payload['outputDir'] = str(Path(output_dir).resolve())
    proc = subprocess.run(['node', str(ROOT / 'migration_pipeline/run_controlled_browser_pixel_v2.cjs')],
                          cwd=ROOT, input=json.dumps(payload), text=True, encoding='utf-8', capture_output=True, timeout=240)
    if proc.returncode not in [0, 1, 2] or proc.stderr:
        raise RuntimeError('Browser execution failed; do not pass: ' + proc.stderr)
    result = json.loads(proc.stdout)
    readonly_baseline()
    return {'status': result['status'], 'passed': result['passed'], 'comparisons': result.get('comparisons'),
            'captures': {name: {'status': c['status'], 'clean': c['clean'], 'stable': c['stable'], 'error': c.get('error'),
                                'extent': c.get('extent'), 'childComponents': c.get('componentEvidence', {}).get('childComponentCount')}
                         for name, c in result.get('captures', {}).items()}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared-dir', required=True)
    parser.add_argument('--output-dir')
    args = parser.parse_args()
    result = execute(args.prepared_dir, args.output_dir) if args.output_dir else prepare(args.prepared_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
