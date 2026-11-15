"""Freeze the post-hoc inline-class candidate before browser review."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_analytics_inline_class_posthoc_candidate_20261027_173453"
)
SOURCE = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_analytics_chart_reactivity_regression_v1_automatic_pass_20261027_172556/"
    "AnalyticsDashboard_repaired_repaired_repaired.san"
)
CANDIDATE = ROOT / (
    "data/experiments/pipeline/manual_fixes/"
    "formal_30_v4_analytics_auto_regression_inline_class_v1/AnalyticsDashboard_repaired.san"
)
REPORT = CANDIDATE.with_name("repair_report.json")
REVIEW = ROOT / (
    "data/experiments/analysis/formal_30_v4_generalization_gap_audit_20261027/"
    "analytics_chart_reactivity_regression_v1_review.json"
)
SOURCE_SHA256 = "426943b3f79e69480b259b18bc78584b794a9d1d6081c0fd2ba9c91638908fa7"
CANDIDATE_SHA256 = "1b2c8143e95f6eadbbdd3740bd864879a0d4742c28a08001667a0ae6cfb5bcb0"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if TARGET.exists():
        raise FileExistsError(TARGET)
    if sha256(SOURCE) != SOURCE_SHA256 or sha256(CANDIDATE) != CANDIDATE_SHA256:
        raise RuntimeError("Frozen source or candidate hash mismatch")
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    review = json.loads(REVIEW.read_text(encoding="utf-8"))
    if report["source_sha256"] != SOURCE_SHA256 or report["candidate_sha256"] != CANDIDATE_SHA256:
        raise RuntimeError("Repair report hash mismatch")
    if review["posthoc_candidate_sha256"] != CANDIDATE_SHA256:
        raise RuntimeError("Review candidate hash mismatch")
    if not all(report.get(key) is True for key in (
        "after_validation_passed", "after_san_compile_passed", "after_lightweight_visual_passed"
    )):
        raise RuntimeError("Post-hoc checks are incomplete")
    files = {
        "automatic_output.san": SOURCE,
        "candidate.san": CANDIDATE,
        "repair_report.json": REPORT,
        "review.json": REVIEW,
        "replay_script.py": ROOT / "migration_pipeline/replay_formal_30_v4_analytics_inline_class_fix.py",
        "validator.py": ROOT / "migration_pipeline/stages/validate.py",
        "repair_stage.py": ROOT / "migration_pipeline/stages/repair.py",
        "validator_tests.py": ROOT / "tests/test_migration_pipeline_regressions.py",
        "repair_tests.py": ROOT / "tests/test_repair_prompt_and_loop.py",
        "manual_san_runner.html": ROOT / "tests/manual/san-test-runner.html",
        "runtime_acceptance.json": ROOT / "migration_pipeline/interaction_configs/formal_30_v4_runtime_acceptance.json",
        "runtime_acceptance.js": ROOT / "tests/manual/formal-30-v4-runtime-acceptance.js",
    }
    TARGET.mkdir(parents=True)
    for name, path in files.items():
        shutil.copy2(path, TARGET / name)
    manifest = {
        "snapshot_id": TARGET.name,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "classification": "reused_development_posthoc_deterministic_replay_candidate",
        "independent_holdout": False,
        "sample_id": "analytics_dashboard",
        "frozen_automatic_source_sha256": SOURCE_SHA256,
        "candidate_sha256": CANDIDATE_SHA256,
        "validation_compile_lightweight_visual": "passed",
        "browser_review": "pending_user_review",
        "batch_result_not_overwritten": True,
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
