"""Read-only source evidence, separate repaired replay artifacts, no LLM requests."""

import json
from pathlib import Path

from migration_pipeline.analyze_formal_30_v4_full_regression import verify_snapshot, digest
from migration_pipeline.stages.repair import RepairStage
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.stages.visual_eval import VisualEvalStage, VisualEvalStageInput
from migration_pipeline.utils.repair_scheduler import candidate_gate


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/experiments/snapshots/formal_30_v4_repair_scheduling_v1_results_20261102_224614'
OUTPUT = ROOT / 'data/experiments/analysis/formal_30_v4_semantic_closure_v1_20261102'


def evaluate(code, state, vue):
    validation = ValidateStage().run(ValidateStageInput(generated_code=code, ssm=state['ssm'],
                                                       vue_file_path=str(vue)))
    visual = VisualEvalStage().run(VisualEvalStageInput(generated_code=code, vue_file_path=str(vue)))
    return {'generated_code': code, 'ssm': state['ssm'], 'vue_file_path': str(vue),
            'validation_errors': validation.validation_errors, 'visual_eval_errors': visual.visual_eval_errors,
            'visual_eval_passed': visual.visual_eval_passed, 'validation_passed': validation.validation_passed,
            'structure_similarity': visual.structure_similarity}


def main():
    checked = verify_snapshot(SOURCE)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    data = {'verified_raw_files': checked, 'source_snapshot': SOURCE.name, 'llm_requests': 0,
            'classification': 'frozen_failure_development_replay_not_model_regression', 'cases': []}
    cases = [('TaskManager_final', 'TaskManager', 'TaskManager_repaired.san'),
             ('TaskManager_rejected', 'TaskManager', 'TaskManager_repaired_repaired.san'),
             ('MonitoringDashboard_final', 'MonitoringDashboard',
              'MonitoringDashboard_normalized_1_repaired_normalized_2_repaired_normalized_3_repaired.san')]
    for name, component, filename in cases:
        state = json.loads((SOURCE / f'repair_reports/complex/{component}_repair_history.json').read_text(encoding='utf-8'))['state']
        vue = SOURCE / f'protocol/frozen/data/datasets/components/03_complex/{component}/vue/{component}.vue'
        original = SOURCE / 'pipeline/complex' / filename
        current = evaluate(original.read_text(encoding='utf-8'), state, vue)
        before_codes = sorted({e['code'] for e in current['validation_errors']})
        steps = []
        for _ in range(4):
            code, repairs = RepairStage._deterministic_repair_plan(current['generated_code'], current['validation_errors'],
                current['visual_eval_errors'], state['ssm'], str(vue))
            if code == current['generated_code']:
                break
            candidate = evaluate(code, state, vue)
            gate = candidate_gate(current, candidate)
            steps.append({'repairs': [label for _, label in repairs], 'gate': gate,
                          'validation_errors': candidate['validation_errors'],
                          'structure_similarity': candidate['structure_similarity']})
            if gate['should_stop']:
                raise AssertionError(f'Unexpected gate rejection: {name}/{gate}')
            current = candidate
        output = OUTPUT / f'{name}.san'
        output.write_text(current['generated_code'], encoding='utf-8')
        row = {'case': name, 'input_sha256': digest(original), 'output_sha256': digest(output),
               'steps': steps, 'before_error_codes': before_codes,
               'remaining_errors': current['validation_errors'],
               'visual_eval_passed': current['visual_eval_passed'], 'structure_similarity': current['structure_similarity'],
               'validation_passed': current['validation_passed'],
               'passed_replay': current['validation_passed'] and current['visual_eval_passed']}
        data['cases'].append(row)
    if any(not r['visual_eval_passed'] for r in data['cases']):
        raise AssertionError('Offline visual regression')
    if not data['cases'][-1]['passed_replay']:
        raise AssertionError('Expected bounded MonitoringDashboard residuals to close')
    expected_task = [
        {'invalid_san_event_handler_syntax', 'missing_self_click_guard',
         'invalid_san_computed_instance_method_call', 'hidden_template_reactive_dependency'},
        {'invalid_san_event_handler_syntax', 'invalid_san_computed_instance_method_call'},
    ]
    for row, expected in zip(data['cases'][:2], expected_task):
        if {e['code'] for e in row['remaining_errors']} != expected:
            raise AssertionError(f'Unexpected TaskManager residual: {row}')
    verify_snapshot(SOURCE)
    (OUTPUT / 'replay.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'llm_requests': 0, 'cases': [{k: row[k] for k in
        ('case', 'passed_replay', 'remaining_errors', 'structure_similarity')} for row in data['cases']]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
