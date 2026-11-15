"""Freeze the user-confirmed AnalyticsDashboard chart-geometry repair evidence."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_analytics_chart_reactivity_v3_manual_geometry_pass_20261027_164258"
)
SOURCE = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_analytics_computed_focus_probe_v2_static_pass_20261027_152434/"
    "candidate.san"
)
CANDIDATE = ROOT / (
    "data/experiments/pipeline/manual_fixes/"
    "formal_30_v4_analytics_chart_reactivity_v3/AnalyticsDashboard_repaired.san"
)
REPORT = CANDIDATE.with_name("repair_report.json")
REVIEW = ROOT / (
    "data/experiments/analysis/formal_30_v4_generalization_gap_audit_20261027/"
    "analytics_chart_reactivity_v3_review.json"
)
V2_REVIEW = REVIEW.with_name("analytics_computed_focus_v2_review.json")
SOURCE_SHA256 = "c0503283250a6467d7a6cb4e8a03caae057197ed9d5b11d82d316994d0d6c647"
CANDIDATE_SHA256 = "4fa173dba666dfe743fdd71fa776b890bb213cd3475146821bde1fbce78080f1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if TARGET.exists():
        raise FileExistsError(f"Snapshot already exists: {TARGET}")
    if sha256(SOURCE) != SOURCE_SHA256 or sha256(CANDIDATE) != CANDIDATE_SHA256:
        raise RuntimeError("Source or repaired candidate differs from reviewed SHA-256")

    report = json.loads(REPORT.read_text(encoding="utf-8"))
    review = json.loads(REVIEW.read_text(encoding="utf-8"))
    v2_review = json.loads(V2_REVIEW.read_text(encoding="utf-8"))
    if report["source_sha256"] != SOURCE_SHA256 or report["candidate_sha256"] != CANDIDATE_SHA256:
        raise RuntimeError("Repair report does not identify these exact files")
    if review["candidate_sha256"] != CANDIDATE_SHA256:
        raise RuntimeError("Manual review does not identify this exact candidate")
    if review["browser_runtime"]["status"] != "user_reported_pass":
        raise RuntimeError("User manual geometry pass is not recorded")
    if "failed_by_user_manual_observation" not in v2_review["browser_runtime_scenario"]:
        raise RuntimeError("The preceding v2 runtime failure is not recorded")
    if not all(report.get(key) is True for key in (
        "validation_passed", "ssm_aware_validation_passed", "san_compile_passed",
        "lightweight_visual_eval_passed",
    )):
        raise RuntimeError("Static or lightweight visual checks are incomplete")

    candidate_code = CANDIDATE.read_text(encoding="utf-8")
    for expression in (
        "getX(idx, data.length)",
        "getY(point.value, maxValue, minValue)",
        "getXForChart(index, dataLength)",
        "getYForChart(value, maxValue, minValue)",
    ):
        if expression not in candidate_code:
            raise RuntimeError(f"Missing explicit chart dependency: {expression}")

    files = {
        "v2_candidate.san": SOURCE,
        "v3_candidate.san": CANDIDATE,
        "v3_repair_report.json": REPORT,
        "v3_manual_review.json": REVIEW,
        "v2_failure_review.json": V2_REVIEW,
        "chart_reactivity_replay.py": ROOT / "migration_pipeline/replay_formal_30_v4_analytics_chart_reactivity_fix.py",
        "validator.py": ROOT / "migration_pipeline/stages/validate.py",
        "repair_prompt.py": ROOT / "migration_pipeline/utils/repair_prompt.py",
        "validator_regression_tests.py": ROOT / "tests/test_migration_pipeline_regressions.py",
        "chart_regression_tests.py": ROOT / "tests/test_analytics_chart_reactivity_fix.py",
        "geometry_probe.cjs": ROOT / "tests/diagnostics/analytics_chart_period_probe.cjs",
        "manual_san_runner.html": ROOT / "tests/manual/san-test-runner.html",
        "browser_scenario.json": ROOT / "migration_pipeline/interaction_configs/formal_30_v4_runtime_acceptance.json",
        "browser_scenario.js": ROOT / "tests/manual/formal-30-v4-runtime-acceptance.js",
    }
    TARGET.mkdir(parents=True)
    for name, source in files.items():
        shutil.copy2(source, TARGET / name)
    manifest = {
        "snapshot_id": TARGET.name,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "classification": "reused_development_regression_manual_repair",
        "independent_holdout": False,
        "sample_id": "analytics_dashboard",
        "v2_browser_geometry_result": "user_reported_fail",
        "v3_browser_geometry_result": "user_reported_pass_7d_and_90d",
        "automated_browser_scenario": "not_run",
        "vue_period_switch_review": "not_checked",
        "full_vue_san_parity": "not_established",
        "candidate_sha256": CANDIDATE_SHA256,
        "original_paths": {name: path.relative_to(ROOT).as_posix() for name, path in files.items()},
        "integrity_file": "SHA256SUMS.txt",
    }
    (TARGET / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    payloads = sorted(path for path in TARGET.iterdir() if path.is_file())
    (TARGET / "SHA256SUMS.txt").write_text(
        "\n".join(f"{sha256(path)}  {path.name}" for path in payloads) + "\n",
        encoding="utf-8",
    )
    for line in (TARGET / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        expected, name = line.split("  ", 1)
        if sha256(TARGET / name) != expected:
            raise RuntimeError(f"Snapshot checksum mismatch: {name}")
    print(f"frozen: {TARGET.relative_to(ROOT)} ({len(payloads)} verified payloads)")


if __name__ == "__main__":
    main()
