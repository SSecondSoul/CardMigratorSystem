"""Verify and freeze a separate watcher-persistence replay; zero model calls."""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from migration_pipeline.analyze_formal_30_v4_full_regression import digest, verify_snapshot
from migration_pipeline.freeze_formal_30_v3_results import VERIFY_SCRIPT
from migration_pipeline.replay_formal_30_v4_semantic_closure import evaluate
from migration_pipeline.analyze_formal_30_v4_semantic_closure_v5 import inspect_startup_and_storage
from migration_pipeline.utils.bounded_semantics import inspect_semantics
from migration_pipeline.utils.repair_scheduler import candidate_gate
from migration_pipeline.stages.repair import RepairStage

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/experiments/snapshots/formal_30_v4_semantic_closure_v5_results_20261104_150846'
OUTPUT = ROOT / 'data/experiments/analysis/formal_30_v4_watch_persistence_closure_v1_20261104'
CHANGED = {'migration_pipeline/utils/source_phase_semantics.cjs',
    'migration_pipeline/utils/bounded_semantics.cjs', 'migration_pipeline/utils/repair_prompt.py',
    'migration_pipeline/stages/repair.py', 'tests/test_migration_pipeline_regressions.py',
    'tests/test_monitoring_remaining_bounded_fix.py'}
ADDED = ('migration_pipeline/utils/watch_persistence_semantics.cjs',
    'tests/test_watch_persistence_closure.py', 'migration_pipeline/analyze_formal_30_v4_semantic_closure_v5.py',
    'tests/test_semantic_closure_v5_analysis.py', 'migration_pipeline/replay_formal_30_v4_watch_persistence_closure.py')


def inventory():
    if verify_snapshot(SOURCE) != 364:
        raise RuntimeError('Raw snapshot inventory changed')
    rows = [line.split('  ', 1) for line in (SOURCE / 'protocol/SHA256SUMS.txt').read_text(encoding='utf-8').splitlines()]
    old = {n.removeprefix('frozen/'): h for h, n in rows if n.startswith('frozen/')}
    changed = {n for n, h in old.items() if digest(ROOT / n) != h}
    if len(old) != 312 or changed != CHANGED:
        raise RuntimeError(f'Unexpected runtime boundary: {sorted(changed)}')
    return {name: digest(ROOT / name) for name in set(old) | set(ADDED)}


