"""Freeze the v4 reused-development manual closeout without changing prior evidence."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ID = "formal_30_v4_development_manual_closeout_20261027"
TARGET = ROOT / "data/experiments/snapshots" / SNAPSHOT_ID
ANALYSIS = Path("data/experiments/analysis/formal_30_v4_development_closeout_20261025")
PASS_STATUSES = {
    "user_reported_pass",
    "user_reported_pass_after_repair",
    "user_reported_pass_after_visual_repair",
    "user_reported_pass_after_settings_and_tag_repair",
    "user_reported_san_pass_after_settings_kpi_log_repair",
}
EVIDENCE = [
    *(ANALYSIS / name for name in (
        "REPORT.md", "summary.json", "sample_results.csv", "manual_validation.json",
        "analytics_dashboard_manual_audit.json", "task_manager_manual_audit.json",
        "monitoring_dashboard_manual_audit.json",
    )),
    Path("data/experiments/batch_reports/formal_30_v4_targeted_summary.json"),
    Path("data/experiments/batch_reports/formal_30_v4_deferred_regression_summary.json"),
    Path("data/experiments/batch_reports/formal_30_v4_analytics_manual_followup_summary.json"),
    Path("data/experiments/batch_reports/formal_30_v4_analytics_runtime_followup_summary.json"),
    Path("data/experiments/batch_reports/formal_30_v4_task_manager_manual_followup_summary.json"),
    Path("data/experiments/analysis/formal_30_v4_planning_20261022/remediation_log.json"),
    Path("notebooks/02-migration-experiments/2026-10-23_formal_30_v4_deferred_regression.ipynb"),
]
CODE = [
    "migration_pipeline/analyze_formal_30_v4_development.py",
    "migration_pipeline/freeze_formal_30_v4_development_manual_closeout.py",
    "migration_pipeline/run_batch_pipeline.py",
    "migration_pipeline/config.py",
    "migration_pipeline/generation_client.py",
    "migration_pipeline/stages/generate.py",
    "migration_pipeline/stages/repair.py",
    "migration_pipeline/stages/validate.py",
    "migration_pipeline/stages/visual_eval.py",
    "migration_pipeline/utils/repair_prompt.py",
    "migration_pipeline/utils/san_compile.py",
    "migration_pipeline/utils/san_render.py",
    "migration_pipeline/utils/vue_render.py",
    "migration_pipeline/utils/dom_compare.py",
    "migration_pipeline/utils/ast_compare.py",
    "local_server/api/evaluation_routes.py",
    "local_server/config.py",
    "tests/test_migration_pipeline_regressions.py",
    "tests/test_repair_prompt_and_loop.py",
    "migration_pipeline/batch_configs/formal_30_v4_targeted.json",
    "migration_pipeline/batch_configs/formal_30_v4_deferred_regression.json",
    "migration_pipeline/batch_configs/formal_30_v4_analytics_manual_followup.json",
    "migration_pipeline/batch_configs/formal_30_v4_analytics_runtime_followup.json",
    "migration_pipeline/batch_configs/formal_30_v4_task_manager_manual_followup.json",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source(relative: str | Path) -> Path:
    candidate = (ROOT / relative).resolve()
    if not candidate.is_relative_to(ROOT) or not candidate.is_file():
        raise RuntimeError(f"Invalid or missing evidence file: {relative}")
    return candidate


def read_json(relative: str | Path) -> dict:
    return json.loads(source(relative).read_text(encoding="utf-8"))


def copy(relative: str | Path, destination: Path) -> None:
    original = source(relative)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(original, destination)


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, encoding="utf-8"
    ).strip()


def main() -> None:
    if TARGET.exists():
        raise FileExistsError(f"Frozen snapshot already exists: {TARGET}")

    manual = read_json(ANALYSIS / "manual_validation.json")
    latest = {entry["sample_id"]: entry for entry in manual["results"]}
    with source(ANALYSIS / "sample_results.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    ids = [row["sample_id"] for row in rows]
    if len(ids) != 12 or len(set(ids)) != 12 or set(latest) != set(ids):
        raise RuntimeError("Manual results do not cover exactly the 12 development samples")

    summary = read_json(ANALYSIS / "summary.json")
    if summary["independent_holdout"] is not False:
        raise RuntimeError("The closeout must remain classified as development evidence")
    targeted = read_json("data/experiments/batch_reports/formal_30_v4_targeted_summary.json")
    deferred = read_json("data/experiments/batch_reports/formal_30_v4_deferred_regression_summary.json")
    batch_samples = {sample["id"]: sample for batch in (targeted, deferred) for sample in batch["samples"]}
    if set(batch_samples) != set(ids):
        raise RuntimeError("Batch summaries and closeout CSV disagree on sample IDs")

    review = []
    repairs = set()
    replays = set()
    for row in rows:
        sample_id = row["sample_id"]
        entry = latest[sample_id]
        status = entry["result"]
        if status not in PASS_STATUSES:
            raise RuntimeError(f"Latest manual status is not a pass: {sample_id}: {status}")
        san_path = entry["san_artifact"]
        san_hash = sha256(source(san_path))
        expected = entry.get("candidate_sha256") or entry.get("artifact_sha256")
        if expected and san_hash != expected.lower():
            raise RuntimeError(f"Manual artifact SHA-256 mismatch: {sample_id}")
        vue_path = batch_samples[sample_id]["vue_file"]
        vue_hash = sha256(source(vue_path))
        is_posthoc = san_path.startswith("data/experiments/pipeline/manual_fixes/")
        if is_posthoc != bool(entry.get("repair_report")):
            raise RuntimeError(f"Post-hoc candidate provenance is incomplete: {sample_id}")
        if is_posthoc:
            report_path = entry["repair_report"]
            repair = read_json(report_path)
            repair_hash = repair.get("candidate_sha256")
            if repair_hash and repair_hash.lower() != san_hash:
                raise RuntimeError(f"Candidate repair report hash mismatch: {sample_id}")
            repairs.add(report_path)
            replay = repair.get("replay_script")
            if replay:
                replays.add(replay)
        review.append({
            "sample_id": sample_id,
            "complexity": row["complexity"],
            "manual_status": status,
            "reviewed_artifact_kind": "posthoc_manual_candidate" if is_posthoc else "frozen_automatic_artifact",
            "reviewed_san_source": san_path,
            "reviewed_san_sha256": san_hash,
            "vue_source": vue_path,
            "vue_sha256": vue_hash,
            "original_automatic_snapshot": row["canonical_snapshot"],
            "repair_report": entry.get("repair_report"),
        })

    for relative in [*EVIDENCE, *(Path(path) for path in CODE), *repairs, *replays]:
        source(relative)
    for case in review:
        source(case["reviewed_san_source"])
        source(case["vue_source"])

    git_head = git("rev-parse", "HEAD")
    worktree_status = git("status", "--short")
    TARGET.mkdir(parents=True)
    for relative in EVIDENCE:
        copy(relative, TARGET / "evidence" / relative)
    for relative in sorted(repairs | replays):
        copy(relative, TARGET / "evidence" / relative)
    for relative in CODE:
        copy(relative, TARGET / "code" / relative)
    for case in review:
        copy(case["reviewed_san_source"], TARGET / "reviewed_san" / f"{case['sample_id']}.san")
        copy(case["vue_source"], TARGET / "vue_sources" / f"{case['sample_id']}.vue")

    manifest = {
        "snapshot_id": SNAPSHOT_ID,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "classification": "reused_development_regression_manual_closeout",
        "independent_holdout": False,
        "automatic_checkpoint": "historical_12_of_12_not_runtime_manual_pass",
        "latest_reviewed_san_artifacts_user_reported_pass": 12,
        "original_frozen_automatic_artifacts_user_reported_pass": sum(
            case["reviewed_artifact_kind"] == "frozen_automatic_artifact" for case in review
        ),
        "posthoc_manual_candidates_user_reported_pass": sum(
            case["reviewed_artifact_kind"] == "posthoc_manual_candidate" for case in review
        ),
        "vue_san_full_parity": "not_established_monitoring_vue_manual_runner_chart_limitation",
        "manual_evidence_type": "user_chat_confirmation_not_automated_interaction_eval",
        "reviewed_samples": review,
        "prior_snapshot_payload_counts": summary["verified_snapshot_payload_counts"],
        "git_head": git_head,
        "code_worktree_clean_at_freeze": not bool(worktree_status),
        "worktree_status_at_freeze": worktree_status.splitlines(),
        "code_scope": "Relevant local migration, prompt, validation, rendering, and regression-test files are copied under code/; this is not a full formal protocol freeze.",
        "test_evidence": {
            "command": "python -m unittest tests.test_migration_pipeline_regressions tests.test_repair_prompt_and_loop",
            "result": "104 tests passed on 2026-10-27",
            "scope": "unit and regression tests; no automated browser interaction evaluation",
        },
        "boundaries": [
            "Original frozen automatic snapshots and checkpoint summaries were not rewritten.",
            "Four reviewed San artifacts are post-hoc candidates, not their original automatic passes.",
            "MonitoringDashboard was accepted as a San component; full Vue/San chart parity was not established.",
            "This reused development set is not an independent formal test or a generalization estimate.",
            "The copied implementation is a local state and may include uncommitted changes; a later formal protocol freeze is separate.",
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
    for line in (TARGET / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        if sha256(TARGET / relative) != expected:
            raise RuntimeError(f"Snapshot checksum verification failed: {relative}")
    print(f"frozen: {TARGET.relative_to(ROOT)} ({len(payloads)} verified payload files)")


if __name__ == "__main__":
    main()
