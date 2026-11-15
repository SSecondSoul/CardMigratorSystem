"""Prepare and freeze the final-rule full-30 development regression; no model calls."""
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

from migration_pipeline.analyze_formal_30_v4_full_regression import digest, verify_snapshot
from migration_pipeline.run_batch_pipeline import config_fingerprint, default_paths, validate_batch_config
from migration_pipeline.run_formal_30_v4_full_regression_v2 import ROOT, BATCH_ID, CONFIG, PROTOCOL, EXPECTED_ENV, batch_command
from migration_pipeline.prepare_formal_30_v4_full_regression import build_config as original_plan, BASE_PROTOCOL
from migration_pipeline.replay_formal_30_v4_watch_persistence_closure import OUTPUT as OFFLINE, SOURCE as LAST_RAW

BASE_V3 = ROOT / 'data/experiments/snapshots/formal_30_v3_results_20261022_200548'
BASE_V4 = ROOT / 'data/experiments/snapshots/formal_30_v4_full_regression_results_20261030_215511'
TASK_PACKAGE = ROOT / 'data/experiments/manual_followups/formal_30_v4_semantic_closure_v2_TaskManager_textarea_v1_20261103'
ACCEPTANCES = (
    ('TaskManager', ROOT / 'data/experiments/analysis/formal_30_v4_semantic_closure_v2_20261103_160541/TaskManager_manual_acceptance_20261103.json',
     '2431dad82beb05b9c1211adddcd83b2a395d51bb1a27c4e7e8e99cf1587335dd'),
    ('MonitoringDashboard', ROOT / 'data/experiments/analysis/formal_30_v4_semantic_closure_v5_20261104_150846/MonitoringDashboard_manual_acceptance_20261104.json',
     '37446d0e6196a5afc27625a9d532c03b5c5a816bf8c8d69d1bbe5f96b0d6ed69'),
)
ADDED = (
    'migration_pipeline/run_formal_30_v4_full_regression_v2.py',
    'migration_pipeline/prepare_formal_30_v4_full_regression_v2.py',
    'migration_pipeline/freeze_formal_30_v4_full_regression_v2_results.py',
    'tests/test_full_regression_v2_protocol_launch.py',
    f'migration_pipeline/batch_configs/{BATCH_ID}.json',
)


def check(command):
    proc = subprocess.run(command, cwd=ROOT, env={**os.environ, **EXPECTED_ENV, 'PYTHONIOENCODING': 'utf-8'},
        capture_output=True, text=True, encoding='utf-8')
    output = proc.stdout + proc.stderr
    if proc.returncode:
        raise RuntimeError(f'Check failed: {command}\n{output}')
    return output


def validate_config(config):
    validate_batch_config(config)
    baseline = original_plan()
    if (config['batch_id'] != BATCH_ID or config['samples'] != baseline['samples']
            or len(config['samples']) != 30
            or Counter(s['complexity'] for s in config['samples']) != Counter(simple=10, medium=10, complex=10)
            or config['expected_counts'] != {'simple': 10, 'medium': 10, 'complex': 10}
            or config['classification'] != 'reused_development_full_regression_after_semantic_closure'
            or config['independent_holdout'] or not config['source_split_name_is_historical_not_holdout_claim']
            or config['max_repair_rounds'] != 3 or config['repair_policy'] != 'bounded_prepass_v1'
            or config['semantic_rule_set'] != 'residual_v2' or config['repair_budget_unit'] != 'llm_calls'
            or config['max_normalization_steps_per_llm_call'] != 4
            or config['required_launch_environment'] != EXPECTED_ENV
            or config['generation_input_policy'] != 'fresh_from_vue_not_prior_san'
            or config['accepted_candidate_policy'] != 'manual_candidates_retained_separately_not_model_inputs_or_checkpoint'
            or config['sample_selection_policy'] != 'all_original_30_in_original_order_including_TaskManager_and_MonitoringDashboard'
            or config['previous_full_regression_snapshot'] != BASE_V4.name):
        raise RuntimeError('Unexpected full-30 sample/order, budget, exposure, environment or fresh-input policy')
    for name in ('baseline_batch_id', 'baseline_config', 'baseline_config_sha256',
                 'baseline_summary', 'baseline_summary_sha256', 'source_split', 'source_split_sha256'):
        if config[name] != baseline[name]:
            raise RuntimeError(f'Original baseline metadata changed: {name}')


