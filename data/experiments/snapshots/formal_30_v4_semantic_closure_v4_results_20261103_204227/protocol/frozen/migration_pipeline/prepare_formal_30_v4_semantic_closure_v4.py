"""Freeze coverage/helper single-sample regression after local checks; no LLM."""

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone

from migration_pipeline.analyze_formal_30_v4_full_regression import digest, verify_snapshot
from migration_pipeline.run_batch_pipeline import config_fingerprint, validate_batch_config, default_paths
from migration_pipeline.run_formal_30_v4_semantic_closure_v4 import (
    ROOT, BATCH_ID, CONFIG, PROTOCOL, EXPECTED_ENV, batch_command,
)
from migration_pipeline.replay_formal_30_v4_coverage_helper_closure import SOURCE, OUTPUT, CODE_PATHS


ACCEPTANCE = ROOT / 'data/experiments/analysis/formal_30_v4_semantic_closure_v2_20261103_160541/TaskManager_manual_acceptance_20261103.json'
TASK_PACKAGE = ROOT / 'data/experiments/manual_followups/formal_30_v4_semantic_closure_v2_TaskManager_textarea_v1_20261103'
ACCEPTANCE_SHA256 = '2431dad82beb05b9c1211adddcd83b2a395d51bb1a27c4e7e8e99cf1587335dd'
CHANGED_ALLOWED = {
    'migration_pipeline/stages/repair.py', 'migration_pipeline/utils/repair_scheduler.py',
    'migration_pipeline/utils/residual_semantics.cjs', 'migration_pipeline/utils/source_phase_semantics.cjs',
}
ADDED = (
    'migration_pipeline/utils/inline_identifier_recovery.py',
    'migration_pipeline/utils/inline_identifier_recovery.cjs',
    'migration_pipeline/utils/semantic_coverage.py', 'migration_pipeline/utils/semantic_coverage.cjs',
    'migration_pipeline/utils/stateful_helper_semantics.py',
    'migration_pipeline/utils/stateful_helper_semantics.cjs',
    'migration_pipeline/replay_formal_30_v4_coverage_helper_closure.py',
    'migration_pipeline/analyze_formal_30_v4_semantic_closure_v3.py',
    'migration_pipeline/prepare_formal_30_v4_semantic_closure_v4.py',
    'migration_pipeline/run_formal_30_v4_semantic_closure_v4.py',
    'migration_pipeline/freeze_formal_30_v4_semantic_closure_v4_results.py',
    'tests/test_coverage_and_helper_closure.py', 'tests/test_source_phase_v3_analysis.py',
    'tests/test_coverage_helper_protocol_launch.py',
    f'migration_pipeline/batch_configs/{BATCH_ID}.json',
)


def check(command):
    result = subprocess.run(command, cwd=ROOT,
        env={**os.environ, **EXPECTED_ENV, 'PYTHONIOENCODING': 'utf-8'},
        capture_output=True, text=True, encoding='utf-8')
    output = result.stdout + result.stderr
    if result.returncode:
        raise RuntimeError(f'Local check failed: {command}\n{output}')
    return output


def validate_offline(evidence):
    cases = evidence['cases']
    if (evidence['model_requests'] != 0 or evidence['source_snapshot'] != SOURCE.name
            or evidence['original_summary_modified'] or evidence['browser_interaction_test_performed']
            or evidence['known_transition_gate']['should_stop']
            or not evidence['changed_calculation_counterexample_gate']['should_stop']
            or [row['case'] for row in cases] != ['retained_failure', 'rejected_candidate']
            or cases[0]['passed_offline'] or not cases[1]['passed_offline']
            or not cases[1]['after']['validation_passed']
            or not cases[1]['after']['visual_eval_passed']):
        raise RuntimeError('Offline proof must preserve original failure and close only captured candidate')
    if digest(SOURCE / 'formal_30_v4_semantic_closure_v3_summary.json') != evidence['source_summary_sha256']:
        raise RuntimeError('Offline proof refers to a different raw result')


