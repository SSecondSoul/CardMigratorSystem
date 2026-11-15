"""Freeze the single-round TaskManager semantic probe before interpreting it."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "data/experiments/pipeline/probes/formal_30_v4_task_manager_semantic_probe_v1"
PRE_RUN = ROOT / "data/experiments/snapshots/formal_30_v4_task_manager_semantic_probe_v1_pre_run_20261028"
INPUT = ROOT / "data/experiments/snapshots/formal_30_v4_semantic_focus_v2_TaskManager_automatic_fail_20261028_140129"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    report_path = PROBE / "probe_report.json"
    output_path = PROBE / "TaskManager_semantic_probe.san"
    for path in (report_path, output_path, PRE_RUN / "manifest.json", INPUT / "manifest.json"):
        if not path.is_file():
            raise FileNotFoundError(path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    pre_run = json.loads((PRE_RUN / "manifest.json").read_text(encoding="utf-8"))
    input_manifest = json.loads((INPUT / "manifest.json").read_text(encoding="utf-8"))
    if report.get("classification") != "reused_development_single_repair_probe":
        raise RuntimeError("Unexpected probe classification")
    if report.get("frozen_input") != input_manifest["snapshot_id"]:
        raise RuntimeError("Probe input differs from frozen failure")
    if report.get("pre_run_snapshot") != pre_run["snapshot_id"]:
        raise RuntimeError("Probe pre-run snapshot differs")
    if report.get("input_sha256") != pre_run["input_sha256"]:
        raise RuntimeError("Frozen input hash differs")
    if report.get("prompt_sha256") != pre_run["prompt_sha256"]:
        raise RuntimeError("Frozen prompt hash differs")
    if report.get("output_sha256") != sha256(output_path):
        raise RuntimeError("Probe output hash mismatch")

    stamp = datetime.fromisoformat(report["created_at"]).strftime("%Y%m%d_%H%M%S")
    target = ROOT / "data/experiments/snapshots" / f"formal_30_v4_task_manager_semantic_probe_v1_result_{stamp}"
    if target.exists():
        raise FileExistsError(target)
    files = {
        "candidate.san": output_path,
        "probe_report.json": report_path,
        "pre_run_manifest.json": PRE_RUN / "manifest.json",
        "pre_run_SHA256SUMS.txt": PRE_RUN / "SHA256SUMS.txt",
        "input_result_manifest.json": INPUT / "manifest.json",
        "prompt.txt": PRE_RUN / "prompt.txt",
    }
    target.mkdir(parents=True)
    for name, source in files.items():
        shutil.copy2(source, target / name)
    manifest = {
        "snapshot_id": target.name,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "classification": "reused_development_single_repair_probe_result",
        "independent_holdout": False,
        "frozen_input": input_manifest["snapshot_id"],
        "pre_run_snapshot": pre_run["snapshot_id"],
        "candidate_sha256": sha256(output_path),
        "report_sha256": sha256(report_path),
        "automatic_batch_outcome_unchanged": True,
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
    for line in (target / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        expected, name = line.split("  ", 1)
        if sha256(target / name) != expected:
            raise RuntimeError(f"Snapshot checksum mismatch: {name}")
    print(f"frozen: {target.relative_to(ROOT)} ({len(payloads)} verified payloads)")


if __name__ == "__main__":
    main()
