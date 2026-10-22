"""Build the formal_30_v1/v2 thesis-analysis artifacts from frozen evidence."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V1_SNAPSHOT = ROOT / "data/experiments/snapshots/formal_30_v1_results_20261015_161053"
V2_SNAPSHOT = ROOT / "data/experiments/snapshots/formal_30_v2_manual_results_20261022_152408"
OUTPUT_DIR = ROOT / "data/experiments/analysis/formal_30_v1_v2_20261022"


TAXONOMY = {
    "DeliveryPhaseCard": {
        "primary": "loop_scope_binding",
        "labels": ["loop_binding_or_syntax"],
        "issue_zh": "阶段推进后颜色不随活动阶段变化。",
    },
    "PollResults": {
        "primary": "no_discrepancy_confirmed",
        "labels": ["no_discrepancy_confirmed"],
        "issue_zh": "人工浏览器检查未发现 Vue/San 差异。",
    },
    "ImageCropControls": {
        "primary": "initialization_or_lifecycle",
        "labels": [
            "initialization_or_lifecycle",
            "event_conversion",
            "watcher_mapping",
            "dom_order_or_layout",
        ],
        "issue_zh": "缺少初始裁剪框；参数不能驱动画布；宽高比锁定样式与功能异常。",
    },
    "AttendanceRoster": {
        "primary": "no_discrepancy_confirmed",
        "labels": ["no_discrepancy_confirmed"],
        "issue_zh": "人工浏览器检查未发现 Vue/San 差异。",
    },
    "InventoryBatchManager": {
        "primary": "hidden_reactive_dependency",
        "labels": ["hidden_reactive_dependency"],
        "issue_zh": "单行选择和全选后，选择样式不更新。",
    },
    "MediaReviewStudio": {
        "primary": "nested_state_mutation",
        "labels": ["nested_state_mutation", "event_conversion"],
        "issue_zh": "决策和批注操作不生效，提交批注会触发页面刷新。",
    },
    "EnergyLoadScheduler": {
        "primary": "hidden_reactive_dependency",
        "labels": ["hidden_reactive_dependency"],
        "issue_zh": "切换运行时段后文字变化，但按钮颜色不更新。",
    },
    "ForecastSimulator": {
        "primary": "initialization_or_lifecycle",
        "labels": ["initialization_or_lifecycle", "repair_regression"],
        "issue_zh": "缺少初始模拟结果、图表、汇总和月度明细。",
    },
    "TopologyEditor": {
        "primary": "nested_state_mutation",
        "labels": [
            "nested_state_mutation",
            "initialization_or_lifecycle",
            "prop_default",
            "timer_ownership",
        ],
        "issue_zh": "标题缺失，节点移动和连线不生效，模拟日志不持续更新。",
    },
    "DocumentApprovalFlow": {
        "primary": "no_discrepancy_confirmed",
        "labels": ["no_discrepancy_confirmed"],
        "issue_zh": "人工浏览器检查未发现 Vue/San 差异。",
    },
    "CapacityPlanningBoard": {
        "primary": "template_syntax",
        "labels": ["loop_binding_or_syntax", "validator_false_negative"],
        "issue_zh": "错误的 s-for/trackby 语法导致 San 模板解析失败。",
    },
    "GradebookMatrix": {
        "primary": "dom_child_order",
        "labels": ["dom_order_or_layout"],
        "issue_zh": "复选框与百分号相对输入框的位置和 Vue 不一致。",
    },
    "SupportTicketConsole": {
        "primary": "dom_child_order",
        "labels": ["dom_order_or_layout"],
        "issue_zh": "内部备注复选框和文字的先后位置与 Vue 不一致。",
    },
    "ExperimentRolloutConsole": {
        "primary": "hidden_reactive_dependency",
        "labels": ["hidden_reactive_dependency"],
        "issue_zh": "选择胜出版本后，表格行颜色不实时更新。",
    },
}


PRIMARY_LABELS_ZH = {
    "no_discrepancy_confirmed": "未发现差异",
    "hidden_reactive_dependency": "模板隐藏响应式依赖",
    "initialization_or_lifecycle": "初始化或生命周期迁移",
    "nested_state_mutation": "嵌套状态直接修改",
    "dom_child_order": "DOM 子节点顺序",
    "loop_scope_binding": "循环作用域绑定",
    "template_syntax": "模板语法错误",
}


MULTI_LABELS_ZH = {
    "no_discrepancy_confirmed": "未发现差异",
    "hidden_reactive_dependency": "模板隐藏响应式依赖",
    "initialization_or_lifecycle": "初始化或生命周期迁移",
    "nested_state_mutation": "嵌套状态直接修改",
    "event_conversion": "事件参数或修饰符转换",
    "watcher_mapping": "Watcher 映射",
    "dom_order_or_layout": "DOM 顺序或布局",
    "loop_binding_or_syntax": "循环绑定或模板语法",
    "repair_regression": "Repair 回归",
    "prop_default": "Prop 默认值",
    "timer_ownership": "定时器生命周期",
    "validator_false_negative": "Validator 假阴性",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_snapshot(snapshot: Path) -> int:
    checksum_file = snapshot / "SHA256SUMS.txt"
    checked = 0
    failures = []
    for line in checksum_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split("  ", 1)
        path = snapshot / relative
        if not path.is_file():
            failures.append(f"missing: {relative}")
        elif sha256(path).lower() != expected.lower():
            failures.append(f"hash mismatch: {relative}")
        checked += 1
    if failures:
        raise RuntimeError("Snapshot verification failed:\n" + "\n".join(failures))
    return checked


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def markdown_table(headers: list[str], rows: list[list[object]]) -> str:
    def clean(value: object) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    lines.extend("| " + " | ".join(clean(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def normalize_v1_result(sample: dict) -> str:
    if sample.get("status") == "error":
        return "execution_error"
    return "passed" if sample.get("final_passed") else "failed"


def collect_report_evidence(report: dict, keys: tuple[str, ...]) -> str:
    values = []
    for key in keys:
        value = report.get(key)
        if value in (None, "", [], {}):
            continue
        if isinstance(value, (dict, list)):
            rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
        else:
            rendered = str(value)
        values.append(f"{key}: {rendered}")
    return " | ".join(values)


def main() -> None:
    v1_checked = verify_snapshot(V1_SNAPSHOT)
    v2_checked = verify_snapshot(V2_SNAPSHOT)
    v1_manifest = read_json(V1_SNAPSHOT / "manifest.json")
    v1_summary = read_json(V1_SNAPSHOT / "formal_30_v1_summary.json")
    v2_manifest = read_json(V2_SNAPSHOT / "manifest.json")

    aggregate = v1_summary["aggregate"]
    v1_by_name = {item["component_name"]: item for item in v1_summary["samples"]}
    records = []
    for item in v2_manifest["samples"]:
        sample_id = item["sample_id"]
        if sample_id not in TAXONOMY:
            raise RuntimeError(f"Missing taxonomy entry: {sample_id}")
        v1_sample = v1_by_name[sample_id]
        report = read_json(V2_SNAPSHOT / item["report"])
        taxonomy = TAXONOMY[sample_id]
        code_modified = "/formal_30_v2/" in item["canonical_artifact"].replace("\\", "/")
        observed_evidence = collect_report_evidence(
            report, ("observed_issue", "follow_up_issue", "lock_issue")
        )
        root_cause_evidence = collect_report_evidence(
            report,
            ("root_cause", "follow_up_root_cause", "lock_root_cause"),
        )
        fix_evidence = collect_report_evidence(
            report, ("fix", "follow_up_fix", "lock_fix")
        )
        records.append(
            {
                "sample_id": sample_id,
                "complexity": item["complexity"],
                "v1_automatic_result": normalize_v1_result(v1_sample),
                "v1_stop_reason": v1_sample.get("stop_reason") or "execution_error",
                "v1_repair_rounds": v1_sample.get("repair_rounds") if v1_sample.get("repair_rounds") is not None else "",
                "v2_code_modified": code_modified,
                "primary_category": taxonomy["primary"],
                "primary_category_zh": PRIMARY_LABELS_ZH[taxonomy["primary"]],
                "multi_labels": ";".join(taxonomy["labels"]),
                "issue_zh": taxonomy["issue_zh"],
                "observed_issue_evidence": observed_evidence,
                "root_cause_evidence": root_cause_evidence,
                "fix_evidence": fix_evidence,
                "v1_final_validation_error_codes": ";".join(v1_sample.get("final_validation_error_codes") or []),
                "v1_final_visual_error_codes": ";".join(v1_sample.get("final_visual_error_codes") or []),
                "manual_result": item["manual_validation"],
                "canonical_artifact": item["canonical_artifact"],
                "snapshot_artifact": item["artifact"],
                "canonical_report": item["canonical_report"],
                "snapshot_report": item["report"],
                "artifact_sha256": item["artifact_sha256"],
                "baseline_sha256": item["baseline_sha256"],
                "report_status": report["status"],
            }
        )

    if len(records) != 14 or any(row["manual_result"] != "passed" for row in records):
        raise RuntimeError("Expected 14 manually passed v2 records")

    primary_counts = Counter(row["primary_category"] for row in records)
    multi_counts = Counter(
        label for row in records for label in row["multi_labels"].split(";")
    )
    modified_count = sum(bool(row["v2_code_modified"]) for row in records)
    v2_v1_result_counts = Counter(row["v1_automatic_result"] for row in records)
    auto_passed_with_manual_defect = [
        row["sample_id"]
        for row in records
        if row["v1_automatic_result"] == "passed" and row["v2_code_modified"]
    ]

    complexity_rows = []
    for name in ("simple", "medium", "complex"):
        item = aggregate["by_complexity"][name]
        complexity_rows.append(
            {
                "complexity": name,
                "configured": item["configured"],
                "completed": item["completed"],
                "passed": item["passed"],
                "failed": item["failed"],
                "execution_errors": item["execution_errors"],
                "pass_rate_completed": item["pass_rate_completed"],
                "pass_rate_configured": item["passed"] / item["configured"],
            }
        )

    summary = {
        "analysis_id": "formal_30_v1_v2_20261022",
        "generated_from_frozen_evidence_at": v2_manifest["created_at"],
        "sources": {
            "formal_30_v1_snapshot": v1_manifest["snapshot_id"],
            "formal_30_v2_snapshot": v2_manifest["snapshot_id"],
            "v1_verified_files": v1_checked,
            "v2_verified_files": v2_checked,
        },
        "interpretation": {
            "formal_30_v1": "Independent automatic migration baseline on 30 held-out samples.",
            "formal_30_v2": "Post-hoc manual browser diagnosis and targeted repair of 14 registered samples; not a new automatic 30-sample pass rate.",
        },
        "formal_30_v1": {
            "aggregate": aggregate,
            "pass_rate_all_configured": aggregate["passed"] / aggregate["configured"],
            "initial_pass_rate_all_configured": aggregate["initial_passed"] / aggregate["configured"],
            "complexity": complexity_rows,
        },
        "formal_30_v2": {
            "registered": len(records),
            "manual_passed": sum(row["manual_result"] == "passed" for row in records),
            "code_modified": modified_count,
            "unchanged_confirmed": len(records) - modified_count,
            "v1_result_distribution_in_review_set": dict(sorted(v2_v1_result_counts.items())),
            "auto_passed_but_manual_defect_found": auto_passed_with_manual_defect,
            "primary_category_counts": dict(sorted(primary_counts.items())),
            "multi_label_counts": dict(sorted(multi_counts.items())),
        },
        "claims_boundary": [
            "The unbiased automatic result is formal_30_v1: 16/30 configured samples passed.",
            "The 14/14 formal_30_v2 result describes manual rechecks after targeted intervention.",
            "It must not be reported as a 100% automatic migration success rate.",
            "Two v1 automatic passes had browser-visible defects in the reviewed set; this is evidence of evaluator blind spots, not an estimate for all automatic passes.",
        ],
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_csv(
        OUTPUT_DIR / "sample_results.csv",
        records,
        list(records[0].keys()),
    )
    taxonomy_rows = [
        {
            "category": key,
            "category_zh": PRIMARY_LABELS_ZH[key],
            "sample_count": value,
            "share_of_14": f"{value / len(records):.4f}",
        }
        for key, value in sorted(primary_counts.items(), key=lambda pair: (-pair[1], pair[0]))
    ]
    write_csv(
        OUTPUT_DIR / "primary_defect_taxonomy.csv",
        taxonomy_rows,
        ["category", "category_zh", "sample_count", "share_of_14"],
    )

    aggregate_table = markdown_table(
        ["Metric", "Value"],
        [
            ["Configured", aggregate["configured"]],
            ["Completed", aggregate["completed"]],
            ["Automatic passed", aggregate["passed"]],
            ["Automatic failed", aggregate["failed"]],
            ["Execution errors", aggregate["execution_errors"]],
            ["Pass rate among completed", percent(aggregate["pass_rate_completed"])],
            ["Pass rate among configured", percent(aggregate["passed"] / aggregate["configured"])],
            ["Initial passed", aggregate["initial_passed"]],
            ["Repaired to pass", aggregate["repaired_to_pass"]],
            ["Repair rounds total / average", f"{aggregate['repair_rounds_total']} / {aggregate['repair_rounds_average']}"],
            ["Generation / repair / total tokens", f"{aggregate['generation_tokens']:,} / {aggregate['repair_tokens']:,} / {aggregate['total_tokens']:,}"],
        ],
    )
    complexity_table = markdown_table(
        ["Complexity", "Configured", "Completed", "Passed", "Failed", "Errors", "Completed pass rate", "Configured pass rate"],
        [
            [
                row["complexity"],
                row["configured"],
                row["completed"],
                row["passed"],
                row["failed"],
                row["execution_errors"],
                percent(row["pass_rate_completed"]),
                percent(row["pass_rate_configured"]),
            ]
            for row in complexity_rows
        ],
    )
    sample_table = markdown_table(
        ["Sample", "Level", "v1 auto", "v2 changed", "Primary category", "Manual result", "Observed issue"],
        [
            [
                row["sample_id"],
                row["complexity"],
                row["v1_automatic_result"],
                "yes" if row["v2_code_modified"] else "no",
                row["primary_category_zh"],
                row["manual_result"],
                row["issue_zh"],
            ]
            for row in records
        ],
    )
    taxonomy_table = markdown_table(
        ["Primary category", "Samples", "Share of reviewed set"],
        [
            [row["category_zh"], row["sample_count"], percent(float(row["share_of_14"]))]
            for row in taxonomy_rows
        ],
    )
    report = f"""# formal_30_v1 and formal_30_v2 results analysis

