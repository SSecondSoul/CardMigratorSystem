"""Offline evaluator calibration on frozen full-30 artifacts; no model calls or score writes."""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from migration_pipeline.analyze_formal_30_v4_full_regression import ROOT, digest, verify_snapshot
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.utils.repair_scheduler import candidate_gate
from migration_pipeline.utils.bounded_semantics import inspect_semantics

BATCH = 'formal_30_v4_full_regression_v2'
SOURCE = ROOT / 'data/experiments/snapshots/formal_30_v4_full_regression_v2_results_20261104_214821'
PROTOCOL = ROOT / 'data/experiments/protocols/formal_30_v4_full_regression_v2_frozen_20261104'
OUTPUT = ROOT / 'data/experiments/analysis/formal_30_v4_evaluator_calibration_v1_20261104'
CHANGED = {
    'migration_pipeline/stages/validate.py', 'migration_pipeline/stages/repair.py',
    'migration_pipeline/utils/repair_scheduler.py', 'migration_pipeline/utils/repair_prompt.py',
    'migration_pipeline/utils/semantic_coverage.py', 'migration_pipeline/utils/watch_persistence_semantics.cjs',
}
ADDED = {
    'migration_pipeline/utils/detached_record_semantics.py',
    'migration_pipeline/utils/detached_record_semantics.cjs',
    'migration_pipeline/replay_formal_30_v4_evaluator_calibration_v1.py',
    'tests/test_evaluator_calibration_v1.py',
    'migration_pipeline/analyze_formal_30_v4_full_regression_v2.py',
    'tests/test_full_regression_v2_analysis.py',
}


