"""Freeze the single-sample development regression inputs before the LLM run."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ID = "formal_30_v4_analytics_chart_reactivity_regression_v1_pre_run_20261027_164749"
TARGET = ROOT / "data/experiments/snapshots" / SNAPSHOT_ID
CONFIG = Path("migration_pipeline/batch_configs/formal_30_v4_analytics_chart_reactivity_regression_v1.json")
OUTPUT = ROOT / "data/experiments/pipeline/batches/formal_30_v4_analytics_chart_reactivity_regression_v1"
REPORTS = ROOT / "data/experiments/repair_reports/batches/formal_30_v4_analytics_chart_reactivity_regression_v1"
SUMMARY = ROOT / "data/experiments/batch_reports/formal_30_v4_analytics_chart_reactivity_regression_v1_summary.json"
FILES = [
    CONFIG,
    Path("migration_pipeline/run_batch_pipeline.py"),
    Path("migration_pipeline/config.py"),
    Path("migration_pipeline/orchestrator.py"),
    Path("migration_pipeline/generation_client.py"),
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
    Path("tests/test_migration_pipeline_regressions.py"),
    Path("tests/test_repair_prompt_and_loop.py"),
    Path("tests/test_analytics_chart_reactivity_fix.py"),
    Path("tests/diagnostics/analytics_chart_period_probe.cjs"),
    Path("migration_pipeline/freeze_formal_30_v4_analytics_chart_reactivity_regression_pre_run.py"),
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
    if config.get("batch_id") != "formal_30_v4_analytics_chart_reactivity_regression_v1":
        raise RuntimeError("Unexpected batch id")
    samples = config.get("samples", [])
    if len(samples) != 1 or samples[0].get("id") != "analytics_dashboard":
        raise RuntimeError("Expected only the AnalyticsDashboard development sample")
    source = Path(samples[0]["vue_file"])
    source_path = (ROOT / source).resolve()
    if not source_path.is_relative_to(ROOT) or not source_path.is_file():
        raise RuntimeError(f"Missing source: {source}")
    if sha256(source_path) != samples[0]["source_sha256"]:
        raise RuntimeError("Frozen Vue source hash mismatch")
    previous = ROOT / "data/experiments/snapshots/formal_30_v4_analytics_chart_reactivity_v3_manual_geometry_pass_20261027_164258/manifest.json"
    previous_manifest = json.loads(previous.read_text(encoding="utf-8"))
    if previous_manifest.get("v3_browser_geometry_result") != "user_reported_pass_7d_and_90d":
        raise RuntimeError("Preceding manual repair evidence is incomplete")

    payloads = list(dict.fromkeys([*FILES, source]))
    for relative in payloads:
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise RuntimeError(f"Missing payload: {relative}")
    git_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    git_dirty = bool(subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True).strip())
    TARGET.mkdir(parents=True)
    for relative in payloads:
        destination = TARGET / (Path("source") / "AnalyticsDashboard.vue" if relative == source else Path("payload") / relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    shutil.copy2(previous, TARGET / "prior_manual_repair_manifest.json")
    manifest = {
        "snapshot_id": SNAPSHOT_ID,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "classification": "reused_development_regression_pre_run",
        "independent_holdout": False,
        "batch_id": config["batch_id"],
        "sample_ids": ["analytics_dashboard"],
        "batch_config_sha256": sha256(ROOT / CONFIG),
        "source_sha256": sha256(source_path),
        "source_payload": "source/AnalyticsDashboard.vue",
        "git_head": git_head,
        "worktree_clean": not git_dirty,
        "test_evidence": "138/138 unittest passed before this pre-run; the new one-sample config passed --dry-run",
        "output_paths_empty_at_freeze": True,
        "prior_manual_repair": previous_manifest["snapshot_id"],
        "boundaries": [
            "This captures the input and implementation bytes before an LLM source-to-San development rerun.",
            "Copied files, rather than potentially dirty Git HEAD, define this run.",
            "The previous hand-repaired San candidate is evidence only, not a pipeline input.",
            "This is not an independent formal-test result and does not overwrite prior checkpoints.",
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
