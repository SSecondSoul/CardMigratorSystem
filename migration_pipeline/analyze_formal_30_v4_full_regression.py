"""Analyze one immutable full-v4 regression attempt; never calls a model."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BATCH = "formal_30_v4_full_regression"
FIRST_ATTEMPT_SNAPSHOT = "formal_30_v4_full_regression_results_20261030_215511"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_snapshot(snapshot: Path) -> int:
    entries = (snapshot / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
    for line in entries:
        expected, name = line.split("  ", 1)
        path = (snapshot / name).resolve()
        if not path.is_relative_to(snapshot) or not path.is_file() or digest(path) != expected:
            raise RuntimeError(f"Snapshot checksum mismatch: {name}")
    return len(entries)


def outcome(sample: dict) -> str:
    return "error" if sample["status"] == "error" else "pass" if sample["final_passed"] else "fail"


def analyze(snapshot: Path) -> Path:
    snapshot = snapshot.resolve()
    if snapshot.name != FIRST_ATTEMPT_SNAPSHOT:
        raise ValueError("This diagnostic report is tied to the first frozen attempt; analyze a resumed run in a separate report version")
    checked = verify_snapshot(snapshot)
    result_path = snapshot / f"{BATCH}_summary.json"
    baseline_path = snapshot / "protocol/frozen/data/experiments/batch_reports/formal_30_v3_summary.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    before = {s["id"]: s for s in baseline["samples"]}
    if result["batch_id"] != BATCH or len(before) != 30 or [s["id"] for s in result["samples"]] != list(before):
        raise RuntimeError("Expected a paired, ordered 30-sample comparison")
    rows = []
    for sample in result["samples"]:
        current = outcome(sample)
        old = outcome(before[sample["id"]])
        transition = (
            "kept_pass" if old == current == "pass" else
            "regressed_to_fail" if old == "pass" else
            "improved_to_pass" if current == "pass" else "still_not_pass"
        )
        row = {
            "id": sample["id"], "component_name": sample["component_name"],
            "complexity": sample["complexity"], "before": old, "after": current,
            "transition": transition, "repair_rounds": sample.get("repair_rounds"),
            "stop_reason": sample.get("stop_reason"),
            "final_validation_error_codes": sample.get("final_validation_error_codes", []),
            "final_visual_error_codes": sample.get("final_visual_error_codes", []),
            "error_message": sample.get("error_message", ""),
            "final_file_sha256": None,
        }
        if current != "error":
            report_path = snapshot / "repair_reports" / sample["complexity"] / Path(sample["report_file"]).name
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if report["summary"]["final_passed"] != sample["final_passed"] or report["summary"]["repair_rounds"] != sample["repair_rounds"]:
                raise RuntimeError(f"Report/summary mismatch: {sample['id']}")
            state = report["state"]
            validation = state["final_validate_result"]
            visual = state["final_visual_eval_result"]
            if (sorted(item["code"] for item in validation["validation_errors"]) != sorted(sample["final_validation_error_codes"])
                    or sorted(item["code"] for item in visual["visual_eval_errors"]) != sorted(sample["final_visual_error_codes"])):
                raise RuntimeError(f"Detailed issues/summary mismatch: {sample['id']}")
            row["validation_issues"] = validation["validation_errors"]
            row["visual_issues"] = visual["visual_eval_errors"]
            row["visual_warnings"] = visual["visual_eval_warnings"]
            row["final_file_sha256"] = digest(snapshot / "pipeline" / sample["complexity"] / Path(sample["final_file_path"]).name)
        rows.append(row)
    a = result["aggregate"]
    b = baseline["aggregate"]
    actual = Counter(row["after"] for row in rows)
    if (actual["pass"], actual["fail"], actual["error"]) != (a["passed"], a["failed"], a["execution_errors"]):
        raise RuntimeError("Aggregate/sample outcome mismatch")
    for level in ("simple", "medium", "complex"):
        level_rows = [row for row in rows if row["complexity"] == level]
        observed = Counter(row["after"] for row in level_rows)
        expected = a["by_complexity"][level]
        if len(level_rows) != 10 or (observed["pass"], observed["fail"], observed["error"]) != (expected["passed"], expected["failed"], expected["execution_errors"]):
            raise RuntimeError(f"Stratum aggregate mismatch: {level}")
    transitions = dict(Counter(row["transition"] for row in rows))
    if (actual["pass"], actual["fail"], actual["error"]) != (25, 3, 2) or transitions != {
        "kept_pass": 16, "regressed_to_fail": 2, "improved_to_pass": 9, "still_not_pass": 3,
    }:
        raise RuntimeError("Frozen results differ from the first-attempt diagnostic findings")
    data = {
        "classification": "paired_reused_development_regression_attempt",
        "strict_independent_holdout": False,
        "source_snapshot": snapshot.relative_to(ROOT).as_posix(),
        "verified_snapshot_files": checked,
        "source_summary_sha256": digest(result_path),
        "baseline_summary_sha256": digest(baseline_path),
        "baseline_aggregate": b,
        "current_aggregate": a,
        "baseline_pass_rate_all_configured": b["passed"] / 30,
        "current_pass_rate_all_configured": a["passed"] / 30,
        "pass_rate_all_configured_change_percentage_points": round((a["passed"] - b["passed"]) / 30 * 100, 2),
        "transition_counts": transitions,
        "token_scope": "Aggregate token totals cover completed samples only; spending in execution-error attempts is not fully recorded.",
        "causal_limit": "Same source inputs, but model sampling and the evaluator changed; differences cannot be attributed to prompt changes alone.",
        "samples": rows,
    }
    output = ROOT / "data/experiments/analysis" / snapshot.name.replace("_results_", "_")
    output.mkdir(parents=True, exist_ok=True)
    (output / "summary.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    labels = {"kept_pass": "保持通过", "regressed_to_fail": "由通过变未通过", "improved_to_pass": "改善为通过", "still_not_pass": "仍未通过／执行错误"}
    sample_table = "\n".join(f"| {r['component_name']} | {r['complexity']} | {r['before']} | {r['after']} | {labels[r['transition']]} |" for r in rows)
    strata = "\n".join(
        f"| {level} | {b['by_complexity'][level]['passed']}/10 | {a['by_complexity'][level]['passed']}/10 | {a['by_complexity'][level]['failed']} | {a['by_complexity'][level]['execution_errors']} |"
        for level in ("simple", "medium", "complex")
    )
    report_text = f"""# v4 完整 30 样本开发回归：本次执行结果

