"""Offline proof: recovery, coverage gate, captured candidate closure; no LLM."""

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
from migration_pipeline.stages.repair import RepairStage
from migration_pipeline.utils.repair_scheduler import candidate_gate


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/experiments/snapshots/formal_30_v4_semantic_closure_v3_results_20261103_175401'
OUTPUT = ROOT / 'data/experiments/analysis/formal_30_v4_coverage_helper_closure_v1_20261103'
CODE_PATHS = (
    'migration_pipeline/utils/inline_identifier_recovery.py',
    'migration_pipeline/utils/inline_identifier_recovery.cjs',
    'migration_pipeline/utils/semantic_coverage.py', 'migration_pipeline/utils/semantic_coverage.cjs',
    'migration_pipeline/utils/stateful_helper_semantics.py', 'migration_pipeline/utils/stateful_helper_semantics.cjs',
    'migration_pipeline/utils/residual_semantics.py', 'migration_pipeline/utils/residual_semantics.cjs',
    'migration_pipeline/utils/bounded_semantics.py', 'migration_pipeline/utils/bounded_semantics.cjs',
    'migration_pipeline/utils/source_phase_semantics.cjs', 'migration_pipeline/utils/repair_scheduler.py',
    'migration_pipeline/utils/repair_regression_guard.py', 'migration_pipeline/stages/repair.py',
    'migration_pipeline/stages/validate.py', 'tests/test_coverage_and_helper_closure.py',
    'migration_pipeline/replay_formal_30_v4_coverage_helper_closure.py',
)


def compact(state):
    return {k: v for k, v in state.items() if k not in {'generated_code', 'ssm'}}


