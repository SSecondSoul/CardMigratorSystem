"""Freeze the source-to-San AnalyticsDashboard development regression result."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from migration_pipeline.run_batch_pipeline import config_fingerprint


TARGET = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_analytics_chart_reactivity_regression_v1_automatic_pass_20261027_172556"
)
PRE_RUN = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_analytics_chart_reactivity_regression_v1_pre_run_20261027_164749"
)
CONFIG = ROOT / "migration_pipeline/batch_configs/formal_30_v4_analytics_chart_reactivity_regression_v1.json"
SUMMARY = ROOT / "data/experiments/batch_reports/formal_30_v4_analytics_chart_reactivity_regression_v1_summary.json"
OUTPUT = ROOT / "data/experiments/pipeline/batches/formal_30_v4_analytics_chart_reactivity_regression_v1/complex"
HISTORY = ROOT / "data/experiments/repair_reports/batches/formal_30_v4_analytics_chart_reactivity_regression_v1/complex/AnalyticsDashboard_repair_history.json"
SOURCE = ROOT / (
    "data/experiments/protocols/formal_30_v3_frozen_20261022/frozen/"
    "data/datasets/components/03_complex/AnalyticsDashboard/vue/AnalyticsDashboard.vue"
)
STAGES = (
    "AnalyticsDashboard.san",
    "AnalyticsDashboard_repaired.san",
    "AnalyticsDashboard_repaired_repaired.san",
    "AnalyticsDashboard_repaired_repaired_repaired.san",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if TARGET.exists():
        raise FileExistsError(f"Snapshot already exists: {TARGET}")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    history = json.loads(HISTORY.read_text(encoding="utf-8"))
    pre_run = json.loads((PRE_RUN / "manifest.json").read_text(encoding="utf-8"))
    sample = summary["samples"]
    if summary["batch_id"] != config["batch_id"] or len(sample) != 1:
        raise RuntimeError("Unexpected batch or sample count")
    sample = sample[0]
    if sample["id"] != "analytics_dashboard" or sample["status"] != "completed":
        raise RuntimeError("Unexpected sample status")
    if not sample["final_passed"] or sample["stop_reason"] != "passed":
        raise RuntimeError("This snapshot expects an automatic pass")
    if sample["repair_rounds"] != 3 or sample["final_validation_error_codes"] or sample["final_visual_error_codes"]:
        raise RuntimeError("Unexpected final round count or remaining automatic errors")
    if summary["config_sha256"] != config_fingerprint(config):
        raise RuntimeError("Summary canonical config fingerprint mismatch")
    if pre_run["batch_config_sha256"] != sha256(CONFIG):
        raise RuntimeError("Config bytes differ from the pre-run snapshot")
    if pre_run["source_sha256"] != sha256(SOURCE):
        raise RuntimeError("Vue source differs from the pre-run snapshot")
    if history["summary"]["final_passed"] is not True or history["state"]["validation_passed"] is not True:
        raise RuntimeError("Repair history disagrees with summary")
    if history["state"]["visual_eval_passed"] is not True:
        raise RuntimeError("Repair history visual assessment disagrees with summary")
    for filename in STAGES:
        if not (OUTPUT / filename).is_file():
            raise FileNotFoundError(OUTPUT / filename)

    files = {
        "batch_config.json": CONFIG,
        "batch_summary.json": SUMMARY,
        "repair_history.json": HISTORY,
        "source.vue": SOURCE,
        "pre_run_manifest.json": PRE_RUN / "manifest.json",
        "pre_run_SHA256SUMS.txt": PRE_RUN / "SHA256SUMS.txt",
        **{filename: OUTPUT / filename for filename in STAGES},
    }
    TARGET.mkdir(parents=True)
    for name, path in files.items():
        shutil.copy2(path, TARGET / name)
    manifest = {
        "snapshot_id": TARGET.name,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "classification": "reused_development_source_to_san_regression",
        "independent_holdout": False,
        "sample_id": "analytics_dashboard",
        "automatic_passed": True,
        "repair_rounds": 3,
        "initial_hidden_template_reactive_dependency_count": sample["initial_validation_error_codes"].count("hidden_template_reactive_dependency"),
        "final_validation_error_codes": [],
        "final_visual_error_codes": [],
        "structure_similarity": sample["final_structure_similarity"],
        "interaction_eval_passed": None,
        "browser_runtime_review": "not_yet_performed_for_this_new_output",
        "manual_v3_repair_was_not_pipeline_input": True,
        "pre_run_snapshot": pre_run["snapshot_id"],
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