def preflight():
    for path in (PROTOCOL, *default_paths(BATCH_ID)):
        if path.exists():
            raise FileExistsError(f'Unused protocol and output paths required: {path}')
    counts = tuple(verify_snapshot(p) for p in (BASE_V3, BASE_V4, LAST_RAW, OFFLINE, TASK_PACKAGE))
    if counts != (234, 359, 364, 16, 13):
        raise RuntimeError(f'Immutable evidence inventory differs: {counts}')
    config = json.loads(CONFIG.read_text(encoding='utf-8'))
    validate_config(config)
    evidence = json.loads((OFFLINE / 'replay.json').read_text(encoding='utf-8'))
    if (evidence['model_requests'] != 0 or not evidence['after']['validation_passed']
            or not evidence['after']['visual_eval_passed'] or not evidence['fixed_point']
            or evidence['gate']['should_stop'] or not evidence['reverse_gate']['should_stop']
            or evidence['original_automatic_score_modified']):
        raise RuntimeError('Offline closure proof invalid')
    for name, path, expected in ACCEPTANCES:
        accepted = json.loads(path.read_text(encoding='utf-8'))
        if (digest(path) != expected or accepted['sample'] != name
                or accepted['candidate_manual_status'] != 'passed_by_user'
                or digest(ROOT / accepted['candidate']) != accepted['candidate_sha256']
                or digest(ROOT / accepted['source_vue']) != accepted['source_vue_sha256']):
            raise RuntimeError(f'Accepted candidate identity changed: {name}')
    live = json.loads((OFFLINE / 'live_inventory.json').read_text(encoding='utf-8'))
    if len(live) != 317 or any(digest(ROOT / name) != h for name, h in live.items()):
        raise RuntimeError('Current runtime differs from verified offline closure')
    for sample in config['samples']:
        path = sample['vue_file']
        if path not in live or digest(ROOT / path) != digest(BASE_PROTOCOL / 'frozen' / path):
            raise RuntimeError(f'Original Vue bytes changed or omitted: {sample["id"]}')
    paths = {ROOT / name for name in set(live) | set(ADDED)}
    if any(not p.is_file() or not p.resolve().is_relative_to(ROOT) for p in paths):
        raise RuntimeError('Missing or outside-workspace payload')
    return config, paths, counts


