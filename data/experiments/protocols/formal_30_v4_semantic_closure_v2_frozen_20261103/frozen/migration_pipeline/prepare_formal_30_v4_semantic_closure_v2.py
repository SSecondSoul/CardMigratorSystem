"""Freeze residual-v2 only after tests and raw-failure replay; no model call."""

import json
import shutil
import sys
from datetime import datetime, timedelta, timezone

from migration_pipeline.analyze_formal_30_v4_full_regression import verify_snapshot
from migration_pipeline.prepare_formal_30_v4_full_regression import checked_command, digest
from migration_pipeline.run_batch_pipeline import config_fingerprint, validate_batch_config
from migration_pipeline.run_formal_30_v4_semantic_closure_v2 import ROOT, BATCH_ID, CONFIG, PROTOCOL, EXPECTED_ENV
from migration_pipeline.replay_formal_30_v4_residual_v2 import SOURCE, OUTPUT


def main():
    for path in (PROTOCOL, ROOT / f'data/experiments/pipeline/batches/{BATCH_ID}',
                 ROOT / f'data/experiments/repair_reports/batches/{BATCH_ID}',
                 ROOT / f'data/experiments/batch_reports/{BATCH_ID}_summary.json'):
        if path.exists():
            raise FileExistsError(path)
    verified = verify_snapshot(SOURCE)
    old = json.loads((SOURCE / 'formal_30_v4_semantic_closure_v1.json').read_text(encoding='utf-8'))
    config = {**old, 'batch_id': BATCH_ID, 'classification': 'semantic_recurrence_and_residual_development_regression',
              'semantic_rule_set': 'residual_v2',
              'description': 'Typed semantic recurrence gate, opt-in self-contained computed helper extraction and real inline source prop contracts; reused development inputs.',
              'prior_result_snapshot': SOURCE.name,
              'prior_result_summary_sha256': digest(SOURCE / 'formal_30_v4_semantic_closure_v1_summary.json')}
    validate_batch_config(config)
    if CONFIG.exists() and json.loads(CONFIG.read_text(encoding='utf-8')) != config:
        raise RuntimeError('New config differs')
    for sample in config['samples']:
        if digest(ROOT / sample['vue_file']) != digest(SOURCE / 'protocol/frozen' / sample['vue_file']):
            raise RuntimeError(f"Input changed: {sample['id']}")
    CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    replay = checked_command([sys.executable, '-m', 'migration_pipeline.replay_formal_30_v4_residual_v2'])
    tests = checked_command([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py'])
    dry = checked_command([sys.executable, '-m', 'migration_pipeline.run_formal_30_v4_semantic_closure_v2', '--dry-run'])
    entries = [line.split('  ', 1) for line in (SOURCE / 'protocol/SHA256SUMS.txt').read_text(encoding='utf-8').splitlines()]
    paths = {ROOT / name.removeprefix('frozen/') for _, name in entries if name.startswith('frozen/')}
    changed = [name.removeprefix('frozen/') for expected, name in entries if name.startswith('frozen/')
               and digest(ROOT / name.removeprefix('frozen/')) != expected]
    allowed = {'migration_pipeline/stages/repair.py', 'migration_pipeline/utils/repair_prompt.py',
               'migration_pipeline/utils/repair_scheduler.py', 'migration_pipeline/run_batch_pipeline.py',
               'migration_pipeline/run_pipeline.py'}
    if set(changed) - allowed:
        raise RuntimeError(f'Unexpected changes: {set(changed) - allowed}')
    paths.update(ROOT / name for name in (
        'migration_pipeline/utils/residual_semantics.py', 'migration_pipeline/utils/residual_semantics.cjs',
        'tests/test_semantic_regression_gate.py', 'tests/test_residual_semantics_v2.py',
        'migration_pipeline/replay_formal_30_v4_residual_v2.py',
        'migration_pipeline/run_formal_30_v4_semantic_closure_v2.py',
        'migration_pipeline/prepare_formal_30_v4_semantic_closure_v2.py',
        f'migration_pipeline/batch_configs/{BATCH_ID}.json'))
    PROTOCOL.mkdir(parents=True)
    for source in sorted(paths):
        if not source.is_file() or not source.resolve().is_relative_to(ROOT):
            raise RuntimeError(source)
        destination = PROTOCOL / 'frozen' / source.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    shutil.copy2(SOURCE / 'protocol/verify_protocol.py', PROTOCOL / 'verify_protocol.py')
    shutil.copy2(SOURCE / 'formal_30_v4_semantic_closure_v1_summary.json', PROTOCOL / 'prior_summary.json')
    shutil.copy2(OUTPUT / 'replay.json', PROTOCOL / 'offline_replay.json')
    for name, content in (('unit_tests.txt', tests), ('dry_run.txt', dry), ('offline_replay_log.txt', replay)):
        (PROTOCOL / name).write_text(content, encoding='utf-8')
    text = '''# v4 语义复发保护及残留修复 v2

日期：2026-11-03。重复开发样本 TaskManager、MonitoringDashboard，不是独立测试。来源为 semantic_closure_v1_results_20261103_145253（290 文件），旧分数与原始产物不改。

## 实现及边界

1. bounded 调度候选门新增具体语义诊断差集：隐藏模板依赖、computed 实例方法调用、生命周期行为契约、dataTypes、prop defaults。按 code／location／message 和重复次数比较；即使总错误数下降，有新诊断也拒收。恢复上一候选且仍可失败，保留坏候选及用量。诊断身份依赖同版本验证器的稳定消息；保守拒收不证明所有行为变化都被理解，未知诊断和警告不自动扩展保护范围。
2. 新规则只通过 semantic_rule_set=residual_v2 启用。AST 提取 computed 所调用的自包含组件方法为脚本独立函数，实例方法保留。拒绝 this／外部闭包／参数 mutation／未知副作用；允许限定 Math 和原方法中的局部 Date 计算，Date 仍读取时钟，并非数学纯函数。固定时钟正反例验证旧实例方法与新 helper 的计算一致。原方法定义、坐标分支和空数据行为保持。
3. dataTypes 从完整 SSM inline Vue props 和实际父组件注册映射生成，填入真实字段／可确定类型和 required，数组形式使用 any。不添加空 dataTypes 刷分，不猜父组件无源 props 的契约，不覆盖已有 schema，不支持的类型／不明确注册保持原样；default 等其它契约仍需独立满足。验证器及计分规则本次未改。
4. repair Prompt 允许 missing_data_types 混合残留及单一隐藏依赖／生命周期错误进入聚焦路径；携带真实源 props、源生命周期及递归调用链。没有自动搬移 localStorage／watcher／Notification 初始化，交由有源证据的模型修复后重评估。generation／服务器 Prompt 不变。

## 离线证据与预算

先验证 TaskManager 冻结第 2→3 次会拒收并恢复仍失败的第 2 次，再对两个冻结最终产物应用 residual_v2：TaskManager 仅剩隐藏 tasks 依赖，MonitoringDashboard 仅剩生命周期时序，初始 DOM 通过且仍计失败。没有调用模型，不能将回放当新自动迁移通过。完整测试和 dry-run 通过才冻结。

预算不变：每样本 generation 一次，最多 3 次 LLM repair，每次之前最多 4 个确定性步骤，总计至多 12 步。qwen/qwen-plus、温度 0.2、上游 600 秒、generation／repair 客户端 660 秒。规则／Prompt／候选门同时改变且重新生成，不作单因素因果结论或等实际 token 消耗推断。

## 操作者执行

停止旧服务。窗口 A 设置环境 LLM_API_KEY 后运行：
`python -m migration_pipeline.run_formal_30_v4_semantic_closure_v2 --server`

窗口 B 运行一次：
`python -m migration_pipeline.run_formal_30_v4_semantic_closure_v2 --execute`

launcher 先校验 live 哈希，固定环境，用新批次默认目录，不加 --force。执行完成先冻结证据再检查；所有尝试保留，不择优替换旧失败。后续仍需交互确认及完整 30 项回归，原其它失败事项未结案，v5 等待。本准备过程没有模型调用。
'''
    (PROTOCOL / 'PROTOCOL.md').write_text(text, encoding='utf-8')
    manifest = {'protocol_id': PROTOCOL.name, 'batch_id': BATCH_ID,
                'created_at': datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
                'independent_holdout': False, 'source_snapshot': SOURCE.name,
                'source_verified_files': verified, 'semantic_rule_set': 'residual_v2',
                'repair_policy': 'bounded_prepass_v1', 'max_llm_repair_calls': 3,
                'max_normalization_steps_per_call': 4, 'runtime_env': EXPECTED_ENV,
                'changed_existing_runtime_files': changed, 'config_sha256': digest(CONFIG),
                'config_fingerprint': config_fingerprint(config), 'frozen_payload_files': len(paths),
                'model_request_performed': False}
    (PROTOCOL / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    files = sorted(p for p in PROTOCOL.rglob('*') if p.is_file())
    (PROTOCOL / 'SHA256SUMS.txt').write_text('\n'.join(f'{digest(p)}  {p.relative_to(PROTOCOL).as_posix()}' for p in files) + '\n', encoding='utf-8')
    print(checked_command([sys.executable, str(PROTOCOL / 'verify_protocol.py'), '--live']))
    print(PROTOCOL.relative_to(ROOT))
    print('model_request_performed: false')


if __name__ == '__main__':
    main()
