"""Freeze bounded boolean-event offline replay of the failed TaskManager v3b probe."""

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
from migration_pipeline.utils.repair_regression_guard import assess_event_contract_regression
from migration_pipeline.utils.san_compile import check_san_compile


SOURCE = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_semantic_focus_v2_TaskManager_automatic_fail_20261028_140129"
)
FAILED = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_task_manager_event_focus_v3b_result_20261028_203015"
)
IMPLEMENTATION = [
    "migration_pipeline/replay_formal_30_v4_task_manager_boolean_event_fix.py",
    "migration_pipeline/stages/repair.py",
    "migration_pipeline/stages/validate.py",
    "migration_pipeline/utils/repair_regression_guard.py",
    "tests/test_repair_regression_guard.py",
]


def main() -> None:
    verify_checksums(SOURCE)
    verify_checksums(FAILED)
    source_state = json.loads((SOURCE / "repair_history.json").read_text(encoding="utf-8"))["state"]
    failed_report = json.loads((FAILED / "probe_report.json").read_text(encoding="utf-8"))
    original = (FAILED / "candidate.san").read_text(encoding="utf-8")
    if failed_report.get("automatic_passed") is not False:
        raise RuntimeError("Expected frozen automatic failure")
    candidate = RepairStage._normalize_source_boolean_assignment_events(original, source_state["ssm"])
    if candidate == original:
        raise RuntimeError("Bounded rule did not apply")
    validation = ValidateStage().run(ValidateStageInput(
        generated_code=candidate, ssm=source_state["ssm"], compile_check=False,
    ))
    compile_result = check_san_compile(san_source=candidate)
    gate = assess_event_contract_regression(
        ssm=source_state["ssm"], before_code=original, after_code=candidate,
        before_errors=failed_report["validation_errors"],
        after_errors=validation.validation_errors,
    )
    visual = VisualEvalStage().run(VisualEvalStageInput(
        vue_file_path=source_state.get("vue_file_path"),
        vue_source=source_state.get("vue_source"),
        generated_code=candidate, source_file=source_state.get("source_file", ""),
    ))
    passed = bool(validation.validation_passed and compile_result.passed
                  and visual.visual_eval_passed and not gate["should_stop"])
    if not passed:
        raise RuntimeError("Offline replay failed a required gate; no passing freeze written")
    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    target = ROOT / "data/experiments/snapshots" / (
        f"formal_30_v4_task_manager_event_boolean_offline_pass_{stamp}"
    )
    if target.exists():
        raise FileExistsError(target)
    target.mkdir(parents=True)
    (target / "candidate.san").write_bytes(candidate.encode("utf-8"))
    for name, source in {
        "failed_manifest.json": FAILED / "manifest.json",
        "failed_SHA256SUMS.txt": FAILED / "SHA256SUMS.txt",
        "source_manifest.json": SOURCE / "manifest.json",
        "source_SHA256SUMS.txt": SOURCE / "SHA256SUMS.txt",
    }.items():
        shutil.copy2(source, target / name)
    for relative in IMPLEMENTATION:
        source = ROOT / relative
        if not source.is_file():
            raise FileNotFoundError(source)
        destination = target / "code" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    report = {
        "classification": "reused_development_bounded_boolean_event_offline_replay",
        "independent_holdout": False,
        "model_request_performed": False,
        "failed_snapshot": FAILED.name,
        "source_snapshot": SOURCE.name,
        "rule": "source_corroborated_boolean_data_assignment_event",
        "validation_passed": validation.validation_passed,
        "validation_error_codes": [item.get("code") for item in validation.validation_errors],
        "san_compile_passed": compile_result.passed,
        "visual_eval_passed": visual.visual_eval_passed,
        "visual_error_codes": [item.get("code") for item in visual.visual_eval_errors],
        "structure_similarity": visual.structure_similarity,
        "event_regression_gate": gate["decision"],
        "offline_replay_passed": passed,
        "automatic_pipeline_passed": False,
        "browser_manual_review": "not_performed",
    }
    (target / "replay_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    manifest = {
        "snapshot_id": target.name,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "classification": report["classification"],
        "independent_holdout": False,
        "failed_snapshot": FAILED.name,
        "candidate_sha256": sha256(target / "candidate.san"),
        "offline_replay_passed": passed,
        "browser_manual_review": "not_performed",
        "integrity_file": "SHA256SUMS.txt",
    }
    (target / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    payloads = sorted(path for path in target.rglob("*") if path.is_file())
    (target / "SHA256SUMS.txt").write_text(
        "\n".join(f"{sha256(path)}  {path.relative_to(target).as_posix()}" for path in payloads) + "\n",
        encoding="utf-8",
    )
    verify_checksums(target)
    print(f"frozen: {target.relative_to(ROOT)} ({len(payloads)} verified payloads)")
    print(f"validation_passed: {validation.validation_passed}")
    print(f"san_compile_passed: {compile_result.passed}")
    print(f"visual_eval_passed: {visual.visual_eval_passed}")
    print(f"event_gate: {gate['decision']}")
    print("browser_manual_review: not_performed")


if __name__ == "__main__":
    main()
