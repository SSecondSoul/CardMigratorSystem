"""Freeze the failed TaskManager development rerun before diagnosis or repair."""

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
    "formal_30_v4_generalization_remaining_v1_task_manager_failed_20261027_195349"
)
PRE_RUN = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_generalization_remaining_v1_pre_run_20261027_190033"
)
CONFIG = ROOT / "migration_pipeline/batch_configs/formal_30_v4_generalization_remaining_v1.json"
SUMMARY = ROOT / "data/experiments/batch_reports/formal_30_v4_generalization_remaining_v1_summary.json"
OUTPUT = ROOT / "data/experiments/pipeline/batches/formal_30_v4_generalization_remaining_v1/complex"
HISTORY = ROOT / "data/experiments/repair_reports/batches/formal_30_v4_generalization_remaining_v1/complex/TaskManager_repair_history.json"
SOURCE = ROOT / (
    "data/experiments/protocols/formal_30_v3_frozen_20261022/frozen/"
    "data/datasets/components/03_complex/TaskManager/vue/TaskManager.vue"
)
STAGES = (
    "TaskManager.san",
    "TaskManager_repaired.san",
    "TaskManager_repaired_repaired.san",
    "TaskManager_repaired_repaired_repaired.san",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if TARGET.exists():
        raise FileExistsError(TARGET)
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    history = json.loads(HISTORY.read_text(encoding="utf-8"))
    pre = json.loads((PRE_RUN / "manifest.json").read_text(encoding="utf-8"))
    if summary["batch_id"] != config["batch_id"] or summary["config_sha256"] != config_fingerprint(config):
        raise RuntimeError("Batch id or canonical config fingerprint mismatch")
    if pre["batch_config_sha256"] != sha256(CONFIG):
        raise RuntimeError("Config bytes differ from pre-run snapshot")
    if sha256(SOURCE) != config["samples"][0]["source_sha256"]:
        raise RuntimeError("Frozen Vue source hash mismatch")
    samples = summary["samples"]
    if len(samples) != 1 or samples[0]["id"] != "TaskManager":
        raise RuntimeError("Unexpected completed sample set")
    sample = samples[0]
    if sample["status"] != "completed" or sample["final_passed"] is not False:
        raise RuntimeError("Expected a completed automatic failure")
    if sample["repair_rounds"] != 3 or sample["stop_reason"] != "max_repair_rounds_reached":
        raise RuntimeError("Unexpected repair count or stop reason")
    if history["summary"]["final_passed"] is not False or history["state"]["validation_passed"] is not False:
        raise RuntimeError("Repair history disagrees with checkpoint")
    if history["state"]["visual_eval_passed"] is not True:
        raise RuntimeError("Visual history disagrees with checkpoint")
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
        "classification": "reused_development_source_to_san_regression_failed",
        "independent_holdout": False,
        "sample_id": "TaskManager",
        "automatic_passed": False,
        "repair_rounds": 3,
        "stop_reason": sample["stop_reason"],
        "final_validation_error_codes": sample["final_validation_error_codes"],
        "final_visual_error_codes": sample["final_visual_error_codes"],
        "structure_similarity": sample["final_structure_similarity"],
        "interaction_eval_passed": None,
        "browser_runtime_review": "not_performed_for_this_failed_output",
        "pre_run_snapshot": pre["snapshot_id"],
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
