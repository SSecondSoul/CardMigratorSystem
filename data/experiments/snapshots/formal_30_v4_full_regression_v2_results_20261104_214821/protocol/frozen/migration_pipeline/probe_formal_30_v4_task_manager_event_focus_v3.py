"""Freeze and execute one guarded event-only TaskManager development probe."""

from __future__ import annotations

import argparse
import hashlib
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
from migration_pipeline.stages.repair import RepairStage, RepairStageInput
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.stages.visual_eval import VisualEvalStage, VisualEvalStageInput
from migration_pipeline.utils.repair_prompt import RepairPromptInput, build_repair_prompt
from migration_pipeline.utils.repair_regression_guard import assess_event_contract_regression
from migration_pipeline.utils.san_compile import check_san_compile


SOURCE = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_semantic_focus_v2_TaskManager_automatic_fail_20261028_140129"
)
CANDIDATE = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_task_manager_semantic_probe_v2b_result_20261028_181549"
)
PRE_RUN = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_task_manager_event_focus_v3b_pre_run_20261028"
)
OUTPUT_DIR = ROOT / "data/experiments/pipeline/probes/formal_30_v4_task_manager_event_focus_v3b"
OUTPUT = OUTPUT_DIR / "TaskManager_event_focus_v3b.san"
REPORT = OUTPUT_DIR / "probe_report.json"
IMPLEMENTATION = [
    "migration_pipeline/probe_formal_30_v4_task_manager_event_focus_v3.py",
    "migration_pipeline/probe_formal_30_v4_task_manager_semantic_focus_v2.py",
    "migration_pipeline/stages/repair.py",
    "migration_pipeline/stages/validate.py",
    "migration_pipeline/stages/visual_eval.py",
    "migration_pipeline/utils/repair_prompt.py",
    "migration_pipeline/utils/repair_regression_guard.py",
    "migration_pipeline/utils/san_compile.py",
    "migration_pipeline/utils/san_render.py",
    "migration_pipeline/utils/vue_render.py",
    "migration_pipeline/utils/dom_compare.py",
    "migration_pipeline/repair_client.py",
    "local_server/api/evaluation_routes.py",
]
EXPECTED_ERRORS = {
    "event_arguments_not_landed", "missing_event_bindings", "missing_event_handlers"
}


def prepare() -> tuple[dict, dict, str, list[dict], str]:
    verify_checksums(SOURCE)
    verify_checksums(CANDIDATE)
    source_manifest = json.loads((SOURCE / "manifest.json").read_text(encoding="utf-8"))
    candidate_manifest = json.loads((CANDIDATE / "manifest.json").read_text(encoding="utf-8"))
    if source_manifest.get("sample_id") != "TaskManager":
        raise RuntimeError("Expected frozen TaskManager source")
    if candidate_manifest.get("sample_id") not in (None, "TaskManager"):
        raise RuntimeError("Expected frozen TaskManager candidate")
    state = json.loads((SOURCE / "repair_history.json").read_text(encoding="utf-8"))["state"]
    ssm = state["ssm"]
    candidate = (CANDIDATE / "candidate.san").read_text(encoding="utf-8")
    prepared = RepairStage._normalize_unresolved_source_event_alias(candidate, ssm)
    prepared = RepairStage._normalize_misplaced_mounted_first_call(prepared, ssm)
    prepared = RepairStage._normalize_terminal_state_array_splice(prepared, ssm)
    if prepared == candidate:
        raise RuntimeError("Bounded offline replay did not change candidate")
    compiled = check_san_compile(san_source=prepared)
    if compiled.skipped or not compiled.passed:
        raise RuntimeError(f"Prepared San does not compile: {compiled.diagnostics}")
    validation = ValidateStage().run(ValidateStageInput(
        generated_code=prepared, ssm=ssm,
        source_file=state.get("source_file", ""),
        vue_file_path=state.get("vue_file_path", ""),
    ))
    errors = validation.validation_errors
    if {issue.get("code") for issue in errors} != EXPECTED_ERRORS:
        raise RuntimeError("Prepared input no longer has only the expected event residuals")
    unchanged, applied = RepairStage._deterministic_repair_plan(prepared, errors, [], ssm)
    if unchanged != prepared or applied:
        raise RuntimeError("Probe would not make a model request")
    prompt = build_repair_prompt(RepairPromptInput(
        ssm=ssm, current_code=prepared,
        source_file=state.get("source_file", ""), validation_errors=errors,
    ))
    if "repairing ONLY the remaining event contract errors" not in prompt:
        raise RuntimeError("Event-only prompt did not activate")
    return source_manifest, state, prepared, errors, prompt


