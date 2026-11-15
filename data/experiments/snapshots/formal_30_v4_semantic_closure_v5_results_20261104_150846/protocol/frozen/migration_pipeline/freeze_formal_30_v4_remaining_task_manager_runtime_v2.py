"""Freeze the TaskManager v2 post-hoc runtime candidate before browser review."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_remaining_task_manager_runtime_v2_candidate_20261027_202500"
)
V1 = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_remaining_task_manager_bounded_candidate_20261027_200300"
)
CANDIDATE = ROOT / (
    "data/experiments/pipeline/manual_fixes/"
    "formal_30_v4_remaining_task_manager_runtime_v2/TaskManager_repaired.san"
)
REVIEW = ROOT / (
    "data/experiments/analysis/formal_30_v4_generalization_gap_audit_20261027/"
    "task_manager_remaining_v1_review.json"
)
V1_SHA256 = "06e1db96c365592fe13f8bd9e92376ae1384ccb3cdc091ffcf612acf3170ca8d"
CANDIDATE_SHA256 = "924c33e224776152e9533469e68c32f897a08581a62fee0cc5995ff89e0cbb22"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if TARGET.exists():
        raise FileExistsError(TARGET)
    if sha256(V1 / "candidate.san") != V1_SHA256 or sha256(CANDIDATE) != CANDIDATE_SHA256:
        raise RuntimeError("Frozen v1 source or v2 candidate hash mismatch")
    report_path = CANDIDATE.with_name("repair_report.json")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    review = json.loads(REVIEW.read_text(encoding="utf-8"))
    if (report["source_sha256"] != V1_SHA256
            or report["candidate_sha256"] != CANDIDATE_SHA256
            or review["posthoc_runtime_v2_candidate"]["sha256"] != CANDIDATE_SHA256):
        raise RuntimeError("Report/review candidate hash mismatch")
    if not all(report[key] is True for key in (
        "validation_passed", "san_compile_passed", "lightweight_visual_passed"
    )):
        raise RuntimeError("v2 checks are incomplete")
    files = {
        "v1_manual_rejected.san": V1 / "candidate.san",
        "source.vue": V1 / "source.vue",
        "candidate.san": CANDIDATE,
        "repair_report.json": report_path,
        "manual_failure.json": REVIEW.with_name("task_manager_bounded_v1_manual_fail.json"),
        "review.json": REVIEW,
        "replay_script.py": ROOT / "migration_pipeline/replay_formal_30_v4_remaining_task_manager_runtime_fix.py",
        "focused_tests.py": ROOT / "tests/test_task_manager_remaining_bounded_fix.py",
    }
    TARGET.mkdir(parents=True)
    for name, path in files.items():
        shutil.copy2(path, TARGET / name)
    manifest = {
        "snapshot_id": TARGET.name,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "classification": "reused_development_posthoc_runtime_repair_candidate",
        "independent_holdout": False,
        "sample_id": "TaskManager",
        "v1_manual_review": "failed",
        "v1_source_sha256": V1_SHA256,
        "candidate_sha256": CANDIDATE_SHA256,
        "static_compile_lightweight_visual_and_san_instance_checks": "passed",
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
