"""Prepare the formal_30_v4 targeted remediation plan from frozen v3 evidence."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PARENT_SNAPSHOT = (
    ROOT / "data/experiments/snapshots/formal_30_v3_results_20261022_200548"
)
OUTPUT_DIR = ROOT / "data/experiments/analysis/formal_30_v4_planning_20261022"
SPLIT_FILE = ROOT / "data/datasets/splits/formal_30_v4_targeted_development.json"
CONFIG_FILE = ROOT / "migration_pipeline/batch_configs/formal_30_v4_targeted.json"
NOTEBOOK_FILE = (
    ROOT
    / "notebooks/02-migration-experiments/2026-10-22_formal_30_v4_failure_diagnosis.ipynb"
)

TARGETS = {
    "course_module_accordion": {
        "selection_role": "semantic_reactivity_representative",
        "target_defects": [
            "hidden_template_reactive_dependency",
            "dom_structure_similarity_low",
        ],
        "rationale": "Covers hidden template dependencies plus structural drift.",
    },
    "schema_mapping_workbench": {
        "selection_role": "loop_key_and_no_progress_representative",
        "target_defects": [
            "invalid_s_for_key_binding",
            "dom_critical_attribute_mismatch",
            "no_repair_progress",
        ],
        "rationale": "Covers invalid San loop-key placement and a repeated no-progress stop.",
    },
    "incident_response_board": {
        "selection_role": "state_access_and_no_progress_representative",
        "target_defects": [
            "vue_this_state",
            "dom_critical_attribute_mismatch",
            "no_repair_progress",
        ],
        "rationale": "Covers residual Vue-style state access and a repeated no-progress stop.",
    },
    "rule_builder": {
        "selection_role": "prop_default_representative",
        "target_defects": [
            "missing_prop_defaults",
            "dom_structure_similarity_low",
            "dom_critical_attribute_mismatch",
        ],
        "rationale": "Covers the remaining prop-default failure and combined DOM drift.",
    },
    "habit_week_tracker": {
        "selection_role": "structure_only_representative",
        "target_defects": ["dom_structure_similarity_low"],
        "rationale": "Isolates a final structural mismatch with no final static-validation error.",
    },
    "playback_queue": {
        "selection_role": "critical_attribute_only_representative",
        "target_defects": ["dom_critical_attribute_mismatch"],
        "rationale": "Isolates a critical-attribute mismatch with no final static-validation error.",
    },
    "analytics_dashboard": {
        "selection_role": "infrastructure_timeout_representative",
        "target_defects": ["generation_timeout"],
        "rationale": "Represents the three reproducible generation timeouts; it is not a migration-quality failure.",
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def verify_parent_snapshot() -> int:
    failures = []
    checked = 0
    checksum_file = PARENT_SNAPSHOT / "SHA256SUMS.txt"
    for line in checksum_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split("  ", 1)
        path = PARENT_SNAPSHOT / relative
        if not path.is_file() or sha256(path) != expected:
            failures.append(relative)
        checked += 1
    if failures:
        raise RuntimeError("Parent snapshot verification failed: " + ", ".join(failures))
    return checked


def notebook(summary: dict, target_rows: list[dict]) -> dict:
    table = [
        "| Sample | Complexity | Role | Target defects |",
        "| --- | --- | --- | --- |",
    ]
    for row in target_rows:
        table.append(
            f"| `{row['id']}` | {row['complexity']} | "
            f"{row['selection_role']} | {', '.join(row['target_defects'])} |"
        )
    markdown = "\n".join(table)
    return {
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "# formal_30_v4 targeted failure diagnosis\n",
                    "\n",
                    "This notebook starts a development-only remediation cycle from the frozen `formal_30_v3` evidence. It does not reinterpret v3 as a tunable holdout and does not alter any v3 result.\n",
                ],
            },
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "## Frozen evidence boundary\n",
                    "\n",
                    "- Parent snapshot: `data/experiments/snapshots/formal_30_v3_results_20261022_200548`\n",
                    f"- Parent files verified by the preparation step: {summary['parent_verified_files']}\n",
                    "- v3 outcome: 18/30 configured passed, 18/27 completed passed, 9 completed failures, and 3 execution errors.\n",
                    "- v4 is a targeted development batch. Its pass rate must not be reported as an independent generalization result.\n",
                ],
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "import json\n",
                    "from pathlib import Path\n",
                    "\n",
                    "diagnosis_path = Path('data/experiments/analysis/formal_30_v4_planning_20261022/diagnosis.json')\n",
                    "diagnosis = json.loads(diagnosis_path.read_text(encoding='utf-8'))\n",
                    "diagnosis['summary']\n",
                ],
            },
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "## Targeted development samples\n",
                    "\n",
                    markdown + "\n",
                ],
            },
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "## Remediation order\n",
                    "\n",
                    "1. Reproduce each selected defect from its frozen final artifact and repair history.\n",
                    "2. Add a focused regression test that fails before changing production logic.\n",
                    "3. Fix the narrowest responsible layer: extractor/schema, validator, evaluator, or Prompt.\n",
                    "4. Run existing regression tests and the v4 dry-run.\n",
                    "5. Execute targeted samples incrementally; do not use `--force` unless a deliberate rerun is recorded.\n",
                    "6. Keep the three timeout cases separate from migration-quality failures.\n",
                    "7. After remediation stabilizes, evaluate on another untouched holdout rather than claiming v4 as independent evidence.\n",
                ],
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "config_path = Path('migration_pipeline/batch_configs/formal_30_v4_targeted.json')\n",
                    "config = json.loads(config_path.read_text(encoding='utf-8'))\n",
                    "[(item['id'], item['selection_role']) for item in config['samples']]\n",
                ],
            },
        ],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "version": "3.10"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def main() -> None:
    required = [
        PARENT_SNAPSHOT / "SHA256SUMS.txt",
        PARENT_SNAPSHOT / "manifest.json",
        PARENT_SNAPSHOT / "formal_30_v3_summary.json",
        PARENT_SNAPSHOT / "formal_30_v3.json",
        PARENT_SNAPSHOT / "formal_30_v3_untouched_holdout.json",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing planning input: " + ", ".join(missing))

    parent_verified_files = verify_parent_snapshot()
    parent_manifest = load_json(PARENT_SNAPSHOT / "manifest.json")
    parent_summary = load_json(PARENT_SNAPSHOT / "formal_30_v3_summary.json")
    parent_config = load_json(PARENT_SNAPSHOT / "formal_30_v3.json")
    parent_split = load_json(PARENT_SNAPSHOT / "formal_30_v3_untouched_holdout.json")

    terminal = [
        item
        for item in parent_summary["samples"]
        if item.get("status") == "error" or not item.get("final_passed")
    ]
    completed_failures = [item for item in terminal if item.get("status") == "completed"]
    execution_errors = [item for item in terminal if item.get("status") == "error"]
    if len(completed_failures) != 9 or len(execution_errors) != 3:
        raise RuntimeError("Frozen v3 failure counts differ from the recorded terminal state")

    validation_counts = Counter()
    visual_counts = Counter()
    stop_counts = Counter()
    failure_rows = []
    for item in terminal:
        validation_codes = sorted(set(item.get("final_validation_error_codes") or []))
        visual_codes = sorted(set(item.get("final_visual_error_codes") or []))
        validation_counts.update(validation_codes)
        visual_counts.update(visual_codes)
        if item.get("stop_reason"):
            stop_counts[item["stop_reason"]] += 1
        failure_rows.append(
            {
                "id": item["id"],
                "component_name": item["component_name"],
                "complexity": item["complexity"],
                "status": item["status"],
                "stop_reason": item.get("stop_reason") or None,
                "repair_rounds": item.get("repair_rounds"),
                "final_validation_errors": validation_codes,
                "final_visual_errors": visual_codes,
                "error_type": item.get("error_type") or None,
                "error_message": (item.get("error_message") or "").strip() or None,
                "total_tokens": item.get("total_tokens"),
            }
        )

    config_by_id = {item["id"]: item for item in parent_config["samples"]}
    split_by_id = {item["id"]: item for item in parent_split["samples"]}
    terminal_by_id = {item["id"]: item for item in terminal}
    target_rows = []
    split_samples = []
    config_samples = []
    for sample_id, selection in TARGETS.items():
        terminal_item = terminal_by_id.get(sample_id)
        config_item = config_by_id.get(sample_id)
        split_item = split_by_id.get(sample_id)
        if not terminal_item or not config_item or not split_item:
            raise RuntimeError(f"Target is missing from frozen v3 evidence: {sample_id}")
        if terminal_item.get("final_passed"):
            raise RuntimeError(f"Refusing to select an automatic pass: {sample_id}")
        row = {
            "id": sample_id,
            "component_name": config_item["component_name"],
            "complexity": config_item["complexity"],
            **selection,
        }
        target_rows.append(row)
        split_samples.append(
            {
                "id": sample_id,
                "component_name": split_item["component_name"],
                "complexity": split_item["complexity"],
                "vue_file": split_item["vue_file"],
                "san_file": split_item["san_file"],
                "selection_role": selection["selection_role"],
                "target_defects": selection["target_defects"],
                "rationale": selection["rationale"],
            }
        )
        config_samples.append(
            {
                "id": sample_id,
                "component_name": config_item["component_name"],
                "complexity": config_item["complexity"],
                "vue_file": config_item["vue_file"],
                "coverage_focus": config_item["coverage_focus"],
                "selection_role": selection["selection_role"],
                "target_defects": selection["target_defects"],
            }
        )

    created_at = datetime.now().astimezone().isoformat(timespec="seconds")
    split = {
        "split_id": "formal_30_v4_targeted_development",
        "created_at": created_at,
        "purpose": "Development-only representatives selected from frozen formal_30_v3 failures and execution errors.",
        "parent_snapshot_id": parent_manifest["snapshot_id"],
        "parent_snapshot_manifest_sha256": sha256(PARENT_SNAPSHOT / "manifest.json"),
        "selection_method": "One minimal representative for each distinct final defect family, plus one reproducible timeout case.",
        "counts": {
            "selected": len(split_samples),
            "medium": sum(item["complexity"] == "medium" for item in split_samples),
            "complex": sum(item["complexity"] == "complex" for item in split_samples),
            "migration_failure_representatives": 6,
            "infrastructure_error_representatives": 1,
        },
        "evidence_boundary": [
            "This split is derived from v3 outcomes and is therefore a development set, not an untouched holdout.",
            "Unselected duplicate failures remain available for internal regression after targeted fixes.",
            "A later generalization claim requires another untouched holdout.",
        ],
        "samples": split_samples,
    }
    write_json(SPLIT_FILE, split)

    config = {
        "batch_id": "formal_30_v4_targeted",
        "description": "Development-only targeted remediation of representative formal_30_v3 failures; not an independent evaluation.",
        "source_batch": "formal_30_v3",
        "source_snapshot": parent_manifest["snapshot_id"],
        "source_split": SPLIT_FILE.relative_to(ROOT).as_posix(),
        "source_split_sha256": sha256(SPLIT_FILE),
        "max_repair_rounds": 3,
        "expected_counts": {"medium": 3, "complex": 4},
        "samples": config_samples,
    }
    write_json(CONFIG_FILE, config)

    diagnosis = {
        "analysis_id": "formal_30_v4_planning_20261022",
        "created_at": created_at,
        "source": {
            "snapshot_id": parent_manifest["snapshot_id"],
            "snapshot_manifest_sha256": sha256(PARENT_SNAPSHOT / "manifest.json"),
            "snapshot_verified_files": parent_verified_files,
            "summary_sha256": sha256(PARENT_SNAPSHOT / "formal_30_v3_summary.json"),
            "baseline_commit": "df284a3",
        },
        "summary": {
            "v3_configured": 30,
            "v3_automatic_passed": 18,
            "completed_failures": len(completed_failures),
            "execution_errors": len(execution_errors),
            "targeted_samples": len(target_rows),
            "targeted_migration_failures": 6,
            "targeted_infrastructure_errors": 1,
        },
        "taxonomy": {
            "final_validation_error_sample_counts": dict(validation_counts),
            "final_visual_error_sample_counts": dict(visual_counts),
            "stop_reason_sample_counts": dict(stop_counts),
            "observations": [
                "All nine completed failures retain at least one final DOM comparison error.",
                "Six completed failures also retain a static semantic validation error.",
                "The three generation timeouts are infrastructure errors and must not be classified as migration-quality failures.",
            ],
        },
        "all_terminal_nonpasses": failure_rows,
        "targeted_selection": target_rows,
        "deferred_duplicate_regression_ids": [
            "access_matrix",
            "localization_workspace",
            "trip_itinerary_planner",
            "TaskManager",
            "MonitoringDashboard",
        ],
        "remediation_sequence": [
            "Inspect frozen final artifacts and repair histories for the seven selected representatives.",
            "Add one focused failing regression per confirmed root cause before changing production logic.",
            "Apply minimal fixes to the responsible extractor, schema, validator, evaluator, Prompt, or timeout layer.",
            "Run the existing regression suite and the formal_30_v4_targeted dry-run.",
            "Execute selected samples incrementally and preserve checkpoint history.",
            "Run deferred duplicate cases as internal regression after the representative fixes stabilize.",
            "Use another untouched holdout for any later generalization claim.",
        ],
    }
    write_json(OUTPUT_DIR / "diagnosis.json", diagnosis)
    write_json(NOTEBOOK_FILE, notebook(diagnosis["summary"] | {"parent_verified_files": parent_verified_files}, target_rows))

    print(OUTPUT_DIR.relative_to(ROOT).as_posix())
    print(SPLIT_FILE.relative_to(ROOT).as_posix())
    print(CONFIG_FILE.relative_to(ROOT).as_posix())
    print(NOTEBOOK_FILE.relative_to(ROOT).as_posix())
    print(
        json.dumps(
            {
                "parent_verified_files": parent_verified_files,
                "completed_failures": len(completed_failures),
                "execution_errors": len(execution_errors),
                "targets": len(target_rows),
            }
        )
    )


if __name__ == "__main__":
    main()
