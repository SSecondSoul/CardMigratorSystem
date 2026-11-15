"""Rebuild the v4 development-regression closeout from frozen evidence."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "data/experiments/analysis/formal_30_v4_development_closeout_20261025"
TARGETED = ROOT / "data/experiments/batch_reports/formal_30_v4_targeted_summary.json"
DEFERRED = ROOT / "data/experiments/batch_reports/formal_30_v4_deferred_regression_summary.json"
REMEDIATION = ROOT / "data/experiments/analysis/formal_30_v4_planning_20261022/remediation_log.json"
DEFERRED_NOTEBOOK = ROOT / "notebooks/02-migration-experiments/2026-10-23_formal_30_v4_deferred_regression.ipynb"
TARGETED_SNAPSHOT = "formal_30_v4_targeted_final_20261023_152047"
ANALYTICS_FOLLOWUP_SNAPSHOT = "formal_30_v4_analytics_manual_followup_automatic_pass_20261026_152546"
ANALYTICS_FOLLOWUP_SUMMARY = ROOT / "data/experiments/batch_reports/formal_30_v4_analytics_manual_followup_summary.json"
ANALYTICS_RUNTIME_SNAPSHOT = "formal_30_v4_analytics_runtime_followup_automatic_pass_20261026_160213"
ANALYTICS_RUNTIME_SUMMARY = ROOT / "data/experiments/batch_reports/formal_30_v4_analytics_runtime_followup_summary.json"
TASK_MANAGER_TIMEOUT_SNAPSHOT = "formal_30_v4_task_manager_manual_followup_generation_timeout_20261026_201844"
TASK_MANAGER_FOLLOWUP_FAILED_SNAPSHOT = "formal_30_v4_task_manager_manual_followup_failed_20261026_203625"

# Order and attempt counts are transcribed from the deferred experiment notebook.
# The last tuple member is the canonical, audit-confirmed passing snapshot.
DEFERRED_EVIDENCE = {
    "access_matrix": (1, 0, "formal_30_v4_deferred_access_matrix_pass_20261023_155031"),
    "localization_workspace": (2, 0, "formal_30_v4_deferred_localization_workspace_pass_20261023_163149"),
    "trip_itinerary_planner": (1, 0, "formal_30_v4_deferred_trip_itinerary_planner_pass_20261023_165740"),
    "TaskManager": (4, 0, "formal_30_v4_deferred_task_manager_pass_20261023_190805"),
    "MonitoringDashboard": (8, 1, "formal_30_v4_deferred_monitoring_dashboard_pass_20261025_124927"),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_snapshot(name: str) -> int:
    root = ROOT / "data/experiments/snapshots" / name
    checksums = root / "SHA256SUMS.txt"
    count = 0
    for line in checksums.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split("  ", 1)
        path = root / relative
        if not path.is_file() or sha256(path).lower() != expected.lower():
            raise RuntimeError(f"Snapshot checksum mismatch: {name}/{relative}")
        count += 1
    if not count:
        raise RuntimeError(f"Empty snapshot checksum file: {name}")
    return count


def targeted_evidence(entry: dict) -> tuple[int, str]:
    runs = [
        value for key, value in entry.items()
        if ("run" in key) and isinstance(value, dict) and value.get("snapshot")
    ]
    if not runs or not runs[-1].get("final_passed"):
        raise RuntimeError(f"No passing final targeted run: {entry['sample_id']}")
    return len(runs), Path(runs[-1]["snapshot"]).name


def main() -> None:
    targeted = read_json(TARGETED)
    deferred = read_json(DEFERRED)
    remediation = read_json(REMEDIATION)
    by_id = {entry["sample_id"]: entry for entry in remediation["entries"]}
    batches = ((targeted, "targeted"), (deferred, "deferred"))
    rows = []
    checks = {TARGETED_SNAPSHOT: verify_snapshot(TARGETED_SNAPSHOT)}

    for batch, group in batches:
        aggregate = batch["aggregate"]
        if (aggregate["configured"], aggregate["completed"], aggregate["passed"],
                aggregate["failed"], aggregate["execution_errors"], aggregate["pending"]) != (
                    len(batch["samples"]), len(batch["samples"]), len(batch["samples"]), 0, 0, 0
                ):
            raise RuntimeError(f"Batch is not fully passed: {batch['batch_id']}")
        for sample in batch["samples"]:
            sample_id = sample["id"]
            if sample["status"] != "completed" or sample["final_passed"] is not True:
                raise RuntimeError(f"Not passed: {sample_id}")
            if sample["final_validation_error_codes"] or sample["final_visual_error_codes"]:
                raise RuntimeError(f"Final errors present: {sample_id}")
            if group == "targeted":
                attempts, snapshot = targeted_evidence(by_id[sample_id])
                timeouts = 0
            else:
                attempts, timeouts, snapshot = DEFERRED_EVIDENCE[sample_id]
            checks[snapshot] = verify_snapshot(snapshot)
            manifest = read_json(ROOT / "data/experiments/snapshots" / snapshot / "manifest.json")
            if manifest.get("sample_id") not in (None, sample_id):
                raise RuntimeError(f"Snapshot sample mismatch: {snapshot}")
            rows.append({
                "batch_id": batch["batch_id"],
                "sample_id": sample_id,
                "component_name": sample["component_name"],
                "complexity": sample["complexity"],
                "final_passed": sample["final_passed"],
                "final_repair_rounds": sample["repair_rounds"],
                "recorded_completed_attempts": attempts,
                "recorded_generation_timeouts": timeouts,
                "final_generation_tokens": sample["generation_tokens"],
                "final_repair_tokens": sample["repair_tokens"],
                "final_total_tokens": sample["total_tokens"],
                "final_structure_similarity": sample["final_structure_similarity"],
                "final_tag_sequence_similarity": sample["final_tag_sequence_similarity"],
                "final_text_similarity": sample["final_text_similarity"],
                "final_tree_edit_distance": sample["final_tree_edit_distance"],
                "interaction_eval_passed": sample["interaction_eval_passed"],
                "canonical_snapshot": f"data/experiments/snapshots/{snapshot}",
            })

    if len(rows) != 12 or len({row["sample_id"] for row in rows}) != 12:
        raise RuntimeError("Expected 12 distinct development cases")
    totals = {
        "configured": 12,
        "completed": 12,
        "automatic_passed": 12,
        "terminal_repair_rounds": sum(row["final_repair_rounds"] for row in rows),
        "recorded_completed_attempts": sum(row["recorded_completed_attempts"] for row in rows),
        "recorded_generation_timeouts": sum(row["recorded_generation_timeouts"] for row in rows),
        "terminal_generation_tokens": sum(row["final_generation_tokens"] for row in rows),
        "terminal_repair_tokens": sum(row["final_repair_tokens"] for row in rows),
        "terminal_total_tokens": sum(row["final_total_tokens"] for row in rows),
        "interaction_evaluated": sum(row["interaction_eval_passed"] is not None for row in rows),
    }
    for key in ("generation_tokens", "repair_tokens", "total_tokens", "repair_rounds_total"):
        expected = sum(batch["aggregate"][key] for batch, _ in batches)
        actual = totals["terminal_repair_rounds" if key == "repair_rounds_total" else "terminal_" + key]
        if actual != expected:
            raise RuntimeError(f"Aggregate mismatch: {key}: {actual} != {expected}")

    ANALYSIS.mkdir(parents=True, exist_ok=True)
    with (ANALYSIS / "sample_results.csv").open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    result = {
        "analysis_id": ANALYSIS.name,
        "classification": "development_internal_regression",
        "independent_holdout": False,
        "sources": {
            "targeted_summary": str(TARGETED.relative_to(ROOT)).replace("\\", "/"),
            "targeted_summary_sha256": sha256(TARGETED),
            "deferred_summary": str(DEFERRED.relative_to(ROOT)).replace("\\", "/"),
            "deferred_summary_sha256": sha256(DEFERRED),
            "targeted_remediation_log": str(REMEDIATION.relative_to(ROOT)).replace("\\", "/"),
            "targeted_remediation_log_sha256": sha256(REMEDIATION),
            "deferred_notebook": str(DEFERRED_NOTEBOOK.relative_to(ROOT)).replace("\\", "/"),
            "deferred_notebook_sha256": sha256(DEFERRED_NOTEBOOK),
        },
        "verified_snapshot_payload_counts": checks,
        "batches": {batch["batch_id"]: batch["aggregate"] for batch, _ in batches},
        "totals": totals,
        "interpretation": [
            "All 12 cases are reused development failures/timeouts from formal_30_v3, not untouched holdout cases.",
            "Terminal token counts sum only the final checkpoint per sample; they exclude prior failed and superseded reruns.",
            "Automatic static/visual pass does not establish interaction parity; all 12 interaction_eval_passed fields are null.",
            "Recorded completed attempt counts are traced to the targeted remediation log and deferred notebook; one MonitoringDashboard generation timeout is separate.",
        ],
    }
    manual_log = ANALYSIS / "manual_validation.json"
    if manual_log.is_file():
        manual = read_json(manual_log)
        recorded = {(item["sample_id"], item["result"]) for item in manual["results"]}
        required = {
            ("analytics_dashboard", "user_reported_runtime_error_original_automatic_pass_rejected"),
            ("analytics_dashboard", "user_reported_runtime_error_followup_automatic_pass_rejected"),
            ("analytics_dashboard", "user_reported_loading_overlay_stuck_runtime_followup_rejected"),
            ("rule_builder", "user_reported_fail"),
            ("rule_builder", "user_reported_pass_after_repair"),
            ("TaskManager", "user_reported_browser_load_error_frozen_automatic_pass_rejected"),
            ("TaskManager", "user_reported_pass_after_settings_and_tag_repair"),
            ("MonitoringDashboard", "user_reported_settings_kpi_log_display_failure"),
            ("MonitoringDashboard", "user_reported_san_pass_after_settings_kpi_log_repair"),
        }
        if not required <= recorded:
            raise RuntimeError("Manual audit overlay is incomplete")
        result["posthoc_manual_audit"] = {
            "source": str(manual_log.relative_to(ROOT)).replace("\\", "/"),
            "source_sha256": sha256(manual_log),
            "analytics_dashboard_frozen_result": "rejected_browser_runtime_error",
            "TaskManager_frozen_result": "rejected_browser_load_error",
            "rule_builder_frozen_result": "rejected_style_difference",
            "rule_builder_separate_candidate": "user_reported_pass",
            "warning": "Raw 12/12 automatic checkpoint is historical and must not be presented as 12 runtime-usable samples.",
        }
        timeout_root = ROOT / "data/experiments/snapshots" / TASK_MANAGER_TIMEOUT_SNAPSHOT
        if timeout_root.is_dir():
            checks[TASK_MANAGER_TIMEOUT_SNAPSHOT] = verify_snapshot(TASK_MANAGER_TIMEOUT_SNAPSHOT)
            result["posthoc_manual_audit"]["TaskManager_followup_timeout_snapshot"] = TASK_MANAGER_TIMEOUT_SNAPSHOT
        failed_root = ROOT / "data/experiments/snapshots" / TASK_MANAGER_FOLLOWUP_FAILED_SNAPSHOT
        if failed_root.is_dir():
            checks[TASK_MANAGER_FOLLOWUP_FAILED_SNAPSHOT] = verify_snapshot(TASK_MANAGER_FOLLOWUP_FAILED_SNAPSHOT)
            result["posthoc_manual_audit"]["TaskManager_followup_failed_snapshot"] = TASK_MANAGER_FOLLOWUP_FAILED_SNAPSHOT
            result["posthoc_manual_audit"]["TaskManager_computed_candidate"] = {
                "source": "data/experiments/repair_reports/manual_fixes/formal_30_v4_task_manager_computed_context.json",
                "static_and_initial_visual_replay": "passed",
                "user_manual_browser_status": "failed_san_template_parse",
                "excluded_from_original_12_case_checkpoint": True,
            }
            result["posthoc_manual_audit"]["TaskManager_template_syntax_candidate"] = {
                "source": "data/experiments/repair_reports/manual_fixes/formal_30_v4_task_manager_template_syntax.json",
                "static_initial_visual_and_san_parser_replay": "passed",
                "user_manual_browser_status": "failed_missing_inline_display_values",
                "excluded_from_original_12_case_checkpoint": True,
            }
            result["posthoc_manual_audit"]["TaskManager_inline_format_candidate"] = {
                "source": "data/experiments/repair_reports/manual_fixes/formal_30_v4_task_manager_inline_format_methods.json",
                "static_initial_visual_and_san_parser_replay": "passed",
                "user_manual_browser_status": "failed_task_form_modal_content_mismatch",
                "excluded_from_original_12_case_checkpoint": True,
            }
            result["posthoc_manual_audit"]["TaskManager_form_initialization_candidate"] = {
                "source": "data/experiments/repair_reports/manual_fixes/formal_30_v4_task_manager_form_initialization.json",
                "static_initial_visual_and_san_parser_replay": "passed",
                "user_manual_browser_status": "failed_settings_controls_and_task_tag_selected_style",
                "excluded_from_original_12_case_checkpoint": True,
            }
            result["posthoc_manual_audit"]["TaskManager_settings_tags_candidate"] = {
                "source": "data/experiments/repair_reports/manual_fixes/formal_30_v4_task_manager_settings_tags.json",
                "static_initial_visual_and_san_parser_replay": "passed",
                "user_manual_browser_status": "user_reported_pass_2026-10-26",
                "excluded_from_original_12_case_checkpoint": True,
            }
            result["posthoc_manual_audit"]["MonitoringDashboard_frozen_result"] = {
                "source": "data/experiments/analysis/formal_30_v4_development_closeout_20261025/monitoring_dashboard_manual_audit.json",
                "user_manual_browser_status": "rejected_settings_kpi_log_display_failure",
                "excluded_from_original_12_case_checkpoint": False,
            }
            result["posthoc_manual_audit"]["MonitoringDashboard_manual_candidate"] = {
                "source": "data/experiments/repair_reports/manual_fixes/formal_30_v4_monitoring_settings_kpi_logs.json",
                "static_initial_visual_and_san_parser_replay": "passed",
                "user_manual_browser_status": "user_reported_san_pass_2026-10-26",
                "vue_san_chart_parity": "not_established_vue_manual_runner_renders_one_chart",
                "excluded_from_original_12_case_checkpoint": True,
            }
    if ANALYTICS_FOLLOWUP_SUMMARY.is_file():
        followup = read_json(ANALYTICS_FOLLOWUP_SUMMARY)
        if followup["aggregate"]["passed"] != 1 or followup["samples"][0]["id"] != "analytics_dashboard":
            raise RuntimeError("Analytics follow-up is not a single passing development result")
        checks[ANALYTICS_FOLLOWUP_SNAPSHOT] = verify_snapshot(ANALYTICS_FOLLOWUP_SNAPSHOT)
        result["sources"]["analytics_followup_summary"] = str(ANALYTICS_FOLLOWUP_SUMMARY.relative_to(ROOT)).replace("\\", "/")
        result["sources"]["analytics_followup_summary_sha256"] = sha256(ANALYTICS_FOLLOWUP_SUMMARY)
        result.setdefault("posthoc_manual_audit", {})["analytics_followup"] = {
            "automatic_passed": True,
            "frozen_snapshot": ANALYTICS_FOLLOWUP_SNAPSHOT,
            "manual_browser_status": "failed_this_data_map_runtime_error",
            "excluded_from_original_12_case_checkpoint": True,
        }
    if ANALYTICS_RUNTIME_SUMMARY.is_file():
        runtime = read_json(ANALYTICS_RUNTIME_SUMMARY)
        if runtime["aggregate"]["passed"] != 1 or runtime["samples"][0]["id"] != "analytics_dashboard":
            raise RuntimeError("Analytics runtime follow-up is not a single passing development result")
        checks[ANALYTICS_RUNTIME_SNAPSHOT] = verify_snapshot(ANALYTICS_RUNTIME_SNAPSHOT)
        result["sources"]["analytics_runtime_summary"] = str(ANALYTICS_RUNTIME_SUMMARY.relative_to(ROOT)).replace("\\", "/")
        result["sources"]["analytics_runtime_summary_sha256"] = sha256(ANALYTICS_RUNTIME_SUMMARY)
        result.setdefault("posthoc_manual_audit", {})["analytics_runtime_followup"] = {
            "automatic_passed": True,
            "frozen_snapshot": ANALYTICS_RUNTIME_SNAPSHOT,
            "manual_browser_status": "failed_loading_overlay_stuck",
            "excluded_from_original_12_case_checkpoint": True,
        }
        result["posthoc_manual_audit"]["analytics_visual_bindings_candidate"] = {
            "source": "data/experiments/repair_reports/manual_fixes/formal_30_v4_analytics_visual_bindings.json",
            "local_browser_replay": "passed",
            "user_manual_browser_status": "user_reported_pass",
            "excluded_from_original_12_case_checkpoint": True,
        }
    (ANALYSIS / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"verified {len(checks)} snapshots; wrote {len(rows)} rows to {ANALYSIS}")


if __name__ == "__main__":
    main()
