"""Build formal_30_v3 thesis-analysis artifacts without modifying raw results."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V1_SNAPSHOT = ROOT / "data/experiments/snapshots/formal_30_v1_results_20261015_161053"
V3_SUMMARY = ROOT / "data/experiments/batch_reports/formal_30_v3_summary.json"
V3_NOTES = ROOT / "data/experiments/batch_reports/formal_30_v3_execution_notes.json"
V3_PROTOCOL = ROOT / "data/experiments/protocols/formal_30_v3_frozen_20261022"
OUTPUT = ROOT / "data/experiments/analysis/formal_30_v3_20261022"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_checksums(root: Path) -> int:
    failures = []
    checked = 0
    for line in (root / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split("  ", 1)
        path = root / relative
        if not path.is_file():
            failures.append(f"missing: {relative}")
        elif digest(path).lower() != expected.lower():
            failures.append(f"hash mismatch: {relative}")
        checked += 1
    if failures:
        raise RuntimeError("Evidence verification failed:\n" + "\n".join(failures))
    return checked


def percent(numerator: int, denominator: int) -> str:
    return "n/a" if not denominator else f"{numerator / denominator * 100:.2f}%"


def main() -> None:
    v1_checked = verify_checksums(V1_SNAPSHOT)
    protocol_checked = verify_checksums(V3_PROTOCOL)
    v1 = json.loads((V1_SNAPSHOT / "formal_30_v1_summary.json").read_text(encoding="utf-8"))
    v3 = json.loads(V3_SUMMARY.read_text(encoding="utf-8"))
    notes = json.loads(V3_NOTES.read_text(encoding="utf-8"))
    a1 = v1["aggregate"]
    a3 = v3["aggregate"]

    if a3.get("configured") != 30 or a3.get("pending") != 0:
        raise RuntimeError("formal_30_v3 is not terminal")

    rows = []
    for sample in v3["samples"]:
        rows.append({
            "id": sample["id"],
            "component_name": sample["component_name"],
            "complexity": sample["complexity"],
            "status": sample["status"],
            "final_passed": sample.get("final_passed", ""),
            "stop_reason": sample.get("stop_reason", ""),
            "repair_rounds": sample.get("repair_rounds", ""),
            "initial_validation_errors": ";".join(sample.get("initial_validation_error_codes") or []),
            "initial_visual_errors": ";".join(sample.get("initial_visual_error_codes") or []),
            "final_validation_errors": ";".join(sample.get("final_validation_error_codes") or []),
            "final_visual_errors": ";".join(sample.get("final_visual_error_codes") or []),
            "structure_similarity": sample.get("final_structure_similarity", ""),
            "total_tokens": sample.get("total_tokens", ""),
            "error_type": sample.get("error_type", ""),
            "error_message": (sample.get("error_message") or "").strip(),
        })

    status_counts = Counter(row["status"] for row in rows)
    failed = [row for row in rows if row["status"] == "completed" and not row["final_passed"]]
    errors = [row for row in rows if row["status"] == "error"]
    comparison = {
        "configured_pass_rate_change_points": round(
            (a3["passed"] / a3["configured"] - a1["passed"] / a1["configured"]) * 100, 2
        ),
        "completed_pass_rate_change_points": round(
            (a3["passed"] / a3["completed"] - a1["passed"] / a1["completed"]) * 100, 2
        ),
        "token_change": a3["total_tokens"] - a1["total_tokens"],
        "token_change_percent": round((a3["total_tokens"] / a1["total_tokens"] - 1) * 100, 2),
        "warning": "v1 and v3 use different complexity-balanced samples; this is not a paired comparison.",
    }
    analysis = {
        "analysis_id": "formal_30_v3_20261022",
        "sources": {
            "v1_snapshot": V1_SNAPSHOT.name,
            "v1_verified_files": v1_checked,
            "v3_protocol": V3_PROTOCOL.name,
            "v3_protocol_verified_files": protocol_checked,
            "v3_summary_sha256": digest(V3_SUMMARY),
            "v3_execution_notes_sha256": digest(V3_NOTES),
        },
        "formal_30_v3": {
            "aggregate": a3,
            "pass_rate_all_configured": a3["passed"] / a3["configured"],
            "terminal_status_counts": dict(status_counts),
            "failed_completed_ids": [row["id"] for row in failed],
            "execution_error_ids": [row["id"] for row in errors],
            "execution_retry": notes,
        },
        "formal_30_v1_to_v3": comparison,
        "claims_boundary": [
            "formal_30_v3 is an untouched post-remediation holdout selected before its first model call.",
            "The configured-sample automatic pass rate is 18/30 (60.00%).",
            "The completed-sample automatic pass rate is 18/27 (66.67%).",
            "Three complex samples remain execution errors after one unchanged-command retry.",
            "The automatic evaluator does not establish browser interaction equivalence.",
            "Do not tune on v3 and continue to call it untouched; any remediation requires a new development version and another untouched holdout.",
        ],
    }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "summary.json").write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (OUTPUT / "sample_results.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    complexity_lines = []
    for level in ("simple", "medium", "complex"):
        item = a3["by_complexity"][level]
        complexity_lines.append(
            f"| {level} | {item['configured']} | {item['completed']} | {item['passed']} | "
            f"{item['failed']} | {item['execution_errors']} | "
            f"{percent(item['passed'], item['configured'])} | "
            f"{percent(item['passed'], item['completed'])} |"
        )

    failed_lines = "\n".join(
        f"| {row['id']} | {row['complexity']} | {row['stop_reason']} | "
        f"{row['final_validation_errors'] or '-'} | {row['final_visual_errors'] or '-'} |"
        for row in failed
    )
    error_lines = "\n".join(
        f"| {row['id']} | {row['complexity']} | {row['error_message'].replace('|', '/')} |"
        for row in errors
    )
    report = f"""# formal_30_v3 automatic results

