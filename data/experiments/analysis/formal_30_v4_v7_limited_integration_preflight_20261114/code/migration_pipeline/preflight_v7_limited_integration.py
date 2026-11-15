"""Record explicit manual acceptance and freeze a fail-closed integration preflight.

Only local evidence, native offline checks and unit tests. No model/browser/server.
The accepted application declaration does not remove semantic diagnostics.
"""
import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

from migration_pipeline.utils.v7_integration_contract import V7_APPLICATION_SCOPE, evaluate_v7_application_scope

ROOT = Path(__file__).resolve().parents[1]
PREPARED = ROOT / 'data/experiments/manual_followups/task_manager_v7_class_binding_prepared_20261114'
OUTPUT = ROOT / 'data/experiments/analysis/formal_30_v4_v7_limited_integration_preflight_20261114'
NOTEBOOK = ROOT / 'notebooks/02-migration-experiments/2026-11-04_formal_30_v4_full_regression_v2.ipynb'
CODE = ['migration_pipeline/utils/v7_integration_contract.py',
        'migration_pipeline/preflight_v7_limited_integration.py', 'tests/test_v7_integration_contract.py']
RUNTIME = ['migration_pipeline/stages/validate.py', 'migration_pipeline/stages/repair.py',
           'migration_pipeline/utils/repair_scheduler.py', 'migration_pipeline/utils/repair_prompt.py',
           'migration_pipeline/utils/source_parent_watch_semantics.cjs',
           'migration_pipeline/probe_async_watcher_scope_v7.cjs',
           'migration_pipeline/probe_async_watcher_scope_adapter_v7.cjs',
           'tests/manual/v7-acceptance.html', 'tests/manual/v7-acceptance.js',
           'tests/manual/v7-acceptance-config.json']
SUITES = ['test_v7_integration_contract.py', 'test_async_watcher_scope_v7.py',
          'test_parent_watch_scope_guard.py', 'test_class_binding_closure_v1.py']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()


def write_json(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2); stream.write('\n')


