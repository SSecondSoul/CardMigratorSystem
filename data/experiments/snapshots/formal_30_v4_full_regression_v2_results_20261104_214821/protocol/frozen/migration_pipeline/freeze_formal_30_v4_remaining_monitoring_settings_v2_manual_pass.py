"""Freeze user-confirmed MonitoringDashboard v2 browser pass separately from the batch."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_remaining_monitoring_settings_v2_manual_pass_20261027_215100"
)
PRE = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_remaining_monitoring_settings_v2_candidate_20261027_213000"
)
REVIEW = ROOT / (
    "data/experiments/analysis/formal_30_v4_generalization_gap_audit_20261027/"
    "monitoring_remaining_v1_review.json"
)
MANUAL = REVIEW.with_name("monitoring_settings_v2_manual_pass.json")
SUMMARY = ROOT / (
    "data/experiments/batch_reports/"
    "formal_30_v4_generalization_remaining_v1_summary.json"
)
CANDIDATE_SHA256 = "6847de423b95ef768f8c7705ba935445bc8d26a03fa6bddf1f5cc8e1b656d7c1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if TARGET.exists():
        raise FileExistsError(TARGET)
    candidate = PRE / "candidate.san"
    if sha256(candidate) != CANDIDATE_SHA256:
        raise RuntimeError("Pre-review candidate SHA-256 mismatch")
    manual = json.loads(MANUAL.read_text(encoding="utf-8"))
    review = json.loads(REVIEW.read_text(encoding="utf-8"))
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    if (manual["candidate_sha256"] != CANDIDATE_SHA256
            or manual["manual_result"] != "passed_by_user"
            or review["posthoc_settings_v2_candidate"]["sha256"] != CANDIDATE_SHA256):
        raise RuntimeError("Manual report or review does not match the candidate")
    result = next(sample for sample in summary["samples"] if sample["id"] == "MonitoringDashboard")
    if result["final_passed"] is not False:
        raise RuntimeError("Automatic MonitoringDashboard result must remain failed")
    files = {
        "candidate.san": candidate,
        "source.vue": PRE / "source.vue",
        "repair_report.json": PRE / "repair_report.json",
        "v2_manual_pass.json": MANUAL,
        "review.json": REVIEW,
        "batch_summary_at_manual_pass.json": SUMMARY,
        "v1_replay_script.py": ROOT / "migration_pipeline/replay_formal_30_v4_remaining_monitoring_syntax_fix.py",
        "v2_replay_script.py": ROOT / "migration_pipeline/replay_formal_30_v4_remaining_monitoring_settings_fix.py",
        "focused_tests.py": ROOT / "tests/test_monitoring_remaining_bounded_fix.py",
        "manual_vue_runner.html": ROOT / "tests/manual/vue-test-runner.html",
        "manual_san_runner.html": ROOT / "tests/manual/san-test-runner.html",
    }
    TARGET.mkdir(parents=True)
    for name, path in files.items():
        shutil.copy2(path, TARGET / name)
    manifest = {
        "snapshot_id": TARGET.name,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "classification": "reused_development_posthoc_manual_pass",
        "independent_holdout": False,
        "sample_id": "MonitoringDashboard",
        "candidate_sha256": CANDIDATE_SHA256,
        "browser_review": "passed_by_user",
        "per_scenario_browser_log": "not_supplied",
        "automatic_batch_status": "failed; preserved in copied summary",
        "original_paths": {name: path.relative_to(ROOT).as_posix() for name, path in files.items()},
        "integrity_file": "SHA256SUMS.txt",
    }
    (TARGET / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
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
