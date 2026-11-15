"""Freeze the one-sample TaskManager development regression before model use."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from migration_pipeline.probe_formal_30_v4_task_manager_semantic_focus_v2 import (
    sha256,
    verify_checksums,
)


BATCH_ID = "formal_30_v4_task_manager_boolean_event_regression_v1"
SNAPSHOT_ID = f"{BATCH_ID}_pre_run_20261028"
TARGET = ROOT / "data/experiments/snapshots" / SNAPSHOT_ID
CONFIG = Path("migration_pipeline/batch_configs") / f"{BATCH_ID}.json"
OUTPUT = ROOT / "data/experiments/pipeline/batches" / BATCH_ID
REPORTS = ROOT / "data/experiments/repair_reports/batches" / BATCH_ID
SUMMARY = ROOT / "data/experiments/batch_reports" / f"{BATCH_ID}_summary.json"
PRIOR = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_task_manager_event_boolean_offline_pass_20261028_210032"
)
FILES = [
    CONFIG,
    Path("migration_pipeline/freeze_formal_30_v4_task_manager_boolean_event_regression_pre_run.py"),
    Path("migration_pipeline/run_batch_pipeline.py"),
    Path("migration_pipeline/config.py"),
    Path("migration_pipeline/orchestrator.py"),
    Path("migration_pipeline/generation_client.py"),
    Path("migration_pipeline/repair_client.py"),
    Path("migration_pipeline/stages/generate.py"),
    Path("migration_pipeline/stages/repair.py"),
    Path("migration_pipeline/stages/validate.py"),
    Path("migration_pipeline/stages/visual_eval.py"),
    Path("migration_pipeline/utils/repair_prompt.py"),
    Path("migration_pipeline/utils/repair_regression_guard.py"),
    Path("migration_pipeline/utils/san_compile.py"),
    Path("migration_pipeline/utils/san_render.py"),
    Path("migration_pipeline/utils/vue_render.py"),
    Path("migration_pipeline/utils/dom_compare.py"),
    Path("local_server/api/migration_routes.py"),
    Path("local_server/api/evaluation_routes.py"),
    Path("local_server/config.py"),
    Path("tests/test_repair_regression_guard.py"),
    Path("tests/test_repair_prompt_and_loop.py"),
    Path("tests/test_semantic_residual_repair_prompt.py"),
    Path("tests/test_migration_pipeline_regressions.py"),
]


def main() -> None:
    for path in (TARGET, OUTPUT, REPORTS, SUMMARY):
        if path.exists():
            raise FileExistsError(f"Pre-run requires an unused target: {path}")
    verify_checksums(PRIOR)
    prior_manifest = json.loads((PRIOR / "manifest.json").read_text(encoding="utf-8"))
    if prior_manifest.get("offline_replay_passed") is not True:
        raise RuntimeError("Prior bounded offline replay did not pass")
    config = json.loads((ROOT / CONFIG).read_text(encoding="utf-8"))
    samples = config.get("samples", [])
    if (config.get("batch_id") != BATCH_ID or len(samples) != 1
            or samples[0].get("id") != "TaskManager"):
        raise RuntimeError("Expected only frozen development TaskManager")
    source_relative = Path(samples[0]["vue_file"])
    source = (ROOT / source_relative).resolve()
    if not source.is_relative_to(ROOT) or not source.is_file():
        raise FileNotFoundError(source)
    if sha256(source) != samples[0]["source_sha256"]:
        raise RuntimeError("Frozen Vue source hash mismatch")
    for relative in FILES:
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise FileNotFoundError(path)
    git_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True).strip())
    TARGET.mkdir(parents=True)
    shutil.copy2(source, TARGET / "source.vue")
    shutil.copy2(PRIOR / "manifest.json", TARGET / "prior_offline_manifest.json")
    shutil.copy2(PRIOR / "SHA256SUMS.txt", TARGET / "prior_offline_SHA256SUMS.txt")
    for relative in FILES:
        destination = TARGET / "payload" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    manifest = {
        "snapshot_id": SNAPSHOT_ID,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "classification": "reused_development_regression_pre_run",
        "independent_holdout": False,
        "batch_id": BATCH_ID,
        "sample_ids": ["TaskManager"],
        "batch_config_sha256": sha256(ROOT / CONFIG),
        "source_sha256": sha256(source),
        "source_payload": "source.vue",
        "prior_offline_replay": prior_manifest["snapshot_id"],
        "git_head": git_head,
        "worktree_clean": not dirty,
        "test_evidence": "193/193 full unittest tests passed; one-sample --dry-run passed",
        "output_paths_empty_at_freeze": True,
        "boundaries": [
            "The source is reused development material, not independent holdout evidence.",
            "The prior hand-repaired San replay is evidence only, not batch input.",
            "Copied payload bytes, not potentially dirty Git HEAD, define this run.",
            "Use new output paths without --force; do not overwrite prior checkpoints.",
            "Automatic result and browser manual acceptance remain separate outcomes.",
        ],
        "integrity_file": "SHA256SUMS.txt",
    }
    (TARGET / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    payloads = sorted(path for path in TARGET.rglob("*") if path.is_file())
    (TARGET / "SHA256SUMS.txt").write_text(
        "\n".join(f"{sha256(path)}  {path.relative_to(TARGET).as_posix()}" for path in payloads) + "\n",
        encoding="utf-8",
    )
    verify_checksums(TARGET)
    print(f"frozen: {TARGET.relative_to(ROOT)} ({len(payloads)} verified payloads)")
    print(f"config_sha256: {manifest['batch_config_sha256']}")
    print(f"source_sha256: {manifest['source_sha256']}")
    print("model_request_performed: false")


if __name__ == "__main__":
    main()
