"""Freeze the two remaining development-regression samples before LLM work."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ID = "formal_30_v4_generalization_remaining_v1_pre_run_20261027_190033"
TARGET = ROOT / "data/experiments/snapshots" / SNAPSHOT_ID
CONFIG = Path("migration_pipeline/batch_configs/formal_30_v4_generalization_remaining_v1.json")
OUTPUT = ROOT / "data/experiments/pipeline/batches/formal_30_v4_generalization_remaining_v1"
REPORTS = ROOT / "data/experiments/repair_reports/batches/formal_30_v4_generalization_remaining_v1"
SUMMARY = ROOT / "data/experiments/batch_reports/formal_30_v4_generalization_remaining_v1_summary.json"
FILES = [
    CONFIG,
    Path("migration_pipeline/interaction_configs/formal_30_v4_runtime_acceptance.json"),
    Path("tests/manual/formal-30-v4-runtime-acceptance.js"),
    Path("tests/test_formal_30_v4_runtime_acceptance.py"),
    Path("tests/test_migration_pipeline_regressions.py"),
    Path("tests/test_repair_prompt_and_loop.py"),
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
    Path("migration_pipeline/freeze_formal_30_v4_generalization_remaining_pre_run.py"),
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if TARGET.exists():
        raise FileExistsError(f"Snapshot already exists: {TARGET}")
    for path in (OUTPUT, REPORTS, SUMMARY):
        if path.exists():
            raise FileExistsError(f"Regression output path already exists: {path}")
    config = json.loads((ROOT / CONFIG).read_text(encoding="utf-8"))
    if config.get("batch_id") != "formal_30_v4_generalization_remaining_v1":
        raise RuntimeError("Unexpected batch id")
    samples = config.get("samples", [])
    if [sample.get("id") for sample in samples] != ["TaskManager", "MonitoringDashboard"]:
        raise RuntimeError("Unexpected sample order")
    sources = [Path(sample["vue_file"]) for sample in samples]
    for sample, relative in zip(samples, sources):
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise RuntimeError(f"Missing frozen Vue source: {relative}")
        if sha256(path) != sample["source_sha256"]:
            raise RuntimeError(f"Frozen Vue source hash mismatch: {relative}")

    payloads = list(dict.fromkeys([*FILES, *sources]))
    for relative in payloads:
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise RuntimeError(f"Missing payload: {relative}")
    git_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    git_dirty = bool(subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True).strip())
    source_destinations = {
        relative: Path("sources") / f"{sample['id']}.vue"
        for sample, relative in zip(samples, sources)
    }
    TARGET.mkdir(parents=True)
    for relative in payloads:
        destination = TARGET / source_destinations.get(relative, Path("payload") / relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    manifest = {
        "snapshot_id": SNAPSHOT_ID,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "classification": "reused_development_regression_pre_run",
        "independent_holdout": False,
        "batch_id": config["batch_id"],
        "batch_config_sha256": sha256(ROOT / CONFIG),
        "sample_ids": [sample["id"] for sample in samples],
        "source_payload_paths": {
            sample["id"]: source_destinations[relative].as_posix()
            for sample, relative in zip(samples, sources)
        },
        "git_head": git_head,
        "worktree_clean": not git_dirty,
        "test_evidence": "140/140 unittest passed; TaskManager selection passed --dry-run; local_server /health ok with qwen-plus",
        "output_paths_empty_at_freeze": True,
        "boundaries": [
            "The two samples reuse diagnosed development sources, not the independent holdout.",
            "Copied implementation bytes, not potentially dirty Git HEAD, define this run.",
            "Run one sample at a time and preserve the summary checkpoint; do not use --force.",
            "No prior batch output or frozen result is overwritten.",
        ],
        "integrity_file": "SHA256SUMS.txt",
    }
    (TARGET / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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
