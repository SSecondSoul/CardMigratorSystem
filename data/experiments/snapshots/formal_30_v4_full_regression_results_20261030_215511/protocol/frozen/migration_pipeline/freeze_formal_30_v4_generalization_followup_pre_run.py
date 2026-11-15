"""Freeze local development-regression inputs before the LLM rerun.

This is a targeted implementation snapshot, not the independent-test protocol.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ID = "formal_30_v4_generalization_followup_pre_run_20261027_v2"
TARGET = ROOT / "data/experiments/snapshots" / SNAPSHOT_ID
BATCH = Path("migration_pipeline/batch_configs/formal_30_v4_generalization_followup.json")
FILES = [
    BATCH,
    Path("migration_pipeline/interaction_configs/formal_30_v4_runtime_acceptance.json"),
    Path("tests/manual/formal-30-v4-runtime-acceptance.html"),
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
    Path("data/experiments/analysis/formal_30_v4_generalization_gap_audit_20261027/IMPLEMENTATION_LOG.md"),
    Path("migration_pipeline/freeze_formal_30_v4_generalization_followup_pre_run.py"),
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if TARGET.exists():
        raise FileExistsError(f"Snapshot already exists: {TARGET}")
    batch = json.loads((ROOT / BATCH).read_text(encoding="utf-8"))
    if batch["batch_id"] != "formal_30_v4_generalization_followup":
        raise RuntimeError("Unexpected batch id")
    sources = [Path(sample["vue_file"]) for sample in batch["samples"]]
    for sample, relative in zip(batch["samples"], sources):
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise RuntimeError(f"Missing source: {relative}")
        if sha256(path) != sample["source_sha256"]:
            raise RuntimeError(f"Source hash mismatch: {relative}")

    payloads = list(dict.fromkeys([*FILES, *sources]))
    for relative in payloads:
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise RuntimeError(f"Missing payload: {relative}")

    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    status = subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True).splitlines()
    TARGET.mkdir(parents=True)
    source_destinations = {
        relative: Path("sources") / f"{sample['id']}.vue"
        for sample, relative in zip(batch["samples"], sources)
    }
    for relative in payloads:
        destination = TARGET / source_destinations.get(relative, Path("payload") / relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)

    manifest = {
        "snapshot_id": SNAPSHOT_ID,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "classification": "reused_development_regression_pre_run",
        "independent_holdout": False,
        "batch_id": batch["batch_id"],
        "batch_config_sha256": sha256(ROOT / BATCH),
        "sample_ids": [sample["id"] for sample in batch["samples"]],
        "source_payload_paths": {
            sample["id"]: source_destinations[relative].as_posix()
            for sample, relative in zip(batch["samples"], sources)
        },
        "git_head": head,
        "worktree_clean": not bool(status),
        "worktree_status_at_freeze": status,
        "test_evidence": "112/112 unittest passed; four reviewed browser baselines passed and four historical failures were rejected on 2026-10-27",
        "boundaries": [
            "This is an implementation and input snapshot before any new LLM batch run.",
            "The code may contain uncommitted worktree changes; copied bytes, not Git HEAD, define this run.",
            "The browser acceptance page checks selected San runtime invariants, not complete Vue/San parity.",
            "Previously frozen results and independent holdout data are not modified.",
        ],
        "integrity_file": "SHA256SUMS.txt",
    }
    (TARGET / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    files = sorted(path for path in TARGET.rglob("*") if path.is_file())
    (TARGET / "SHA256SUMS.txt").write_text(
        "\n".join(
            f"{sha256(path)}  {path.relative_to(TARGET).as_posix()}" for path in files
        ) + "\n",
        encoding="utf-8",
    )
    for line in (TARGET / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        if sha256(TARGET / relative) != expected:
            raise RuntimeError(f"Snapshot checksum mismatch: {relative}")
    print(f"frozen: {TARGET.relative_to(ROOT)} ({len(files)} verified payloads)")


if __name__ == "__main__":
    main()
