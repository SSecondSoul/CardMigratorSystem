"""Freeze the source-event TaskManager development regression before model use."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BATCH_ID = "formal_30_v4_task_manager_source_events_regression_v1"
TARGET = ROOT / "data/experiments/snapshots" / f"{BATCH_ID}_pre_run_20261029"
CONFIG = Path("migration_pipeline/batch_configs") / f"{BATCH_ID}.json"
OUTPUT = ROOT / "data/experiments/pipeline/batches" / BATCH_ID
REPORTS = ROOT / "data/experiments/repair_reports/batches" / BATCH_ID
SUMMARY = ROOT / "data/experiments/batch_reports" / f"{BATCH_ID}_summary.json"
AUTOMATIC = ROOT / "data/experiments/snapshots/formal_30_v4_task_manager_five_residual_regression_v1_TaskManager_automatic_pass_20261029_200650"
MANUAL = ROOT / "data/experiments/snapshots/formal_30_v4_task_manager_source_events_manual_pass_20261029_215547"
FILES = [
    CONFIG,
    Path("migration_pipeline/freeze_formal_30_v4_task_manager_source_events_regression_pre_run.py"),
    Path("migration_pipeline/run_batch_pipeline.py"),
    Path("migration_pipeline/run_pipeline.py"),
    Path("migration_pipeline/config.py"),
    Path("migration_pipeline/orchestrator.py"),
    Path("migration_pipeline/generation_client.py"),
    Path("migration_pipeline/repair_client.py"),
    Path("migration_pipeline/stages/generate.py"),
    Path("migration_pipeline/stages/repair.py"),
    Path("migration_pipeline/stages/validate.py"),
    Path("migration_pipeline/stages/visual_eval.py"),
    Path("migration_pipeline/utils/source_event_semantics.py"),
    Path("migration_pipeline/utils/repair_prompt.py"),
    Path("migration_pipeline/utils/repair_regression_guard.py"),
    Path("migration_pipeline/utils/interaction_eval.py"),
    Path("migration_pipeline/utils/san_compile.py"),
    Path("migration_pipeline/utils/san_render.py"),
    Path("migration_pipeline/utils/vue_render.py"),
    Path("migration_pipeline/utils/dom_compare.py"),
    Path("local_server/api/migration_routes.py"),
    Path("local_server/api/evaluation_routes.py"),
    Path("local_server/config.py"),
    Path("tests/test_source_event_semantics.py"),
    Path("tests/test_repair_prompt_and_loop.py"),
    Path("tests/test_migration_pipeline_regressions.py"),
    Path("tests/test_monitoring_remaining_bounded_fix.py"),
    Path("tests/test_repair_regression_guard.py"),
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(directory: Path) -> None:
    for line in (directory / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        if sha256(directory / relative) != expected:
            raise RuntimeError(f"Frozen evidence mismatch: {directory / relative}")


def main() -> None:
    for target in (TARGET, OUTPUT, REPORTS, SUMMARY):
        if target.exists():
            raise FileExistsError(f"Unused pre-run path required: {target}")
    verify(AUTOMATIC)
    verify(MANUAL)
    config = json.loads((ROOT / CONFIG).read_text(encoding="utf-8"))
    manual = json.loads((MANUAL / "manifest.json").read_text(encoding="utf-8"))
    automatic = json.loads((AUTOMATIC / "manifest.json").read_text(encoding="utf-8"))
    samples = config.get("samples", [])
    if (config.get("batch_id") != BATCH_ID
            or config.get("max_repair_rounds") != 5
            or len(samples) != 1
            or samples[0].get("id") != "TaskManager"
            or config.get("prior_manual_pass_snapshot") != MANUAL.name
            or config.get("prior_automatic_snapshot") != AUTOMATIC.name
            or manual.get("browser_review") != "passed_by_user"
            or automatic.get("automatic_passed") is not True):
        raise RuntimeError("Expected frozen one-sample development regression lineage")
    source = (ROOT / samples[0]["vue_file"]).resolve()
    if not source.is_relative_to(ROOT) or not source.is_file():
        raise FileNotFoundError(source)
    if sha256(source) != samples[0]["source_sha256"]:
        raise RuntimeError("Frozen Vue source hash mismatch")
    for relative in FILES:
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise FileNotFoundError(path)
    git_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    worktree_dirty = bool(subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True).strip())
    TARGET.mkdir(parents=True)
    shutil.copy2(source, TARGET / "source.vue")
    for name, prior in {
        "prior_automatic_manifest.json": AUTOMATIC / "manifest.json",
        "prior_manual_manifest.json": MANUAL / "manifest.json",
        "prior_manual_review.json": MANUAL / "manual_review.json",
    }.items():
        shutil.copy2(prior, TARGET / name)
    for relative in FILES:
        destination = TARGET / "payload" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    manifest = {
        "snapshot_id": TARGET.name,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "classification": "reused_development_regression_pre_run",
        "independent_holdout": False,
        "batch_id": BATCH_ID,
        "sample_ids": ["TaskManager"],
        "batch_config_sha256": sha256(ROOT / CONFIG),
        "source_sha256": sha256(source),
        "source_payload": "source.vue",
        "prior_automatic_snapshot": AUTOMATIC.name,
        "prior_manual_pass_snapshot": MANUAL.name,
        "git_head": git_head,
        "worktree_clean": not worktree_dirty,
        "test_evidence": "213/213 unittest tests passed; one-sample --dry-run passed",
        "max_repair_rounds": 5,
        "output_paths_empty_at_freeze": True,
        "boundaries": [
            "Reused development sample; not independent formal-test evidence.",
            "Prior manually accepted San is evidence only, not generation input.",
            "The fifth round is a cap for a bounded event repair, not an automatic pass exemption.",
            "Copied payload bytes, not potentially dirty Git HEAD, define the pipeline version.",
            "Use new output paths without --force and preserve previous checkpoints.",
            "Static/visual result and browser manual acceptance remain separate outcomes.",
        ],
        "integrity_file": "SHA256SUMS.txt",
    }
    (TARGET / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    payloads = sorted(path for path in TARGET.rglob("*") if path.is_file())
    (TARGET / "SHA256SUMS.txt").write_text(
        "\n".join(f"{sha256(path)}  {path.relative_to(TARGET).as_posix()}" for path in payloads) + "\n",
        encoding="utf-8",
    )
    verify(TARGET)
    print(f"frozen: {TARGET.relative_to(ROOT)} ({len(payloads)} verified payloads)")
    print(f"config_sha256: {manifest['batch_config_sha256']}")
    print(f"source_sha256: {manifest['source_sha256']}")
    print("model_request_performed: false")


if __name__ == "__main__":
    main()
