"""Freeze the user's browser acceptance of the source-event replay candidate."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_task_manager_source_events_candidate_20261029_214742"
)
AUTOMATIC = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_task_manager_five_residual_regression_v1_TaskManager_automatic_pass_20261029_200650"
)
EXPECTED_SHA256 = "f7e8eef6f66a2a46d6443548550f20207817ce8d75d1828118f36e6bb431c39f"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(directory: Path) -> None:
    for line in (directory / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        if sha256(directory / relative) != expected:
            raise RuntimeError(f"Frozen payload changed: {directory / relative}")


def main() -> None:
    verify(CANDIDATE)
    verify(AUTOMATIC)
    candidate = CANDIDATE / "candidate.san"
    if sha256(candidate) != EXPECTED_SHA256:
        raise RuntimeError("Candidate hash does not match user-reviewed artifact")
    automatic_manifest = json.loads((AUTOMATIC / "manifest.json").read_text(encoding="utf-8"))
    if automatic_manifest.get("browser_runtime_review") != "not_performed_for_this_automatic_output":
        raise RuntimeError("Unexpected automatic snapshot review status")
    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    target = ROOT / "data/experiments/snapshots" / f"formal_30_v4_task_manager_source_events_manual_pass_{stamp}"
    target.mkdir(parents=True, exist_ok=False)
    files = {
        "candidate.san": candidate,
        "source.vue": AUTOMATIC / "source.vue",
        "offline_replay_report.json": CANDIDATE / "replay_report.json",
        "manual_san_runner.html": ROOT / "tests/manual/san-test-runner.html",
        "manual_vue_runner.html": ROOT / "tests/manual/vue-test-runner.html",
    }
    for name, source in files.items():
        shutil.copy2(source, target / name)
    review = {
        "sample_id": "TaskManager",
        "classification": "reused_development_offline_candidate_manual_pass",
        "independent_holdout": False,
        "candidate_snapshot": CANDIDATE.name,
        "candidate_sha256": EXPECTED_SHA256,
        "manual_result": "passed_by_user",
        "confirmation_scope": [
            "Clicking inside settings modal does not close it",
            "Clicking inside create/edit task modal does not close it",
            "Overlay click closes the modal",
            "Task drag-and-drop sorting works",
        ],
        "per_scenario_browser_log": "not_supplied",
        "automatic_pipeline_reexecution": "not_performed_for_this_candidate",
        "automatic_snapshot": AUTOMATIC.name,
        "independent_test_evidence": False,
    }
    (target / "manual_review.json").write_text(
        json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    manifest = {
        "snapshot_id": target.name,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "classification": review["classification"],
        "independent_holdout": False,
        "sample_id": "TaskManager",
        "candidate_sha256": EXPECTED_SHA256,
        "browser_review": "passed_by_user",
        "per_scenario_browser_log": "not_supplied",
        "automatic_pipeline_reexecution": "not_performed_for_this_candidate",
        "original_paths": {name: source.relative_to(ROOT).as_posix() for name, source in files.items()},
        "integrity_file": "SHA256SUMS.txt",
    }
    (target / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    payloads = sorted(path for path in target.iterdir() if path.is_file())
    (target / "SHA256SUMS.txt").write_text(
        "\n".join(f"{sha256(path)}  {path.name}" for path in payloads) + "\n",
        encoding="utf-8",
    )
    verify(target)
    print(f"frozen: {target.relative_to(ROOT)} ({len(payloads)} verified payloads)")
    print(f"candidate_sha256: {EXPECTED_SHA256}")
    print("browser_review: passed_by_user; independent_holdout: false")


if __name__ == "__main__":
    main()