## Evidence and reporting boundary

- v1 snapshot: `{v1_manifest['snapshot_id']}` ({v1_checked} verified files)
- v2 snapshot: `{v2_manifest['snapshot_id']}` ({v2_checked} verified files)
- `formal_30_v1` is the independent 30-sample automatic baseline.
- `formal_30_v2` is a post-hoc manual browser diagnosis and targeted-repair layer for 14 registered samples.
- The v2 14/14 manual result must not be described as a 100% automatic success rate on 30 samples.

## formal_30_v1 aggregate

{aggregate_table}

## Complexity breakdown

{complexity_table}

## formal_30_v2 manual review

- Registered and manually passed: 14/14
- Samples with a v2 code artifact: {modified_count}
- Samples confirmed without code modification: {len(records) - modified_count}
- v1 distribution inside the reviewed set: {dict(sorted(v2_v1_result_counts.items()))}
- v1 automatic passes with browser-visible defects: {', '.join(auto_passed_with_manual_defect)}

{sample_table}

## Primary defect taxonomy

Primary categories are mutually exclusive and support percentage reporting. The CSV sample table also retains non-exclusive multi-label categories for compound defects.

{taxonomy_table}

## Thesis-ready interpretation

1. The unbiased automatic baseline passed 16 of 30 configured samples (53.33%), or 16 of 29 normally completed samples (55.17%).
2. Difficulty had a strong effect: configured-sample pass rates were 90.00% for simple, 50.00% for medium, and 20.00% for complex components.
3. Repair converted 13 samples from initial failure to automatic pass, but the pipeline still left 13 completed failures and one execution error.
4. Manual browser review covered 14 targeted samples. Eleven required code changes and all 14 passed after recheck.
5. DeliveryPhaseCard and EnergyLoadScheduler had passed the v1 automatic evaluator but still contained browser-visible state-style defects. This demonstrates an evaluator blind spot; it does not establish a false-positive rate for all automatic passes because the manual subset was targeted rather than random.
6. The most frequent mutually exclusive categories in the reviewed set were hidden reactive dependencies and confirmed no-discrepancy cases (three samples each). Compound labels additionally expose lifecycle, event conversion, DOM order, nested mutation, timer, and validator issues.
7. Any Prompt, validator, or migration-rule changes derived from these 14 samples are post-hoc development work. A new untouched holdout is required for an unbiased estimate of the improved system.
"""
    (OUTPUT_DIR / "REPORT.md").write_text(report, encoding="utf-8")

    print(f"verified: v1={v1_checked} files, v2={v2_checked} files")
    print(f"output: {OUTPUT_DIR.relative_to(ROOT).as_posix()}")
    print(f"v1 automatic: {aggregate['passed']}/{aggregate['configured']} configured")
    print(f"v2 manual: {len(records)}/{len(records)} passed; {modified_count} modified")


if __name__ == "__main__":
    main()
