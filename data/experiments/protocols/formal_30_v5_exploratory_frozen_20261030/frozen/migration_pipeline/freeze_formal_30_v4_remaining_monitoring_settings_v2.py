"""Freeze the MonitoringDashboard post-hoc settings candidate before manual review."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_remaining_monitoring_settings_v2_candidate_20261027_213000"
)
FAILED = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_generalization_remaining_v1_monitoring_failed_20261027_205900"
)
V1 = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_remaining_monitoring_syntax_v1_candidate_20261027_211600"
)
CANDIDATE = ROOT / (
    "data/experiments/pipeline/manual_fixes/"
    "formal_30_v4_remaining_monitoring_settings_v2/MonitoringDashboard_repaired.san"
)
REVIEW = ROOT / (
    "data/experiments/analysis/formal_30_v4_generalization_gap_audit_20261027/"
    "monitoring_remaining_v1_review.json"
)
SOURCE_SHA256 = "6a9da9e71e8a0695583d5097dd86425dbe5130b77428075ba57ea1e0138c889c"
CANDIDATE_SHA256 = "6847de423b95ef768f8c7705ba935445bc8d26a03fa6bddf1f5cc8e1b656d7c1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if TARGET.exists():
        raise FileExistsError(TARGET)
    source = V1 / "candidate.san"
    if sha256(source) != SOURCE_SHA256 or sha256(CANDIDATE) != CANDIDATE_SHA256:
        raise RuntimeError("Frozen source or candidate SHA-256 mismatch")
    report_path = CANDIDATE.with_name("repair_report.json")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    review = json.loads(REVIEW.read_text(encoding="utf-8"))
    if (report["source_sha256"] != SOURCE_SHA256
            or report["candidate_sha256"] != CANDIDATE_SHA256
            or review["posthoc_settings_v2_candidate"]["sha256"] != CANDIDATE_SHA256):
        raise RuntimeError("Report or review does not match candidate")
    if not all(report[key] is True for key in (
        "validation_passed", "san_compile_passed", "lightweight_visual_passed"
    )):
        raise RuntimeError("Candidate checks are incomplete")
    files = {
        "failed_automatic_output.san": FAILED / "MonitoringDashboard_repaired_repaired_repaired.san",
        "v1_candidate.san": source,
        "source.vue": FAILED / "source.vue",
        "candidate.san": CANDIDATE,
        "repair_report.json": report_path,
        "review.json": REVIEW,
        "v1_replay_script.py": ROOT / "migration_pipeline/replay_formal_30_v4_remaining_monitoring_syntax_fix.py",
        "v2_replay_script.py": ROOT / "migration_pipeline/replay_formal_30_v4_remaining_monitoring_settings_fix.py",
        "focused_tests.py": ROOT / "tests/test_monitoring_remaining_bounded_fix.py",
    }
    TARGET.mkdir(parents=True)
    for name, path in files.items():
        shutil.copy2(path, TARGET / name)
    manifest = {
        "snapshot_id": TARGET.name,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "classification": "reused_development_posthoc_settings_candidate",
        "independent_holdout": False,
        "sample_id": "MonitoringDashboard",
        "v1_sha256": SOURCE_SHA256,
        "candidate_sha256": CANDIDATE_SHA256,
        "static_compile_lightweight_visual": "passed",
        "unit_tests": "149/149 passed",
        "browser_review": "pending_user_review",
        "batch_result_not_overwritten": True,
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
