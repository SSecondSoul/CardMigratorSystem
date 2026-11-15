"""Freeze the second focused AnalyticsDashboard repair probe for runtime review."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_generalization_followup_analytics_dashboard_automatic_fail_20261027_144124"
)
PROBE = ROOT / "data/experiments/pipeline/probes/formal_30_v4_analytics_computed_focus_v2"
PRE_PROBE = ROOT / (
    "data/experiments/analysis/formal_30_v4_generalization_gap_audit_20261027/"
    "analytics_computed_focus_v2_pre_probe.json"
)
TARGET = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_analytics_computed_focus_probe_v2_static_pass_20261027_152434"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def block(code: str, name: str) -> str:
    match = re.search(rf"<{name}>(.*?)</{name}>", code, re.S)
    if not match:
        raise RuntimeError(f"Missing {name} block")
    return match.group(1)


def main() -> None:
    if TARGET.exists():
        raise FileExistsError(TARGET)
    pre = json.loads(PRE_PROBE.read_text(encoding="utf-8"))
    report = json.loads((PROBE / "probe_report.json").read_text(encoding="utf-8"))
    source = INPUT / "final.san"
    candidate = PROBE / "AnalyticsDashboard_repaired.san"
    if sha256(source) != pre["frozen_input_final_san_sha256"]:
        raise RuntimeError("Frozen source hash mismatch")
    if report["input_sha256"] != sha256(source) or report["output_sha256"] != sha256(candidate):
        raise RuntimeError("Probe report/input/candidate hash mismatch")
    if report["prompt_sha256"] != pre["focused_prompt_sha256"]:
        raise RuntimeError("Prompt differs from pre-probe record")
    if not report["validation_passed"] or not report["visual_eval_passed"]:
        raise RuntimeError("Unexpected automatic probe outcome")
    files = {
        "failed_input.san": source,
        "candidate.san": candidate,
        "probe_report.json": PROBE / "probe_report.json",
        "pre_probe.json": PRE_PROBE,
        "repair_prompt.py": ROOT / "migration_pipeline/utils/repair_prompt.py",
        "probe_script.py": ROOT / "migration_pipeline/probe_formal_30_v4_analytics_computed_repair.py",
        "runtime_acceptance.json": ROOT / "migration_pipeline/interaction_configs/formal_30_v4_runtime_acceptance.json",
        "runtime_acceptance.js": ROOT / "tests/manual/formal-30-v4-runtime-acceptance.js",
    }
    for name, key in (
        ("repair_prompt.py", "repair_prompt_implementation_sha256"),
        ("probe_script.py", "probe_script_sha256"),
        ("runtime_acceptance.json", "browser_scenario_config_sha256"),
        ("runtime_acceptance.js", "browser_scenario_script_sha256"),
    ):
        if sha256(files[name]) != pre[key]:
            raise RuntimeError(f"Pre-probe implementation hash mismatch: {name}")
    source_code = source.read_text(encoding="utf-8")
    candidate_code = candidate.read_text(encoding="utf-8")
    if any(block(source_code, tag) != block(candidate_code, tag) for tag in ("template", "style")):
        raise RuntimeError("Template or style changed unexpectedly")
    if not all(fragment in candidate_code for fragment in (
        'cx="{{ getX(idx) }}"',
        'cy="{{ getY(point.value) }}"',
        "getX(index) {",
        "getY(value) {",
        "function getXForChart(index, dataLength) {",
        "function getYForChart(value, maxValue, minValue) {",
    )):
        raise RuntimeError("Computed helper or template-method compatibility missing")
    if "this.getX(idx)" in candidate_code or "this.getY(point.value)" in candidate_code:
        raise RuntimeError("Forbidden computed instance call remains")

    TARGET.mkdir(parents=True)
    for name, path in files.items():
        shutil.copy2(path, TARGET / name)
    manifest = {
        "snapshot_id": TARGET.name,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "classification": "reused_development_regression_repair_probe",
        "independent_holdout": False,
        "frozen_input": report["frozen_input"],
        "probe_validation_passed": True,
        "probe_visual_eval_passed": True,
        "template_style_unchanged": True,
        "template_method_signature_compatible_by_code_inspection": True,
        "browser_review": "not_yet_performed",
        "manual_vue_san_review": "not_yet_performed",
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
