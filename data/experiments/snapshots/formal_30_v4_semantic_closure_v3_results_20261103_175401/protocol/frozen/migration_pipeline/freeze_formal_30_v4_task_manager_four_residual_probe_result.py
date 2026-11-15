"""Freeze the exact four-residual probe output before interpreting its gates."""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from migration_pipeline import probe_formal_30_v4_task_manager_four_residual_v1 as probe


def main() -> None:
    source_manifest, _, prepared, _, prompt = probe.prepare()
    probe.verify_pre_run(source_manifest, prepared, prompt)
    if not probe.OUTPUT.is_file() or not probe.REPORT.is_file():
        raise FileNotFoundError("Probe candidate or report missing")
    report = json.loads(probe.REPORT.read_text(encoding="utf-8"))
    pre_run = json.loads((probe.PRE_RUN / "manifest.json").read_text(encoding="utf-8"))
    if (report.get("classification") != "reused_development_guarded_four_residual_probe_result"
            or report.get("source_snapshot") != source_manifest["snapshot_id"]
            or report.get("pre_run_snapshot") != pre_run["snapshot_id"]
            or report.get("input_sha256") != pre_run["input_sha256"]
            or report.get("prompt_sha256") != pre_run["prompt_sha256"]
            or report.get("output_sha256") != probe.sha256(probe.OUTPUT)):
        raise RuntimeError("Probe report does not match frozen inputs/output")
    stamp = datetime.fromisoformat(report["created_at"]).strftime("%Y%m%d_%H%M%S")
    target = ROOT / "data/experiments/snapshots" / f"formal_30_v4_task_manager_four_residual_probe_v1_result_{stamp}"
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
        "source.vue": probe.SOURCE / "source.vue",
    }
    target.mkdir(parents=True)
    for name, source in files.items():
        shutil.copy2(source, target / name)
    manifest = {
        "snapshot_id": target.name,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "classification": report["classification"],
        "independent_holdout": False,
        "source_snapshot": source_manifest["snapshot_id"],
        "pre_run_snapshot": pre_run["snapshot_id"],
        "candidate_sha256": probe.sha256(probe.OUTPUT),
        "report_sha256": probe.sha256(probe.REPORT),
        "validation_passed": report["validation_passed"],
        "visual_eval_passed": report["visual_eval_passed"],
        "regression_gate_decision": report["regression_gate"]["decision"],
        "automatic_passed": report["automatic_passed"],
        "browser_manual_review": "not_performed",
        "original_paths": {name: source.relative_to(ROOT).as_posix() for name, source in files.items()},
        "integrity_file": "SHA256SUMS.txt",
    }
    (target / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    payloads = sorted(path for path in target.iterdir() if path.is_file())
    (target / "SHA256SUMS.txt").write_text(
        "\n".join(f"{probe.sha256(path)}  {path.name}" for path in payloads) + "\n",
        encoding="utf-8",
    )
    probe.verify(target)
    print(f"frozen: {target.relative_to(ROOT)} ({len(payloads)} verified payloads)")
    print(f"validation_passed: {report['validation_passed']}")
    print(f"visual_eval_passed: {report['visual_eval_passed']}")
    print(f"regression_gate: {report['regression_gate']['decision']}")
    print(f"automatic_passed: {report['automatic_passed']}")


if __name__ == "__main__":
    main()
