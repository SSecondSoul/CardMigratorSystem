"""Prepare a separately attributed manual-feedback repair; never overwrite v2."""

import json
import shutil
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from migration_pipeline.analyze_formal_30_v4_full_regression import digest, verify_snapshot
from migration_pipeline.freeze_formal_30_v3_results import VERIFY_SCRIPT
from migration_pipeline.stages.repair import RepairStage
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.utils.textarea_binding import textarea_binding


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/experiments/snapshots/formal_30_v4_semantic_closure_v2_results_20261103_160541'
TARGET = ROOT / 'data/experiments/manual_followups/formal_30_v4_semantic_closure_v2_TaskManager_textarea_v1_20261103'


def main():
    # A failed preparation may have written only this candidate. Resume only
    # that exact shape, and verify the existing candidate before adding files.
    if TARGET.exists() and {p.relative_to(TARGET).as_posix() for p in TARGET.rglob('*') if p.is_file()} != {'TaskManager_textarea_fixed.san'}:
        raise FileExistsError(TARGET)
    verified = verify_snapshot(SOURCE)
    report = json.loads((SOURCE / 'repair_reports/complex/TaskManager_repair_history.json').read_text(encoding='utf-8'))
    state = report['state']
    old_path = SOURCE / 'pipeline/complex' / Path(state['final_file_path']).name
    vue = SOURCE / 'protocol/frozen/data/datasets/components/03_complex/TaskManager/vue/TaskManager.vue'
    original = old_path.read_text(encoding='utf-8')
    before = ValidateStage().run(ValidateStageInput(generated_code=original, vue_file_path=str(vue), ssm=state['ssm']))
    if {e['code'] for e in before.validation_errors} != {'invalid_san_textarea_binding'}:
        raise RuntimeError(f'Unexpected current-validator baseline: {before.validation_errors}')
    repaired, rules = RepairStage._deterministic_repair_plan(original, before.validation_errors, [], state['ssm'], str(vue))
    if [name for _, name in rules] != ['normalized_textarea_value_binding'] or repaired == original:
        analysis = textarea_binding(original, True)
        raise RuntimeError(f'Expected only textarea rule: rules={rules}; error={analysis.get("error")}; findings={analysis["findings"]}')
    after = ValidateStage().run(ValidateStageInput(generated_code=repaired, vue_file_path=str(vue), ssm=state['ssm']))
    if not after.validation_passed:
        raise RuntimeError(f'Repaired candidate failed: {after.validation_errors}')
    # Keep both the Vue and San notification behavior, not just a similar phrase.
    message = '设置已更新：${key}'
    if message not in original or message not in repaired or message not in vue.read_text(encoding='utf-8'):
        raise RuntimeError('Source notification wording mismatch')
    TARGET.mkdir(parents=True, exist_ok=True)
    candidate = TARGET / 'TaskManager_textarea_fixed.san'
    if candidate.exists():
        if candidate.read_text(encoding='utf-8') != repaired:
            raise RuntimeError('Partial candidate differs; do not overwrite')
    else:
        candidate.write_text(repaired, encoding='utf-8')
    (TARGET / 'validation_before.json').write_text(json.dumps(asdict(before), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (TARGET / 'validation_after.json').write_text(json.dumps(asdict(after), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    metadata = {
        'created_at': datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'classification': 'manual_feedback_triggered_deterministic_followup_not_original_batch_score',
        'sample': 'TaskManager', 'source_snapshot': SOURCE.name, 'source_verified_files': verified,
        'original_san_sha256': digest(old_path), 'source_vue': vue.relative_to(ROOT).as_posix(),
        'source_vue_sha256': digest(vue), 'candidate_sha256': digest(TARGET / 'TaskManager_textarea_fixed.san'),
        'original_frozen_automatic_pass': True, 'original_manual_status': 'issues_reported_not_passed',
        'candidate_manual_status': 'pending_retest', 'llm_calls': 0,
        'user_reports': ['新建任务的任务描述里面有代码，右下角掏出的提示带英文',
                         '设置已更新：defaultView  更改设置后出现'],
        'textarea_issue': {'source': '<textarea v-model="formData.description"></textarea>',
                           'generated': '<textarea>{= formData.description =}</textarea>',
                           'fix': '<textarea value="{= formData.description =}"></textarea>'},
        'notification_issue': {'message': '设置已更新：defaultView',
                               'classification': 'same_as_vue_source_not_san_regression', 'changed': False},
        'applied_rules': [name for _, name in rules], 'batch_summary_modified': False,
    }
    (TARGET / 'manifest.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    sources = ['migration_pipeline/utils/textarea_binding.py', 'migration_pipeline/utils/textarea_binding.cjs',
               'migration_pipeline/stages/validate.py', 'migration_pipeline/stages/repair.py',
               'migration_pipeline/utils/repair_scheduler.py', 'migration_pipeline/utils/repair_prompt.py',
               'tests/test_textarea_binding.py', 'migration_pipeline/prepare_task_manager_textarea_manual_followup.py']
    for name in sources:
        destination = TARGET / 'code' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, destination)
    (TARGET / 'verify_snapshot.py').write_text(VERIFY_SCRIPT, encoding='utf-8')
    files = sorted(p for p in TARGET.rglob('*') if p.is_file())
    (TARGET / 'SHA256SUMS.txt').write_text('\n'.join(f'{digest(p)}  {p.relative_to(TARGET).as_posix()}' for p in files) + '\n', encoding='utf-8')
    subprocess.run([sys.executable, str(TARGET / 'verify_snapshot.py')], cwd=ROOT, check=True)
    verify_snapshot(SOURCE)
    print(TARGET.relative_to(ROOT))
    print('candidate_manual_status: pending_retest; original_batch_score_unchanged: true; llm_calls: 0')


if __name__ == '__main__':
    main()