def verify_bundle(folder):
    for line in (folder / 'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        expected, name = line.split('  ', 1); path = (folder / name).resolve()
        if not path.is_relative_to(folder.resolve()) or sha(path) != expected:
            raise RuntimeError('Frozen evidence mismatch: ' + name)


def prepare():
    if OUTPUT.exists(): raise FileExistsError('Never overwrite an integration preflight')
    from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
    from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
    from migration_pipeline.utils.repair_scheduler import candidate_gate
    verify_bundle(PREPARED)
    manifest = json.loads((PREPARED / 'manifest.json').read_text(encoding='utf-8'))
    prepared = json.loads((PREPARED / 'status.json').read_text(encoding='utf-8'))
    for name, expected in {**prepared['original_files_sha256'], **prepared['new_files_sha256'], **prepared['sources']}.items():
        if sha(ROOT / name) != expected: raise RuntimeError('Prepared file drift: ' + name)
    hashes = {name: sha(ROOT / name) for name in [*CODE, *RUNTIME]}
    original = json.loads(NOTEBOOK.read_text(encoding='utf-8'))
    vue_path = ROOT / manifest['frameworks']['vue']['component']['path']
    san_path = ROOT / manifest['frameworks']['san']['component']['path']
    vue = vue_path.read_text(encoding='utf-8'); code = san_path.read_text(encoding='utf-8')
    scope = evaluate_v7_application_scope(V7_APPLICATION_SCOPE, manifest)
    if not scope['application_scope_accepted'] or scope['production_eligible']:
        raise RuntimeError('Expected scope acceptance, not production promotion')
    validation = ValidateStage().run(ValidateStageInput(generated_code=code, vue_file_path=str(vue_path))).to_state_update()
    diagnostics = source_parent_watch_semantics(code, vue)
    codes = sorted({e['code'] for e in validation['validation_errors']})
    expected_codes = ['source_parent_watch_dynamic_key_unproven', 'source_parent_watch_exception_policy_unproven',
                      'source_parent_watch_not_landed']
    if codes != expected_codes or validation['validation_passed']:
        raise RuntimeError('Production blockers changed: ' + str(codes))
    before = {'generated_code': code, 'vue_source': vue, **validation}
    forged = candidate_gate(before, {**before, 'validation_passed': True, 'validation_errors': []})
    if not forged['should_stop'] or len(forged['waived_source_parent_watch_boundaries']) != 2:
        raise RuntimeError('Scope declaration must not waive production boundaries')
    OUTPUT.mkdir(parents=True, exist_ok=False)
    shutil.copy2(NOTEBOOK, OUTPUT / 'notebook_before.ipynb')
    # Acceptance is immutable follow-up evidence; the preparation manifest stays
    # awaiting_user as originally frozen, rather than rewriting old history.
    acceptance = {
        'recorded_at': datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'case_id': manifest['case_id'], 'component': manifest['component'], 'complexity': 'complex',
        'prepared_bundle': PREPARED.relative_to(ROOT).as_posix(), 'manifest_sha256': sha(PREPARED / 'manifest.json'),
        'user_confirmation': '通过，开始下一步', 'normal_interaction': 'confirmed_by_user',
        'individual_checklist_items': 'not_individually_attested', 'optional_storage_failure': 'not_confirmed',
        'planned_pairs_this_followup': 1, 'confirmed_pairs_this_followup': 1,
        'not_independent_test_set': True, 'production_pass': False, 'original_scores_modified': False,
        'assets': manifest['frameworks'], 'user_supplied_screenshots_or_browser_logs': False,
        'application_scope_authorization': '先按此受限范围推进',
        'issues': [{'id': 'class-map-prefix-escape', 'category': 'production_defect', 'framework': 'san',
                    'symptom': 'False initial theme flags still produced an always-on dark-theme token.',
                    'status': 'confirmed_by_user_for_this_frozen_candidate',
                    'remaining_risk': 'Experimental runtime binding and source watcher contracts still block production admission.'}]
    }
    write_json(OUTPUT / 'manual_acceptance.json', acceptance)
    write_json(OUTPUT / 'application_scope.json', V7_APPLICATION_SCOPE)
    write_json(OUTPUT / 'scope_assessment.json', scope)
    write_json(OUTPUT / 'actual_validation.json', validation)
    write_json(OUTPUT / 'watcher_analysis.json', {k: v for k, v in diagnostics.items() if k != 'code'})
    write_json(OUTPUT / 'forged_pass_gate.json', forged)
    tests = []
    for suite in SUITES:
        print('Testing ' + suite, flush=True)
        run = subprocess.run(['python', '-m', 'unittest', 'discover', '-s', 'tests', '-p', suite, '-v'], cwd=ROOT,
            capture_output=True, text=True, encoding='utf-8')
        log = run.stdout + run.stderr
        with (OUTPUT / (suite + '.log')).open('x', encoding='utf-8') as stream: stream.write(log)
        match = re.search(r'Ran (\d+) tests? in ([\d.]+)s', log)
        item = {'suite': suite, 'tests': int(match[1]) if match else None, 'returncode': run.returncode,
                'seconds': float(match[2]) if match else None}
        tests.append(item); print(json.dumps(item), flush=True)
    write_json(OUTPUT / 'tests.json', tests)
    current_hashes = {name: sha(ROOT / name) for name in hashes}
    if hashes != current_hashes: raise RuntimeError('Files changed during preflight')
    current = json.loads(NOTEBOOK.read_text(encoding='utf-8'))
    if current != original: raise RuntimeError('Notebook changed; never overwrite editor changes')
    audit = {
        'classification': 'manual_acceptance_and_limited_integration_prerequisite_not_production_release',
        'manual_status': 'normal_interaction_confirmed_by_user', 'optional_storage_failure': 'not_confirmed',
        'application_scope_accepted': True, 'production_eligible': False,
        'remaining_validation_codes': codes, 'source_watch_proofs': diagnostics['proofs'],
        'production_code_modified': False, 'validator_or_scheduler_relaxed': False,
        'existing_files_sha256': hashes, 'prepared_original_files_sha256': prepared['original_files_sha256'],
        'source_assets': prepared['sources'], 'test_results': tests,
        'prior_notebook_cells': len(original['cells']), 'prior_notebook_cells_sha256': stable(original['cells']),
        'prior_notebook_metadata_sha256': stable(original['metadata']),
        'model_requests': 0, 'browser_started_by_agent': False, 'server_started_by_agent': False,
        'original_aggregate': prepared['original_aggregate'], 'original_scores_modified': False,
        'next_implementation_order': [
            'Prove the exact v7 async queue/source-lifecycle match without accepting marker names alone.',
            'Prove dynamic object-key/property-shape behavior and public method consumers; do not narrow arbitrary keys to UI-only keys.',
            'Implement a source-matched runtime reporting bridge for the declared browser scope, including timing/disposal/dependency boundaries.',
            'Only then connect proven diagnostics, deterministic repair and independent regression gates; no fake-pass metadata.',
            'Replay frozen failures and broaden regression before any paid single-sample rerun or 30-sample batch.'
        ]
    }
    write_json(OUTPUT / 'audit.json', audit)
    for name in CODE:
        target = OUTPUT / 'code' / name; target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT / name, target)
    all_passed = all(t['returncode'] == 0 for t in tests)
    count = sum(t['tests'] or 0 for t in tests)
    report = f'''# v7 受限接入预检与人工确认 — 2026-11-14

## 本次结论

- 用户明确反馈“通过，开始下一步”：记录本次 1/1 对正常交互人工通过。未逐项提供检查结果、截图或浏览器日志；可选保存故障未确认，不推断为执行过或通过。
- 确认对象是 manifest 固定的 TaskManager v7 + class 修复候选，不是旧默认暗黑版本。旧准备目录的 awaiting_user 保持原样，结果另存 manual_acceptance.json。
- 用户选择“先按此受限范围推进”：固定浏览器、无源祖先错误捕获、全局同步只报告错误及不访问响应式状态、固定 Vue 2.7.16 / San 3.15.6。其他配置拒绝，不宣称验证任意函数纯度。
- 新增通用、无组件名特例的应用范围声明检查器。scope accepted 只是前置条件，source equivalence / runtime callback purity / production eligible 均为 false；尚未接入生产放行路径。
- 当前完整 ValidateStage 仍有三项：{', '.join(codes)}。即使伪造 validation_passed 并清空诊断，独立候选门仍拒绝。
- {count} 项定向测试，全部通过：{all_passed}；不是完整测试集或新模型运行。0 模型调用，未启动浏览器或服务器。原批 24/30、6 失败、1,821,544 tokens 不变。

## 不能混淆的差距

1. v7 完整模板正常交互得到人工确认；现有源码 matcher 对 v7 私有队列/生命周期包装仍不给出 normal-flow proof。不能只看到 __watcherScope_v7 字符串就消除 not_landed。
2. source updateSettings(key,value) 仍有任意动态键／属性形状、继承和别名语义的证明缺口。UI 已知选项不等于公开方法只允许这些键，不能为修复而缩小业务接口。
3. 验收页在 inited 后、首次排队前配置的 reporting-only bridge 仍是实验应用代码；受限范围已得到授权，但生产 emitter、运行时调用时机和依赖边界尚未证明与默认 Vue 匹配。

## 下一阶段顺序

先做异步队列与源码契约的精确识别，再做动态键／形状和受限错误桥接。每项以冻结失败 oracle 和正负测试验收，再接入规则、验证器、调度器与模型前后处理。保留三项阻断直到证据足够，不继续堆 Prompt 或用付费复跑代替证明。

旧页面、组件、准备 manifest、生产 validator/repair/scheduler/Prompt 均未修改；Notebook 只追加，不覆盖历史 {len(original['cells'])} 单元。
'''
    with (OUTPUT / 'REPORT.md').open('x', encoding='utf-8') as stream: stream.write(report)
    items = sorted(p for p in OUTPUT.rglob('*') if p.is_file())
    with (OUTPUT / 'SHA256SUMS.txt').open('x', encoding='utf-8') as stream:
        stream.write('\n'.join(sha(p) + '  ' + p.relative_to(OUTPUT).as_posix() for p in items) + '\n')
    if not all_passed: raise RuntimeError('Preflight tests failed; evidence retained, Notebook not promoted')
    check = '''from pathlib import Path
import json, hashlib
root = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / 'migration_pipeline').is_dir())
folder = root / 'data/experiments/analysis/formal_30_v4_v7_limited_integration_preflight_20261114'
audit = json.loads((folder / 'audit.json').read_text(encoding='utf-8'))
acceptance = json.loads((folder / 'manual_acceptance.json').read_text(encoding='utf-8'))
for line in (folder / 'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
    expected, name = line.split('  ', 1)
    assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == expected, name
for name, expected in {**audit['existing_files_sha256'], **audit['prepared_original_files_sha256'], **audit['source_assets']}.items():
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected, name
assert acceptance['normal_interaction'] == 'confirmed_by_user' and acceptance['optional_storage_failure'] == 'not_confirmed'
assert acceptance['planned_pairs_this_followup'] == acceptance['confirmed_pairs_this_followup'] == 1
scope = json.loads((folder / 'scope_assessment.json').read_text(encoding='utf-8'))
assert scope['application_scope_accepted'] and not scope['production_eligible'] and not scope['source_equivalence_proven']
validation = json.loads((folder / 'actual_validation.json').read_text(encoding='utf-8'))
assert not validation['validation_passed'] and len(audit['remaining_validation_codes']) == 3
assert json.loads((folder / 'forged_pass_gate.json').read_text(encoding='utf-8'))['should_stop']
assert all(t['returncode'] == 0 for t in audit['test_results']) and audit['model_requests'] == 0
nb = json.loads((root / 'notebooks/02-migration-experiments/2026-11-04_formal_30_v4_full_regression_v2.ipynb').read_text(encoding='utf-8'))
stable = lambda value: hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()
assert stable(nb['cells'][:audit['prior_notebook_cells']]) == audit['prior_notebook_cells_sha256']
assert stable(nb['metadata']) == audit['prior_notebook_metadata_sha256']
print({'normal_manual_pairs': '1/1 user-confirmed', 'optional_fault': 'not confirmed', 'production': 'blocked', 'tests': sum(t['tests'] for t in audit['test_results'])})
'''
    markdown = '## 2026-11-14：v7 人工通过与受限接入预检\n\n' + report.split('\n', 1)[1]
    markdown += '\n证据目录：`data/experiments/analysis/formal_30_v4_v7_limited_integration_preflight_20261114`。\n'
    original['cells'].extend([
        {'cell_type': 'markdown', 'id': 'v7-limited-integration-preflight-20261114', 'metadata': {}, 'source': markdown.splitlines(keepends=True)},
        {'cell_type': 'code', 'id': 'v7-limited-integration-check-20261114', 'metadata': {}, 'execution_count': None, 'outputs': [], 'source': check.splitlines(keepends=True)}])
    # Mechanical Notebook append; old cell content and metadata remain exact.
    NOTEBOOK.write_text(json.dumps(original, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    actual = json.loads(NOTEBOOK.read_text(encoding='utf-8'))
    assert len(actual['cells']) == len({c['id'] for c in actual['cells']})
    for cell in actual['cells']:
        if cell['cell_type'] == 'code': compile(''.join(cell['source']), cell['id'], 'exec')
    exec(compile(check, 'new-readonly-v7-preflight-check', 'exec'), {'__name__': '__main__'})
    verify_bundle(OUTPUT)
    print(json.dumps({'payloads': len(items), 'tests': count, 'notebook_cells': len(actual['cells']),
        'manual_normal': 'confirmed_by_user', 'production_eligible': False, 'model_requests': 0}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--prepare', action='store_true')
    if not parser.parse_args().prepare: parser.error('Use --prepare for this explicitly authorized preflight')
    prepare()
