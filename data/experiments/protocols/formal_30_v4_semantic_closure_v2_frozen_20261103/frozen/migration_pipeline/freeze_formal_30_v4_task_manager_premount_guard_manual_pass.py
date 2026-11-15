"""Freeze user browser acceptance of the automatic TaskManager regression output."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUTOMATIC = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_task_manager_premount_guard_regression_v1_TaskManager_automatic_pass_20261029_232535"
)
EXPECTED_SHA256 = "409e6372bc2760fc08b43fe27c7f3c875867c873618296ad7e39d57536290a3e"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(directory: Path) -> None:
    for line in (directory / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        if sha256(directory / relative) != expected:
            raise RuntimeError(f"Frozen payload changed: {directory / relative}")


def main() -> None:
    verify(AUTOMATIC)
    result = json.loads((AUTOMATIC / "manifest.json").read_text(encoding="utf-8"))
    if (result.get("automatic_passed") is not True
            or result.get("sample_id") != "TaskManager"
            or result.get("browser_runtime_review") != "not_performed_for_this_automatic_output"):
        raise RuntimeError("Unexpected automatic outcome")
    candidate = AUTOMATIC / "repair_round_6.san"
    if sha256(candidate) != EXPECTED_SHA256:
        raise RuntimeError("Final San differs from the user-reviewed candidate")
    san_runner = ROOT / "tests/manual/san-test-runner.html"
    vue_runner = ROOT / "tests/manual/vue-test-runner.html"
    if f"{AUTOMATIC.name}/repair_round_6.san" not in san_runner.read_text(encoding="utf-8"):
        raise RuntimeError("San runner does not reference reviewed final San")
    vue_source = ROOT / (
        "data/experiments/snapshots/"
        "formal_30_v4_task_manager_five_residual_regression_v1_TaskManager_automatic_pass_20261029_200650/source.vue"
    )
    if (str(vue_source.relative_to(ROOT)).replace("\\", "/") not in vue_runner.read_text(encoding="utf-8")
            or sha256(vue_source) != sha256(AUTOMATIC / "source.vue")):
        raise RuntimeError("Vue runner source does not match frozen regression source")
    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    target = ROOT / "data/experiments/snapshots" / f"formal_30_v4_task_manager_premount_guard_manual_pass_{stamp}"
    target.mkdir(parents=True, exist_ok=False)
    files = {
        "final.san": candidate,
        "source.vue": AUTOMATIC / "source.vue",
        "automatic_manifest.json": AUTOMATIC / "manifest.json",
        "batch_summary.json": AUTOMATIC / "batch_summary.json",
        "manual_san_runner.html": san_runner,
        "manual_vue_runner.html": vue_runner,
    }
    for name, source in files.items():
        shutil.copy2(source, target / name)
    review = {
        "sample_id": "TaskManager",
        "classification": "reused_development_automatic_output_manual_pass",
        "independent_holdout": False,
        "automatic_snapshot": AUTOMATIC.name,
        "final_san_sha256": EXPECTED_SHA256,
        "automatic_result": "passed",
        "browser_result": "passed_by_user",
        "confirmation_basis": "User replied pass after being asked to review settings and create/edit modal clicks, overlay closing, drag sorting, initial notification and auto-sync.",
        "per_scenario_browser_log": "not_supplied",
        "interaction_eval_passed": None,
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
        "final_san_sha256": EXPECTED_SHA256,
        "automatic_result": "passed",
        "browser_review": "passed_by_user",
        "per_scenario_browser_log": "not_supplied",
        "automatic_snapshot": AUTOMATIC.name,
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
    print(f"final_san_sha256: {EXPECTED_SHA256}")
    print("automatic_result: passed; browser_review: passed_by_user; independent_holdout: false")


if __name__ == "__main__":
    main()