def inventory():
    verify_snapshot(PROTOCOL.resolve())
    prior = {}
    for line in (PROTOCOL / 'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        sha, name = line.split('  ', 1)
        if name.startswith('frozen/'):
            prior[name[len('frozen/'):]] = sha
    if len(prior) != 322:
        raise RuntimeError('Expected full-30 protocol inventory')
    current = {name: digest(ROOT / name) for name in sorted(set(prior) | ADDED)}
    actual = {name for name, sha in prior.items() if current[name] != sha}
    if actual != CHANGED:
        raise RuntimeError(f'Unexpected live changes: {actual ^ CHANGED}')
    return current


def replay():
    verified = verify_snapshot(SOURCE.resolve())
    summary = json.loads((SOURCE / f'{BATCH}_summary.json').read_text(encoding='utf-8'))
    config = json.loads((SOURCE / f'{BATCH}.json').read_text(encoding='utf-8'))
    if len(config['samples']) != 30 or [s['id'] for s in summary['samples']] != [s['id'] for s in config['samples']]:
        raise RuntimeError('Full-30 order mismatch')
    rows, rollbacks = [], []
    for plan, sample in zip(config['samples'], summary['samples']):
        print(f"Calibrating {sample['id']} (offline)", flush=True)
        folder = SOURCE / 'pipeline' / sample['complexity']
        report = SOURCE / 'repair_reports' / sample['complexity'] / Path(sample['report_file']).name
        original = json.loads(report.read_text(encoding='utf-8'))['state']
        vue = SOURCE / 'protocol/frozen' / plan['vue_file']
        final = folder / Path(sample['final_file_path']).name
        if final.read_text(encoding='utf-8') != original['final_code']:
            raise RuntimeError('Final code mismatch')

        def assess(code, visual):
            val = ValidateStage().run(ValidateStageInput(generated_code=code, ssm=original['ssm'],
                vue_file_path=str(vue), compile_check=True)).to_state_update()
            return {'generated_code': code, 'ssm': original['ssm'], 'vue_file_path': str(vue),
                    'visual_eval_passed': visual, **val}

        before = assess(original['final_code'], original['final_visual_eval_result']['visual_eval_passed'])
        old_errors = original['final_validate_result']['validation_errors']
        row = {'id': sample['id'], 'complexity': sample['complexity'], 'final_sha256': digest(final),
            'vue_sha256': digest(vue), 'original_automatic_passed': sample['final_passed'],
            'original_validation_errors': old_errors,
            'calibrated_validation_errors': before['validation_errors'],
            'calibrated_validation_passed': before['validation_passed'],
            'visual_pass_reused_from_frozen_run': before['visual_eval_passed'],
            'visual_reexecuted': False, 'fresh_model_run': False, 'manual_pass_claimed': False}
        rows.append(row)
        if sample['retained_previous_candidate']:
            candidate = folder / Path(original['rejected_candidate_file']).name
            entry = original['repair_history'][-1]
            after = assess(candidate.read_text(encoding='utf-8'), entry['visual_eval_passed'])
            gate = candidate_gate(before, after)
            rollbacks.append({'id': sample['id'], 'candidate_sha256': digest(candidate),
                'original_gate': entry['repair_regression_gate'], 'calibrated_gate': gate,
                'candidate_validation_errors': after['validation_errors'],
                'candidate_validation_passed': after['validation_passed'],
                'continued_repair_or_replacement_performed': False})
        if sample['id'] == 'MonitoringDashboard':
            row['watcher_contracts'] = inspect_semantics(original['final_code'], vue.read_text(encoding='utf-8'),
                ssm=original['ssm']).get('watcher_contracts', [])
            if [e['code'] for e in before['validation_errors']] != ['source_watch_persistence_unproven']:
                raise RuntimeError('Monitoring boundary differs from expected calibration')
    rule = next(r for r in rollbacks if r['id'] == 'rule_builder')
    if rule['calibrated_gate']['should_stop'] or rule['candidate_validation_passed']:
        raise RuntimeError('RuleBuilder must be allowed to progress but still fail validation')
    if any(not r['calibrated_gate']['should_stop'] for r in rollbacks if r is not rule):
        raise RuntimeError('An unrelated rollback lost its regression protection')
    if any(r['original_automatic_passed'] and not r['calibrated_validation_passed'] for r in rows):
        raise RuntimeError('Previously passed artifact gained a validation error')
    verify_snapshot(SOURCE.resolve())
    return {'created_at': datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'classification': 'offline_evaluator_calibration_on_reused_development_artifacts_not_fresh_regression',
        'source_snapshot': SOURCE.relative_to(ROOT).as_posix(), 'source_verified_files': verified,
        'original_aggregate': summary['aggregate'], 'model_requests': 0, 'original_score_modified': False,
        'canonical_artifacts_modified': False, 'exception_equivalence_waived': False,
        'offline_calibrated_validation_pass_count': sum(r['calibrated_validation_passed'] for r in rows),
        'no_fresh_batch_pass_rate_inferred': True, 'samples': rows, 'rollback_reassessments': rollbacks}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-evidence', action='store_true')
    args = parser.parse_args()
    if args.write_evidence and OUTPUT.exists():
        raise FileExistsError('Never overwrite calibration evidence')
    hashes = inventory()
    tests = ''
    if args.write_evidence:
        print('Running full unit tests; no model requests.', flush=True)
        proc = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py'],
            cwd=ROOT, env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}, text=True, encoding='utf-8', capture_output=True)
        tests = proc.stdout + proc.stderr
        if proc.returncode:
            raise RuntimeError('Full tests failed:\n' + tests)
    data = replay()
    if inventory() != hashes:
        raise RuntimeError('Runtime changed during offline replay')
    if args.write_evidence:
        match = re.search(r'Ran (\d+) tests in ([\d.]+)s', tests)
        if not match or '\nOK' not in tests:
            raise RuntimeError('Test success/count not found')
        data['unit_tests'] = {'passed': int(match[1]), 'failed': 0, 'elapsed_seconds': float(match[2])}
        OUTPUT.mkdir(parents=True)
        for name in sorted(CHANGED | ADDED):
            target = OUTPUT / 'code' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        for name, value in (('replay.json', data), ('live_inventory.json', hashes)):
            (OUTPUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (OUTPUT / 'unit_tests.txt').write_text(tests, encoding='utf-8')
        files = sorted(p for p in OUTPUT.rglob('*') if p.is_file())
        (OUTPUT / 'SHA256SUMS.txt').write_text('\n'.join(
            f'{digest(p)}  {p.relative_to(OUTPUT).as_posix()}' for p in files) + '\n', encoding='utf-8')
        verify_snapshot(OUTPUT.resolve())
    print(json.dumps({'original_passed': data['original_aggregate']['passed'], 'model_requests': 0,
        'offline_validation_pass_count': data['offline_calibrated_validation_pass_count'],
        'rule_builder_progress_allowed_not_passed': True, 'unit_tests': data.get('unit_tests'),
        'evidence_written': args.write_evidence}))


if __name__ == '__main__':
    main()
