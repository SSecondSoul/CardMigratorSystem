"""Freeze a read-only-origin replay of two bounded TaskManager repair rules."""

from __future__ import annotations

import json
import shutil
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
from migration_pipeline.stages.repair import RepairStage
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.stages.visual_eval import VisualEvalStage, VisualEvalStageInput
from migration_pipeline.utils.san_compile import check_san_compile


SOURCE = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_task_manager_boolean_event_regression_v1_"
    "TaskManager_automatic_fail_20261028_220158"
)
IMPLEMENTATION = [
    "migration_pipeline/replay_formal_30_v4_task_manager_semantic_residual_rules.py",
    "migration_pipeline/stages/repair.py",
    "migration_pipeline/stages/validate.py",
    "tests/test_repair_regression_guard.py",
]


def main() -> None:
    verify_checksums(SOURCE)
    source_manifest = json.loads((SOURCE / "manifest.json").read_text(encoding="utf-8"))
    if source_manifest.get("sample_id") != "TaskManager" or source_manifest.get("automatic_passed") is not False:
        raise RuntimeError("Expected the frozen TaskManager automatic failure")
    state = json.loads((SOURCE / "repair_history.json").read_text(encoding="utf-8"))["state"]
    original = (SOURCE / "repair_round_3.san").read_text(encoding="utf-8")
    candidate = RepairStage._normalize_empty_modifier_handlers(original)
    candidate = RepairStage._normalize_misplaced_mounted_first_call(candidate, state["ssm"])
    if candidate == original:
        raise RuntimeError("Neither bounded rule applied")
    validation = ValidateStage().run(ValidateStageInput(
        generated_code=candidate,
        ssm=state["ssm"],
        source_file=state.get("source_file", ""),
        vue_file_path=state.get("vue_file_path", ""),
        compile_check=False,
    ))
    compile_result = check_san_compile(san_source=candidate)
    visual = VisualEvalStage().run(VisualEvalStageInput(
        vue_file_path=state.get("vue_file_path"),
        vue_source=state.get("vue_source"),
        generated_code=candidate,
        source_file=state.get("source_file", ""),
    ))
    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    target = ROOT / "data/experiments/snapshots" / (
        f"formal_30_v4_task_manager_semantic_residual_bounded_replay_{stamp}"
    )
    if target.exists():
        raise FileExistsError(target)
    for relative in IMPLEMENTATION:
        if not (ROOT / relative).is_file():
            raise FileNotFoundError(ROOT / relative)
    target.mkdir(parents=True)
    (target / "candidate.san").write_text(candidate, encoding="utf-8")
    shutil.copy2(SOURCE / "manifest.json", target / "source_manifest.json")
    shutil.copy2(SOURCE / "SHA256SUMS.txt", target / "source_SHA256SUMS.txt")
    for relative in IMPLEMENTATION:
        destination = target / "code" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    report = {
        "classification": "reused_development_partial_bounded_offline_replay",
        "independent_holdout": False,
        "source_snapshot": SOURCE.name,
        "model_request_performed": False,
        "rules": ["empty_quoted_modifier_handler", "exact_mounted_sequence_to_attached"],
        "before_validation_error_codes": source_manifest["final_validation_error_codes"],
        "after_validation_error_codes": [item["code"] for item in validation.validation_errors],
        "validation_passed": validation.validation_passed,
        "san_compile_passed": compile_result.passed,
        "visual_eval_passed": visual.visual_eval_passed,
        "visual_error_codes": [item.get("code") for item in visual.visual_eval_errors],
        "structure_similarity": visual.structure_similarity,
        "automatic_pipeline_passed": False,
        "browser_manual_review": "not_performed",
        "note": "A partial offline replay is not a new automatic batch pass or independent-test result.",
    }
    (target / "replay_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    manifest = {
        "snapshot_id": target.name,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "classification": report["classification"],
        "independent_holdout": False,
        "source_snapshot": SOURCE.name,
        "candidate_sha256": sha256(target / "candidate.san"),
        "validation_passed": validation.validation_passed,
        "browser_manual_review": "not_performed",
        "integrity_file": "SHA256SUMS.txt",
    }
    (target / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    payloads = sorted(path for path in target.rglob("*") if path.is_file())
    (target / "SHA256SUMS.txt").write_text(
        "\n".join(
            f"{sha256(path)}  {path.relative_to(target).as_posix()}" for path in payloads
        ) + "\n",
        encoding="utf-8",
    )
    verify_checksums(target)
    print(f"frozen: {target.relative_to(ROOT)} ({len(payloads)} verified payloads)")
    print(f"validation_passed: {validation.validation_passed}")
    print(f"residual_codes: {report['after_validation_error_codes']}")
    print(f"san_compile_passed: {compile_result.passed}")
    print(f"visual_eval_passed: {visual.visual_eval_passed}")
    print(f"structure_similarity: {visual.structure_similarity}")


if __name__ == "__main__":
    main()
