"""Re-capture exactly the prior sealed HTML under native per-page contexts. No LLM."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from migration_pipeline.utils.browser_feedback_v1 import verify_seal

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'data/experiments/analysis/browser_session_isolation_v1_20261115'


def execute(output_dir):
    baseline = json.loads((BASE/'baseline.json').read_text(encoding='utf-8'))
    for path, pin in {**baseline['protected'], **baseline['manual']}.items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != pin:
            raise RuntimeError('Protected baseline changed: ' + path)
    previous_seal = ROOT/baseline['prior_seal']['path']
    verify_seal(previous_seal.parent, baseline['prior_seal']['sha256'])
    previous_baseline = json.loads((previous_seal.parent/'baseline.json').read_text(encoding='utf-8'))
    recording_seal = ROOT/previous_baseline['prior_seal']['path']
    verify_seal(recording_seal.parent, previous_baseline['prior_seal']['sha256'])
    old = recording_seal.parent/'corrected_run'
    payload = json.loads((old/'input.json').read_text(encoding='utf-8'))
    output = Path(output_dir).resolve()
    if output.exists():
        raise FileExistsError('Never overwrite a browser recording')
    payload['outputDir'] = str(output)
    proc = subprocess.run(['node', str(ROOT/'migration_pipeline/run_controlled_browser_pixel_v3.cjs')],
                          cwd=ROOT, input=json.dumps(payload), text=True, encoding='utf-8',
                          capture_output=True, timeout=240)
    if proc.returncode != 2 or proc.stderr:
        raise RuntimeError('Expected preserved source-warning block, inspect output: ' + proc.stderr)
    result = json.loads(proc.stdout)
    prior = json.loads((old/'result.json').read_text(encoding='utf-8'))
    registry = result['nativeRegistry']
    events = registry['events']
    checks = {
        'ten_native_pages_verified_and_disposed': len(registry['entries'])==10 and registry['complete'],
        'ten_unique_contexts': len({e['contextId'] for e in registry['entries']})==10,
        'ten_unique_sessions': len({e['sessionId'] for e in registry['entries']})==10,
        'raw_native_target_and_frame_observations_retained': all(len(e['nativeObservations'])==2 for e in registry['entries']),
        'ten_pages_captured_stably': all(c['status']=='captured' and c['stable'] for c in result['captures'].values()),
        'four_static_scene_matches_preserved': all(p['passed'] for p in result['comparisons'][:4]),
        'analytics_source_warnings_preserved_and_owned': len(events)==10 and all(e['owner']['page']=='analytics_default_vue' and e['attribution']=='native_session' for e in events),
        'analytics_target_clean': result['captures']['analytics_default_san']['clean'],
        'actual_html_unchanged': all(result['captures'][n]['htmlSha256']==prior['captures'][n]['htmlSha256'] for n in prior['captures']),
        'screenshots_unchanged_vs_old_capture': all(result['captures'][n]['screenshotSha256']==prior['captures'][n]['screenshotSha256'] for n in prior['captures']),
        'old_business_observations_unchanged': all(result['captures'][n]['componentEvidence']==prior['captures'][n]['componentEvidence'] for n in prior['captures']),
        'analytics_height_and_seven_rect_differences_preserved': result['comparisons'][-1]['dimensions']=={'source':[1280,1326],'target':[1280,1625]} and len(result['comparisons'][-1]['styleChanges'])==7 and result['comparisons'][-1]['metrics'] is None,
        'no_model_or_production_admission': result['boundary']['modelCalls']==0 and not result['boundary']['productionIntegrated'] and not result['passed'],
    }
    (output/'replay_checks.json').write_text(json.dumps({'checks':checks,'allPassed':all(checks.values()),
        'componentPairs':3,'staticScenes':5,'modelCalls':0,'oldScoresChanged':False,
        'priorRecordingSeal':previous_baseline['prior_seal']},ensure_ascii=False,indent=2),encoding='utf-8')
    if not all(checks.values()):
        raise AssertionError('Replay checks failed: '+str([k for k,v in checks.items() if not v]))
    return checks


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',required=True)
    print(json.dumps(execute(parser.parse_args().output_dir),indent=2))
