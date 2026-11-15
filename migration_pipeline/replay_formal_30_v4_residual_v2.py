"""Replay semantic rollback and residual repairs against verified frozen bytes."""

import json
from pathlib import Path
from unittest.mock import patch

from migration_pipeline.analyze_formal_30_v4_full_regression import digest, verify_snapshot
from migration_pipeline.replay_formal_30_v4_repair_scheduling import ReplayGenerate, ReplayCandidate
from migration_pipeline.replay_formal_30_v4_semantic_closure import evaluate
from migration_pipeline.orchestrator import MigrationPipelineOrchestrator
from migration_pipeline.stages.generate import GenerateStageInput
from migration_pipeline.stages.repair import RepairStage
from migration_pipeline.stages.validate import ValidateStage
from migration_pipeline.stages.visual_eval import VisualEvalStage
from migration_pipeline.utils.repair_scheduler import candidate_gate
from migration_pipeline.utils.repair_prompt import RepairPromptInput, build_repair_prompt


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/experiments/snapshots/formal_30_v4_semantic_closure_v1_results_20261103_145253'
OUTPUT = ROOT / 'data/experiments/analysis/formal_30_v4_residual_v2_20261103'


def main():
    checked = verify_snapshot(SOURCE)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    results = {'source_snapshot': SOURCE.name, 'verified_files': checked, 'llm_network_requests': 0,
               'classification': 'offline_frozen_development_replay', 'cases': []}
    for component in ('TaskManager', 'MonitoringDashboard'):
        report = json.loads((SOURCE / f'repair_reports/complex/{component}_repair_history.json').read_text(encoding='utf-8'))
        state = report['state']
        vue = SOURCE / f'protocol/frozen/data/datasets/components/03_complex/{component}/vue/{component}.vue'
        original = SOURCE / 'pipeline/complex' / Path(state['final_file_path']).name
        current = evaluate(original.read_text(encoding='utf-8'), state, vue)
        before_errors = current['validation_errors']
        steps = []
        for _ in range(4):
            code, repairs = RepairStage._deterministic_repair_plan(
                current['generated_code'], current['validation_errors'], current['visual_eval_errors'],
                state['ssm'], str(vue), enable_residual_v2=True)
            if code == current['generated_code']:
                break
            after = evaluate(code, state, vue)
            gate = candidate_gate(current, after)
            steps.append({'repairs': [name for _, name in repairs], 'gate': gate,
                          'remaining_errors': after['validation_errors']})
            if gate['should_stop']:
                raise AssertionError(f'Unexpected replay rejection: {component}/{gate}')
            current = after
        path = OUTPUT / f'{component}_prepared.san'
        path.write_text(current['generated_code'], encoding='utf-8')
        prompt = build_repair_prompt(RepairPromptInput(
            current_code=current['generated_code'], ssm=state['ssm'],
            validation_errors=current['validation_errors'], visual_eval_errors=current['visual_eval_errors']))
        prompt_path = OUTPUT / f'{component}_focused_prompt.txt'
        prompt_path.write_text(prompt, encoding='utf-8')
        expected = {'hidden_template_reactive_dependency'} if component == 'TaskManager' else {'lifecycle_behavior_not_landed'}
        if {e['code'] for e in current['validation_errors']} != expected or not current['visual_eval_passed']:
            raise AssertionError(f'Unexpected residual: {component}/{current["validation_errors"]}')
        if not prompt.startswith('You are repairing a standalone San single-file component.'):
            raise AssertionError('Focused route was not selected')
        results['cases'].append({'component': component, 'before_errors': before_errors,
            'remaining_errors': current['validation_errors'], 'steps': steps,
            'visual_eval_passed': current['visual_eval_passed'], 'structure_similarity': current['structure_similarity'],
            'input_sha256': digest(original), 'output_sha256': digest(path),
            'focused_prompt_chars': len(prompt), 'focused_prompt_sha256': digest(prompt_path),
            'passed': False})
        if component == 'TaskManager':
            before, bad = [h['repair_result']['repaired_code'] for h in state['repair_history'][1:3]]
            generate = ReplayGenerate(state, before, OUTPUT / 'rollback_before.san')
            repair = ReplayCandidate(bad, OUTPUT / 'rollback_rejected.san')
            orchestrator = MigrationPipelineOrchestrator(generate, ValidateStage(), VisualEvalStage(), repair)
            # Isolate the rejection gate. Captured model bytes replace any network call.
            with patch.object(RepairStage, '_deterministic_repair_plan', side_effect=lambda code, *_: (code, [])):
                rollback = orchestrator.run_generate_validate_visual_eval_and_repair_loop(
                    GenerateStageInput(vue_file_path=str(vue), metadata={'repair_policy': 'bounded_prepass_v1'}),
                    max_repair_rounds=3).state
            if (not rollback['retained_previous_candidate'] or rollback['final_code'] != before
                    or rollback['final_passed'] or not rollback['repair_history'][-1]['repair_regression_rejected']):
                raise AssertionError('Semantic rollback did not preserve failed previous candidate')
            results['semantic_rollback'] = {'previous_failed_candidate_retained': True,
                'gate': rollback['repair_regression_gate'], 'final_passed': False,
                'rejected_sha256': digest(Path(rollback['rejected_candidate_file']))}
    verify_snapshot(SOURCE)
    (OUTPUT / 'replay.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'llm_network_requests': 0, 'rollback_verified': True,
        'cases': [{'component': c['component'], 'remaining_errors': [e['code'] for e in c['remaining_errors']],
                   'focused_prompt_chars': c['focused_prompt_chars']} for c in results['cases']]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
