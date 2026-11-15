"""Freeze user acceptance of the bounded TaskManager pre-mount replay."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_task_manager_premount_noop_candidate_20261029_225953"
)
EXPECTED_SHA256 = "dd80e7039e21827a205f0974ae3517510a51a05b70d10f33559e3056807f524b"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(directory: Path) -> None:
    for line in (directory / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        if sha256(directory / relative) != expected:
            raise RuntimeError(f"Frozen payload changed: {directory / relative}")


def main() -> None:
    verify(CANDIDATE)
    candidate = CANDIDATE / "candidate.san"
    if sha256(candidate) != EXPECTED_SHA256:
        raise RuntimeError("Candidate hash does not match user-reviewed artifact")
    report = json.loads((CANDIDATE / "replay_report.json").read_text(encoding="utf-8"))
    if (report.get("validation_passed") is not True
            or report.get("san_compile_passed") is not True
            or report.get("visual_eval_passed") is not True
            or report.get("event_gate_decision") != "pass"
            or report.get("browser_manual_review") != "pending"):
        raise RuntimeError("Unexpected offline replay state")
    san_runner = ROOT / "tests/manual/san-test-runner.html"
    vue_runner = ROOT / "tests/manual/vue-test-runner.html"
    if CANDIDATE.name not in san_runner.read_text(encoding="utf-8"):
        raise RuntimeError("San runner does not reference accepted candidate")
    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    target = ROOT / "data/experiments/snapshots" / f"formal_30_v4_task_manager_premount_noop_manual_pass_{stamp}"
    target.mkdir(parents=True, exist_ok=False)
    files = {
        "candidate.san": candidate,
        "source.vue": CANDIDATE / "source.vue",
        "offline_replay_report.json": CANDIDATE / "replay_report.json",
        "manual_san_runner.html": san_runner,
        "manual_vue_runner.html": vue_runner,
    }
    for name, source in files.items():
        shutil.copy2(source, target / name)
    review = {
        "sample_id": "TaskManager",
        "classification": "reused_development_bounded_offline_candidate_manual_pass",
        "independent_holdout": False,
        "candidate_snapshot": CANDIDATE.name,
        "candidate_sha256": EXPECTED_SHA256,
        "manual_result": "passed_by_user",
        "confirmation_basis": "User replied '通过' after being asked to review settings and create/edit modal clicks, drag sorting, initial notification, and auto-sync.",
        "per_scenario_browser_log": "not_supplied",
        "automatic_pipeline_reexecution": "not_performed_for_this_candidate",
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
        "\n".join(f"{sha256(path)}  {path.name}" for path in payloads) + "\n", encoding="utf-8",
    )
    verify(target)
    print(f"frozen: {target.relative_to(ROOT)} ({len(payloads)} verified payloads)")
    print(f"candidate_sha256: {EXPECTED_SHA256}")
    print("browser_review: passed_by_user; automatic_pipeline_reexecution: not_performed")


if __name__ == "__main__":
    main()
