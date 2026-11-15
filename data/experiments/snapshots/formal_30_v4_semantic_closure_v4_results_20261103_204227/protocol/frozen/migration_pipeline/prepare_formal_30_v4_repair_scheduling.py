"""Freeze the opt-in scheduling policy as a new development experiment."""

import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from migration_pipeline.analyze_formal_30_v4_full_regression import verify_snapshot
from migration_pipeline.prepare_formal_30_v4_full_regression import checked_command, digest
from migration_pipeline.run_formal_30_v4_repair_scheduling import ROOT, BATCH_ID, CONFIG, PROTOCOL, EXPECTED_ENV
from migration_pipeline.run_batch_pipeline import config_fingerprint, validate_batch_config


PRIOR = ROOT / "data/experiments/snapshots/formal_30_v4_timeout_diagnostic_v1_results_20261102_173627"
ANALYSIS = ROOT / "data/experiments/analysis/formal_30_v4_repair_scheduling_v1_20261102"


def main():
    for path in (PROTOCOL, ROOT / f"data/experiments/pipeline/batches/{BATCH_ID}",
                 ROOT / f"data/experiments/repair_reports/batches/{BATCH_ID}",
                 ROOT / f"data/experiments/batch_reports/{BATCH_ID}_summary.json"):
        if path.exists():
            raise FileExistsError(path)
    verified = verify_snapshot(PRIOR)
    old_config = json.loads((PRIOR / "formal_30_v4_timeout_diagnostic_v1.json").read_text(encoding="utf-8"))
    for sample in old_config["samples"]:
        if digest(ROOT / sample["vue_file"]) != digest(PRIOR / "protocol/frozen" / sample["vue_file"]):
            raise RuntimeError(f"Source changed: {sample['id']}")
    config = {
        **old_config, "batch_id": BATCH_ID,
        "description": "Opt-in bounded deterministic prepass, three LLM-repair-call budget and rejected-candidate rollback; reused development regression.",
        "classification": "repair_scheduling_policy_development_regression",
        "repair_policy": "bounded_prepass_v1", "repair_budget_unit": "llm_calls",
        "prior_result_snapshot": PRIOR.name,
        "prior_result_summary_sha256": digest(PRIOR / "formal_30_v4_timeout_diagnostic_v1_summary.json"),
        "max_repair_rounds": 3, "max_normalization_steps_per_llm_call": 4,
    }
    validate_batch_config(config)
    if CONFIG.exists() and json.loads(CONFIG.read_text(encoding="utf-8")) != config:
        raise RuntimeError("Existing new config differs")
    if not CONFIG.exists():
        CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    replay = checked_command([sys.executable, "-m", "migration_pipeline.replay_formal_30_v4_repair_scheduling"])
    tests = checked_command([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"])
    dry = checked_command([sys.executable, "-m", "migration_pipeline.run_formal_30_v4_repair_scheduling", "--dry-run"])
    baseline_files = [(line.split("  ", 1)[1], line.split("  ", 1)[0]) for line in (PRIOR / "protocol/SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()]
    paths = {ROOT / name.removeprefix("frozen/") for name, _ in baseline_files if name.startswith("frozen/")}
    runtime_changes = []
    for name, expected in baseline_files:
        if name.startswith("frozen/"):
            path = ROOT / name.removeprefix("frozen/")
            if digest(path) != expected:
                runtime_changes.append(name.removeprefix("frozen/"))
    allowed = {"migration_pipeline/orchestrator.py", "migration_pipeline/stages/repair.py",
               "migration_pipeline/run_batch_pipeline.py", "migration_pipeline/run_pipeline.py"}
    if set(runtime_changes) - allowed:
        raise RuntimeError(f"Unexpected runtime changes: {set(runtime_changes) - allowed}")
    paths.update(ROOT / name for name in (
        "migration_pipeline/utils/repair_scheduler.py", "migration_pipeline/prepare_formal_30_v4_repair_scheduling.py",
        "migration_pipeline/run_formal_30_v4_repair_scheduling.py", "migration_pipeline/replay_formal_30_v4_repair_scheduling.py",
        "tests/test_bounded_repair_scheduler.py", f"migration_pipeline/batch_configs/{BATCH_ID}.json",
    ))
    PROTOCOL.mkdir(parents=True)
    for source in sorted(paths):
        if not source.is_file() or not source.resolve().is_relative_to(ROOT):
            raise RuntimeError(source)
        destination = PROTOCOL / "frozen" / source.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    shutil.copy2(PRIOR / "protocol/verify_protocol.py", PROTOCOL / "verify_protocol.py")
    shutil.copy2(PRIOR / "formal_30_v4_timeout_diagnostic_v1_summary.json", PROTOCOL / "prior_diagnostic_summary.json")
    shutil.copy2(ANALYSIS / "replay.json", PROTOCOL / "offline_replay.json")
    for name, content in (("unit_tests.txt", tests), ("dry_run.txt", dry), ("offline_replay_log.txt", replay)):
        (PROTOCOL / name).write_text(content, encoding="utf-8")
    protocol = """# v4 新调度策略针对性开发回归 v1

日期：2026-11-02；批次 formal_30_v4_repair_scheduling_v1。

仅复用 TaskManager、MonitoringDashboard，原 Vue 输入相同；采用 bounded_prepass_v1。旧策略最多 3 个混合 attempt；本版本的最大轮数 **明确改为最多 3 次 LLM repair 调用**，每次之前最多 4 个确定性步骤，最多 12 个确定性步骤。每一步重评估，遇到固定点／重复代码／上限转交 LLM，若归一化已通过则不调用 LLM。循环检测与规则幂等性不是完整等价，本版本未宣称所有规则已经幂等。

这改变了计算预算，不能把新 3 次调用结果与旧 3 混合轮结果当作等成本比较。generation、Prompt、模型、验证器、归一化变换规则本身与前次保持；调度、候选拒收／保留及计数报告改变。legacy 默认路径保持，旧批次／快照不回填。原 30 样本及 v5 冻结协议的 live 代码基线已不再与新实现一致，不能继续当作当前代码可运行协议。

新策略对所有候选应用事件契约与关键错误／视觉通过退化检查，不依赖特定 Prompt 文本标记。拒绝的产物留在单独文件和历史里；LLM 候选被拒后恢复上一候选的代码、路径、验证与视觉状态，停止并保留失败，不把上一份候选自动宣称为通过。确定性候选被拒则保留原候选交给 LLM。TaskManager 离线首次归一化被保守的事件契约检查拒绝（closeModal 包装后追溯不完整）；这是已知限制，不因追求通过而绕过检查。

离线回放证明 TaskManager 能到达 LLM-only 阶段，MonitoringDashboard 第三轮和 BudgetThreshold 第一轮退化候选会被拒并保留上一文件；不代表模型回归已通过。TipSplitCalculator 事件方法契约、LocalizationWorkspace 隐藏语言依赖仍待后续修复，不包含在本次两样本结案结论中。

继续使用 qwen/qwen-plus、温度 0.2、上游 600 秒／两类客户端 660 秒。先在旧服务器 Ctrl+C，然后窗口 A 设置环境密钥并运行：

```powershell
$env:LLM_API_KEY = "<你的密钥>"
python -m migration_pipeline.run_formal_30_v4_repair_scheduling --server
```

窗口 B 执行一次：

```powershell
python -m migration_pipeline.run_formal_30_v4_repair_scheduling --execute
```

launcher 核对 live 哈希并固定环境。--dry-run 可无模型查看计划。运行结束先冻结，不加 --force，不挑选多次结果。输出与 summary 使用批次名对应的独立默认目录。报告 LLM 次数与确定性步数、拒收历史及 token；手工交互结论另列。运行代码的文件基线以 frozen/ 为准，服务器实际加载仍需操作者按上述命令确认。该批是复用开发样本，不是独立测试；v5 暂停。
"""
    (PROTOCOL / "PROTOCOL.md").write_text(protocol, encoding="utf-8")
    manifest = {
        "protocol_id": PROTOCOL.name, "batch_id": BATCH_ID,
        "created_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
        "classification": config["classification"], "independent_holdout": False,
        "repair_policy": config["repair_policy"], "max_llm_repair_calls": 3,
        "max_normalization_steps_per_call": 4, "runtime_env": EXPECTED_ENV,
        "prior_verified_files": verified, "changed_existing_runtime_files": runtime_changes,
        "config_sha256": digest(CONFIG), "config_fingerprint": config_fingerprint(config),
        "model_request_performed": False, "frozen_payload_files": len(paths),
    }
    (PROTOCOL / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    payloads = sorted(p for p in PROTOCOL.rglob("*") if p.is_file())
    (PROTOCOL / "SHA256SUMS.txt").write_text("\n".join(f"{digest(p)}  {p.relative_to(PROTOCOL).as_posix()}" for p in payloads) + "\n", encoding="utf-8")
    print(checked_command([sys.executable, str(PROTOCOL / "verify_protocol.py"), "--live"]))
    print(PROTOCOL.relative_to(ROOT))
    print("model_request_performed: false")


if __name__ == "__main__":
    main()
