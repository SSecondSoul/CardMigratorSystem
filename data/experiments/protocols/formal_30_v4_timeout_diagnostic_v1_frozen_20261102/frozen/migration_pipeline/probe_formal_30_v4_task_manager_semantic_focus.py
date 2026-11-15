"""One LLM repair probe from the frozen TaskManager v2 failure; never rerun generation."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from migration_pipeline.repair_client import RepairRequest, create_repair_client
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.stages.visual_eval import VisualEvalStage, VisualEvalStageInput
from migration_pipeline.utils.repair_prompt import RepairPromptInput, build_repair_prompt


SNAPSHOT = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_semantic_focus_v2_TaskManager_automatic_fail_20261028_140129"
)
PRE_RUN = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_task_manager_semantic_probe_v1_pre_run_20261028"
)
OUTPUT_DIR = ROOT / "data/experiments/pipeline/probes/formal_30_v4_task_manager_semantic_probe_v1"
OUTPUT = OUTPUT_DIR / "TaskManager_semantic_probe.san"
REPORT = OUTPUT_DIR / "probe_report.json"
SERVER_DEFAULT = ROOT / "data/experiments/TaskManager_semantic_probe.san"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_frozen_input() -> tuple[dict, dict, str, str]:
    checksums = (SNAPSHOT / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
    if len(checksums) != 11:
        raise RuntimeError("Unexpected frozen result payload count")
    for line in checksums:
        expected, name = line.split("  ", 1)
        if name != Path(name).name or sha256(SNAPSHOT / name) != expected:
            raise RuntimeError(f"Frozen input checksum mismatch: {name}")
    manifest = json.loads((SNAPSHOT / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("sample_id") != "TaskManager" or manifest.get("automatic_passed") is not False:
        raise RuntimeError("Unexpected frozen sample or outcome")
    history = json.loads((SNAPSHOT / "repair_history.json").read_text(encoding="utf-8"))
    state = history["state"]
    code = (SNAPSHOT / "repair_round_3.san").read_text(encoding="utf-8")
    errors = state["final_validate_result"]["validation_errors"]
    prompt = build_repair_prompt(RepairPromptInput(
        ssm=state["ssm"],
        current_code=code,
        source_file=state.get("source_file", ""),
        validation_errors=errors,
        visual_eval_errors=[],
    ))
    if not prompt.startswith("You are repairing a standalone San single-file component."):
        raise RuntimeError("Focused semantic prompt did not activate")
    return manifest, state, code, prompt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Make one model request and validate its output")
    args = parser.parse_args()
    manifest, state, code, prompt = load_frozen_input()
    prompt_digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    print(f"frozen_input: {manifest['snapshot_id']}")
    print(f"focused_prompt_sha256: {prompt_digest}")
    print(f"focused_prompt_chars: {len(prompt)}")
    if not args.execute:
        print("dry_run: no model request or output write")
        return
    if OUTPUT.exists() or REPORT.exists() or SERVER_DEFAULT.exists():
        raise FileExistsError("Probe output or server default already exists; preserve existing evidence")
    frozen_prompt = PRE_RUN / "prompt.txt"
    if not frozen_prompt.is_file() or frozen_prompt.read_text(encoding="utf-8") != prompt:
        raise RuntimeError("Prompt differs from the pre-run freeze")
    frozen_manifest = json.loads((PRE_RUN / "manifest.json").read_text(encoding="utf-8"))
    if frozen_manifest.get("prompt_sha256") != prompt_digest:
        raise RuntimeError("Pre-run prompt hash mismatch")

    result = create_repair_client().repair(RepairRequest(
        ssm=state["ssm"],
        repair_prompt=prompt,
        source_file="TaskManager_semantic_probe.vue",
        current_code=code,
        output_file_path=str(OUTPUT),
        repair_report={"validation": {"errors": state["final_validate_result"]["validation_errors"]}},
        metadata={"experiment": "reused_development_semantic_probe_v1"},
    ))
    if not OUTPUT.is_file() or OUTPUT.read_text(encoding="utf-8") != result.code:
        raise RuntimeError("Probe output was not saved at the expected unique path")
    validation = ValidateStage().run(ValidateStageInput(
        generated_code=result.code,
        generated_file_path=str(OUTPUT),
        ssm=state["ssm"],
        source_file=state.get("source_file", ""),
        vue_file_path=state.get("vue_file_path", "") or "",
    ))
    visual = VisualEvalStage().run(VisualEvalStageInput(
        vue_file_path=state.get("vue_file_path"),
        vue_source=state.get("vue_source"),
        generated_code=result.code,
        generated_file_path=str(OUTPUT),
        source_file=state.get("source_file", ""),
    ))
    report = {
        "classification": "reused_development_single_repair_probe",
        "independent_holdout": False,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "frozen_input": manifest["snapshot_id"],
        "pre_run_snapshot": frozen_manifest["snapshot_id"],
        "input_sha256": sha256(SNAPSHOT / "repair_round_3.san"),
        "prompt_sha256": prompt_digest,
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
        "tree_edit_distance": visual.tree_edit_distance,
        "browser_manual_review": "not_performed",
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"report: {REPORT.relative_to(ROOT)}")
    print(f"validation_passed: {validation.validation_passed}")
    print(f"visual_eval_passed: {visual.visual_eval_passed}")


if __name__ == "__main__":
    main()
