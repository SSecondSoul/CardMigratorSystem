"""Probe a focused, single-round repair from the frozen AnalyticsDashboard failure.

This is a development-only repair probe, not a fresh Vue-to-San batch run.
The frozen source is read-only; --execute requires a running local LLM server.
"""

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

from migration_pipeline.stages.repair import RepairStage, RepairStageInput
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.stages.visual_eval import VisualEvalStage, VisualEvalStageInput
from migration_pipeline.utils.repair_prompt import RepairPromptInput, build_repair_prompt


SNAPSHOT = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_generalization_followup_analytics_dashboard_automatic_fail_20261027_144124"
)
OUTPUT_DIR = ROOT / "data/experiments/pipeline/probes/formal_30_v4_analytics_computed_focus_v1"
OUTPUT = OUTPUT_DIR / "AnalyticsDashboard_repaired.san"
REPORT = OUTPUT_DIR / "probe_report.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_frozen_input() -> tuple[dict, dict, str]:
    checksums = (SNAPSHOT / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
    if len(checksums) != 8:
        raise RuntimeError("Unexpected snapshot payload count")
    for line in checksums:
        expected, name = line.split("  ", 1)
        if name != Path(name).name or sha256(SNAPSHOT / name) != expected:
            raise RuntimeError(f"Frozen snapshot checksum mismatch: {name}")
    manifest = json.loads((SNAPSHOT / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("sample_id") != "analytics_dashboard" or manifest.get("automatic_passed") is not False:
        raise RuntimeError("Unexpected frozen sample or result")
    history = json.loads((SNAPSHOT / "repair_history.json").read_text(encoding="utf-8"))
    state = history["state"]
    code = (SNAPSHOT / "final.san").read_text(encoding="utf-8")
    codes = {issue.get("code") for issue in state["validation_errors"]}
    if codes != {"invalid_san_computed_instance_method_call"} or state["visual_eval_errors"]:
        raise RuntimeError("The frozen failure is no longer the single targeted error")
    if not state.get("ssm"):
        raise RuntimeError("Frozen repair history lacks SSM")
    return manifest, state, code


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Call the local LLM once and write a new candidate/report")
    args = parser.parse_args()
    manifest, state, code = load_frozen_input()
    prompt = build_repair_prompt(RepairPromptInput(
        ssm=state["ssm"],
        current_code=code,
        source_file=state.get("source_file", ""),
        validation_errors=state["validation_errors"],
        visual_eval_errors=state["visual_eval_errors"],
    ))
    if not prompt.startswith("You are repairing a standalone San single-file component."):
        raise RuntimeError("Focused prompt did not activate")
    print(f"frozen_input: {manifest['snapshot_id']}")
    print(f"input_sha256: {sha256(SNAPSHOT / 'final.san')}")
    print(f"focused_prompt_sha256: {hashlib.sha256(prompt.encode('utf-8')).hexdigest()}")
    print(f"focused_prompt_chars: {len(prompt)}")
    if not args.execute:
        print("dry_run: no LLM call or file write")
        return
    if OUTPUT.exists() or REPORT.exists():
        raise FileExistsError("Probe output already exists; preserve it and choose a new probe version")

    result = RepairStage().run(RepairStageInput(
        ssm=state["ssm"],
        generated_code=code,
        source_file=state.get("source_file", "AnalyticsDashboard.vue"),
        output_file_path=str(OUTPUT),
        validation_errors=state["validation_errors"],
        validation_warnings=state.get("validation_warnings", []),
        visual_eval_errors=state["visual_eval_errors"],
        visual_eval_warnings=state.get("visual_eval_warnings", []),
        repair_attempt=1,
    ))
    validation = ValidateStage().run(ValidateStageInput(
        generated_code=result.repaired_code,
        generated_file_path=str(OUTPUT),
        ssm=state["ssm"],
        source_file=state.get("source_file", ""),
        vue_file_path=state.get("vue_file_path", "") or "",
    ))
    visual = VisualEvalStage().run(VisualEvalStageInput(
        vue_file_path=state.get("vue_file_path"),
        vue_source=state.get("vue_source"),
        generated_code=result.repaired_code,
        generated_file_path=str(OUTPUT),
        source_file=state.get("source_file", ""),
    ))
    report = {
        "classification": "reused_development_regression_repair_probe",
        "independent_holdout": False,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "frozen_input": manifest["snapshot_id"],
        "input_sha256": sha256(SNAPSHOT / "final.san"),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
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
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"report: {REPORT.relative_to(ROOT)}")
    print(f"validation_passed: {validation.validation_passed}")
    print(f"visual_eval_passed: {visual.visual_eval_passed}")


if __name__ == "__main__":
    main()
