"""Analyze a verified scheduling regression snapshot; no model calls or repairs."""

import argparse
import hashlib
import json
from pathlib import Path

from migration_pipeline.analyze_formal_30_v4_full_regression import digest, verify_snapshot
from migration_pipeline.run_formal_30_v4_repair_scheduling import ROOT, BATCH_ID


def progress_code_hash(path):
    # Progress signatures intentionally ignore trailing whitespace; snapshot
    # digests above independently verify the exact on-disk bytes.
    code = path.read_text(encoding="utf-8")
    normalized = "\n".join(line.rstrip() for line in code.replace("\r\n", "\n").split("\n")).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def analyze(snapshot):
    snapshot = snapshot.resolve()
    checked = verify_snapshot(snapshot)
    summary_path = snapshot / f"{BATCH_ID}_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary["batch_id"] != BATCH_ID:
        raise RuntimeError("Unexpected batch")
    rows = []
    for sample in summary["samples"]:
        if sample["status"] != "completed":
            raise RuntimeError("Execution errors require a separate analysis")
        report_path = snapshot / "repair_reports/complex" / Path(sample["report_file"]).name
        report = json.loads(report_path.read_text(encoding="utf-8"))
        state = report["state"]
        history = state["repair_history"]
        normalizations = state["normalization_history"]
        calls = len(history)
        if (calls != sample["llm_repair_calls"] or calls != sample["repair_rounds"]
                or len(normalizations) != sample["deterministic_steps"]
                or not 0 <= calls <= 3 or not len(normalizations) <= 4 * calls
                or any(h["repair_result"]["provider"] == "deterministic" for h in history)):
            raise RuntimeError(f"Counter mismatch: {sample['id']}")
        for key in ("final_passed", "repair_rounds", "llm_repair_calls", "deterministic_steps",
                    "retained_previous_candidate", "stop_reason"):
            if report["summary"][key] != sample[key]:
                raise RuntimeError(f"Summary/report mismatch: {sample['id']}/{key}")
        final = snapshot / "pipeline/complex" / Path(sample["final_file_path"]).name
        final_hash = digest(final)
        if final.read_text(encoding="utf-8") != state["generated_code"]:
            raise RuntimeError(f"Final code mismatch: {sample['id']}")
        final_validation = state["final_validate_result"]
        if final_validation["validation_errors"] != state["validate_result"]["validation_errors"]:
            raise RuntimeError(f"Final evaluation mismatch: {sample['id']}")
        rollback = None
        if sample["retained_previous_candidate"]:
            rejected = snapshot / "pipeline/complex" / Path(state["rejected_candidate_file"]).name
            accepted_history = history[-2]
            last = history[-1]
            if (not last["repair_regression_rejected"] or not last["repair_regression_gate"]["should_stop"]
                    or rejected.read_text(encoding="utf-8") != last["repair_result"]["repaired_code"]
                    or final.read_text(encoding="utf-8") != accepted_history["repair_result"]["repaired_code"]
                    or progress_code_hash(rejected) != last["progress_signature"]["generated_code_sha256"]
                    or progress_code_hash(final) != accepted_history["progress_signature"]["generated_code_sha256"]
                    or final_validation != accepted_history["validate_result"]
                    or state["final_visual_eval_result"] != accepted_history["visual_eval_result"]):
                raise RuntimeError(f"Rollback evidence mismatch: {sample['id']}")
            rollback = {"retained_file": final.name, "rejected_file": rejected.name,
                        "rejected_sha256": digest(rejected), "verified": True}
        elif progress_code_hash(final) != history[-1]["progress_signature"]["generated_code_sha256"]:
            raise RuntimeError(f"Final history mismatch: {sample['id']}")
        generation_tokens = state.get("generation_usage", {}).get("total_tokens", 0)
        repair_tokens = sum(h["repair_result"].get("usage", {}).get("total_tokens", 0) for h in history)
        if generation_tokens != sample["generation_tokens"] or repair_tokens != sample["repair_tokens"]:
            raise RuntimeError(f"Token mismatch: {sample['id']}")
        rows.append({
            "id": sample["id"], "passed": sample["final_passed"],
            "elapsed_seconds": sample["elapsed_seconds"], "stop_reason": sample["stop_reason"],
            "llm_repair_calls": calls, "deterministic_steps": len(normalizations),
            "accepted_deterministic_steps": sum(n["accepted"] for n in normalizations),
            "normalization_history": normalizations,
            "normalization_stop_reasons": state["normalization_stop_reasons"],
            "rounds": [{"attempt": h["repair_attempt"], "signature": h["progress_signature"],
                        "gate": h["repair_regression_gate"],
                        "issues": h["validate_result"]["validation_errors"],
                        "usage": h["repair_result"].get("usage", {})} for h in history],
            "final_file": final.name, "final_sha256": final_hash,
            "final_validation_issues": final_validation["validation_errors"],
            "final_structure_similarity": sample["final_structure_similarity"],
            "rollback": rollback, "generation_tokens": generation_tokens,
            "repair_tokens": repair_tokens, "interaction_evaluated": False,
        })
    aggregate = summary["aggregate"]
    if (aggregate["completed"] != len(rows) or aggregate["passed"] != sum(r["passed"] for r in rows)
            or aggregate["generation_tokens"] != sum(r["generation_tokens"] for r in rows)
            or aggregate["repair_tokens"] != sum(r["repair_tokens"] for r in rows)):
        raise RuntimeError("Aggregate mismatch")
    output = ROOT / "data/experiments/analysis" / snapshot.name.replace("_results_", "_")
    output.mkdir(parents=True, exist_ok=True)
    data = {"snapshot": snapshot.relative_to(ROOT).as_posix(), "verified_files": checked,
            "summary_sha256": digest(summary_path), "aggregate": aggregate,
            "classification": "repair_scheduling_policy_development_regression_analysis",
            "independent_holdout": False, "repair_budget_unit": "llm_calls", "samples": rows}
    (output / "summary.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    table = "\n".join(f"| {r['id']} | {r['llm_repair_calls']} | {r['deterministic_steps']} ({r['accepted_deterministic_steps']} 接受) | {r['final_structure_similarity']} | 未通过 |" for r in rows)
    report_text = f"""# repair 调度策略 v1：执行完成，语义修复未闭环

日期：2026-11-02。批次 `{BATCH_ID}`，2026-11-02 18:32:32–19:04:47（UTC+8）。先冻结后诊断：`{snapshot.name}`，{checked} 文件哈希验证通过；冻结时协议 263 项 live 校验通过。

## 实际结果

两项执行完成、零执行错误、**0/2 自动通过**。两项初始 DOM 评估最终均通过，不代表交互或静态迁移正确。此次没有进行新的人工交互确认。

| 样本 | LLM repair 调用 | 确定性步骤 | 最终 DOM 相似度 | 自动结论 |
| --- | ---: | ---: | ---: | --- |
{table}

TaskManager 总用时 757.109 秒，MonitoringDashboard 1177.797 秒。生成 {aggregate['generation_tokens']:,}、repair {aggregate['repair_tokens']:,}，合计 **{aggregate['total_tokens']:,} tokens**，包含被拒的第二次 TaskManager repair。此次预算为最多 3 次 LLM repair，而前轮为 3 个混合 attempt；这是不同预算、不同随机新生成结果，不能作等成本因果比较，也不能用本轮替换原完整 30 项的结论。

## TaskManager：调用路径修复生效，事件追溯存在覆盖缺口

两次确定性候选均被拒（新增 1 个无法追溯的 `click:closeModal`），随后均实际进入 LLM。第一次 LLM 后剩四类错误：事件语法、self-click guard、computed 中的 isOverdue 实例方法调用、getTaskCount 隐藏 tasks 依赖。

第二次 LLM 后静态错误减少到两类：事件语法、computed 实例方法调用；但事件追溯从 0 个 unresolved 变为 1 个。保护门据此拒收，停止并把 final 恢复为 `TaskManager_repaired.san`，而不是第二次文件。最终代码、文件哈希、静态和视觉评估均已核对匹配第一轮；拒收产物、评估和 token 在历史中保留，仍计失败。

代码中存在 `handleModalBackdropClick(e)`，带 target/currentTarget 相等检查并调用 closeModal。当前追溯器只识别直接绑定及少量命名别名，无法据该包装证明与原 `@click.self` 等价；而模板绑定没有显式传 `$event`。因此本轮不能把“无法追溯”直接解释为真实功能删除，也不能直接认定为纯误报或人工放行。下一步应检查包装函数传参、分支和调用语义，并为等价包装及不等价包装增加正反例测试。

## MonitoringDashboard：3 次 LLM 后仍有明确残留

三个确定性步骤均被接受，三次 LLM 分别产生 5、4、2 类错误。未发生候选回退；最终文件确实是第三轮，DOM 相似度 0.9605。

1. `invalid_san_inline_computed_method_invocation`：requestChart 的 computed `barWidth()` 返回函数，但模板仍使用 `barWidth(data.length)`。需修复参数化计算的落地方式，而不是删除检查。
2. `event_arguments_not_landed`：绑定变为无参数 onKPIClick 和 changePeriod，未保留源 `onKPIClick(kpi)`、`changePeriod(period.value)`；方法依赖 `this.event.target` 取 data-*。不能仅凭初始 DOM 通过证明这条事件链可用，需要显式传参并验证真实事件／payload。

## 已证明与未证明

已证明本轮 LLM-only 路径可达，确定性步骤与 LLM 次数分开计数，TaskManager 的拒收与回退证据一致。未证明迁移质量已经合格；保守追溯拒收可能阻断有效改写，原规则与 checker 的协调还需边界测试。原 BudgetThreshold、TipSplitCalculator、LocalizationWorkspace 事项不属于本次两样本结案。

## 建议下一步（尚未实施）

先用本次冻结产物做无模型回放：审查事件包装追溯和显式传参规则，修复 computed 参数化计算及事件 payload 的通用落地，再添加反例防止误放行。涉及 Prompt／规则／checker 的改动应建新版本并记录，不改本轮冻结包或原始 San，不降低通过标准。局部回归通过后再完整跑 30 项，v5 探索性评估继续等待。当前不建议直接强制重跑同批，也不把 DOM 通过当成人工通过。

复现：`python -m migration_pipeline.analyze_formal_30_v4_repair_scheduling --snapshot {snapshot.relative_to(ROOT).as_posix()}`。
"""
    (output / "REPORT.md").write_text(report_text, encoding="utf-8")
    print(output.relative_to(ROOT))
    print(json.dumps({"verified_files": checked, "completed": len(rows),
                      "passed": aggregate["passed"], "llm_repair_calls": sum(r["llm_repair_calls"] for r in rows),
                      "deterministic_steps": sum(r["deterministic_steps"] for r in rows),
                      "total_tokens": aggregate["total_tokens"]}))
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    args = parser.parse_args()
    analyze(args.snapshot if args.snapshot.is_absolute() else ROOT / args.snapshot)


if __name__ == "__main__":
    main()
