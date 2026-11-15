"""Guarded one-request repair probe for TaskManager's initial TaskForm prop copy."""

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


FAILED_BATCH = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_task_manager_boolean_event_regression_v1_"
    "TaskManager_automatic_fail_20261028_220158"
)
SOURCE = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_task_manager_initdata_computed_probe_v1_result_20261028_233258"
)
PRE_RUN = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_task_manager_inline_prop_probe_v1_pre_run_20261028"
)
OUTPUT_DIR = ROOT / "data/experiments/pipeline/probes/formal_30_v4_task_manager_inline_prop_v1"
OUTPUT = OUTPUT_DIR / "TaskManager_inline_prop_v1.san"
REPORT = OUTPUT_DIR / "probe_report.json"
IMPLEMENTATION = [
    "migration_pipeline/probe_formal_30_v4_task_manager_inline_prop_v1.py",
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


def prepare() -> tuple[dict, dict, bytes, list[dict], bytes]:
    verify_checksums(FAILED_BATCH)
    verify_checksums(SOURCE)
    manifest = json.loads((SOURCE / "manifest.json").read_text(encoding="utf-8"))
    if (manifest.get("classification") != "reused_development_guarded_two_error_probe_result"
            or manifest.get("candidate_sha256") != sha256(SOURCE / "candidate.san")):
        raise RuntimeError("Expected the frozen, verified two-error probe result")
    state = json.loads((FAILED_BATCH / "repair_history.json").read_text(encoding="utf-8"))["state"]
    code = (SOURCE / "candidate.san").read_text(encoding="utf-8")
    validation = ValidateStage().run(ValidateStageInput(
        generated_code=code, ssm=state["ssm"],
        source_file=state.get("source_file", ""),
        vue_file_path=state.get("vue_file_path", ""),
    ))
    errors = validation.validation_errors
    if [item.get("code") for item in errors] != ["missing_inline_prop_dependent_initialization"]:
        raise RuntimeError("Frozen candidate no longer has only the expected initial prop error")
    unchanged, applied = RepairStage._deterministic_repair_plan(code, errors, [], state["ssm"])
    if unchanged != code or applied:
        raise RuntimeError("Probe would consume a deterministic repair round")
    prompt = build_repair_prompt(RepairPromptInput(
        ssm=state["ssm"], current_code=code,
        source_file=state.get("source_file", ""), validation_errors=errors,
    ))
    if (not prompt.startswith("Repair ONLY missing_inline_prop_dependent_initialization")
            or "const TaskForm" not in prompt
            or "BEFORE this.watch" not in prompt):
        raise RuntimeError("Focused inline-prop prompt did not activate")
    return manifest, state, code.encode("utf-8"), errors, prompt.encode("utf-8")


def freeze(manifest: dict, code: bytes, errors: list[dict], prompt: bytes) -> None:
    if PRE_RUN.exists() or OUTPUT.exists() or REPORT.exists():
        raise FileExistsError("Pre-run or output already exists; no overwrite allowed")
    for relative in IMPLEMENTATION:
        if not (ROOT / relative).is_file():
            raise FileNotFoundError(ROOT / relative)
    PRE_RUN.mkdir(parents=True)
    (PRE_RUN / "input.san").write_bytes(code)
    (PRE_RUN / "prompt.txt").write_bytes(prompt)
    (PRE_RUN / "validation_errors.json").write_text(
        json.dumps(errors, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    shutil.copy2(SOURCE / "manifest.json", PRE_RUN / "source_manifest.json")
    shutil.copy2(SOURCE / "SHA256SUMS.txt", PRE_RUN / "source_SHA256SUMS.txt")
    for relative in IMPLEMENTATION:
        destination = PRE_RUN / "code" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    metadata = {
        "snapshot_id": PRE_RUN.name,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "classification": "reused_development_guarded_inline_prop_probe_pre_run",
        "independent_holdout": False,
        "source_snapshot": manifest["snapshot_id"],
        "failed_batch_snapshot": FAILED_BATCH.name,
        "input_sha256": sha256(PRE_RUN / "input.san"),
        "prompt_sha256": sha256(PRE_RUN / "prompt.txt"),
        "validation_error_codes": [item.get("code") for item in errors],
        "boundary": "One repair request on a frozen development candidate; not a fresh batch or independent formal test.",
    }
    (PRE_RUN / "manifest.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    files = sorted(path for path in PRE_RUN.rglob("*") if path.is_file())
    (PRE_RUN / "SHA256SUMS.txt").write_text(
        "\n".join(
            f"{sha256(path)}  {path.relative_to(PRE_RUN).as_posix()}" for path in files
        ) + "\n", encoding="utf-8",
    )
    verify_checksums(PRE_RUN)
    print(f"frozen: {PRE_RUN.relative_to(ROOT)} ({len(files)} verified payloads)")


def verify_pre_run(manifest: dict, code: bytes, prompt: bytes) -> None:
    verify_checksums(PRE_RUN)
    frozen = json.loads((PRE_RUN / "manifest.json").read_text(encoding="utf-8"))
    if (frozen.get("source_snapshot") != manifest["snapshot_id"]
            or (PRE_RUN / "input.san").read_bytes() != code
            or (PRE_RUN / "prompt.txt").read_bytes() != prompt
            or frozen.get("input_sha256") != sha256(PRE_RUN / "input.san")
            or frozen.get("prompt_sha256") != sha256(PRE_RUN / "prompt.txt")):
        raise RuntimeError("Current input or prompt differs from pre-run freeze")
    for relative in IMPLEMENTATION:
        if sha256(ROOT / relative) != sha256(PRE_RUN / "code" / relative):
            raise RuntimeError(f"Implementation differs from pre-run freeze: {relative}")


def execute(manifest: dict, state: dict, code: bytes, errors: list[dict], prompt: bytes) -> None:
    verify_pre_run(manifest, code, prompt)
    if OUTPUT.exists() or REPORT.exists():
        raise FileExistsError("Probe output already exists; no overwrite allowed")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result = RepairStage().run(RepairStageInput(
        ssm=state["ssm"], generated_code=code.decode("utf-8"),
        source_file=state.get("source_file", ""),
        output_file_path=str(OUTPUT), validation_errors=errors,
        metadata={"experiment": "reused_development_inline_prop_probe_v1"},
    ))
    if result.repair_prompt.encode("utf-8") != prompt:
        raise RuntimeError("Actual model request prompt differs from pre-run freeze")
    if result.provider == "deterministic" or not OUTPUT.is_file():
        raise RuntimeError("Expected exactly one model repair response")
    candidate = OUTPUT.read_text(encoding="utf-8")
    if candidate != result.repaired_code:
        raise RuntimeError("Saved candidate differs from repair result")
    validation = ValidateStage().run(ValidateStageInput(
        generated_code=candidate, ssm=state["ssm"],
        source_file=state.get("source_file", ""),
        vue_file_path=state.get("vue_file_path", ""),
    ))
    visual = VisualEvalStage().run(VisualEvalStageInput(
        vue_file_path=state.get("vue_file_path"),
        vue_source=state.get("vue_source"),
        generated_code=candidate, generated_file_path=str(OUTPUT),
        source_file=state.get("source_file", ""),
    ))
    gate = assess_event_contract_regression(
        ssm=state["ssm"], before_code=code.decode("utf-8"),
        after_code=candidate, before_errors=errors,
        after_errors=validation.validation_errors,
    )
    report = {
        "classification": "reused_development_guarded_inline_prop_probe_result",
        "independent_holdout": False,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_snapshot": manifest["snapshot_id"],
        "pre_run_snapshot": PRE_RUN.name,
        "input_sha256": hashlib.sha256(code).hexdigest(),
        "prompt_sha256": hashlib.sha256(prompt).hexdigest(),
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
        "regression_gate": gate,
        "automatic_passed": bool(
            validation.validation_passed and visual.visual_eval_passed and not gate["should_stop"]
        ),
        "browser_manual_review": "not_performed",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"report: {REPORT.relative_to(ROOT)}")
    print(f"validation_passed: {validation.validation_passed}")
    print(f"visual_eval_passed: {visual.visual_eval_passed}")
    print(f"regression_gate: {gate['decision']}")
    print(f"automatic_passed: {report['automatic_passed']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--freeze", action="store_true", help="Freeze input, prompt, and code")
    group.add_argument("--execute", action="store_true", help="Make one model repair request")
    args = parser.parse_args()
    manifest, state, code, errors, prompt = prepare()
    print(f"source_snapshot: {manifest['snapshot_id']}")
    print(f"input_sha256: {hashlib.sha256(code).hexdigest()}")
    print(f"prompt_sha256: {hashlib.sha256(prompt).hexdigest()}")
    print(f"validation_error_codes: {[item.get('code') for item in errors]}")
    if args.freeze:
        freeze(manifest, code, errors, prompt)
    elif args.execute:
        execute(manifest, state, code, errors, prompt)
    else:
        print("dry_run: no model request or output write")


if __name__ == "__main__":
    main()
