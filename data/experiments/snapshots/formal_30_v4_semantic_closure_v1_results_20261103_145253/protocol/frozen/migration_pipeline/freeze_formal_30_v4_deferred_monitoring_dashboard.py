"""Freeze the audit-confirmed MonitoringDashboard regression pass."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BATCH = "formal_30_v4_deferred_regression"
SAMPLE = "MonitoringDashboard"
SUMMARY = ROOT / f"data/experiments/batch_reports/{BATCH}_summary.json"
CONFIG = ROOT / f"migration_pipeline/batch_configs/{BATCH}.json"
PIPELINE = ROOT / f"data/experiments/pipeline/batches/{BATCH}/complex"
REPORT = ROOT / f"data/experiments/repair_reports/batches/{BATCH}/complex/{SAMPLE}_repair_history.json"
SOURCE = ROOT / (
    "data/experiments/protocols/formal_30_v3_frozen_20261022/frozen/"
    "data/datasets/components/03_complex/MonitoringDashboard/vue/MonitoringDashboard.vue"
)
PROTOCOL = ROOT / "data/experiments/protocols/formal_30_v4_deferred_regression_frozen_20261023"
ANALYSIS = ROOT / "data/experiments/analysis/formal_30_v4_deferred_regression_20261023"

VERIFY_SCRIPT = '''"""Verify every file recorded in this frozen snapshot."""

import hashlib
from pathlib import Path


HERE = Path(__file__).resolve().parent


def main() -> None:
    failures = []
    checked = 0
    for line in (HERE / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split("  ", 1)
        path = HERE / relative
        if not path.is_file():
            failures.append(f"missing: {relative}")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            failures.append(f"hash mismatch: {relative}")
        checked += 1
    if failures:
        raise SystemExit("snapshot verification failed: " + "; ".join(failures))
    print(f"snapshot verification passed: {checked} files")


if __name__ == "__main__":
    main()
'''


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_file(source: Path, target: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def main() -> None:
    required = [SUMMARY, CONFIG, PIPELINE, REPORT, SOURCE, PROTOCOL, ANALYSIS]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing freeze input: " + ", ".join(missing))

    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    sample = next(item for item in summary["samples"] if item["id"] == SAMPLE)
    if not sample.get("final_passed") or sample.get("stop_reason") != "passed":
        raise RuntimeError("MonitoringDashboard is not a terminal pass")

    timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    target = ROOT / "data/experiments/snapshots" / (
        f"formal_30_v4_deferred_monitoring_dashboard_pass_{timestamp}"
    )
    if target.exists():
        raise FileExistsError(target)
    target.mkdir(parents=True)

    copy_file(SUMMARY, target / SUMMARY.name)
    copy_file(CONFIG, target / CONFIG.name)
    copy_file(SOURCE, target / "source/MonitoringDashboard.vue")
    copy_file(REPORT, target / "repair_reports/complex/MonitoringDashboard_repair_history.json")
    # A --force rerun may leave older, higher-round artifacts in the output
    # directory. Copy only the initial file and this run's repair rounds.
    artifact_names = [
        f"{SAMPLE}{'_repaired' * round_index}.san"
        for round_index in range(sample["repair_rounds"] + 1)
    ]
    for artifact_name in artifact_names:
        path = PIPELINE / artifact_name
        if not path.is_file():
            raise FileNotFoundError(path)
        copy_file(path, target / "pipeline/complex" / path.name)
    for path in sorted(PROTOCOL.iterdir()):
        if path.is_file():
            copy_file(path, target / "protocol" / path.name)
    for path in sorted(ANALYSIS.iterdir()):
        if path.is_file():
            copy_file(path, target / "analysis" / path.name)

    code_files = [
        ROOT / "migration_pipeline/stages/repair.py",
        ROOT / "migration_pipeline/stages/validate.py",
        ROOT / "migration_pipeline/utils/san_render.py",
        ROOT / "migration_pipeline/utils/repair_prompt.py",
        ROOT / "migration_pipeline/utils/vue_render.py",
        ROOT / "SSM/extractors/parse_sfc.cjs",
        ROOT / "SSM/extractors/script_extractor.py",
        ROOT / "SSM/extractors/template_extractor.py",
        ROOT / "SSM/extractors/vue_parser.py",
        ROOT / "tests/test_migration_pipeline_regressions.py",
        ROOT / "tests/test_repair_prompt_and_loop.py",
        ROOT / "tests/test_ssm_event_extraction.py",
        Path(__file__).resolve(),
    ]
    for path in code_files:
        copy_file(path, target / "code" / path.relative_to(ROOT))

    (target / "verify_snapshot.py").write_text(VERIFY_SCRIPT, encoding="utf-8")
    manifest = {
        "snapshot_id": target.name,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "purpose": "Freeze the audit-confirmed MonitoringDashboard pass after parent component registration, initData collision, and renderer-global fixes.",
        "batch_id": BATCH,
        "sample_id": SAMPLE,
        "classification": "development_internal_regression",
        "not_independent_holdout": True,
        "status": "frozen_audit_confirmed_pass",
        "implementation_commit": "eafcd3d43805747d5c9665047c260b66b1b4a913",
        "working_tree_note": "The deterministic fixes and renderer test changes were present in the working tree when this evidence was frozen; generated batch artifacts were not manually edited.",
        "artifact_selection": artifact_names,
        "result": {
            key: sample.get(key)
            for key in (
                "started_at", "finished_at", "elapsed_seconds", "final_passed",
                "stop_reason", "repair_rounds", "generation_provider",
                "generation_model", "generation_tokens", "repair_tokens",
                "total_tokens", "initial_validation_error_codes",
                "initial_visual_error_codes", "final_validation_error_codes",
                "final_visual_error_codes", "final_structure_similarity",
                "final_tag_sequence_similarity", "final_text_similarity",
                "final_tree_edit_distance",
            )
        },
        "boundaries": [
            "This is an audit-confirmed pass for a reused development regression case.",
            "It is not independent holdout or generalization evidence.",
            "Earlier MonitoringDashboard failures remain frozen separately and were not overwritten.",
            "Any later reinterpretation or modification requires a new snapshot directory.",
        ],
        "integrity_file": "SHA256SUMS.txt",
    }
    (target / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    files = sorted(path for path in target.rglob("*") if path.is_file() and path.name != "SHA256SUMS.txt")
    (target / "SHA256SUMS.txt").write_text(
        "\n".join(f"{sha256(path)}  {path.relative_to(target).as_posix()}" for path in files) + "\n",
        encoding="utf-8",
    )
    print(target.relative_to(ROOT))
    print(json.dumps({"files": len(files), "sample": SAMPLE}, ensure_ascii=False))


if __name__ == "__main__":
    main()
