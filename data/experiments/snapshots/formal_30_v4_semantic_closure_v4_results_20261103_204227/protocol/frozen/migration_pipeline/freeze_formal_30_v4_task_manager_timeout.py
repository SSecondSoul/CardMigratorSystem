"""Freeze the isolated TaskManager generation timeout before resuming its checkpoint."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BATCH = "formal_30_v4_task_manager_manual_followup"
SUMMARY = ROOT / f"data/experiments/batch_reports/{BATCH}_summary.json"
CONFIG = ROOT / f"migration_pipeline/batch_configs/{BATCH}.json"
SOURCE = ROOT / (
    "data/experiments/protocols/formal_30_v3_frozen_20261022/frozen/"
    "data/datasets/components/03_complex/TaskManager/vue/TaskManager.vue"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy(source: Path, target: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def main() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    if summary.get("batch_id") != BATCH or len(summary.get("samples", [])) != 1:
        raise RuntimeError("Unexpected batch summary")
    sample = summary["samples"][0]
    if sample.get("id") != "TaskManager" or sample.get("status") != "error":
        raise RuntimeError("TaskManager is not an execution error")
    if "The read operation timed out" not in sample.get("error_message", ""):
        raise RuntimeError("This is not the expected generation timeout")
    if summary["aggregate"]["completed"] != 0 or summary["aggregate"]["execution_errors"] != 1:
        raise RuntimeError("Unexpected aggregate counts")

    stamp = datetime.fromisoformat(sample["finished_at"]).strftime("%Y%m%d_%H%M%S")
    target = ROOT / "data/experiments/snapshots" / f"{BATCH}_generation_timeout_{stamp}"
    if target.exists():
        raise FileExistsError(target)
    target.mkdir(parents=True)

    copy(SUMMARY, target / SUMMARY.name)
    copy(CONFIG, target / CONFIG.name)
    copy(SOURCE, target / "source/TaskManager.vue")
    code_files = [
        "local_server/config.py",
        "local_server/api/evaluation_routes.py",
        "migration_pipeline/config.py",
        "migration_pipeline/generation_client.py",
        "migration_pipeline/run_batch_pipeline.py",
        "migration_pipeline/stages/validate.py",
        "migration_pipeline/utils/repair_prompt.py",
        "migration_pipeline/freeze_formal_30_v4_task_manager_timeout.py",
    ]
    for relative in code_files:
        copy(ROOT / relative, target / "code" / relative)

    manifest = {
        "snapshot_id": target.name,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "batch_id": BATCH,
        "sample_id": "TaskManager",
        "classification": "development_manual_audit_followup_generation_timeout",
        "not_independent_holdout": True,
        "status": "generation_request_execution_error",
        "started_at": sample["started_at"],
        "finished_at": sample["finished_at"],
        "elapsed_seconds": sample["elapsed_seconds"],
        "error_type": sample["error_type"],
        "error_message": sample["error_message"],
        "generated_artifact": None,
        "source_sha256": sha256(SOURCE),
        "prior_frozen_artifact": (
            "data/experiments/snapshots/formal_30_v4_deferred_task_manager_pass_20261023_190805/"
            "pipeline/complex/TaskManager_repaired_repaired_repaired.san"
        ),
        "boundary": "This records a failed request, not a completed migration or manual browser result.",
        "integrity_file": "SHA256SUMS.txt",
    }
    (target / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    files = sorted(path for path in target.rglob("*") if path.is_file())
    (target / "SHA256SUMS.txt").write_text(
        "\n".join(f"{sha256(path)}  {path.relative_to(target).as_posix()}" for path in files) + "\n",
        encoding="utf-8",
    )
    for line in (target / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        if sha256(target / relative) != expected:
            raise RuntimeError(f"Snapshot verification failed: {relative}")
    print(f"frozen: {target.relative_to(ROOT)} ({len(files)} verified payload files)")


if __name__ == "__main__":
    main()