def replay():
    report = SOURCE / 'repair_reports/complex/MonitoringDashboard_repair_history.json'
    state = json.loads(report.read_text(encoding='utf-8'))['state']
    vue_path = SOURCE / 'protocol/frozen/data/datasets/components/03_complex/MonitoringDashboard/vue/MonitoringDashboard.vue'
    vue = vue_path.read_text(encoding='utf-8')
    code = state['final_code']
    before = evaluate(code, state, vue_path)
    if [e['code'] for e in before['validation_errors']] != ['source_watch_persistence_not_landed']:
        raise RuntimeError(f'Unexpected initial findings: {before["validation_errors"]}')
    fixed, rules = RepairStage._deterministic_repair_plan(code, before['validation_errors'],
        before['visual_eval_errors'], state['ssm'], str(vue_path), enable_residual_v2=True)
    if [r for _, r in rules] != ['restored_source_watch_persistence']:
        raise RuntimeError('Only proven persistence insertion is authorized')
    after = evaluate(fixed, state, vue_path)
    gate, reverse = candidate_gate(before, after), candidate_gate(after, before)
    if (not after['validation_passed'] or not after['visual_eval_passed'] or gate['should_stop']
            or not reverse['should_stop']):
        raise RuntimeError('Static/render/forward/reverse closure failed')
    checked = inspect_semantics(fixed, vue, repair=True, ssm=state['ssm'])
    if checked.get('error') or checked['findings'] or checked['changes'] or checked['code'] != fixed:
        raise RuntimeError('Fixed-point contract failed')
    audit = inspect_startup_and_storage(vue, fixed)
    if (audit['watcher']['trailing_settings_write_missing']
            or len(audit['watcher']['target_listener_writes']) != 1
            or not audit['initializer']['expanded_source_prefix_once_in_attached']):
        raise RuntimeError('Independent persistence/startup audit failed')
    method = next(c for c in checked['method_contracts'] if c.get('name') == 'requestNotificationPermission')
    if method['status'] != 'callable_present' or method['target_references']['count']:
        raise RuntimeError('Notification interface/no-new-trigger regressed')
    insertion = '\nlocalStorage.setItem("dashboard_settings", JSON.stringify(newValue));\n'
    if fixed.replace(insertion, '', 1) != code:
        raise RuntimeError('Unexpected change outside the single storage insertion')
    compact = lambda state: {k: v for k, v in state.items() if k not in {'generated_code', 'ssm'}}
    return fixed, {'created_at': datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'classification': 'offline_source_watcher_persistence_closure_not_fresh_model_or_manual_score',
        'source_snapshot': SOURCE.name, 'source_verified_files': 364,
        'source_summary_sha256': digest(SOURCE / 'formal_30_v4_semantic_closure_v5_summary.json'),
        'source_history_sha256': digest(report), 'before': compact(before), 'after': compact(after),
        'rules': [r for _, r in rules], 'gate': gate, 'reverse_gate': reverse,
        'watcher_contracts': checked['watcher_contracts'], 'notification_contract': method,
        'independent_ast_review': audit, 'fixed_point': True,
        'model_requests': 0, 'original_automatic_score_modified': False,
        'canonical_san_modified': False, 'browser_interaction_test_performed': False,
        'real_browser_storage_or_permission_performed': False,
        'boundary': 'Source-proven exported parent trailing direct storage write only. Scope-aware alpha '
          'mapping plus unchanged translated callback body and unused old-value binding are required for '
          'restoration. Missing/unproven writes stay diagnostics outside the repair subset. No arbitrary '
          'watcher equivalence, inherited registrations or indirect storage aliases are claimed.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-evidence', action='store_true')
    args = parser.parse_args()
    if args.write_evidence and OUTPUT.exists():
        raise FileExistsError('Never replace frozen offline evidence')
    hashes = inventory()
    tests = ''
    if args.write_evidence:
        print('Running complete tests; no model requests.', flush=True)
        p = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py'], cwd=ROOT,
            env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}, capture_output=True, text=True, encoding='utf-8')
        tests = p.stdout + p.stderr
        if p.returncode:
            raise RuntimeError(f'Complete tests failed:\n{tests}')
    print('Replaying frozen final candidate; no model requests.', flush=True)
    fixed, data = replay()
    if hashes != inventory():
        raise RuntimeError('Runtime changed during verification')
    if args.write_evidence:
        match = re.search(r'Ran (\d+) tests in ([\d.]+)s', tests)
        if not match or '\nOK' not in tests:
            raise RuntimeError('Test count or success marker missing')
        data['unit_tests'] = {'passed': int(match[1]), 'failed': 0, 'elapsed_seconds': float(match[2])}
        OUTPUT.mkdir(parents=True)
        candidate = OUTPUT / 'MonitoringDashboard_watch_persistence_offline.san'
        candidate.write_text(fixed, encoding='utf-8')
        data['candidate_sha256'] = digest(candidate)
        for name in sorted(CHANGED | set(ADDED)):
            target = OUTPUT / 'code' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        data['changed_prior_live_files'] = sorted(CHANGED)
        data['frozen_code_files'] = len(CHANGED | set(ADDED))
        (OUTPUT / 'live_inventory.json').write_text(json.dumps(hashes, indent=2) + '\n', encoding='utf-8')
        (OUTPUT / 'unit_tests.txt').write_text(tests, encoding='utf-8')
        (OUTPUT / 'replay.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (OUTPUT / 'verify_snapshot.py').write_text(VERIFY_SCRIPT, encoding='utf-8')
        files = sorted(p for p in OUTPUT.rglob('*') if p.is_file())
        (OUTPUT / 'SHA256SUMS.txt').write_text('\n'.join(
            f'{digest(p)}  {p.relative_to(OUTPUT).as_posix()}' for p in files) + '\n', encoding='utf-8')
        verify_snapshot(OUTPUT)
    print(json.dumps({'model_requests': 0, 'evidence_written': args.write_evidence,
        'validation_passed': data['after']['validation_passed'],
        'visual_eval_passed': data['after']['visual_eval_passed'],
        'structure_similarity': data['after']['structure_similarity'], 'unit_tests': data.get('unit_tests')}))


if __name__ == '__main__':
    main()