PROTOCOL_TEXT = '''# formal v4：最终规则完整 30 样本开发回归（第二批）

冻结日期：2026-11-04（Asia/Shanghai）。批次 formal_30_v4_full_regression_v2。
v2 是本次完整回归的第二批，不是旧 formal_30_v2，也不是独立测试集。

## 范围、输入与停止规则

沿用原 v3／首次 v4 完整回归的同一份 30 项、原顺序和逐字节一致的 Vue；简单／中等／复杂各 10 项。
TaskManager、MonitoringDashboard 与其余 28 项全部重新提取 SSM、生成一次并在本轮候选上修复。
已人工通过的派生 San 仅作独立历史证据，不作为模型参考答案、输入、分数或跳过依据。
source_split 文件名中的 untouched_holdout 只是历史名称；这 30 项已经用于开发，明确为重复开发回归，不是独立未见测试。

使用全新默认 pipeline、repair reports、summary checkpoint。不加 --force，不传 --sample-id 或旧输出路径。
同一代码版本下中断可用原命令恢复待处理项；不能挑选重跑来替换已记录失败或异常。
发现问题先冻结已观察结果，再在后续版本修复；运行期间不修改冻结代码或覆盖旧 SHA 清单。
代码变化需另建协议，不混用本批后续样本的运行版本。

## 固定预算与环境

每样本最多 3 次 LLM repair，repair_policy=bounded_prepass_v1、semantic_rule_set=residual_v2。
每次模型调用前最多 4 步确定性处理，每样本累计最多 12 步；按 LLM calls 计费轮数，不等同旧版本 3 次混合尝试。
qwen/qwen-plus，客户端 temperature=0.2，LLM_TIMEOUT=600，生成／修复客户端各 660 秒。
通过专用 launcher 在新进程导入设置前固定 API URL、端口、关闭 debug 和上述超时。
没有固定模型或渲染随机种子，服务商实际版本与旧进程是否停止不能由文件哈希独立证明。
不在协议或仓库保存 API key。

## 系统与证据

本步骤不改生产规则，只冻结当前有效实现、配置和运行工具。
冻结前校验原 v3 原始结果 234 文件、首次 v4 完整结果 359、最新单样本原始结果 364、持久化闭环包 16、TaskManager 候选包 13。
当前 317 项代码／输入 inventory 与最后通过的离线闭环一致，30 份 Vue 逐项匹配最初冻结输入。
两份用户验收记录和精确候选另行复制为历史证据；不把人工修复计作原自动端到端成功。
重新执行完整本地测试、无模型持久化回放和 30 项 dry-run；随后校验本协议 frozen/live 哈希。
生成、修复、验证器、门禁、规则、预算和超时均与早期版本存在变化，不作 Prompt 单因素因果结论。

## 结果报告口径

保留旧 v3：18/30 自动通过、9 评估失败、3 执行异常；首次 v4：25/30、3 评估失败、2 执行异常。
本批必须报告 30 项总分母、完成项通过率、每层 10 项分母、首次通过、确定性处理次数／接受拒绝、LLM 次数、token、耗时、异常。
逐样本配对区分保持通过、回归失败、改善通过、仍未通过，执行异常另列，不继承旧结论。
保留所有初始候选、模型和确定性候选、拒绝与回退。不要挑较高 DOM 分数替换最终结果。
自动通过、人工通过和独立测试分列；本批自动通过不等于所有交互已验证。
未披露早期接触的候选池不得改称独立测试；后续探索性评估继续等待本批结果。

## 操作者执行

项目根目录，cardmig 环境。先在旧服务器窗口 Ctrl+C 停止旧服务。

窗口 A：

```powershell
$env:LLM_API_KEY = "你的密钥"
python -m migration_pipeline.run_formal_30_v4_full_regression_v2 --server
```

保持 A 运行，在窗口 B 启动全部 30 项：

```powershell
python -m migration_pipeline.run_formal_30_v4_full_regression_v2 --execute
```

两个入口先做新协议 live 校验；失败停止，不能修改校验清单绕过。
仅看计划可使用 --dry-run。运行完成后先反馈结果，不马上 force 或修改规则。
本批原始结果封存入口（由后续检查调用）：

```powershell
python -m migration_pipeline.freeze_formal_30_v4_full_regression_v2_results
```

当前两个测试页继续保留已验收 MonitoringDashboard 候选；不会因本批计划而切换。
准备／冻结不调用模型、不启动服务器，不意味着新生成已通过。原单样本与全批历史均不改写。
'''


