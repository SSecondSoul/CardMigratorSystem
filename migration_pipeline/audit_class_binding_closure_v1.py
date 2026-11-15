"""Freeze the class-binding escape before changing production code."""
import argparse
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import shutil
import subprocess

from migration_pipeline.analyze_formal_30_v4_full_regression import ROOT, digest, verify_snapshot

BASELINE = ROOT / 'data/experiments/analysis/formal_30_v4_class_binding_pre_fix_20261113'
V7 = ROOT / 'data/experiments/analysis/formal_30_v4_async_watcher_scope_v7_20261113'
MANUAL = ROOT / 'data/experiments/manual_followups/task_manager_async_scope_v7_prepared_20261113'
TARGETS = ['migration_pipeline/stages/validate.py', 'migration_pipeline/stages/repair.py',
           'migration_pipeline/utils/repair_prompt.py', 'migration_pipeline/utils/repair_scheduler.py',
           'local_server/api/evaluation_routes.py']


def freeze_legacy_guard_before():
    """Additional target discovered during implementation; preserve separately."""
    folder = BASELINE.with_name('formal_30_v4_class_binding_legacy_guard_pre_fix_20261113')
    original = json.loads((BASELINE / 'audit.json').read_text(encoding='utf-8'))
    name = 'migration_pipeline/orchestrator.py'
    if digest(ROOT / name) != original['old_inventory'][name]:
        raise RuntimeError('Legacy orchestrator changed before supplemental baseline')
    folder.mkdir(parents=True, exist_ok=False)
    shutil.copy2(ROOT / name, folder / 'orchestrator.py')
    with (folder / 'SHA256SUMS.txt').open('x', encoding='utf-8') as stream:
        stream.write(f'{digest(folder / "orchestrator.py")}  orchestrator.py\n')
    print(json.dumps({'supplemental_baseline': str(folder.relative_to(ROOT)), 'payloads': verify_snapshot(folder.resolve())}))


def freeze_before():
    if BASELINE.exists():
        raise FileExistsError('Never overwrite class-binding pre-fix evidence')
    inventory = json.loads((MANUAL / 'live_inventory.json').read_text(encoding='utf-8'))
    drift = [name for name, expected in inventory.items() if digest(ROOT / name) != expected]
    if drift:
        raise RuntimeError('Unexpected changes before class-binding fix: ' + str(drift))
    from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
    from migration_pipeline.utils.source_template_semantics import source_template_semantics
    old = json.loads((V7 / 'audit.json').read_text(encoding='utf-8'))
    code = old['candidate']['code']
    vue_path = ROOT / next(name for name in old['source_inputs'] if name.endswith('.vue'))
    validation = ValidateStage().run(ValidateStageInput(generated_code=code, vue_file_path=str(vue_path))).to_state_update()
    node = r'''const fs=require('fs'),san=require('san'),Data=require('san/src/runtime/data'),evalExpr=require('san/src/runtime/eval-expr');
const code=JSON.parse(fs.readFileSync(0,'utf8')).code,template=/<template\b[^>]*>([\s\S]*?)<\/template>/.exec(code)[1];
const prop=san.parseTemplate(template).children.find(n=>n.tagName==='div').props.find(p=>p.name==='class');
const states=[];for(const dark of [false,true])for(const compact of [false,true])states.push({dark,compact,classValue:evalExpr(prop.expr,new Data({isDarkMode:dark,isCompactMode:compact}))});
process.stdout.write(JSON.stringify({classAST:prop.expr,states}));'''
    native = json.loads(subprocess.run(['node', '-e', node], cwd=ROOT, input=json.dumps({'code': code}),
        text=True, encoding='utf-8', capture_output=True, check=True).stdout)
    data = {'created_at': datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'classification': 'frozen_pre_fix_class_binding_validator_escape',
        'manual_symptom': 'User reports San initially dark; no manual pass claimed.',
        'candidate_reference': str((V7 / 'TaskManager_async_scope_v7_offline.san').relative_to(ROOT)),
        'source_reference': vue_path.relative_to(ROOT).as_posix(),
        'validation_before': validation, 'source_template_analysis_before': source_template_semantics(code, vue_path.read_text(encoding='utf-8')),
        'native_before': native, 'target_files_sha256': {name: digest(ROOT / name) for name in TARGETS},
        'old_inventory': inventory, 'old_manual_pages': json.loads((MANUAL / 'status.json').read_text(encoding='utf-8'))['original_pages_unchanged'],
        'original_aggregate': old['original_aggregate'], 'model_requests': 0, 'original_score_modified': False}
    BASELINE.mkdir(parents=True, exist_ok=False)
    for name in TARGETS:
        target = BASELINE / 'code' / name; target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT / name, target)
    with (BASELINE / 'audit.json').open('x', encoding='utf-8') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2); stream.write('\n')
    files = sorted(p for p in BASELINE.rglob('*') if p.is_file())
    with (BASELINE / 'SHA256SUMS.txt').open('x', encoding='utf-8') as stream:
        stream.write('\n'.join(f'{digest(p)}  {p.relative_to(BASELINE).as_posix()}' for p in files) + '\n')
    print(json.dumps({'payloads': verify_snapshot(BASELINE.resolve()), 'native_class_states': native['states'],
        'class_error_codes_before': [e['code'] for e in validation['validation_errors'] if 'class' in e['code']],
        'san_compile_passed_before': validation['san_compile_result']['passed']}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--freeze-before', action='store_true')
    parser.add_argument('--freeze-legacy-guard-before', action='store_true')
    args = parser.parse_args()
    if args.freeze_before: freeze_before()
    elif args.freeze_legacy_guard_before: freeze_legacy_guard_before()
    else: parser.error('Choose a pre-fix freeze action')
