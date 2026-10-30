"""Freeze and run one guarded TaskManager semantic repair probe on development evidence."""

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

from migration_pipeline.stages.repair import RepairStage, RepairStageInput
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.stages.visual_eval import VisualEvalStage, VisualEvalStageInput
from migration_pipeline.utils.repair_prompt import RepairPromptInput, build_repair_prompt
from migration_pipeline.utils.repair_regression_guard import assess_event_contract_regression


SOURCE = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_semantic_focus_v2_TaskManager_automatic_fail_20261028_140129"
)
PRE_RUN = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_task_manager_semantic_probe_v2_pre_run_20261028"
)
OUTPUT_DIR = ROOT / "data/experiments/pipeline/probes/formal_30_v4_task_manager_semantic_probe_v2"
OUTPUT = OUTPUT_DIR / "TaskManager_semantic_probe_v2.san"
REPORT = OUTPUT_DIR / "probe_report.json"
IMPLEMENTATION = [
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


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_checksums(directory: Path) -> None:
    for line in (directory / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        if relative.startswith("/") or ".." in Path(relative).parts:
            raise RuntimeError(f"Unsafe checksum entry: {relative}")
        if sha256(directory / relative) != expected:
            raise RuntimeError(f"Checksum mismatch: {directory / relative}")


def prepare() -> tuple[dict, dict, str, list[dict], str]:
    verify_checksums(SOURCE)
    manifest = json.loads((SOURCE / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("sample_id") != "TaskManager" or manifest.get("automatic_passed") is not False:
        raise RuntimeError("Expected frozen TaskManager failure")
    state = json.loads((SOURCE / "repair_history.json").read_text(encoding="utf-8"))["state"]
    original = (SOURCE / "repair_round_3.san").read_text(encoding="utf-8")
    prepared = RepairStage._normalize_empty_modifier_handlers(
        RepairStage._normalize_simple_template_syntax(original)
    )
    validation = ValidateStage().run(ValidateStageInput(
        generated_code=prepared, ssm=state["ssm"],
        source_file=state.get("source_file", ""),
        vue_file_path=state.get("vue_file_path", ""),
    ))
    errors = validation.validation_errors
    if not prepared or prepared == original or validation.validation_passed:
        raise RuntimeError("Unexpected prepared input or validation result")
    unchanged_plan, applied = RepairStage._deterministic_repair_plan(
        prepared, errors, [], state["ssm"]
    )
    if unchanged_plan != prepared or applied:
        raise RuntimeError("Probe would not make a model request")
    prompt = build_repair_prompt(RepairPromptInput(
        ssm=state["ssm"], current_code=prepared,
        source_file=state.get("source_file", ""), validation_errors=errors,
    ))
    if "ALL listed semantic validation errors" not in prompt:
        raise RuntimeError("Focused semantic prompt did not activate")
    return manifest, state, prepared, errors, prompt


def freeze(manifest: dict, prepared: str, errors: list[dict], prompt: str) -> None:
    if PRE_RUN.exists() or OUTPUT.exists() or REPORT.exists():
        raise FileExistsError("Pre-run or output already exists; no overwrite allowed")
    for relative in IMPLEMENTATION:
        if not (ROOT / relative).is_file():
            raise RuntimeError(f"Missing implementation file: {relative}")
    PRE_RUN.mkdir(parents=True)
    (PRE_RUN / "input.san").write_text(prepared, encoding="utf-8")
    (PRE_RUN / "prompt.txt").write_text(prompt, encoding="utf-8")
    (PRE_RUN / "validation_errors.json").write_text(
        json.dumps(errors, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    shutil.copy2(SOURCE / "manifest.json", PRE_RUN / "source_manifest.json")
    shutil.copy2(SOURCE / "SHA256SUMS.txt", PRE_RUN / "source_SHA256SUMS.txt")
    for relative in IMPLEMENTATION:
        destination = PRE_RUN / "code" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    record = {
        "snapshot_id": PRE_RUN.name,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "classification": "reused_development_guarded_single_repair_probe_pre_run",
        "independent_holdout": False,
        "source_snapshot": manifest["snapshot_id"],
        "input_sha256": sha256(PRE_RUN / "input.san"),
        "prompt_sha256": sha256(PRE_RUN / "prompt.txt"),
        "validation_error_codes": [issue.get("code") for issue in errors],
        "boundary": "One repair request after deterministic syntax preparation; not a fresh batch or independent formal test.",
    }
    (PRE_RUN / "manifest.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    files = sorted(path for path in PRE_RUN.rglob("*") if path.is_file())
    (PRE_RUN / "SHA256SUMS.txt").write_text(
        "\n".join(f"{sha256(path)}  {path.relative_to(PRE_RUN).as_posix()}" for path in files) + "\n",
        encoding="utf-8",
    )
    verify_checksums(PRE_RUN)
    print(f"frozen: {PRE_RUN.relative_to(ROOT)} ({len(files)} verified payloads)")


def execute(manifest: dict, state: dict, prepared: str, errors: list[dict], prompt: str) -> None:
    verify_checksums(PRE_RUN)
    frozen = json.loads((PRE_RUN / "manifest.json").read_text(encoding="utf-8"))
    if (frozen.get("source_snapshot") != manifest["snapshot_id"]
            or frozen.get("input_sha256") != hashlib.sha256(prepared.encode("utf-8")).hexdigest()
            or frozen.get("prompt_sha256") != hashlib.sha256(prompt.encode("utf-8")).hexdigest()
            or (PRE_RUN / "prompt.txt").read_text(encoding="utf-8") != prompt):
        raise RuntimeError("Current input/prompt differs from pre-run freeze")
    for relative in IMPLEMENTATION:
        if sha256(ROOT / relative) != sha256(PRE_RUN / "code" / relative):
            raise RuntimeError(f"Implementation differs from pre-run freeze: {relative}")
    if OUTPUT.exists() or REPORT.exists():
        raise FileExistsError("Probe output already exists; no overwrite allowed")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result = RepairStage().run(RepairStageInput(
        ssm=state["ssm"], generated_code=prepared,
        source_file=state.get("source_file", "TaskManager.vue"),
        output_file_path=str(OUTPUT), validation_errors=errors,
        metadata={"experiment": "reused_development_guarded_semantic_probe_v2"},
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
        "classification": "reused_development_guarded_single_repair_probe_result",
        "independent_holdout": False,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_snapshot": manifest["snapshot_id"],
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
