"""Freeze the TaskManager v3b event-only probe result before diagnosis."""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from migration_pipeline import probe_formal_30_v4_task_manager_event_focus_v3 as probe
from migration_pipeline.probe_formal_30_v4_task_manager_semantic_focus_v2 import sha256, verify_checksums


def main() -> None:
    source_manifest, _, prepared, _, prompt = probe.prepare()
    pre_run = probe.verify_frozen_pre_run(source_manifest, prepared, prompt)
    if not probe.OUTPUT.is_file() or not probe.REPORT.is_file():
        raise FileNotFoundError("Probe candidate or report missing")
    report = json.loads(probe.REPORT.read_text(encoding="utf-8"))
    if (report.get("classification") != "reused_development_guarded_event_only_probe_result"
            or report.get("source_snapshot") != source_manifest["snapshot_id"]
            or report.get("candidate_snapshot") != probe.CANDIDATE.name
            or report.get("pre_run_snapshot") != pre_run["snapshot_id"]
            or report.get("input_sha256") != pre_run["input_sha256"]
            or report.get("prompt_sha256") != pre_run["prompt_sha256"]
            or report.get("output_sha256") != sha256(probe.OUTPUT)):
        raise RuntimeError("Probe result does not match frozen inputs or candidate bytes")

    stamp = datetime.fromisoformat(report["created_at"]).strftime("%Y%m%d_%H%M%S")
    target = ROOT / "data/experiments/snapshots" / (
        f"formal_30_v4_task_manager_event_focus_v3b_result_{stamp}"
    )
    if target.exists():
        raise FileExistsError(target)
    files = {
        "candidate.san": probe.OUTPUT,
        "probe_report.json": probe.REPORT,
        "prepared_input.san": probe.PRE_RUN / "input.san",
        "prompt.txt": probe.PRE_RUN / "prompt.txt",
        "validation_errors.json": probe.PRE_RUN / "validation_errors.json",
        "pre_run_manifest.json": probe.PRE_RUN / "manifest.json",
        "pre_run_SHA256SUMS.txt": probe.PRE_RUN / "SHA256SUMS.txt",
        "source_manifest.json": probe.SOURCE / "manifest.json",
        "source_SHA256SUMS.txt": probe.SOURCE / "SHA256SUMS.txt",
        "prior_candidate_manifest.json": probe.CANDIDATE / "manifest.json",
        "prior_candidate_SHA256SUMS.txt": probe.CANDIDATE / "SHA256SUMS.txt",
    }
    target.mkdir(parents=True)
    for name, source in files.items():
        shutil.copy2(source, target / name)
    manifest = {
        "snapshot_id": target.name,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "classification": "reused_development_guarded_event_only_probe_result",
        "independent_holdout": False,
        "source_snapshot": source_manifest["snapshot_id"],
        "candidate_snapshot": probe.CANDIDATE.name,
        "pre_run_snapshot": pre_run["snapshot_id"],
        "candidate_sha256": sha256(probe.OUTPUT),
        "report_sha256": sha256(probe.REPORT),
        "validation_passed": bool(report.get("validation_passed")),
        "visual_eval_passed": bool(report.get("visual_eval_passed")),
        "event_regression_decision": report.get("event_regression_gate", {}).get("decision"),
        "automatic_passed": bool(report.get("automatic_passed")),
        "browser_manual_review": "not_performed",
        "original_paths": {name: source.relative_to(ROOT).as_posix() for name, source in files.items()},
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
    verify_checksums(target)
    print(f"frozen: {target.relative_to(ROOT)} ({len(payloads)} verified payloads)")


if __name__ == "__main__":
    main()
