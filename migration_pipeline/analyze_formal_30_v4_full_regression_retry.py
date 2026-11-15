"""Compare the frozen infrastructure retry with the first full-v4 attempt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from migration_pipeline.analyze_formal_30_v4_full_regression import ROOT, BATCH, FIRST_ATTEMPT_SNAPSHOT, digest, verify_snapshot


def analyze(snapshot: Path) -> Path:
    current = snapshot.resolve()
    first = ROOT / "data/experiments/snapshots" / FIRST_ATTEMPT_SNAPSHOT
    if current == first:
        raise ValueError("Expected a separate frozen retry result")
    checks = {"first": verify_snapshot(first), "retry": verify_snapshot(current)}
    old = json.loads((first / f"{BATCH}_summary.json").read_text(encoding="utf-8"))
    new = json.loads((current / f"{BATCH}_summary.json").read_text(encoding="utf-8"))
    old_samples = {s["id"]: s for s in old["samples"]}
    new_samples = {s["id"]: s for s in new["samples"]}
    if (new["batch_id"] != BATCH or old_samples.keys() != new_samples.keys()
            or old["config_sha256"] != new["config_sha256"]):
        raise RuntimeError("Retry sample/config mismatch")
    changed = [key for key in old_samples if old_samples[key] != new_samples[key]]
    if set(changed) != {"TaskManager", "MonitoringDashboard"}:
        raise RuntimeError("This report expects only the two infrastructure-error samples to be retried")
    for key in changed:
        s = new_samples[key]
        if s["status"] != "error" or "Generation request failed" not in s["error_message"] or "read operation timed out" not in s["error_message"]:
            raise RuntimeError("Retry outcome differs from this timeout diagnostic")
    if new["aggregate"] != old["aggregate"]:
        raise RuntimeError("Aggregate changed; this unchanged-outcome retry report needs a new analysis version")

    def payload_hashes(root: Path) -> dict[str, str]:
        return {
            path.relative_to(root).as_posix(): digest(path)
            for folder in ("pipeline", "repair_reports")
            for path in (root / folder).rglob("*") if path.is_file()
        }

    old_files = payload_hashes(first)
    new_files = payload_hashes(current)
    differences = [name for name in sorted(old_files.keys() | new_files.keys()) if old_files.get(name) != new_files.get(name)]
    attempts = [
        {"id": key, "before": {k: old_samples[key].get(k) for k in ("status", "started_at", "finished_at", "elapsed_seconds", "error_message")},
         "retry": {k: new_samples[key].get(k) for k in ("status", "started_at", "finished_at", "elapsed_seconds", "error_message")}}
        for key in changed
    ]
    output = ROOT / "data/experiments/analysis" / current.name.replace("_results_", "_retry_")
    output.mkdir(parents=True, exist_ok=True)
    data = {
        "classification": "unchanged_protocol_infrastructure_retry",
        "independent_holdout": False,
        "first_snapshot": first.relative_to(ROOT).as_posix(),
        "retry_snapshot": current.relative_to(ROOT).as_posix(),
        "verified_files": checks,
        "retry_summary_sha256": digest(current / f"{BATCH}_summary.json"),
        "changed_sample_ids": changed,
        "unchanged_completed_records": 28,
        "generated_or_report_files_compared": len(new_files),
        "generated_or_report_file_differences": differences,
        "aggregate": new["aggregate"],
        "attempts": attempts,
        "observed_failure_boundary": "Both retries failed while waiting for generation response at about 240 seconds; provider-side queue/generation/network cause is not established by these logs.",
        "recommendation": "Preserve this protocol result. A longer-timeout diagnostic must use separate config, output/checkpoint and pre-run evidence; do not overwrite this result or change frozen timeout settings in place.",
    }
    (output / "summary.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    table = "\n".join(
        f"| {item['id']} | {'repair' if 'Repair request failed' in item['before']['error_message'] else 'generation'} | generation | {item['retry']['elapsed_seconds']:.3f} 秒 |"
        for item in attempts
    )
    report = f"""# v4 完整 30 样本回归：超时重试记录

本次 checkpoint 更新时间：`{new['updated_at']}`。仅 TaskManager、MonitoringDashboard 两条记录变化，其余 28 条 completed 记录逐字段保持一致（其中 25 通过、3 评估未通过）。结果仍为 **25/30 = 83.33%**，2 项执行错误尚无最终评估。

原始重试结果冻结于 `{current.name}`，校验 {checks['retry']} 个文件通过；首次快照 `{first.name}` 的 {checks['first']} 个文件也校验通过。旧结果及两次错误信息均保留。

| 样本 | 首次异常阶段 | 本次异常阶段 | 本次耗时 |
| --- | --- | --- | ---: |
{table}

两个异常均为本地 HTTP 400 包装的 `The read operation timed out`。冻结代码中 `QwenClient` 通过非流式 HTTP 请求等待响应，`urlopen(..., timeout=self.timeout)` 使用 `LLM_TIMEOUT`，本协议设为 240 秒；批处理到本地服务的 generation／repair HTTP 超时为 300 秒。约 241 秒的失败与上游读取上限一致。健康检查记录 provider=qwen、model=qwen-plus。

直接终止点可定位为上游读取超时，但现有记录不能区分服务端排队、生成耗时或网络读等待；不能据此断言 Prompt 一定错误、密钥错误或组件最终修复失败。TaskManager 首次有生成和 repair 产物、本次却在生成阶段超时，也不能解释为代码再次退化。

对比两份快照的 {len(new_files)} 份 pipeline／repair report 文件，差异文件数为 {len(differences)}。若无差异，当前目录里的 TaskManager 旧产物来自首次执行，不能当成本次重试生成的输出。异常样本没有完整报告，聚合 token 未完整计入其消耗；summary 总 token 保持不变不能解释为重试免费。

## 后续处理边界

本协议已完成一次同条件的超时重试，继续重复相同命令的诊断价值有限。保留原批次的 25 通过、3 评估失败、2 超时，先建立单独的基础设施诊断版本，保持模型、Prompt 与 3 轮上限，考虑把上游超时增至 600 秒，同时把 generation／repair 客户端超时增至 660 秒；两层必须配套，并记录新配置与新输出。它属于条件变化，不能回填本批，也不能直接提高本批通过率。

三个评估失败仍是 BudgetThreshold（repair 模板退化）、TipSplitCalculator（事件辅助方法契约／校验范围待核实）、LocalizationWorkspace（隐藏语言依赖）。后续系统修复采用新的版本和回归配置；v5 探索性评估继续等待。此次仅做记录与诊断，没有改变 Prompt、规则、超时或任何生成产物，也未调用模型。
"""
    (output / "REPORT.md").write_text(report, encoding="utf-8")
    print(output.relative_to(ROOT))
    print(json.dumps({"changed_ids": changed, "unchanged_completed": 28, "payload_differences": differences, "verified_files": checks}, ensure_ascii=False))
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    args = parser.parse_args()
    analyze(args.snapshot if args.snapshot.is_absolute() else ROOT / args.snapshot)


if __name__ == "__main__":
    main()