来源：`{snapshot.name}`，{checked} 个文件校验通过；原始报告、代码和预运行协议均已封存。此报告记录这一执行快照，后续基础设施重试另留记录。

30 项均已尝试：25 通过、3 项评估未通过、2 项执行错误；28 项正常完成。全部 30 项分母通过率为 **25/30 = 83.33%**，正常完成项通过率为 25/28 = 89.29%。旧 v3 为 18/30 = 60.00%；本次增加 7 项，描述性变化 +23.33 个百分点。

| 层级 | 旧 v3 通过／配置数 | 当前 v4 通过／配置数 | 当前评估失败 | 当前执行错误 |
| --- | ---: | ---: | ---: | ---: |
{strata}

配对结果：16 保持通过、9 改善为通过、2 由通过变为未通过、3 仍未通过／执行错误。运行上限均为 3 轮；最近 TaskManager 的 6 轮单样本成功不能替代本次结果。

## 五项未通过的证据

- **BudgetThreshold**：旧 v3 通过；本次初始 DOM 相似度 1.0。首次 repair 把模板的 `remaining`、`statusText` 改为 `this.data.get(...)`，最终渲染警告明确提示 `this.data` 未定义，最终结构相似度 0.75；3 轮耗尽。观察到 repair 产物引入模板回退，尚未修正本批输出。
- **TipSplitCalculator**：旧 v3 通过；本次静态 `custom_event_not_fire` 未消除，2 轮后因无进展停止，DOM 相似度 1.0。源组件唯一 `$emit` 位于没有内部调用的通用 `emitEvent` 方法，生成代码移除了该方法。当前检查未区分可达事件行为与公开辅助方法保留；需审查契约／校验范围，不能直接解释为界面事件丢失，也未据此改写失败评分。
- **LocalizationWorkspace**：3 轮后仍有 `hidden_template_reactive_dependency`。模板 `translationFor(record)` 隐藏读取 `language`；初始 DOM 相似度 1.0 不能证明切换语言时正确更新。
- **TaskManager**：repair HTTP 请求返回 `The read operation timed out`，保留了初始及两份 repair 产物，但没有完整最终报告。此项属于执行错误，不能推断为 3 轮内修复通过或失败。
- **MonitoringDashboard**：generation HTTP 请求返回相同超时，执行约 240.75 秒，属于执行错误，没有最终评估。

这两次 HTTP 400 的响应体写明上游读超时；不应将它们等同于组件语法失败或 API 密钥缺失。相同命令、相同协议的 checkpoint 恢复会跳过全部 28 条 `completed` 记录（其中包括 3 条失败），仅重新执行两个 `error` 样本的链路；它不会从 TaskManager 中断的 repair 步恢复。

## 用量与限制

summary 记录生成 650,037、repair 1,092,872、合计 **1,742,909 tokens**，repair 43 轮。这些聚合只包含正常完成的 28 项，未完整纳入 TaskManager 等异常执行的已发生用量，不能作为全批实际花费，也不能据此宣称成本降低。

本批为复用已接触样本的开发回归。模型采样及评估器变化都会影响结果，两个由通过变未通过的样本是本次观察到的退化，尚不能单凭一次运行归因到某条 Prompt。全部 28 个完成项的自动交互结果为空；自动通过不等于浏览器交互全部通过。启动健康检查记录 qwen/qwen-plus，磁盘代码 live 校验通过，但服务器进程加载字节没有独立证明。

## 下一步

先按原命令、不加 `--force` 恢复两个超时样本并保留本次快照。重试不得改模型、Prompt、轮数或超时。之后再封存新的执行状态、分析三项评估失败；系统修改须建立后续版本。v5 探索性评估继续等待这一步结果。

## 全部 30 项配对清单

| 组件 | 复杂度 | 旧 v3 | 当前 v4 | 观察结果 |
| --- | --- | --- | --- | --- |
{sample_table}

复现本报告（只读冻结证据，不调用模型）：`python -m migration_pipeline.analyze_formal_30_v4_full_regression --snapshot {snapshot.relative_to(ROOT).as_posix()}`。逐样本错误与哈希见 `summary.json`。
"""
    (output / "REPORT.md").write_text(report_text, encoding="utf-8")
    print(output.relative_to(ROOT))
    print(json.dumps({"aggregate": a, "transitions": transitions}, ensure_ascii=False))
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    args = parser.parse_args()
    path = args.snapshot if args.snapshot.is_absolute() else ROOT / args.snapshot
    analyze(path)


if __name__ == "__main__":
    main()