## Evidence boundary

- `formal_30_v3` is a new post-remediation holdout selected from the prior `development_unseen` pool before any v3 model call.
- It has zero overlap with pilot 9 and formal_30_v1.
- The frozen protocol passed {protocol_checked} checksum checks after execution.
- The three generation timeouts were retried once with the unchanged checkpoint command and reproduced; no timeout, model, Prompt, or pipeline setting changed.
- Automatic pass does not imply browser interaction equivalence.

## Aggregate

| Metric | Result |
| --- | --- |
| Configured / completed | {a3['configured']} / {a3['completed']} |
| Passed / failed / execution errors | {a3['passed']} / {a3['failed']} / {a3['execution_errors']} |
| Pass rate among configured | {percent(a3['passed'], a3['configured'])} |
| Pass rate among completed | {percent(a3['passed'], a3['completed'])} |
| Initial passed / repaired to pass | {a3['initial_passed']} / {a3['repaired_to_pass']} |
| Repair rounds total / average | {a3['repair_rounds_total']} / {a3['repair_rounds_average']} |
| Generation / repair / total tokens | {a3['generation_tokens']:,} / {a3['repair_tokens']:,} / {a3['total_tokens']:,} |

## Complexity

| Complexity | Configured | Completed | Passed | Failed | Errors | Configured rate | Completed rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
{chr(10).join(complexity_lines)}

## Completed failures

| Sample | Complexity | Stop reason | Final validation errors | Final visual errors |
| --- | --- | --- | --- | --- |
{failed_lines}

## Execution errors

| Sample | Complexity | Error |
| --- | --- | --- |
{error_lines}

## Comparison with formal_30_v1

- Configured-sample pass rate: 53.33% in v1 and 60.00% in v3, a change of {comparison['configured_pass_rate_change_points']:+.2f} percentage points.
- Completed-sample pass rate: 55.17% in v1 and 66.67% in v3, a change of {comparison['completed_pass_rate_change_points']:+.2f} percentage points.
- Total model tokens: {a1['total_tokens']:,} in v1 and {a3['total_tokens']:,} in v3 ({comparison['token_change_percent']:+.2f}%).
- These are different complexity-balanced samples, so this is not a paired component-level comparison.
- Simple improved from 9/10 configured to 10/10; medium improved from 5/10 to 7/10; complex changed from 2/10 to 1/10 with three v3 generation timeouts.

## Interpretation

The generalized rules improved the overall configured and completed pass rates, but the gain is concentrated in simple and medium components. Complex migration remains the main limitation. The initial validator still reported `missing_prop_defaults` 25 times, and the final failures retain hidden reactive dependency, standalone `key` on `s-for`, state-access, DOM-structure, and critical-attribute errors. These v3 outcomes must now be treated as test evidence, not as another source for modifying the same claimed holdout.
"""
    (OUTPUT / "REPORT.md").write_text(report, encoding="utf-8")

    print(f"verified v1={v1_checked}, protocol={protocol_checked}")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
    print(f"formal_30_v3: {a3['passed']}/{a3['configured']} configured; {a3['passed']}/{a3['completed']} completed")


if __name__ == "__main__":
    main()
