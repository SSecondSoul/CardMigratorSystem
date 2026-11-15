"""One-request development probe for five frozen TaskManager residual errors."""

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


SOURCE = ROOT / "data/experiments/snapshots/formal_30_v4_task_manager_event_computed_regression_v1_TaskManager_automatic_fail_20261029_170150"
PRE_RUN = ROOT / "data/experiments/snapshots/formal_30_v4_task_manager_five_residual_probe_v1_pre_run_20261029"
OUTPUT_DIR = ROOT / "data/experiments/pipeline/probes/formal_30_v4_task_manager_five_residual_v1"
OUTPUT = OUTPUT_DIR / "TaskManager_five_residual_v1.san"
REPORT = OUTPUT_DIR / "probe_report.json"
IMPLEMENTATION = [
    "migration_pipeline/probe_formal_30_v4_task_manager_five_residual_v1.py",
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
    "tests/test_semantic_residual_repair_prompt.py",
]
EXPECTED_ERRORS = [
    "invalid_san_init_data_store_access",
    "missing_inline_prop_dependent_initialization",
    "invalid_san_computed_instance_method_call",
    "hidden_template_reactive_dependency",
    "lifecycle_behavior_not_landed",
]
EXTRA_INSTRUCTION = (
    "The frozen Vue TaskForm data() initializes formData with "
    "this.createFormData(this.task) and watches task for later changes. The San "
    "TaskForm must return an independent default formData from initData(), then "
    "in inited() set formData from the already available first task prop using "
    "createFormData(this.data.get('task')), and watch task for later changes. "
    "Do not access this.data or a component method from initData(). "
    "The source parent mounted() calls loadInitialData(), startAutoSync(), then "
    "showNotification(...) in that order; move precisely those startup calls "
    "from parent inited() to attached() without duplicates. Keep watch registration "
    "in inited() and cleanup in disposed(). In filteredTasks computed, use an "
    "equivalent pure isOverdue helper, retaining the instance method for other "
    "callers. In the filter-tab template pass reactive tasks explicitly to "
    "getTaskCount; that method must count the passed tasks and preserve all "
    "filter branches. Preserve all existing modal and drag/drop bindings."
)


def prepare() -> tuple[dict, dict, bytes, list[dict], bytes]:
    verify_checksums(SOURCE)
    manifest = json.loads((SOURCE / "manifest.json").read_text(encoding="utf-8"))
    if (manifest.get("sample_id") != "TaskManager"
            or manifest.get("automatic_passed") is not False
            or manifest.get("repair_rounds") != 3):
        raise RuntimeError("Expected the frozen failed TaskManager regression")
    state = json.loads((SOURCE / "repair_history.json").read_text(encoding="utf-8"))["state"]
    code = (SOURCE / "repair_round_3.san").read_text(encoding="utf-8")
    source = (SOURCE / "source.vue").read_text(encoding="utf-8")
    if ("this.createFormData(this.task)" not in source
            or "mounted()" not in source
            or "this.loadInitialData();" not in source
            or "this.startAutoSync();" not in source):
        raise RuntimeError("Frozen Vue prop or lifecycle contract changed")
    if ("formData: this.createFormData(this.data.get('task'))" not in code
            or "getTaskCount(filter.value)" not in code
            or "this.isOverdue(task)" not in code):
        raise RuntimeError("Frozen San residual baseline changed")
    validation = ValidateStage().run(ValidateStageInput(
        generated_code=code, ssm=state["ssm"],
        source_file=state.get("source_file", ""),
        vue_file_path=state.get("vue_file_path", ""),
    ))
    errors = validation.validation_errors
    if [item.get("code") for item in errors] != EXPECTED_ERRORS:
        raise RuntimeError("Frozen candidate no longer has the five expected errors")
    unchanged, applied = RepairStage._deterministic_repair_plan(code, errors, [], state["ssm"])
    if unchanged != code or applied:
        raise RuntimeError("Probe would consume a deterministic repair round")
    prompt = build_repair_prompt(RepairPromptInput(
        ssm=state["ssm"], current_code=code,
        source_file=state.get("source_file", ""),
        validation_errors=errors, extra_instruction=EXTRA_INSTRUCTION,
    ))
    if (not prompt.startswith("Repair ONLY these five remaining static error families")
            or "TaskForm" not in prompt or "mounted" not in prompt
            or EXTRA_INSTRUCTION not in prompt):
        raise RuntimeError("Focused five-error prompt did not activate")
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
    for name in ("manifest.json", "SHA256SUMS.txt", "source.vue"):
        shutil.copy2(SOURCE / name, PRE_RUN / f"source_{name}")
    for relative in IMPLEMENTATION:
        destination = PRE_RUN / "code" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    metadata = {
        "snapshot_id": PRE_RUN.name,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "classification": "reused_development_guarded_five_residual_probe_pre_run",
        "independent_holdout": False,
        "source_snapshot": manifest["snapshot_id"],
        "input_sha256": sha256(PRE_RUN / "input.san"),
        "prompt_sha256": sha256(PRE_RUN / "prompt.txt"),
        "validation_error_codes": [item.get("code") for item in errors],
        "boundary": "One model repair request on a frozen failed development candidate, not a fresh batch or independent test.",
    }
    (PRE_RUN / "manifest.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    payloads = sorted(path for path in PRE_RUN.rglob("*") if path.is_file())
    (PRE_RUN / "SHA256SUMS.txt").write_text(
        "\n".join(f"{sha256(path)}  {path.relative_to(PRE_RUN).as_posix()}" for path in payloads) + "\n",
        encoding="utf-8",
    )
    verify_checksums(PRE_RUN)
    print(f"frozen: {PRE_RUN.relative_to(ROOT)} ({len(payloads)} verified payloads)")


def verify_pre_run(manifest: dict, code: bytes, prompt: bytes) -> None:
    verify_checksums(PRE_RUN)
    frozen = json.loads((PRE_RUN / "manifest.json").read_text(encoding="utf-8"))
    if (frozen.get("source_snapshot") != manifest["snapshot_id"]
            or (PRE_RUN / "input.san").read_bytes() != code
            or (PRE_RUN / "prompt.txt").read_bytes() != prompt):
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
        repair_instruction=EXTRA_INSTRUCTION,
        metadata={"experiment": "reused_development_five_residual_probe_v1"},
    ))
    if result.repair_prompt.encode("utf-8") != prompt:
        raise RuntimeError("Actual model prompt differs from pre-run freeze")
    if result.provider == "deterministic" or not OUTPUT.is_file():
        raise RuntimeError("Expected exactly one model repair response")
    candidate = OUTPUT.read_text(encoding="utf-8")
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
        "classification": "reused_development_guarded_five_residual_probe_result",
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
