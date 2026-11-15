"""Freeze the single-sample v3 protocol after local tests/replay; no model calls."""

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from migration_pipeline.analyze_formal_30_v4_full_regression import digest, verify_snapshot
from migration_pipeline.run_batch_pipeline import config_fingerprint, validate_batch_config, default_paths
from migration_pipeline.run_formal_30_v4_semantic_closure_v3 import (
    ROOT, BATCH_ID, CONFIG, PROTOCOL, EXPECTED_ENV, batch_command,
)
from migration_pipeline.replay_formal_30_v4_source_phase_closure import SOURCE, OUTPUT, RULES


ACCEPTANCE = ROOT / 'data/experiments/analysis/formal_30_v4_semantic_closure_v2_20261103_160541/TaskManager_manual_acceptance_20261103.json'
TASK_PACKAGE = ROOT / 'data/experiments/manual_followups/formal_30_v4_semantic_closure_v2_TaskManager_textarea_v1_20261103'
CHANGED_ALLOWED = {
    'migration_pipeline/stages/repair.py', 'migration_pipeline/stages/validate.py',
    'migration_pipeline/utils/bounded_semantics.cjs', 'migration_pipeline/utils/repair_prompt.py',
    'migration_pipeline/utils/repair_scheduler.py',
}
ADDED = (
    'migration_pipeline/utils/textarea_binding.py', 'migration_pipeline/utils/textarea_binding.cjs',
    'migration_pipeline/utils/source_phase_semantics.cjs',
    'migration_pipeline/prepare_task_manager_textarea_manual_followup.py',
    'migration_pipeline/replay_formal_30_v4_source_phase_closure.py',
    'migration_pipeline/prepare_formal_30_v4_semantic_closure_v3.py',
    'migration_pipeline/run_formal_30_v4_semantic_closure_v3.py',
    'migration_pipeline/freeze_formal_30_v4_semantic_closure_v3_results.py',
    'tests/test_textarea_binding.py', 'tests/test_source_phase_semantics.py',
    'tests/test_source_phase_protocol_launch.py',
    f'migration_pipeline/batch_configs/{BATCH_ID}.json',
)


def check(command):
    result = subprocess.run(command, cwd=ROOT, env={**os.environ, **EXPECTED_ENV, 'PYTHONIOENCODING': 'utf-8'},
                            capture_output=True, text=True, encoding='utf-8')
    output = result.stdout + result.stderr
    if result.returncode:
        raise RuntimeError(f'Local check failed: {command}\n{output}')
    return output


def preflight():
    for path in (PROTOCOL, *default_paths(BATCH_ID)):
        if path.exists():
            raise FileExistsError(f'New unused protocol and output paths required: {path}')
    raw_count, offline_count, task_count = (verify_snapshot(p) for p in (SOURCE, OUTPUT, TASK_PACKAGE))
    config = json.loads(CONFIG.read_text(encoding='utf-8'))
    validate_batch_config(config)
    prior = json.loads((SOURCE / 'formal_30_v4_semantic_closure_v2.json').read_text(encoding='utf-8'))
    expected_sample = [s for s in prior['samples'] if s['id'] == 'MonitoringDashboard']
    if (config['batch_id'] != BATCH_ID or config['samples'] != expected_sample
            or config['max_repair_rounds'] != 3 or config['independent_holdout']
            or config['expected_counts'] != {'simple': 0, 'medium': 0, 'complex': 1}
            or config['repair_policy'] != 'bounded_prepass_v1' or config['semantic_rule_set'] != 'residual_v2'
            or config['required_launch_environment'] != EXPECTED_ENV
            or config['generation_input_policy'] != 'fresh_from_vue_not_prior_san'):
        raise RuntimeError('Unexpected sample, budget, environment or input policy')
    for sample in expected_sample:
        if digest(ROOT / sample['vue_file']) != digest(SOURCE / 'protocol/frozen' / sample['vue_file']):
            raise RuntimeError('Source Vue changed')
    acceptance = json.loads(ACCEPTANCE.read_text(encoding='utf-8'))
    if (acceptance['candidate_manual_status'] != 'passed_by_user'
            or digest(ROOT / acceptance['candidate']) != acceptance['candidate_sha256']):
        raise RuntimeError('TaskManager accepted artifact changed')
    offline = json.loads((OUTPUT / 'replay.json').read_text(encoding='utf-8'))
    if (offline['applied_rules'] != RULES or offline['llm_requests'] != 0
            or not offline['after']['validation_passed'] or not offline['after']['visual_eval_passed']
            or offline['candidate_gate']['should_stop']):
        raise RuntimeError('Offline evidence does not demonstrate closure')
    rows = [line.split('  ', 1) for line in (SOURCE / 'protocol/SHA256SUMS.txt').read_text(encoding='utf-8').splitlines()]
    old = {name.removeprefix('frozen/'): h for h, name in rows if name.startswith('frozen/')}
    if any(not (ROOT / name).is_file() for name in old):
        raise RuntimeError('Prior payload file missing from live workspace')
    changed = {name for name, h in old.items() if digest(ROOT / name) != h}
    if changed != CHANGED_ALLOWED:
        raise RuntimeError(f'Unexpected changed-file boundary: {sorted(changed)}')
    paths = {ROOT / name for name in old} | {ROOT / name for name in ADDED}
    # The already frozen offline rules/tests must still be the live ones.
    for frozen in (OUTPUT / 'code').rglob('*'):
        if frozen.is_file() and digest(frozen) != digest(ROOT / frozen.relative_to(OUTPUT / 'code')):
            raise RuntimeError(f'Offline proof code differs: {frozen}')
    if any(not p.is_file() or not p.resolve().is_relative_to(ROOT) for p in paths):
        raise RuntimeError('Missing or outside-workspace protocol payload')
    return config, paths, changed, (raw_count, offline_count, task_count)