def preflight():
    for path in (PROTOCOL, *default_paths(BATCH_ID)):
        if path.exists():
            raise FileExistsError(f'New unused protocol and output paths required: {path}')
    counts = tuple(verify_snapshot(p) for p in (SOURCE, OUTPUT, TASK_PACKAGE))
    if counts != (315, 22, 13):
        raise RuntimeError(f'Unexpected evidence inventory: {counts}')
    config = json.loads(CONFIG.read_text(encoding='utf-8'))
    validate_batch_config(config)
    prior = json.loads((SOURCE / 'formal_30_v4_semantic_closure_v3.json').read_text(encoding='utf-8'))
    if (config['batch_id'] != BATCH_ID or config['samples'] != prior['samples']
            or [s['id'] for s in config['samples']] != ['MonitoringDashboard']
            or config['prior_result_snapshot'] != SOURCE.name
            or config['classification'] != 'coverage_helper_closure_single_sample_development_regression'
            or config['max_repair_rounds'] != 3 or config['independent_holdout']
            or config['expected_counts'] != {'simple': 0, 'medium': 0, 'complex': 1}
            or config['repair_policy'] != 'bounded_prepass_v1'
            or config['semantic_rule_set'] != 'residual_v2'
            or config['max_normalization_steps_per_llm_call'] != 4
            or config['repair_budget_unit'] != 'llm_calls'
            or config['required_launch_environment'] != EXPECTED_ENV
            or config['generation_input_policy'] != 'fresh_from_vue_not_prior_san'
            or config['task_manager_policy'] != 'excluded_keep_current_manual_pass_candidate'):
        raise RuntimeError('Unexpected sample, budget, environment or input policy')
    for sample in config['samples']:
        if digest(ROOT / sample['vue_file']) != digest(SOURCE / 'protocol/frozen' / sample['vue_file']):
            raise RuntimeError('Source Vue changed')
    acceptance = json.loads(ACCEPTANCE.read_text(encoding='utf-8'))
    if (digest(ACCEPTANCE) != ACCEPTANCE_SHA256
            or acceptance['candidate_manual_status'] != 'passed_by_user'
            or digest(ROOT / acceptance['candidate']) != acceptance['candidate_sha256']):
        raise RuntimeError('TaskManager acceptance or accepted artifact changed')
    offline = json.loads((OUTPUT / 'replay.json').read_text(encoding='utf-8'))
    validate_offline(offline)
    rows = [line.split('  ', 1) for line in (SOURCE / 'protocol/SHA256SUMS.txt').read_text(encoding='utf-8').splitlines()]
    old = {name.removeprefix('frozen/'): h for h, name in rows if name.startswith('frozen/')}
    if any(not (ROOT / name).is_file() for name in old):
        raise RuntimeError('Prior payload file missing from live workspace')
    changed = {name for name, h in old.items() if digest(ROOT / name) != h}
    if changed != CHANGED_ALLOWED:
        raise RuntimeError(f'Unexpected changed-file boundary: {sorted(changed)}')
    paths = {ROOT / name for name in old} | {ROOT / name for name in ADDED}
    for name in CODE_PATHS:
        if (digest(OUTPUT / 'code' / name) != digest(ROOT / name)
                or ROOT / name not in paths):
            raise RuntimeError(f'Offline proof code differs or is not included: {name}')
    if any(not p.is_file() or not p.resolve().is_relative_to(ROOT) for p in paths):
        raise RuntimeError('Missing or outside-workspace protocol payload')
    return config, paths, changed, counts


