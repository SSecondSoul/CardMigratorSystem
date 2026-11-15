"""Freeze the observed full-v4 regression result before post-run diagnosis."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from migration_pipeline.freeze_formal_30_v3_results import VERIFY_SCRIPT
from migration_pipeline.prepare_formal_30_v4_full_regression import (
    BATCH_ID, CONFIG, ROOT, TARGET as PROTOCOL, digest,
)
from migration_pipeline.run_batch_pipeline import config_fingerprint


SUMMARY = ROOT / f"data/experiments/batch_reports/{BATCH_ID}_summary.json"


def main() -> None:
    subprocess.run([sys.executable, str(PROTOCOL / "verify_protocol.py"), "--live"], cwd=ROOT, check=True)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    samples = summary["samples"]
    statuses = Counter(s["status"] for s in samples)
    passed = sum(s.get("status") == "completed" and s.get("final_passed") is True for s in samples)
    expected = {
        "configured": 30, "completed": statuses["completed"], "passed": passed,
        "failed": statuses["completed"] - passed, "execution_errors": statuses["error"], "pending": 0,
    }
    if (summary["batch_id"] != BATCH_ID or summary["config_sha256"] != config_fingerprint(config)
            or summary["max_repair_rounds"] != 3 or len(samples) != 30
            or set(statuses) - {"completed", "error"}
            or [s["id"] for s in samples] != [s["id"] for s in config["samples"]]
            or any(summary["aggregate"][key] != value for key, value in expected.items())):
        raise RuntimeError("Result is incomplete or inconsistent with the frozen plan")
    mappings = {SUMMARY: Path(SUMMARY.name), CONFIG: Path(CONFIG.name)}
    for source_dir, destination_dir in (
        (ROOT / f"data/experiments/pipeline/batches/{BATCH_ID}", "pipeline"),
        (ROOT / f"data/experiments/repair_reports/batches/{BATCH_ID}", "repair_reports"),
        (PROTOCOL, "protocol"),
    ):
        if not source_dir.is_dir():
            raise FileNotFoundError(source_dir)
        for source in source_dir.rglob("*"):
            if source.is_file():
                if not source.resolve().is_relative_to(ROOT):
                    raise RuntimeError(f"Out-of-workspace evidence: {source}")
                mappings[source] = Path(destination_dir) / source.relative_to(source_dir)
    for sample in samples:
        if sample["status"] == "completed":
            for name in ("report_file", "final_file_path"):
                source = Path(sample[name])
                source = source if source.is_absolute() else ROOT / source
                if source.resolve() not in {p.resolve() for p in mappings}:
                    raise RuntimeError(f"Missing completed-sample evidence: {sample['id']} {name}")
    original_hashes = {source: digest(source) for source in mappings}
    now = datetime.now(timezone(timedelta(hours=8)))
    target = ROOT / "data/experiments/snapshots" / f"{BATCH_ID}_results_{now:%Y%m%d_%H%M%S}"
    if target.exists():
        raise FileExistsError(target)
    target.mkdir(parents=True)
    for source, destination_relative in mappings.items():
        destination = target / destination_relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        if digest(destination) != original_hashes[source] or digest(source) != original_hashes[source]:
            raise RuntimeError(f"Evidence changed during freeze: {source}")
    shutil.copy2(Path(__file__), target / Path(__file__).name)
    (target / "verify_snapshot.py").write_text(VERIFY_SCRIPT, encoding="utf-8")
    manifest = {
        "snapshot_id": target.name,
        "created_at": now.isoformat(timespec="seconds"),
        "batch_id": BATCH_ID,
        "classification": "reused_development_full_regression_raw_result",
        "independent_holdout": False,
        "summary_sha256": digest(SUMMARY),
        "config_sha256": digest(CONFIG),
        "config_fingerprint": config_fingerprint(config),
        "protocol_id": PROTOCOL.name,
        "protocol_live_verification_passed_at_result_freeze": True,
        "server_loaded_code_proven": False,
        "aggregate": summary["aggregate"],
        "failed_completed_ids": [s["id"] for s in samples if s["status"] == "completed" and not s["final_passed"]],
        "execution_error_ids": [s["id"] for s in samples if s["status"] == "error"],
        "boundary": "As-observed raw files copied and hash-checked before this workflow's diagnosis; no model calls or reruns performed by the freezer.",
    }
    (target / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files = sorted(p for p in target.rglob("*") if p.is_file())
    (target / "SHA256SUMS.txt").write_text("\n".join(f"{digest(p)}  {p.relative_to(target).as_posix()}" for p in files) + "\n", encoding="utf-8")
    subprocess.run([sys.executable, str(target / "verify_snapshot.py")], cwd=ROOT, check=True)
    print(target.relative_to(ROOT))
    print(json.dumps(expected, ensure_ascii=False))


if __name__ == "__main__":
    main()