PROTOCOL_TEXT = '''# v4 semantic closure v3：仅 MonitoringDashboard 的新生成回归

日期：2026-11-03，Asia/Shanghai。重复开发样本，不是独立未见测试。

## 输入、预算与输出口径

仅运行 MonitoringDashboard 一项，源 Vue 必须与 v2 原始结果包逐字节一致。由 Vue 重新提取 SSM、生成一次，再在本次生成候选上迭代修复；不是继续修改上一轮 San，也不把离线修复候选当作本轮初始输出或参考答案。

最多 3 次 LLM repair，bounded_prepass_v1，每次调用前最多 4 个确定性步骤（全样本最多 12 步），semantic_rule_set=residual_v2。qwen/qwen-plus，temperature=0.2（随客户端源码冻结），无固定模型或渲染随机种子。上游 LLM_TIMEOUT=600，generation／repair 客户端各 660 秒；launcher 在新进程导入配置前固定环境。

批次 formal_30_v4_semantic_closure_v3 使用全新的默认输出目录、repair reports 和 summary checkpoint；不用 --force、不覆盖旧结果。首次启动只应有一个未运行样本；中断后保持代码不变，用同一命令依据 checkpoint 恢复。执行异常另列，不能只保留成功尝试。若需要主动重新生成，应先冻结当前尝试，再建立新批次。

TaskManager 排除在本批次外，保留已通过的 textarea 修复候选与独立人工验收；不把人工反馈修复回填为 v2 自动成功。原 v2 批次仍 1/2 自动通过。旧完整 30 项分数不修改，后续仍需完整开发回归，探索性候选集评估继续等待。

## 冻结变更与证据边界

v2 冻结失败产物的源参数链、挂载阶段和 watcher 存储写入闭环已离线验证。通用 repair AST 规则仅在源证据和生成结构满足边界时应用，不按组件名硬编码；不承诺所有新生成结果都能自动修好。新增 source_mounted_order_not_landed、source_watch_persistence_not_landed 检测与语义回退保护，repair 聚焦 Prompt 同步更新；含此前已通过的 textarea 检测／修复。generation 和服务器 Prompt 未在这两步修改。

冻结输入、SSM、generation／repair、验证器、渲染器、候选门、规则／依赖清单和测试；代码在冻结之后不得再改。本次验证器也变化，不能把新结果差异只归因于 Prompt、规则或模型随机性。与旧版本不是同一评估器下的单因素消融。

原始失败快照 297 文件、离线闭环包 12 文件及 TaskManager 人工通过候选包 13 文件各自校验；新包保留旧分数、人工验收和离线证据。旧冻结包不改。离线 DOM 相似度存在变化，不挑选较高值替换记录。离线修复通过不是新鲜模型回归通过，初始 DOM／静态通过也不是全部交互通过。

本协议的首次模型调用前验证：完整单元测试、源输入哈希、离线重放、dry-run、新协议自身与 live 哈希。服务器是否确已重启、运行时环境与实际模型版本不能由文件哈希独立证明，必须由操作者按命令启动，并保留服务与批处理输出。冻结包不含 API 密钥。

## 操作者执行

在项目根目录、cardmig 环境，先于旧服务器窗口按 Ctrl+C 停止旧服务。

窗口 A：

```powershell
$env:LLM_API_KEY = "你的密钥"
python -m migration_pipeline.run_formal_30_v4_semantic_closure_v3 --server
```

保持窗口 A 运行。窗口 B：

```powershell
python -m migration_pipeline.run_formal_30_v4_semantic_closure_v3 --execute
```

两个入口均先检查本包 live 哈希；任何不一致应停止并建立新版本，不修改旧校验清单。运行结束后不要马上修改代码或重跑；先冻结原始产物，再诊断／评估。可使用：

```powershell
python -m migration_pipeline.freeze_formal_30_v4_semantic_closure_v3_results
```

模型调用由用户启动，准备和冻结本协议不调用模型。人工测试页本次不切换，不能把仍指向 TaskManager 的页面通过结论当作新 MonitoringDashboard 的人工通过。待本批原始结果封存后再单独配置页面、进行交互检查。
'''


def main():
    config, paths, changed, counts = preflight()
    initial_hashes = {p: digest(p) for p in paths}
    print('Running complete local tests; no model requests.', flush=True)
    tests = check([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py'])
    print('Tests passed; replaying known failure without model calls.', flush=True)
    replay_log = check([sys.executable, '-m', 'migration_pipeline.replay_formal_30_v4_source_phase_closure'])
    replay = json.loads(replay_log)
    if (replay['llm_requests'] or not replay['validation_passed'] or not replay['visual_eval_passed']
            or replay['rules'] != RULES or replay['evidence_written']):
        raise RuntimeError('Unexpected fresh offline replay')
    dry_log = check(batch_command(dry_run=True))
    dry = json.loads(dry_log)
    if (dry['batch_id'] != BATCH_ID or dry['max_repair_rounds'] != 3
            or [s['id'] for s in dry['samples']] != ['MonitoringDashboard']
            or dry['summary_file'] != f'data/experiments/batch_reports/{BATCH_ID}_summary.json'):
        raise RuntimeError('Unexpected dry-run plan')
    # Avoid freezing a tested old file alongside an untested concurrent edit.
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
    shutil.copy2(SOURCE / 'formal_30_v4_semantic_closure_v2_summary.json', PROTOCOL / 'prior_summary.json')
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
        'frozen_payload_files': len(paths),
        'python_version': sys.version.split()[0],
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
    print('model_request_performed: false')


if __name__ == '__main__':
    main()