PROTOCOL_TEXT = '''# v4 semantic closure v4：覆盖状态与图表依赖单样本回归

日期：2026-11-03（Asia/Shanghai）。仅 MonitoringDashboard；重复开发回归，不是独立未见测试。

## 输入、预算与计分

从与 v3 冻结输入逐字节相同的 Vue 重新提取 SSM、生成一次，再在本轮候选上迭代修复。
不继承上一轮 San，也不把离线修复候选作为生成输入或参考答案。
采用全新批次 formal_30_v4_semantic_closure_v4 的默认输出、repair reports 与 summary checkpoint；
不使用 --force，不覆盖旧结果。中断后代码不变可用同一命令按 checkpoint 恢复；主动重新生成必须先封存并另建批次。

预算沿用最大 3 次 LLM repair，repair_policy=bounded_prepass_v1，semantic_rule_set=residual_v2；
每次调用前最多 4 个确定性步骤，全样本最多 12 步。qwen/qwen-plus，客户端 temperature=0.2；
LLM_TIMEOUT=600，generation/repair 客户端各 660 秒。launcher 在新进程导入设置前固定环境。
没有固定模型/渲染随机种子；实际模型服务版本与旧服务器是否确已停止不能由文件哈希独立证明。

TaskManager 排除在本轮外，保留此前 textarea 候选和独立用户验收，不回填为旧批次自动通过。
旧 v3 原始分数仍为 0/1，240133 tokens；旧完整 30 项分数不修改。
模型与确定性步骤分别记录；异常、拒绝、回退候选都保留，不挑选较高 DOM 分数替换最终结果。

## 本次系统变更与证据边界

冻结失败快照 315 文件、离线闭环包 22 文件和 TaskManager 候选包 13 文件全部校验。
相对 v3 的 4 个修改文件为 repair.py、repair_scheduler.py、residual_semantics.cjs、source_phase_semantics.cjs；
新增注册标识符恢复、语义覆盖证明及只读 helper 显式依赖模块、回放与测试。
生成阶段与服务端 Prompt 未在这一步修改；不是仅改 Prompt 的单因素实验。

候选门只在源注册、方法 AST、作用域和渲染调用等证据严格匹配时，区分“新近可见的旧缺陷”与真实新缺陷。
旧缺陷仍保留为验证错误，不免检、不自动判成功；未知证明和实际计算变化仍拒绝。
图表 helper 规则只转换私有内联组件中可证明只读、自包含且调用覆盖完整的方法，原子更新所有调用及参数。
同时保留源 prop、事件参数、watcher 持久化与布尔事件的有边界修复；不承诺任意新生成代码都能自动修好。

离线包中：原始保留失败产物仍有 19 条静态诊断，DOM 0.9781；捕获的被拒候选经规则处理后静态 0 错误，DOM 0.9825。
这些是冻结产物重放，不是新鲜模型成功，也不是浏览器交互验收。
原先历史记录中的 4 条隐藏依赖拒绝理由不改写；新检测另发现的 watcher 持久化缺陷另行披露。
测试包含真实计算改动必须拒绝的反例，以及 0/1/7/30/90 点和不同画布宽度的坐标一致性验证。

运行前完成：全套本地测试、无模型只读回放、dry-run、新协议 frozen/live 哈希验证。
冻结后不得再改所列代码。模型运行结束先封存全部原始产物，再诊断、配置人工页和交互检查。
当前人工页仍指向已验收 TaskManager，本次不改；不能把它的“通过”当作 MonitoringDashboard 通过。
后续完整 30 样本开发回归仍未完成；候选集探索性评估继续等待。

## 操作者命令

在项目根目录、cardmig 环境中，先在旧服务器窗口按 Ctrl+C 停止旧服务。

窗口 A（本地填写真实密钥，不写入仓库）：

```powershell
$env:LLM_API_KEY = "你的密钥"
python -m migration_pipeline.run_formal_30_v4_semantic_closure_v4 --server
```

保持 A 运行。窗口 B：

```powershell
python -m migration_pipeline.run_formal_30_v4_semantic_closure_v4 --execute
```

两入口先验证本协议 live 哈希；不一致应停止，不修改旧校验清单。
首次运行前可 --dry-run；不要附加 --force 或旧输出路径。运行完成后不要马上重跑或改代码。
原始结果封存入口（由后续检查步骤调用）：

```powershell
python -m migration_pipeline.freeze_formal_30_v4_semantic_closure_v4_results
```

协议准备和冻结不调用模型、不启动服务器、不含密钥。
'''


