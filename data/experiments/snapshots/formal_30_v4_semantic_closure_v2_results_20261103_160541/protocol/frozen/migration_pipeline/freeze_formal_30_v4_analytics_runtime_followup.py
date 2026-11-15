"""Freeze the isolated AnalyticsDashboard runtime follow-up before browser review."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BATCH = "formal_30_v4_analytics_runtime_followup"
SAMPLE = "AnalyticsDashboard"
SUMMARY = ROOT / f"data/experiments/batch_reports/{BATCH}_summary.json"
CONFIG = ROOT / f"migration_pipeline/batch_configs/{BATCH}.json"
PIPELINE = ROOT / f"data/experiments/pipeline/batches/{BATCH}/complex"
REPORT = ROOT / f"data/experiments/repair_reports/batches/{BATCH}/complex/{SAMPLE}_repair_history.json"
SOURCE = ROOT / (
    "data/experiments/protocols/formal_30_v3_frozen_20261022/frozen/"
    "data/datasets/components/03_complex/AnalyticsDashboard/vue/AnalyticsDashboard.vue"
)
PRIOR_SNAPSHOT = "formal_30_v4_analytics_manual_followup_automatic_pass_20261026_152546"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy(source: Path, target: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def main() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    if summary["batch_id"] != BATCH or len(summary["samples"]) != 1:
        raise RuntimeError("Unexpected batch summary")
    sample = summary["samples"][0]
    if sample["id"] != "analytics_dashboard" or sample["status"] != "completed":
        raise RuntimeError("Unexpected sample result")
    if not sample["final_passed"] or sample["final_validation_error_codes"] or sample["final_visual_error_codes"]:
        raise RuntimeError("The runtime follow-up is not an automatic pass")
    artifacts = [
        PIPELINE / f"{SAMPLE}{'_repaired' * index}.san"
        for index in range(sample["repair_rounds"] + 1)
    ]
    required = [SUMMARY, CONFIG, REPORT, SOURCE, *artifacts]
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)

    stamp = datetime.fromisoformat(sample["finished_at"]).strftime("%Y%m%d_%H%M%S")
    target = ROOT / "data/experiments/snapshots" / f"{BATCH}_automatic_pass_{stamp}"
    if target.exists():
        raise FileExistsError(target)
    target.mkdir(parents=True)
    for path in (SUMMARY, CONFIG):
        copy(path, target / path.name)
    copy(SOURCE, target / "source/AnalyticsDashboard.vue")
    copy(REPORT, target / "repair_reports/complex/AnalyticsDashboard_repair_history.json")
    for path in artifacts:
        copy(path, target / "pipeline/complex" / path.name)

    code_files = [
        "local_server/api/evaluation_routes.py",
        "migration_pipeline/stages/validate.py",
        "migration_pipeline/stages/repair.py",
        "migration_pipeline/utils/san_compile.py",
        "migration_pipeline/utils/san_render.py",
        "migration_pipeline/utils/repair_prompt.py",
        "tests/test_migration_pipeline_regressions.py",
        "tests/test_repair_prompt_and_loop.py",
        "migration_pipeline/freeze_formal_30_v4_analytics_runtime_followup.py",
    ]
    for relative in code_files:
        copy(ROOT / relative, target / "code" / relative)

    manifest = {
        "snapshot_id": target.name,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "batch_id": BATCH,
        "sample_id": "analytics_dashboard",
        "classification": "development_manual_runtime_audit_followup",
        "not_independent_holdout": True,
        "status": "frozen_automatic_pass_pending_manual_browser_review",
        "prior_frozen_artifact": (
            f"data/experiments/snapshots/{PRIOR_SNAPSHOT}/"
            "pipeline/complex/AnalyticsDashboard_repaired_repaired.san"
        ),
        "source_sha256": digest(SOURCE),
        "result": {
            key: sample.get(key)
            for key in (
                "started_at", "finished_at", "final_passed", "stop_reason", "repair_rounds",
                "generation_provider", "generation_model", "generation_tokens", "repair_tokens",
                "total_tokens", "final_validation_error_codes", "final_visual_error_codes",
                "final_structure_similarity", "final_tag_sequence_similarity",
                "final_text_similarity", "final_tree_edit_distance", "interaction_eval_passed",
            )
        },
        "artifact_selection": [path.name for path in artifacts],
        "boundaries": [
            "Earlier frozen automatic passes remain immutable and were rejected by browser audit.",
            "This snapshot records a new automatic pass only; browser interaction parity is not yet established.",
            "This reused development case is not independent generalization evidence.",
            "Code files record the local implementation state; some changes may not yet be committed.",
        ],
        "integrity_file": "SHA256SUMS.txt",
    }
    (target / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files = sorted(path for path in target.rglob("*") if path.is_file())
    (target / "SHA256SUMS.txt").write_text(
        "\n".join(f"{digest(path)}  {path.relative_to(target).as_posix()}" for path in files) + "\n",
        encoding="utf-8",
    )
    for line in (target / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        if digest(target / relative) != expected:
            raise RuntimeError(f"Snapshot verification failed: {relative}")
    print(f"frozen: {target.relative_to(ROOT)} ({len(files)} verified payload files)")


if __name__ == "__main__":
    main()
