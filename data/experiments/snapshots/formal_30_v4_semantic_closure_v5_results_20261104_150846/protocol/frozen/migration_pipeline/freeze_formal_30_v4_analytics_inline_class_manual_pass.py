"""Freeze the user-reported San browser acceptance of the post-hoc candidate."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_analytics_inline_class_posthoc_manual_pass_20261027_181036"
)
PRIOR = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_analytics_inline_class_posthoc_candidate_20261027_173453"
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
RUNNER = ROOT / "tests/manual/san-test-runner.html"
EXPECTED_SHA256 = "1b2c8143e95f6eadbbdd3740bd864879a0d4742c28a08001667a0ae6cfb5bcb0"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if TARGET.exists():
        raise FileExistsError(TARGET)
    prior = json.loads((PRIOR / "manifest.json").read_text(encoding="utf-8"))
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    review = json.loads(REVIEW.read_text(encoding="utf-8"))
    if sha256(CANDIDATE) != EXPECTED_SHA256 or sha256(PRIOR / "candidate.san") != EXPECTED_SHA256:
        raise RuntimeError("Candidate bytes differ from the pre-review snapshot")
    if prior["candidate_sha256"] != EXPECTED_SHA256 or report["candidate_sha256"] != EXPECTED_SHA256:
        raise RuntimeError("Candidate hash mismatch in prior snapshot or repair report")
    if review["posthoc_candidate_sha256"] != EXPECTED_SHA256:
        raise RuntimeError("Review references a different candidate")
    if review["posthoc_candidate_browser_review"]["status"] != "user_reported_pass":
        raise RuntimeError("User browser pass has not been recorded")
    if "user_reported_pass" not in report["browser_runtime"]:
        raise RuntimeError("Repair report lacks browser-review status")
    if f"?v={EXPECTED_SHA256[:8]}" not in RUNNER.read_text(encoding="utf-8"):
        raise RuntimeError("Manual runner did not point to the reviewed candidate")

    files = {
        "candidate.san": CANDIDATE,
        "repair_report.json": REPORT,
        "manual_review.json": REVIEW,
        "prior_candidate_manifest.json": PRIOR / "manifest.json",
        "prior_candidate_SHA256SUMS.txt": PRIOR / "SHA256SUMS.txt",
        "san_test_runner.html": RUNNER,
    }
    TARGET.mkdir(parents=True)
    for name, path in files.items():
        shutil.copy2(path, TARGET / name)
    manifest = {
        "snapshot_id": TARGET.name,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "classification": "reused_development_posthoc_manual_san_acceptance",
        "independent_holdout": False,
        "sample_id": "analytics_dashboard",
        "candidate_sha256": EXPECTED_SHA256,
        "browser_review": "user_reported_pass_for_requested_san_checks",
        "review_scope": [
            "statistics cards and insight styling",
            "circle/polyline alignment after switching to 7d and 90d",
            "no browser console errors",
        ],
        "evidence_type": "user_chat_confirmation; no independent screenshot or automated browser replay",
        "vue_period_switch_review": "not_checked",
        "original_automatic_batch_was_not_changed": True,
        "fresh_batch_with_extended_duplicate_class_rule": "not_run",
        "prior_candidate_snapshot": prior["snapshot_id"],
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
