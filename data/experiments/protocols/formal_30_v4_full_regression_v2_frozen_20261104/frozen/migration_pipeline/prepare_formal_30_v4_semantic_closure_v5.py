"""Freeze startup/API-preservation fresh-generation regression; never call a model."""

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone

from migration_pipeline.analyze_formal_30_v4_full_regression import digest, verify_snapshot
from migration_pipeline.run_batch_pipeline import config_fingerprint, default_paths, validate_batch_config
from migration_pipeline.run_formal_30_v4_semantic_closure_v5 import (
    ROOT, BATCH_ID, CONFIG, PROTOCOL, EXPECTED_ENV, batch_command,
)
from migration_pipeline.replay_formal_30_v4_method_interface_closure import SOURCE, PRIOR, OUTPUT


TASK_PACKAGE = ROOT / 'data/experiments/manual_followups/formal_30_v4_semantic_closure_v2_TaskManager_textarea_v1_20261103'
ACCEPTANCE = ROOT / 'data/experiments/analysis/formal_30_v4_semantic_closure_v2_20261103_160541/TaskManager_manual_acceptance_20261103.json'
ACCEPTANCE_SHA256 = '2431dad82beb05b9c1211adddcd83b2a395d51bb1a27c4e7e8e99cf1587335dd'
CHANGED_ALLOWED = {
    'migration_pipeline/stages/repair.py', 'migration_pipeline/stages/validate.py',
    'migration_pipeline/utils/bounded_semantics.cjs', 'migration_pipeline/utils/repair_prompt.py',
    'migration_pipeline/utils/repair_scheduler.py', 'migration_pipeline/utils/semantic_coverage.py',
    'migration_pipeline/utils/source_phase_semantics.cjs', 'tests/test_repair_regression_guard.py',
}
ADDED = (
    'migration_pipeline/prepare_formal_30_v4_semantic_closure_v5.py',
    'migration_pipeline/run_formal_30_v4_semantic_closure_v5.py',
    'migration_pipeline/freeze_formal_30_v4_semantic_closure_v5_results.py',
    'tests/test_method_interface_protocol_launch.py',
    f'migration_pipeline/batch_configs/{BATCH_ID}.json',
)
CASES = ['first_repair', 'final_raw', 'startup_fixed_final']


def check(command):
    result = subprocess.run(command, cwd=ROOT,
        env={**os.environ, **EXPECTED_ENV, 'PYTHONIOENCODING': 'utf-8'},
        capture_output=True, text=True, encoding='utf-8')
    output = result.stdout + result.stderr
    if result.returncode:
        raise RuntimeError(f'Local check failed: {command}\n{output}')
    return output


def validate_offline(evidence):
    if (evidence['model_requests'] != 0 or evidence['source_snapshot'] != SOURCE.name
            or evidence['original_summary_modified'] or evidence['browser_interaction_test_performed']
            or evidence['browser_permission_request_performed']
            or [r['case'] for r in evidence['cases']] != CASES):
        raise RuntimeError('Offline evidence identity or no-model boundary failed')
    for row in evidence['cases']:
        method, startup = row['method_contract'], row['startup_contract']
        if (not row['after']['validation_passed'] or row['after']['validation_errors']
                or not row['after']['visual_eval_passed'] or row['gate']['should_stop']
                or not row['reverse_gate']['should_stop']
                or method['name'] != 'requestNotificationPermission'
                or method['status'] != 'callable_present'
                or any(method[f'{kind}_references']['count'] != 0
                       or method[f'{kind}_references']['uncertain'] for kind in ('source', 'target'))
                or startup['inited_direct_calls'] != 0 or startup['attached_direct_calls'] != 1
                or digest(OUTPUT / f"{row['case']}_offline.san") != row['output_sha256']):
            raise RuntimeError('Offline closure or no-new-trigger contract failed')
    if (digest(SOURCE / 'formal_30_v4_semantic_closure_v4_summary.json') != evidence['source_summary_sha256']
            or digest(SOURCE / 'repair_reports/complex/MonitoringDashboard_repair_history.json')
               != evidence['source_history_sha256']):
        raise RuntimeError('Offline evidence refers to a different raw result')