def replay():
    count = verify_snapshot(SOURCE)
    report_path = SOURCE / 'repair_reports/complex/MonitoringDashboard_repair_history.json'
    state = json.loads(report_path.read_text(encoding='utf-8'))['state']
    vue = SOURCE / 'protocol/frozen/data/datasets/components/03_complex/MonitoringDashboard/vue/MonitoringDashboard.vue'
    before = evaluate(state['generated_code'], state, vue)
    candidate = evaluate(state['repair_history'][0]['repair_result']['repaired_code'], state, vue)
    gate = candidate_gate(before, candidate)
    latent = gate['newly_visible_preexisting_semantic_findings']
    if gate['should_stop'] or sum(x['count'] for x in latent if x['code'] == 'hidden_template_reactive_dependency') != 4:
        raise RuntimeError(f'Known visibility transition not explained: {gate}')
    # Same error messages but changed actual calculation must still be rejected.
    mutated = {**candidate, 'generated_code': candidate['generated_code'].replace(
        'return (index * 800) / data.length + 2;', 'return (index * 800) / data.length + 3;')}
    if mutated['generated_code'] == candidate['generated_code']:
        raise RuntimeError('Counterexample did not mutate input')
    bad_gate = candidate_gate(before, mutated)
    if not bad_gate['should_stop'] or not bad_gate['introduced_semantic_findings']:
        raise RuntimeError('Real changed dependency was silently exempted')
    rows, artifacts = [], {}
    for name, start in (('retained_failure', before), ('rejected_candidate', candidate)):
        current, steps = start, []
        for _ in range(4):
            code, rules = RepairStage._deterministic_repair_plan(
                current['generated_code'], current['validation_errors'], current['visual_eval_errors'],
                state['ssm'], str(vue), enable_residual_v2=True)
            if code == current['generated_code']:
                break
            after = evaluate(code, state, vue)
            decision = candidate_gate(current, after)
            steps.append({'rules': [label for _, label in rules], 'gate': decision, 'evaluation': compact(after)})
            if decision['should_stop']:
                raise RuntimeError(f'Unexpected offline normalization rejection: {name}/{decision}')
            current = after
        artifacts[name] = current['generated_code']
        rows.append({'case': name, 'before': compact(start), 'after': compact(current), 'steps': steps,
            'passed_offline': current['validation_passed'] and current['visual_eval_passed']})
    if not rows[1]['passed_offline']:
        raise RuntimeError('Captured candidate did not close')
    # Idempotence/fixed point, including when unresolved families remain.
    for row in rows:
        final = row['after']
        again, _ = RepairStage._deterministic_repair_plan(artifacts[row['case']], final['validation_errors'],
            final['visual_eval_errors'], state['ssm'], str(vue), enable_residual_v2=True)
        if again != artifacts[row['case']]:
            raise RuntimeError(f"Not a bounded fixed point: {row['case']}")
    result = {
        'created_at': datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'classification': 'offline_coverage_and_private_helper_development_closure_not_fresh_model_score',
        'source_snapshot': SOURCE.name, 'verified_files': count,
        'source_repair_history_sha256': digest(report_path),
        'source_summary_sha256': digest(SOURCE / 'formal_30_v4_semantic_closure_v3_summary.json'),
        'original_batch_passed': False, 'model_requests': 0, 'browser_interaction_test_performed': False,
        'known_transition_gate': gate, 'changed_calculation_counterexample_gate': bad_gate,
        'cases': rows, 'original_summary_modified': False,
        'boundary': 'Latent findings stay validation errors. Only source-registered parse recovery plus '
                    'identical scoped method/render calls (or identical parent inited/source watcher) '
                    'qualify as pre-existing. Unknown proofs fail closed; no fresh generation, no manual pass. '
                    'Private helper conversion requires readonly self-contained calculations, complete call '
                    'coverage and exact arity. This changed-code bundle is not a new model-run protocol.',
    }
    verify_snapshot(SOURCE)
    return artifacts, result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-evidence', action='store_true')
    args = parser.parse_args()
    if args.write_evidence and OUTPUT.exists():
        raise FileExistsError('Do not replace prior evidence')
    hashes = {name: digest(ROOT / name) for name in CODE_PATHS}
    tests = ''
    if args.write_evidence:
        print('Running complete local unit tests; no model requests.', flush=True)
        proc = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py'],
            cwd=ROOT, env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}, capture_output=True,
            text=True, encoding='utf-8')
        tests = proc.stdout + proc.stderr
        if proc.returncode:
            raise RuntimeError(f'Complete tests failed:\n{tests}')
    artifacts, result = replay()
    if any(digest(ROOT / name) != h for name, h in hashes.items()):
        raise RuntimeError('Code changed during verification')
    if args.write_evidence:
        match = re.search(r'Ran (\d+) tests in ([\d.]+)s', tests)
        if not match:
            raise RuntimeError('Unit test count unavailable')
        result['unit_tests'] = {'passed': int(match[1]), 'failed': 0, 'elapsed_seconds': float(match[2])}
        OUTPUT.mkdir(parents=True)
        for name, code in artifacts.items():
            path = OUTPUT / f'{name}_offline.san'
            path.write_text(code, encoding='utf-8')
            next(r for r in result['cases'] if r['case'] == name)['output_sha256'] = digest(path)
        for name in CODE_PATHS:
            path = OUTPUT / 'code' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, path)
        (OUTPUT / 'unit_tests.txt').write_text(tests, encoding='utf-8')
        (OUTPUT / 'replay.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (OUTPUT / 'verify_snapshot.py').write_text(VERIFY_SCRIPT, encoding='utf-8')
        files = sorted(p for p in OUTPUT.rglob('*') if p.is_file())
        (OUTPUT / 'SHA256SUMS.txt').write_text('\n'.join(
            f'{digest(p)}  {p.relative_to(OUTPUT).as_posix()}' for p in files) + '\n', encoding='utf-8')
        verify_snapshot(OUTPUT)
    print(json.dumps({'model_requests': 0, 'evidence_written': args.write_evidence,
        'unit_tests': result.get('unit_tests'), 'cases': [{'name': r['case'], 'passed_offline': r['passed_offline'],
        'remaining_errors': [e['code'] for e in r['after']['validation_errors']],
        'structure_similarity': r['after']['structure_similarity']} for r in result['cases']]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