def main():
    config, paths, counts = preflight()
    hashes = {p: digest(p) for p in paths}
    print('Running complete tests; no model requests.', flush=True)
    tests = check([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py'])
    match = re.search(r'Ran (\d+) tests in ([\d.]+)s', tests)
    if not match or '\nOK' not in tests:
        raise RuntimeError('Missing test success/count marker')
    print(f'Tests passed ({match[1]}); replaying frozen persistence candidate without models.', flush=True)
    replay_log = check([sys.executable, '-m', 'migration_pipeline.replay_formal_30_v4_watch_persistence_closure'])
    replay = json.loads(replay_log.strip().splitlines()[-1])
    if replay['model_requests'] or replay['evidence_written'] or not replay['validation_passed'] or not replay['visual_eval_passed']:
        raise RuntimeError('Offline closure replay failed')
    dry_log = check(batch_command(dry_run=True))
    dry = json.loads(dry_log)
    if (dry['batch_id'] != BATCH_ID or dry['max_repair_rounds'] != 3
            or [s['id'] for s in dry['samples']] != [s['id'] for s in config['samples']]
            or dry['summary_file'] != f'data/experiments/batch_reports/{BATCH_ID}_summary.json'):
        raise RuntimeError('Dry-run plan differs from full-30 protocol')
    if any(digest(p) != h for p, h in hashes.items()):
        raise RuntimeError('Runtime changed during checks')
    preflight()
    PROTOCOL.mkdir(parents=True)
    for source in sorted(paths):
        dest = PROTOCOL / 'frozen' / source.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        if digest(source) != hashes[source] or digest(dest) != hashes[source]:
            raise RuntimeError(f'Copy hash mismatch: {source}')
    shutil.copy2(BASE_PROTOCOL / 'verify_protocol.py', PROTOCOL / 'verify_protocol.py')
    shutil.copy2(BASE_V3 / 'formal_30_v3_summary.json', PROTOCOL / 'baseline_v3_summary.json')
    shutil.copy2(BASE_V4 / 'formal_30_v4_full_regression_summary.json', PROTOCOL / 'baseline_v4_summary.json')
    shutil.copytree(OFFLINE, PROTOCOL / 'offline_evidence')
    for name, path, _ in ACCEPTANCES:
        accepted = json.loads(path.read_text(encoding='utf-8'))
        folder = PROTOCOL / 'manual_acceptance_evidence' / name
        folder.mkdir(parents=True)
        shutil.copy2(path, folder / 'acceptance.json')
        shutil.copy2(ROOT / accepted['candidate'], folder / 'accepted_candidate.san')
    for name, text in (('PROTOCOL.md', PROTOCOL_TEXT), ('unit_tests.txt', tests),
                       ('offline_replay_log.txt', replay_log), ('dry_run.json', dry_log)):
        (PROTOCOL / name).write_text(text, encoding='utf-8')
    manifest = {'protocol_id': PROTOCOL.name, 'batch_id': BATCH_ID,
        'created_at': datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'classification': config['classification'], 'independent_holdout': False,
        'sample_count': 30, 'sample_order': [s['id'] for s in config['samples']],
        'expected_counts': config['expected_counts'], 'all_30_live_vue_match_original_frozen_inputs': True,
        'sample_source_sha256': {s['id']: digest(ROOT / s['vue_file']) for s in config['samples']},
        'generation_input_policy': config['generation_input_policy'],
        'max_llm_repair_calls_per_sample': 3, 'max_normalization_steps_per_call': 4,
        'max_normalization_steps_per_sample': 12,
        'repair_policy': config['repair_policy'], 'semantic_rule_set': config['semantic_rule_set'],
        'baseline_v3_verified_files': counts[0], 'baseline_v4_verified_files': counts[1],
        'last_raw_verified_files': counts[2], 'offline_evidence_verified_files': counts[3],
        'task_manager_package_verified_files': counts[4],
        'accepted_candidates_are_model_inputs': False,
        'acceptance_sha256': {name: digest(path) for name, path, _ in ACCEPTANCES},
        'baseline_v3_summary_sha256': digest(PROTOCOL / 'baseline_v3_summary.json'),
        'baseline_v4_summary_sha256': digest(PROTOCOL / 'baseline_v4_summary.json'),
        'config_sha256': digest(CONFIG), 'config_fingerprint': config_fingerprint(config),
        'runtime_env': EXPECTED_ENV, 'temperature': 0.2, 'python_version': sys.version.split()[0],
        'prior_live_inventory_files': 317, 'added_protocol_payload_files': list(ADDED),
        'frozen_payload_files': len(paths),
        'unit_tests': {'passed': int(match[1]), 'failed': 0, 'elapsed_seconds': float(match[2])},
        'offline_model_requests': 0, 'model_request_performed': False,
        'server_runtime_independently_verified': False, 'output_paths_absent_at_freeze': True}
    (PROTOCOL / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    files = sorted(p for p in PROTOCOL.rglob('*') if p.is_file())
    (PROTOCOL / 'SHA256SUMS.txt').write_text('\n'.join(
        f'{digest(p)}  {p.relative_to(PROTOCOL).as_posix()}' for p in files) + '\n', encoding='utf-8')
    print(check([sys.executable, str(PROTOCOL / 'verify_protocol.py'), '--live']), end='')
    print(f'protocol: {PROTOCOL.relative_to(ROOT)}')
    print(f'frozen_payload_files: {len(paths)}; tests_passed: {match[1]}; model_requests: 0')


if __name__ == '__main__':
    main()
