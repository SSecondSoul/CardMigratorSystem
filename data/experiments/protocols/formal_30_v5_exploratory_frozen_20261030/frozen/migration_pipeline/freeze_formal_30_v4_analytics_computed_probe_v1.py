"""Freeze the first focused AnalyticsDashboard probe without modifying its artifacts."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_generalization_followup_analytics_dashboard_automatic_fail_20261027_144124"
)
PROBE = ROOT / "data/experiments/pipeline/probes/formal_30_v4_analytics_computed_focus_v1"
PRE_PROBE = ROOT / (
    "data/experiments/analysis/formal_30_v4_generalization_gap_audit_20261027/"
    "analytics_computed_focus_pre_probe.json"
)
TARGET = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_analytics_computed_focus_probe_v1_semantic_reject_20261027_151143"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if TARGET.exists():
        raise FileExistsError(TARGET)
    pre = json.loads(PRE_PROBE.read_text(encoding="utf-8"))
    report = json.loads((PROBE / "probe_report.json").read_text(encoding="utf-8"))
    if report["input_sha256"] != sha256(INPUT / "final.san"):
        raise RuntimeError("Probe input no longer matches frozen failure")
    if report["output_sha256"] != sha256(PROBE / "AnalyticsDashboard_repaired.san"):
        raise RuntimeError("Probe candidate hash mismatch")
    if pre["focused_prompt_sha256"] != report["prompt_sha256"]:
        raise RuntimeError("Focused prompt differs from pre-probe record")
    if not report["validation_passed"] or not report["visual_eval_passed"]:
        raise RuntimeError("Unexpected automatic probe outcome")
    files = {
        "failed_input.san": INPUT / "final.san",
        "candidate.san": PROBE / "AnalyticsDashboard_repaired.san",
        "probe_report.json": PROBE / "probe_report.json",
        "pre_probe.json": PRE_PROBE,
        "repair_prompt.py": ROOT / "migration_pipeline/utils/repair_prompt.py",
        "probe_script.py": ROOT / "migration_pipeline/probe_formal_30_v4_analytics_computed_repair.py",
    }
    for name, key in (
        ("repair_prompt.py", "repair_prompt_implementation_sha256"),
        ("probe_script.py", "probe_script_sha256"),
    ):
        if sha256(files[name]) != pre[key]:
            raise RuntimeError(f"Pre-probe implementation hash mismatch: {name}")
    candidate = files["candidate.san"].read_text(encoding="utf-8")
    if not all(fragment in candidate for fragment in (
        'cx="{{ getX(idx) }}"',
        'cy="{{ getY(point.value) }}"',
        "getX(index, dataLength) {",
        "getY(value, maxValue, minValue) {",
    )):
        raise RuntimeError("Expected template/method signature mismatch was not found")

    TARGET.mkdir(parents=True)
    for name, source in files.items():
        shutil.copy2(source, TARGET / name)
    manifest = {
        "snapshot_id": TARGET.name,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "classification": "reused_development_regression_repair_probe",
        "independent_holdout": False,
        "frozen_input": report["frozen_input"],
        "probe_validation_passed": True,
        "probe_visual_eval_passed": True,
        "candidate_semantic_review": "rejected_by_code_inspection",
        "reason": "Template calls getX(idx)/getY(point.value) with one argument, while the candidate component methods require two/three arguments, so chart point coordinates can become NaN after async data loads.",
        "browser_review": "not_performed_browser_control_unavailable",
        "original_paths": {name: path.relative_to(ROOT).as_posix() for name, path in files.items()},
        "integrity_file": "SHA256SUMS.txt",
    }
    (TARGET / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
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
