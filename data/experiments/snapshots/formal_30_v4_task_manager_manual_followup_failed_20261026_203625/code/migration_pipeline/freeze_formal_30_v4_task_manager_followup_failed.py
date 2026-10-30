"""Freeze the terminal TaskManager follow-up failure before diagnosis."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BATCH = "formal_30_v4_task_manager_manual_followup"
SAMPLE = "TaskManager"
SUMMARY = ROOT / f"data/experiments/batch_reports/{BATCH}_summary.json"
CONFIG = ROOT / f"migration_pipeline/batch_configs/{BATCH}.json"
SOURCE = ROOT / (
    "data/experiments/protocols/formal_30_v3_frozen_20261022/frozen/"
    "data/datasets/components/03_complex/TaskManager/vue/TaskManager.vue"
)
PIPELINE = ROOT / f"data/experiments/pipeline/batches/{BATCH}/complex"
REPORT = ROOT / f"data/experiments/repair_reports/batches/{BATCH}/complex/{SAMPLE}_repair_history.json"


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
    if sample.get("id") != SAMPLE or sample.get("status") != "completed":
        raise RuntimeError("TaskManager is not a completed attempt")
    if sample.get("final_passed") or sample.get("stop_reason") != "max_repair_rounds_reached":
        raise RuntimeError("TaskManager is not the expected terminal failure")
    if sample.get("final_validation_error_codes") != ["invalid_san_computed_instance_method_call"]:
        raise RuntimeError("Unexpected final validation errors")
    if summary["aggregate"]["completed"] != 1 or summary["aggregate"]["failed"] != 1:
        raise RuntimeError("Unexpected aggregate counts")

    artifacts = [
        PIPELINE / f"{SAMPLE}{'_repaired' * index}.san"
        for index in range(sample["repair_rounds"] + 1)
    ]
    for path in [SUMMARY, CONFIG, SOURCE, REPORT, *artifacts]:
        if not path.is_file():
            raise FileNotFoundError(path)

    stamp = datetime.fromisoformat(sample["finished_at"]).strftime("%Y%m%d_%H%M%S")
    target = ROOT / "data/experiments/snapshots" / f"{BATCH}_failed_{stamp}"
    if target.exists():
        raise FileExistsError(target)
    target.mkdir(parents=True)
    copy(SUMMARY, target / SUMMARY.name)
    copy(CONFIG, target / CONFIG.name)
    copy(SOURCE, target / "source/TaskManager.vue")
    copy(REPORT, target / "repair_reports/complex/TaskManager_repair_history.json")
    for path in artifacts:
        copy(path, target / "pipeline/complex" / path.name)
    code_files = [
        "local_server/api/evaluation_routes.py",
        "migration_pipeline/stages/repair.py",
        "migration_pipeline/stages/validate.py",
        "migration_pipeline/utils/repair_prompt.py",
        "migration_pipeline/utils/san_compile.py",
        "migration_pipeline/utils/san_render.py",
        "tests/test_migration_pipeline_regressions.py",
        "tests/test_repair_prompt_and_loop.py",
        "migration_pipeline/freeze_formal_30_v4_task_manager_followup_failed.py",
    ]
    for relative in code_files:
        copy(ROOT / relative, target / "code" / relative)

    manifest = {
        "snapshot_id": target.name,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "batch_id": BATCH,
        "sample_id": SAMPLE,
        "classification": "development_manual_audit_followup_failed",
        "not_independent_holdout": True,
        "status": "frozen_terminal_automatic_failure",
        "prior_timeout_snapshot": (
            "formal_30_v4_task_manager_manual_followup_generation_timeout_20261026_201844"
        ),
        "prior_browser_rejected_artifact": (
            "data/experiments/snapshots/formal_30_v4_deferred_task_manager_pass_20261023_190805/"
            "pipeline/complex/TaskManager_repaired_repaired_repaired.san"
        ),
        "source_sha256": sha256(SOURCE),
        "result": {
            key: sample.get(key)
            for key in (
                "started_at", "finished_at", "final_passed", "stop_reason", "repair_rounds",
                "generation_tokens", "repair_tokens", "total_tokens",
                "final_validation_error_codes", "final_visual_error_codes",
                "final_structure_similarity", "final_tag_sequence_similarity",
                "final_text_similarity", "final_tree_edit_distance", "interaction_eval_passed",
            )
        },
        "artifact_selection": [path.name for path in artifacts],
        "boundary": "This is a failed reused development case, not an independent holdout result or manual browser pass.",
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
