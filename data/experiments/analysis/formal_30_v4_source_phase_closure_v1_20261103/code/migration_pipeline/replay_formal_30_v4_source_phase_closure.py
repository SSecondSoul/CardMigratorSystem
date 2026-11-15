"""Replay verified MonitoringDashboard bytes; optional separate evidence, no LLM."""

import argparse
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from migration_pipeline.analyze_formal_30_v4_full_regression import digest, verify_snapshot
from migration_pipeline.freeze_formal_30_v3_results import VERIFY_SCRIPT
from migration_pipeline.replay_formal_30_v4_semantic_closure import evaluate
from migration_pipeline.stages.repair import RepairStage
from migration_pipeline.utils.bounded_semantics import inspect_semantics
from migration_pipeline.utils.repair_scheduler import candidate_gate


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/experiments/snapshots/formal_30_v4_semantic_closure_v2_results_20261103_160541'
OUTPUT = ROOT / 'data/experiments/analysis/formal_30_v4_source_phase_closure_v1_20261103'
RULES = ['restored_source_loop_payload_handler', 'restored_source_mounted_phase_order',
         'restored_source_watch_persistence']


def replay():
    checked = verify_snapshot(SOURCE)
    report_path = SOURCE / 'repair_reports/complex/MonitoringDashboard_repair_history.json'
    state = json.loads(report_path.read_text(encoding='utf-8'))['state']
    original = SOURCE / 'pipeline/complex' / Path(state['final_file_path']).name
    vue = SOURCE / 'protocol/frozen/data/datasets/components/03_complex/MonitoringDashboard/vue/MonitoringDashboard.vue'
    if original.read_text(encoding='utf-8') != state['generated_code']:
        raise RuntimeError('Final artifact differs from repair history')
    before = evaluate(state['generated_code'], state, vue)
    expected = {'event_arguments_not_landed', 'lifecycle_behavior_not_landed',
                'source_watch_persistence_not_landed', 'source_mounted_order_not_landed'}
    if {e['code'] for e in before['validation_errors']} != expected:
        raise RuntimeError(f"Unexpected current-checker baseline: {before['validation_errors']}")
    code, applied = RepairStage._deterministic_repair_plan(
        before['generated_code'], before['validation_errors'], before['visual_eval_errors'],
        state['ssm'], str(vue), enable_residual_v2=True)
    if [label for _, label in applied] != RULES:
        raise RuntimeError(f'Unexpected rule set: {applied}')
    after = evaluate(code, state, vue)
    gate = candidate_gate(before, after)
    if not after['validation_passed'] or not after['visual_eval_passed'] or gate['should_stop']:
        raise RuntimeError(f'Offline candidate failed: {after["validation_errors"]}; {gate}')
    if inspect_semantics(code, vue.read_text(encoding='utf-8'), repair=True, ssm=state['ssm'])['code'] != code:
        raise RuntimeError('Rules are not idempotent')
    # No child edits or CSS/DOM restyling are part of these parent-only repairs.
    if (before['generated_code'].split('<script>', 1)[1].split('module.exports', 1)[0]
            != code.split('<script>', 1)[1].split('module.exports', 1)[0]
            or before['generated_code'].split('<style>', 1)[1] != code.split('<style>', 1)[1]):
        raise RuntimeError('Unexpected child or CSS edit')
    verify_snapshot(SOURCE)
    result = {
        'created_at': datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'classification': 'offline_known_failure_development_replay_not_fresh_model_regression',
        'sample': 'MonitoringDashboard', 'source_snapshot': SOURCE.relative_to(ROOT).as_posix(),
        'source_verified_files': checked, 'original_sha256': digest(original),
        'source_vue': vue.relative_to(ROOT).as_posix(), 'source_vue_sha256': digest(vue),
        'source_repair_history_sha256': digest(report_path),
        'original_frozen_automatic_pass': state['final_passed'],
        'before': {k: v for k, v in before.items() if k not in {'generated_code', 'ssm'}},
        'after': {k: v for k, v in after.items() if k not in {'generated_code', 'ssm'}},
        'applied_rules': RULES, 'candidate_gate': gate,
        'idempotence_passed': True, 'child_code_unchanged': True, 'css_unchanged': True,
        'llm_requests': 0, 'fresh_generation_performed': False,
        'browser_interaction_test_performed': False, 'manual_status': 'not_evaluated',
        'original_batch_summary_modified': False,
        'boundary': 'Current checker adds two source-proven findings. Original frozen scoring is unchanged. '
                    'This replay fixes known bytes and cannot replace a new protocol/fresh model regression '
                    'or prove all inline-child interactions, watcher behaviors, or the full 30-sample regression.',
    }
    return code, result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-evidence', action='store_true')
    args = parser.parse_args()
    if args.write_evidence and OUTPUT.exists():
        raise FileExistsError('Evidence exists; never replace it')
    code, result = replay()
    if args.write_evidence:
        OUTPUT.mkdir(parents=True)
        candidate = OUTPUT / 'MonitoringDashboard_offline_candidate.san'
        candidate.write_text(code, encoding='utf-8')
        result['candidate_sha256'] = digest(candidate)
        result['candidate'] = candidate.relative_to(ROOT).as_posix()
        (OUTPUT / 'replay.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        # A focused changed-code record, NOT a complete new model-run protocol.
        changed = [
            'migration_pipeline/utils/source_phase_semantics.cjs',
            'migration_pipeline/utils/bounded_semantics.cjs',
            'migration_pipeline/utils/bounded_semantics.py',
            'migration_pipeline/utils/repair_prompt.py',
            'migration_pipeline/utils/repair_scheduler.py',
            'migration_pipeline/stages/repair.py', 'migration_pipeline/stages/validate.py',
            'tests/test_source_phase_semantics.py',
            'migration_pipeline/replay_formal_30_v4_source_phase_closure.py',
        ]
        for name in changed:
            destination = OUTPUT / 'code' / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, destination)
        (OUTPUT / 'verify_snapshot.py').write_text(VERIFY_SCRIPT, encoding='utf-8')
        files = sorted(p for p in OUTPUT.rglob('*') if p.is_file())
        (OUTPUT / 'SHA256SUMS.txt').write_text('\n'.join(
            f'{digest(p)}  {p.relative_to(OUTPUT).as_posix()}' for p in files) + '\n', encoding='utf-8')
        verify_snapshot(OUTPUT)
    print(json.dumps({'llm_requests': 0, 'rules': result['applied_rules'],
        'validation_passed': result['after']['validation_passed'],
        'visual_eval_passed': result['after']['visual_eval_passed'],
        'structure_similarity': result['after']['structure_similarity'],
        'evidence_written': args.write_evidence}, ensure_ascii=False))


if __name__ == '__main__':
    main()
