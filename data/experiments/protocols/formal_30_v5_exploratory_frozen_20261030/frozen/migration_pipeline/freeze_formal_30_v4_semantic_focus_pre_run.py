"""Freeze exact inputs and implementation before the semantic-focus regression."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BATCH_ID = "formal_30_v4_semantic_focus_v1"
SNAPSHOT_ID = f"{BATCH_ID}_pre_run_20261027"
TARGET = ROOT / "data/experiments/snapshots" / SNAPSHOT_ID
CONFIG = Path("migration_pipeline/batch_configs") / f"{BATCH_ID}.json"
TEST_EVIDENCE = "4/4 semantic prompt tests and 165/165 full unittest tests passed; TaskManager --dry-run passed"
PAYLOADS = [
    CONFIG,
    Path("data/experiments/analysis/formal_30_v4_generalization_gap_audit_20261027/semantic_focus_v1_pre_run.json"),
    Path("migration_pipeline/interaction_configs/formal_30_v4_runtime_acceptance.json"),
    Path("migration_pipeline/run_batch_pipeline.py"),
    Path("migration_pipeline/config.py"),
    Path("migration_pipeline/generation_client.py"),
    Path("migration_pipeline/orchestrator.py"),
    Path("migration_pipeline/stages/generate.py"),
    Path("migration_pipeline/stages/repair.py"),
    Path("migration_pipeline/stages/validate.py"),
    Path("migration_pipeline/stages/visual_eval.py"),
    Path("migration_pipeline/utils/repair_prompt.py"),
    Path("migration_pipeline/utils/san_compile.py"),
    Path("migration_pipeline/utils/san_render.py"),
    Path("migration_pipeline/utils/vue_render.py"),
    Path("migration_pipeline/utils/dom_compare.py"),
    Path("local_server/api/evaluation_routes.py"),
    Path("local_server/config.py"),
    Path("tests/test_semantic_residual_repair_prompt.py"),
    Path("tests/test_repair_prompt_and_loop.py"),
    Path("tests/test_migration_pipeline_regressions.py"),
    Path("migration_pipeline/freeze_formal_30_v4_semantic_focus_pre_run.py"),
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output_paths = [
        ROOT / "data/experiments/pipeline/batches" / BATCH_ID,
        ROOT / "data/experiments/repair_reports/batches" / BATCH_ID,
        ROOT / "data/experiments/batch_reports" / f"{BATCH_ID}_summary.json",
    ]
    for path in [TARGET, *output_paths]:
        if path.exists():
            raise FileExistsError(f"Pre-run freeze requires an unused target: {path}")

    config = json.loads((ROOT / CONFIG).read_text(encoding="utf-8"))
    samples = config.get("samples", [])
    if config.get("batch_id") != BATCH_ID or [s.get("id") for s in samples] != [
        "TaskManager", "MonitoringDashboard"
    ]:
        raise RuntimeError("Unexpected batch identity or sample order")
    source_destinations: dict[Path, Path] = {}
    for sample in samples:
        relative = Path(sample["vue_file"])
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise RuntimeError(f"Missing frozen Vue source: {relative}")
        if sha256(path) != sample["source_sha256"]:
            raise RuntimeError(f"Frozen Vue source hash mismatch: {relative}")
        source_destinations[relative] = Path("sources") / f"{sample['id']}.vue"

    paths = list(dict.fromkeys([*PAYLOADS, *source_destinations]))
    for relative in paths:
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise RuntimeError(f"Missing payload: {relative}")

    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True).strip())
    TARGET.mkdir(parents=True)
    for relative in paths:
        destination = TARGET / source_destinations.get(relative, Path("payload") / relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)

    manifest = {
        "snapshot_id": SNAPSHOT_ID,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "classification": "reused_development_regression_pre_run",
        "independent_holdout": False,
        "batch_id": BATCH_ID,
        "batch_config_sha256": sha256(ROOT / CONFIG),
        "sample_ids": [sample["id"] for sample in samples],
        "source_payload_paths": {
            sample["id"]: source_destinations[Path(sample["vue_file"])].as_posix()
            for sample in samples
        },
        "git_head": head,
        "worktree_clean": not dirty,
        "test_evidence": TEST_EVIDENCE,
        "output_paths_empty_at_freeze": True,
        "boundaries": [
            "These are reused development sources, not independent holdout cases.",
            "Copied implementation bytes, not potentially dirty Git HEAD, define this run.",
            "Run one sample at a time without --force and keep the summary checkpoint.",
            "Prior batch outputs and frozen failure evidence are not overwritten.",
        ],
        "integrity_file": "SHA256SUMS.txt",
    }
    (TARGET / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    files = sorted(path for path in TARGET.rglob("*") if path.is_file())
    (TARGET / "SHA256SUMS.txt").write_text(
        "\n".join(f"{sha256(path)}  {path.relative_to(TARGET).as_posix()}" for path in files) + "\n",
        encoding="utf-8",
    )
    for line in (TARGET / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        if sha256(TARGET / relative) != expected:
            raise RuntimeError(f"Snapshot checksum mismatch: {relative}")
    print(f"frozen: {TARGET.relative_to(ROOT)} ({len(files)} verified payloads)")


if __name__ == "__main__":
    main()
