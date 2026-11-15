"""Freeze one integrated-v1 development sample's automatic result before review."""

from __future__ import annotations

import argparse
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


BATCH_ID = "formal_30_v4_generalization_integrated_v1"
CONFIG = ROOT / f"migration_pipeline/batch_configs/{BATCH_ID}.json"
SUMMARY = ROOT / f"data/experiments/batch_reports/{BATCH_ID}_summary.json"
PRE_RUN = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_generalization_integrated_v1_pre_run_20261027_221300"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_file(path_value: str | Path) -> Path:
    path = (ROOT / path_value).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise RuntimeError(f"Missing or out-of-workspace evidence: {path_value}")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-id", required=True, choices=["TaskManager", "MonitoringDashboard"])
    args = parser.parse_args()
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    pre_run = json.loads((PRE_RUN / "manifest.json").read_text(encoding="utf-8"))
    if (config["batch_id"] != BATCH_ID or summary["batch_id"] != BATCH_ID
            or summary["config_sha256"] != config_fingerprint(config)
            or pre_run["batch_config_sha256"] != sha256(CONFIG)):
        raise RuntimeError("Batch/config/pre-run fingerprints disagree")
    planned = next(item for item in config["samples"] if item["id"] == args.sample_id)
    matches = [row for row in summary["samples"] if row["id"] == args.sample_id]
    if len(matches) != 1 or matches[0]["status"] != "completed":
        raise RuntimeError("Sample has not completed exactly once")
    row = matches[0]
    if row["vue_file"] != planned["vue_file"]:
        raise RuntimeError("Source path differs from the batch plan")
    source = checked_file(planned["vue_file"])
    if sha256(source) != planned["source_sha256"]:
        raise RuntimeError("Frozen Vue source hash mismatch")
    history_path = checked_file(row["report_file"])
    history = json.loads(history_path.read_text(encoding="utf-8"))
    if history["summary"]["final_passed"] is not row["final_passed"]:
        raise RuntimeError("Repair history disagrees with summary")
    initial_path = checked_file(row["output_file"])
    outputs = {
        "initial.san": initial_path,
    }
    for round_number in range(1, row["repair_rounds"] + 1):
        stage = initial_path.with_name(
            initial_path.stem + "_repaired" * round_number + initial_path.suffix
        )
        outputs[f"repair_round_{round_number}.san"] = checked_file(stage)
    final_path = outputs[f"repair_round_{row['repair_rounds']}.san"] if row["repair_rounds"] else initial_path
    if not final_path.is_file():
        raise RuntimeError("Final San artifact missing")

    stamp = datetime.fromisoformat(row["finished_at"]).strftime("%Y%m%d_%H%M%S")
    outcome = "automatic_pass" if row["final_passed"] else "automatic_fail"
    target = ROOT / "data/experiments/snapshots" / f"{BATCH_ID}_{args.sample_id}_{outcome}_{stamp}"
    if target.exists():
        raise FileExistsError(target)
    files = {
        "batch_config.json": CONFIG,
        "batch_summary.json": SUMMARY,
        "repair_history.json": history_path,
        "source.vue": source,
        "pre_run_manifest.json": PRE_RUN / "manifest.json",
        "pre_run_SHA256SUMS.txt": PRE_RUN / "SHA256SUMS.txt",
        **outputs,
    }
    target.mkdir(parents=True)
    for name, path in files.items():
        shutil.copy2(path, target / name)
    manifest = {
        "snapshot_id": target.name,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "classification": "reused_development_automatic_outcome",
        "independent_holdout": False,
        "sample_id": args.sample_id,
        "automatic_passed": row["final_passed"],
        "repair_rounds": row["repair_rounds"],
        "stop_reason": row["stop_reason"],
        "final_validation_error_codes": row["final_validation_error_codes"],
        "final_visual_error_codes": row["final_visual_error_codes"],
        "structure_similarity": row["final_structure_similarity"],
        "interaction_eval_passed": row["interaction_eval_passed"],
        "browser_runtime_review": "not_performed_for_this_automatic_output",
        "pre_run_snapshot": pre_run["snapshot_id"],
        "original_paths": {name: path.relative_to(ROOT).as_posix() for name, path in files.items()},
        "integrity_file": "SHA256SUMS.txt",
    }
    (target / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    payloads = sorted(path for path in target.iterdir() if path.is_file())
    (target / "SHA256SUMS.txt").write_text(
        "\n".join(f"{sha256(path)}  {path.name}" for path in payloads) + "\n",
        encoding="utf-8",
    )
    for line in (target / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        expected, name = line.split("  ", 1)
        if sha256(target / name) != expected:
            raise RuntimeError(f"Snapshot checksum mismatch: {name}")
    print(f"frozen: {target.relative_to(ROOT)} ({len(payloads)} verified payloads)")


if __name__ == "__main__":
    main()