def main():
    config, paths, changed, counts = preflight()
    initial_hashes = {p: digest(p) for p in paths}
    print('Running complete local tests; no model requests.', flush=True)
    tests = check([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py'])
    match = re.search(r'Ran (\d+) tests in ([\d.]+)s', tests)
    if not match or '\nOK' not in tests:
        raise RuntimeError('Unit test count or success marker unavailable')
    print('Tests passed; replaying both captured artifacts without model calls.', flush=True)
    replay_log = check([sys.executable, '-m', 'migration_pipeline.replay_formal_30_v4_coverage_helper_closure'])
    replay = json.loads(replay_log)
    if (replay['model_requests'] != 0 or replay['evidence_written']
            or [(r['name'], r['passed_offline']) for r in replay['cases']]
            != [('retained_failure', False), ('rejected_candidate', True)]):
        raise RuntimeError('Unexpected fresh offline replay')
    dry_log = check(batch_command(dry_run=True))
    dry = json.loads(dry_log)
    if (dry['batch_id'] != BATCH_ID or dry['max_repair_rounds'] != 3
            or [s['id'] for s in dry['samples']] != ['MonitoringDashboard']
            or dry['summary_file'] != f'data/experiments/batch_reports/{BATCH_ID}_summary.json'):
        raise RuntimeError('Unexpected dry-run plan')
    if any(digest(p) != h for p, h in initial_hashes.items()):
        raise RuntimeError('Payload changed while tests were running')
    preflight()
    PROTOCOL.mkdir(parents=True)
    for source in sorted(paths):
        destination = PROTOCOL / 'frozen' / source.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        if digest(destination) != initial_hashes[source]:
            raise RuntimeError(f'Copy hash mismatch: {source}')
    shutil.copy2(SOURCE / 'protocol/verify_protocol.py', PROTOCOL / 'verify_protocol.py')
    shutil.copy2(SOURCE / 'formal_30_v4_semantic_closure_v3_summary.json', PROTOCOL / 'prior_summary.json')
    shutil.copy2(OUTPUT / 'replay.json', PROTOCOL / 'prior_offline_replay.json')
    shutil.copy2(ACCEPTANCE, PROTOCOL / 'TaskManager_manual_acceptance.json')
    shutil.copytree(OUTPUT, PROTOCOL / 'offline_evidence')
    for name, content in (('PROTOCOL.md', PROTOCOL_TEXT), ('unit_tests.txt', tests),
                          ('offline_replay_log.json', replay_log), ('dry_run.json', dry_log)):
        (PROTOCOL / name).write_text(content, encoding='utf-8')
    manifest = {
        'protocol_id': PROTOCOL.name, 'batch_id': BATCH_ID,
        'created_at': datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'classification': config['classification'], 'independent_holdout': False,
        'samples': ['MonitoringDashboard'], 'sample_count': 1,
        'generation_input_policy': config['generation_input_policy'],
        'source_snapshot': SOURCE.name, 'source_verified_files': counts[0],
        'offline_evidence_verified_files': counts[1], 'task_manager_package_verified_files': counts[2],
        'task_manager_included_in_model_batch': False,
        'task_manager_acceptance_sha256': digest(ACCEPTANCE),
        'prior_summary_sha256': digest(PROTOCOL / 'prior_summary.json'),
        'config_sha256': digest(CONFIG), 'config_fingerprint': config_fingerprint(config),
        'max_llm_repair_calls': 3, 'max_normalization_steps_per_call': 4,
        'repair_policy': config['repair_policy'], 'semantic_rule_set': config['semantic_rule_set'],
        'runtime_env': EXPECTED_ENV, 'temperature': 0.2,
        'changed_prior_payload_files': sorted(changed), 'added_payload_files': list(ADDED),
        'frozen_payload_files': len(paths), 'python_version': sys.version.split()[0],
        'unit_tests': {'passed': int(match[1]), 'failed': 0, 'elapsed_seconds': float(match[2])},
        'offline_model_requests': 0, 'browser_interaction_test_performed': False,
        'server_runtime_independently_verified': False, 'model_request_performed': False,
        'output_paths_absent_at_freeze': True,
    }
    (PROTOCOL / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    payloads = sorted(p for p in PROTOCOL.rglob('*') if p.is_file())
    (PROTOCOL / 'SHA256SUMS.txt').write_text('\n'.join(
        f'{digest(p)}  {p.relative_to(PROTOCOL).as_posix()}' for p in payloads) + '\n', encoding='utf-8')
    print(check([sys.executable, str(PROTOCOL / 'verify_protocol.py'), '--live']), end='')
    print(f'protocol: {PROTOCOL.relative_to(ROOT)}')
    print(f'frozen_payload_files: {len(paths)}')
    print(f'unit_tests_passed: {match[1]}')
    print('model_request_performed: false')


if __name__ == '__main__':
    main()