def preflight():
    for path in (PROTOCOL, *default_paths(BATCH_ID)):
        if path.exists():
            raise FileExistsError(f'New unused protocol and output paths required: {path}')
    counts = tuple(verify_snapshot(p) for p in (SOURCE, OUTPUT, PRIOR, TASK_PACKAGE))
    if counts != (342, 31, 24, 13):
        raise RuntimeError(f'Unexpected immutable evidence inventory: {counts}')
    config = json.loads(CONFIG.read_text(encoding='utf-8'))
    validate_batch_config(config)
    prior = json.loads((SOURCE / 'formal_30_v4_semantic_closure_v4.json').read_text(encoding='utf-8'))
    if (config['batch_id'] != BATCH_ID or config['samples'] != prior['samples']
            or [s['id'] for s in config['samples']] != ['MonitoringDashboard']
            or config['prior_result_snapshot'] != SOURCE.name
            or config['classification'] != 'startup_method_interface_closure_single_sample_development_regression'
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
    validate_offline(json.loads((OUTPUT / 'replay.json').read_text(encoding='utf-8')))
    rows = [line.split('  ', 1) for line in (SOURCE / 'protocol/SHA256SUMS.txt').read_text(encoding='utf-8').splitlines()]
    old = {name.removeprefix('frozen/'): h for h, name in rows if name.startswith('frozen/')}
    if any(not (ROOT / name).is_file() for name in old):
        raise RuntimeError('Prior live payload file missing')
    changed = {name for name, h in old.items() if digest(ROOT / name) != h}
    if changed != CHANGED_ALLOWED:
        raise RuntimeError(f'Unexpected change from raw v4 protocol: {sorted(changed)}')
    live = json.loads((OUTPUT / 'live_inventory.json').read_text(encoding='utf-8'))
    if (len(live) != 307 or not set(old).issubset(live)
            or any(digest(ROOT / name) != h for name, h in live.items())):
        raise RuntimeError('Current runtime differs from verified interface closure evidence')
    code = OUTPUT / 'code'
    for path in code.rglob('*'):
        if path.is_file():
            name = path.relative_to(code).as_posix()
            if name not in live or digest(path) != live[name]:
                raise RuntimeError(f'Offline code differs from included runtime: {name}')
    paths = {ROOT / name for name in set(live) | set(ADDED)}
    if any(not p.is_file() or not p.resolve().is_relative_to(ROOT) for p in paths):
        raise RuntimeError('Missing or outside-workspace protocol payload')
    return config, paths, changed, counts


PROTOCOL_TEXT = '''# formal v4：semantic closure v5 单样本开发回归

冻结日期：2026-11-04（Asia/Shanghai）。仅 MonitoringDashboard。
名称中的 v5 是 formal v4 内部语义闭环的第五轮，不是新的独立正式测试版本。
这是重复开发回归，不是独立未见测试；完整 30 样本最终规则回归仍未完成。

## 输入、预算与计分

从与原 v4 协议逐字节相同的 Vue 重新提取 SSM、生成代码，然后在本轮候选上迭代修复。
不继承上一轮 San，不把离线修复产物作为输入或参考答案。
使用全新批次 formal_30_v4_semantic_closure_v5 的默认 pipeline、repair reports 和 summary checkpoint。
不加 --force，不覆盖旧结果；同代码中断恢复可使用同一命令，主动重新生成必须先封存并另建批次。

预算：最多 3 次 LLM repair；bounded_prepass_v1、residual_v2；每次调用前最多 4 个确定性步骤、共最多 12 步。
qwen/qwen-plus，客户端 temperature=0.2，LLM_TIMEOUT=600，生成/修复客户端各 660 秒。
launcher 在新子进程导入配置前固定环境；没有固定模型或渲染随机种子。
服务商实际模型版本及旧服务进程是否停止不能仅凭代码哈希独立证明。

保留原始 v4 自动 1/1 通过、272803 tokens 记录，不把新检查结果追溯写入旧计分。
TaskManager 不纳入本轮，保留已有用户验收候选；人工页面不切换、不据此声明 MonitoringDashboard 人工通过。
所有初始、确定性和模型候选、拒绝及回退均保留，运行完成先封存全部原始结果，再诊断/安排人工检查。
不选择较高 DOM 分数覆盖最后候选。

## 系统变更和证据边界

本次准备不改生产规则；冻结前已实现的通用启动阶段与源父组件方法接口保留闭环。
原始结果 342 文件、启动闭环 24 文件、方法接口闭环 31 文件、TaskManager 验收候选包 13 文件逐一校验。
307 项已验证代码清单与当前运行时一致；新增本轮配置、launcher、preparer、结果封存器和启动边界测试。
相对旧 v4 运行协议的 8 个已有文件变更逐项记录于 manifest；新增运行时文件也纳入 frozen。
不修改生成阶段或服务器 Prompt；这是验证器、候选门、确定性恢复及 repair Prompt 的联合变更，不是单因素实验。

启动规则仅处理源代码可证明的 mounted 初始化包装器，确保对应 attached 中恰好一次；不猜测未知副作用。
方法接口检查针对可解析的 Options API 导出父组件可调用接口，不证明所有已有方法体或子组件完整等价。
自动恢复仅覆盖内部未引用、无动态/别名逃逸不确定性、同步且参数/表达式受支持的缺失方法。
保留原方法条件与顺序，状态读取转为 San data.get；未知闭包/依赖、写入、复杂签名、保留名或已有不透明项不猜测覆盖。
恢复 requestNotificationPermission 的原接口，不增加保存设置、挂载、勾选时调用权限请求的触发点。
新接口丢失或新触发点由候选门拒绝；仅源码/解析恢复证据严格成立的“新近可见旧缺陷”不算新增，但仍保留验证错误。

离线三产物静态零错误、DOM 通过、固定点和逆向拒绝均已验证；这不等于新生成成功或浏览器交互验收。
同一离线代码哈希曾有不同 DOM 分数，保留观测、不挑选分数，也不单凭分数推断差异原因。
受控 Node Notification stub 测试不是真实浏览器权限请求。
冻结前重新跑完整本地测试、三产物无模型回放、批处理 dry-run，再验证 frozen 和 live 哈希。
冻结后不得改列入清单的文件；若需改动，停止本轮并另建协议，不改旧 SHA 清单。

## 操作者命令

项目根目录、cardmig 环境。先在旧服务器窗口 Ctrl+C 停止旧服务。

窗口 A（本地填密钥，不写入仓库）：

```powershell
$env:LLM_API_KEY = "你的密钥"
python -m migration_pipeline.run_formal_30_v4_semantic_closure_v5 --server
```

保持 A 运行，在窗口 B 执行：

```powershell
python -m migration_pipeline.run_formal_30_v4_semantic_closure_v5 --execute
```

两个入口均先校验本协议 live 哈希。不加 --force 或旧输出路径；校验失败停止，不改校验清单。
仅查看计划可 --dry-run。模型结束后先反馈“运行完成”，不马上复跑或改代码。
随后使用封存入口保存原始结果：

```powershell
python -m migration_pipeline.freeze_formal_30_v4_semantic_closure_v5_results
```

协议准备不启动服务器、不调用模型、不存储密钥。
'''


def main():
    config, paths, changed, counts = preflight()
    hashes = {p: digest(p) for p in paths}
    print('Running complete unit tests; no model requests.', flush=True)
    tests = check([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py'])
    match = re.search(r'Ran (\d+) tests in ([\d.]+)s', tests)
    if not match or '\nOK' not in tests:
        raise RuntimeError('Unit test count or success marker unavailable')
    print(f'Tests passed ({match[1]}); replaying three frozen candidates without model calls.', flush=True)
    replay_log = check([sys.executable, '-m', 'migration_pipeline.replay_formal_30_v4_method_interface_closure'])
    replay = json.loads(replay_log.strip().splitlines()[-1])
    if (replay['model_requests'] != 0 or replay['evidence_written']
            or [r['case'] for r in replay['cases']] != CASES
            or any(not r['validation_passed'] or not r['visual_eval_passed'] for r in replay['cases'])):
        raise RuntimeError('Unexpected fresh offline replay')
    dry_log = check(batch_command(dry_run=True))
    dry = json.loads(dry_log)
    if (dry['batch_id'] != BATCH_ID or dry['max_repair_rounds'] != 3
            or [s['id'] for s in dry['samples']] != ['MonitoringDashboard']
            or dry['summary_file'] != f'data/experiments/batch_reports/{BATCH_ID}_summary.json'):
        raise RuntimeError('Unexpected dry-run plan')
    if any(digest(p) != h for p, h in hashes.items()):
        raise RuntimeError('Payload changed during local checks')
    preflight()
    PROTOCOL.mkdir(parents=True)
    for source in sorted(paths):
        destination = PROTOCOL / 'frozen' / source.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        if digest(source) != hashes[source] or digest(destination) != hashes[source]:
            raise RuntimeError(f'Copy hash mismatch: {source}')
    shutil.copy2(SOURCE / 'protocol/verify_protocol.py', PROTOCOL / 'verify_protocol.py')
    shutil.copy2(SOURCE / 'formal_30_v4_semantic_closure_v4_summary.json', PROTOCOL / 'prior_summary.json')
    shutil.copy2(ACCEPTANCE, PROTOCOL / 'TaskManager_manual_acceptance.json')
    shutil.copytree(OUTPUT, PROTOCOL / 'offline_evidence')
    for name, content in (('PROTOCOL.md', PROTOCOL_TEXT), ('unit_tests.txt', tests),
                          ('offline_replay_log.txt', replay_log), ('dry_run.json', dry_log)):
        (PROTOCOL / name).write_text(content, encoding='utf-8')
    manifest = {
        'protocol_id': PROTOCOL.name, 'batch_id': BATCH_ID,
        'created_at': datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'classification': config['classification'], 'independent_holdout': False,
        'samples': ['MonitoringDashboard'], 'sample_count': 1,
        'generation_input_policy': config['generation_input_policy'],
        'source_snapshot': SOURCE.name, 'source_verified_files': counts[0],
        'offline_evidence': OUTPUT.name, 'offline_evidence_verified_files': counts[1],
        'startup_evidence': PRIOR.name, 'startup_evidence_verified_files': counts[2],
        'task_manager_package_verified_files': counts[3], 'task_manager_included_in_model_batch': False,
        'task_manager_acceptance_sha256': digest(ACCEPTANCE),
        'source_vue_sha256': digest(ROOT / config['samples'][0]['vue_file']),
        'prior_summary_sha256': digest(PROTOCOL / 'prior_summary.json'),
        'offline_replay_sha256': digest(OUTPUT / 'replay.json'),
        'prior_live_inventory_files': 307,
        'config_sha256': digest(CONFIG), 'config_fingerprint': config_fingerprint(config),
        'max_llm_repair_calls': 3, 'max_normalization_steps_per_call': 4,
        'max_normalization_steps_total': 12,
        'repair_policy': config['repair_policy'], 'semantic_rule_set': config['semantic_rule_set'],
        'runtime_env': EXPECTED_ENV, 'temperature': 0.2,
        'changed_prior_payload_files': sorted(changed), 'added_protocol_payload_files': list(ADDED),
        'frozen_payload_files': len(paths), 'python_version': sys.version.split()[0],
        'unit_tests': {'passed': int(match[1]), 'failed': 0, 'elapsed_seconds': float(match[2])},
        'offline_model_requests': 0, 'browser_interaction_test_performed': False,
        'server_runtime_independently_verified': False, 'model_request_performed': False,
        'output_paths_absent_at_freeze': True,
    }
    (PROTOCOL / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    files = sorted(p for p in PROTOCOL.rglob('*') if p.is_file())
    (PROTOCOL / 'SHA256SUMS.txt').write_text('\n'.join(
        f'{digest(p)}  {p.relative_to(PROTOCOL).as_posix()}' for p in files) + '\n', encoding='utf-8')
    print(check([sys.executable, str(PROTOCOL / 'verify_protocol.py'), '--live']), end='')
    print(f'protocol: {PROTOCOL.relative_to(ROOT)}')
    print(f'frozen_payload_files: {len(paths)}')
    print(f'unit_tests_passed: {match[1]}')
    print('model_request_performed: false')


if __name__ == '__main__':
    main()
