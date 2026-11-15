"""Freeze one completed formal_30_v4 development follow-up sample.

The snapshot preserves the automatic outcome; browser/manual review is separate.
"""

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

CONFIG = Path("migration_pipeline/batch_configs/formal_30_v4_generalization_followup.json")
SUMMARY = Path("data/experiments/batch_reports/formal_30_v4_generalization_followup_summary.json")
PRE_RUN = Path("data/experiments/snapshots/formal_30_v4_generalization_followup_pre_run_20261027_v2/manifest.json")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_file(path_value: str | Path) -> Path:
    path = (ROOT / path_value).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise RuntimeError(f"Missing or out-of-workspace evidence: {path_value}")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-id", required=True)
    args = parser.parse_args()
    config_path = checked_file(CONFIG)
    summary_path = checked_file(SUMMARY)
    pre_run_path = checked_file(PRE_RUN)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    pre_run = json.loads(pre_run_path.read_text(encoding="utf-8"))
    if summary.get("batch_id") != config["batch_id"]:
        raise RuntimeError("Batch ID mismatch")
    if summary.get("config_sha256") != config_fingerprint(config):
        raise RuntimeError("Batch config/checkpoint fingerprint mismatch")
    if pre_run.get("batch_config_sha256") != sha256(config_path):
        raise RuntimeError("Pre-run snapshot/config hash mismatch")

    matches = [row for row in summary["samples"] if row["id"] == args.sample_id]
    if len(matches) != 1 or matches[0].get("status") != "completed":
        raise RuntimeError("Sample has not completed exactly once")
    row = matches[0]
    planned = next((item for item in config["samples"] if item["id"] == args.sample_id), None)
    if not planned or planned["vue_file"] != row["vue_file"]:
        raise RuntimeError("Sample source differs from the batch plan")
    source_path = checked_file(planned["vue_file"])
    if sha256(source_path) != planned["source_sha256"]:
        raise RuntimeError("Frozen Vue source hash mismatch")

    initial_path = checked_file(row["output_file"])
    final_path = checked_file(row["final_file_path"])
    history_path = checked_file(row["report_file"])
    output_root = (ROOT / summary["output_dir"]).resolve()
    report_root = (ROOT / summary["report_dir"]).resolve()
    if not initial_path.is_relative_to(output_root) or not final_path.is_relative_to(output_root):
        raise RuntimeError("San artifact outside this batch")
    if not history_path.is_relative_to(report_root):
        raise RuntimeError("Repair history outside this batch")

    finished = datetime.fromisoformat(row["finished_at"])
    stamp = finished.strftime("%Y%m%d_%H%M%S")
    outcome = "automatic_pass" if row["final_passed"] else "automatic_fail"
    snapshot_id = f"{config['batch_id']}_{args.sample_id}_{outcome}_{stamp}"
    target = ROOT / "data/experiments/snapshots" / snapshot_id
    if target.exists():
        raise FileExistsError(f"Snapshot already exists: {target}")

    inputs = {
        "batch_config.json": config_path,
        "batch_summary.json": summary_path,
        "pre_run_manifest.json": pre_run_path,
        "source.vue": source_path,
        "initial.san": initial_path,
        "final.san": final_path,
        "repair_history.json": history_path,
    }
    target.mkdir(parents=True)
    for name, source in inputs.items():
        shutil.copy2(source, target / name)
    manifest = {
        "snapshot_id": snapshot_id,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "classification": "reused_development_regression_automatic_outcome",
        "independent_holdout": False,
        "sample_id": args.sample_id,
        "automatic_passed": row["final_passed"],
        "manual_browser_review": "not_yet_performed_on_this_artifact",
        "interaction_eval_passed": row.get("interaction_eval_passed"),
        "repair_rounds": row.get("repair_rounds"),
        "total_tokens": row.get("total_tokens"),
        "pre_run_snapshot": pre_run["snapshot_id"],
        "original_paths": {name: path.relative_to(ROOT).as_posix() for name, path in inputs.items()},
        "integrity_file": "SHA256SUMS.txt",
    }
    (target / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    files = sorted(path for path in target.iterdir() if path.is_file())
    (target / "SHA256SUMS.txt").write_text(
        "\n".join(f"{sha256(path)}  {path.name}" for path in files) + "\n",
        encoding="utf-8",
    )
    for line in (target / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        expected, name = line.split("  ", 1)
        if sha256(target / name) != expected:
            raise RuntimeError(f"Snapshot checksum mismatch: {name}")
    print(f"frozen: {target.relative_to(ROOT)} ({len(files)} verified payloads)")


if __name__ == "__main__":
    main()