def freeze(source_manifest: dict, prepared: str, errors: list[dict], prompt: str) -> None:
    if PRE_RUN.exists() or OUTPUT.exists() or REPORT.exists():
        raise FileExistsError("Pre-run or output already exists; no overwrite allowed")
    for relative in IMPLEMENTATION:
        if not (ROOT / relative).is_file():
            raise RuntimeError(f"Missing implementation file: {relative}")
    PRE_RUN.mkdir(parents=True)
    (PRE_RUN / "input.san").write_bytes(prepared.encode("utf-8"))
    (PRE_RUN / "prompt.txt").write_bytes(prompt.encode("utf-8"))
    (PRE_RUN / "validation_errors.json").write_text(
        json.dumps(errors, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    shutil.copy2(SOURCE / "manifest.json", PRE_RUN / "source_manifest.json")
    shutil.copy2(CANDIDATE / "manifest.json", PRE_RUN / "candidate_manifest.json")
    for relative in IMPLEMENTATION:
        destination = PRE_RUN / "code" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    manifest = {
        "snapshot_id": PRE_RUN.name,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "classification": "reused_development_guarded_event_only_probe_pre_run",
        "independent_holdout": False,
        "source_snapshot": source_manifest["snapshot_id"],
        "candidate_snapshot": CANDIDATE.name,
        "input_sha256": sha256(PRE_RUN / "input.san"),
        "prompt_sha256": sha256(PRE_RUN / "prompt.txt"),
        "validation_error_codes": [issue.get("code") for issue in errors],
        "boundary": "One model repair request on a bounded offline replay; not a formal independent test.",
    }
    (PRE_RUN / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    files = sorted(path for path in PRE_RUN.rglob("*") if path.is_file())
    (PRE_RUN / "SHA256SUMS.txt").write_text(
        "\n".join(f"{sha256(path)}  {path.relative_to(PRE_RUN).as_posix()}" for path in files) + "\n",
        encoding="utf-8",
    )
    verify_checksums(PRE_RUN)
    print(f"frozen: {PRE_RUN.relative_to(ROOT)} ({len(files)} verified payloads)")


def verify_frozen_pre_run(source_manifest: dict, prepared: str, prompt: str) -> dict:
    verify_checksums(PRE_RUN)
    frozen = json.loads((PRE_RUN / "manifest.json").read_text(encoding="utf-8"))
    if (frozen.get("source_snapshot") != source_manifest["snapshot_id"]
            or frozen.get("candidate_snapshot") != CANDIDATE.name
            or frozen.get("input_sha256") != sha256(PRE_RUN / "input.san")
            or frozen.get("prompt_sha256") != sha256(PRE_RUN / "prompt.txt")
            or (PRE_RUN / "input.san").read_text(encoding="utf-8") != prepared
            or (PRE_RUN / "prompt.txt").read_text(encoding="utf-8") != prompt):
        raise RuntimeError("Current input/prompt differs from pre-run freeze")
    for relative in IMPLEMENTATION:
        if sha256(ROOT / relative) != sha256(PRE_RUN / "code" / relative):
            raise RuntimeError(f"Implementation differs from pre-run freeze: {relative}")
    return frozen


def execute(source_manifest: dict, state: dict, prepared: str,
            errors: list[dict], prompt: str) -> None:
    verify_frozen_pre_run(source_manifest, prepared, prompt)
    if OUTPUT.exists() or REPORT.exists():
        raise FileExistsError("Probe output already exists; no overwrite allowed")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result = RepairStage().run(RepairStageInput(
        ssm=state["ssm"], generated_code=prepared,
        source_file=state.get("source_file", ""),
        output_file_path=str(OUTPUT), validation_errors=errors,
        metadata={"experiment": "reused_development_guarded_event_only_probe_v3b"},
    ))
    if result.provider == "deterministic" or not OUTPUT.is_file():
        raise RuntimeError("Expected one model repair response")
    candidate = OUTPUT.read_text(encoding="utf-8")
    if candidate != result.repaired_code:
        raise RuntimeError("Saved candidate differs from repair result")
    validation = ValidateStage().run(ValidateStageInput(
        generated_code=candidate, ssm=state["ssm"],
        source_file=state.get("source_file", ""),
        vue_file_path=state.get("vue_file_path", ""),
    ))
    gate = assess_event_contract_regression(
        ssm=state["ssm"], before_code=prepared, after_code=candidate,
        before_errors=errors, after_errors=validation.validation_errors,
    )
    visual = VisualEvalStage().run(VisualEvalStageInput(
        vue_file_path=state.get("vue_file_path"),
        vue_source=state.get("vue_source"),
        generated_code=candidate, generated_file_path=str(OUTPUT),
        source_file=state.get("source_file", ""),
    ))
    report = {
        "classification": "reused_development_guarded_event_only_probe_result",
        "independent_holdout": False,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_snapshot": source_manifest["snapshot_id"],
        "candidate_snapshot": CANDIDATE.name,
        "pre_run_snapshot": PRE_RUN.name,
        "input_sha256": hashlib.sha256(prepared.encode("utf-8")).hexdigest(),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "output_file": OUTPUT.relative_to(ROOT).as_posix(),
        "output_sha256": sha256(OUTPUT),
        "provider": result.provider,
        "model": result.model,
        "usage": result.usage,
        "pipeline_postprocessing": result.raw_response.get("pipeline_postprocessing", []),
        "validation_passed": validation.validation_passed,
        "validation_errors": validation.validation_errors,
        "visual_eval_passed": visual.visual_eval_passed,
        "visual_eval_errors": visual.visual_eval_errors,
        "structure_similarity": visual.structure_similarity,
        "event_regression_gate": gate,
        "automatic_passed": bool(validation.validation_passed and visual.visual_eval_passed
                                 and not gate["should_stop"]),
        "browser_manual_review": "not_performed",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"report: {REPORT.relative_to(ROOT)}")
    print(f"validation_passed: {validation.validation_passed}")
    print(f"visual_eval_passed: {visual.visual_eval_passed}")
    print(f"event_gate: {gate['decision']}")
    print(f"automatic_passed: {report['automatic_passed']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--freeze", action="store_true", help="Freeze input, prompt, and implementation")
    group.add_argument("--execute", action="store_true", help="Make exactly one model repair request")
    args = parser.parse_args()
    manifest, state, prepared, errors, prompt = prepare()
    print(f"source_snapshot: {manifest['snapshot_id']}")
    print(f"candidate_snapshot: {CANDIDATE.name}")
    print(f"prepared_input_sha256: {hashlib.sha256(prepared.encode('utf-8')).hexdigest()}")
    print(f"focused_prompt_sha256: {hashlib.sha256(prompt.encode('utf-8')).hexdigest()}")
    print(f"validation_error_codes: {[issue.get('code') for issue in errors]}")
    if args.freeze:
        freeze(manifest, prepared, errors, prompt)
    elif args.execute:
        execute(manifest, state, prepared, errors, prompt)
    else:
        print("dry_run: no model request or output write")


if __name__ == "__main__":
    main()
