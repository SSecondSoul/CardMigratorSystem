"""Replay the bounded RuleBuilder class merge without changing frozen evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from migration_pipeline.stages.repair import RepairStage, RepairStageInput
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.stages.visual_eval import VisualEvalStage, VisualEvalStageInput


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data/experiments/snapshots/formal_30_v4_rule_builder_pass_20261022_233452"
SOURCE = SNAPSHOT / "pipeline/complex/RuleBuilder_repaired.san"
VUE = ROOT / "data/datasets/components/03_complex/RuleBuilder/vue/RuleBuilder.vue"
OUTPUT = ROOT / "data/experiments/pipeline/manual_fixes/formal_30_v4_rule_builder/RuleBuilder_class_merge.san"
REPORT = ROOT / "data/experiments/repair_reports/manual_fixes/formal_30_v4_rule_builder_class_merge.json"


class NoLLM:
    def repair(self, _request):
        raise RuntimeError("This replay must not call an LLM")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    checksum_lines = (SNAPSHOT / "SHA256SUMS.txt").read_text(encoding="utf-8-sig").splitlines()
    expected = {
        relative: checksum.lower()
        for line in checksum_lines if line.strip()
        for checksum, relative in [line.split("  ", 1)]
    }
    if digest(SOURCE) != expected["pipeline/complex/RuleBuilder_repaired.san"]:
        raise RuntimeError("Frozen source checksum mismatch")

    original = SOURCE.read_text(encoding="utf-8")
    before = ValidateStage().run(ValidateStageInput(generated_code=original, compile_check=False))
    if [issue["code"] for issue in before.validation_errors] != ["duplicate_class_attribute"]:
        raise RuntimeError(f"Unexpected source errors: {before.validation_errors}")
    normalized, repairs = RepairStage._deterministic_repair_plan(
        original, before.validation_errors, [],
    )
    if [item[0] for item in repairs] != ["san_duplicate_class_normalizer"]:
        raise RuntimeError(f"Unexpected repair plan: {repairs}")
    after = ValidateStage().run(ValidateStageInput(generated_code=normalized))
    if not after.validation_passed or not after.san_compile_result or not after.san_compile_result["passed"]:
        raise RuntimeError(f"Static or compile replay failed: {after.validation_errors}")
    visual = VisualEvalStage().run(VisualEvalStageInput(
        vue_file_path=str(VUE), generated_code=normalized,
    ))
    if not visual.visual_eval_passed:
        raise RuntimeError(f"Visual replay failed: {visual.visual_eval_errors}")

    result = RepairStage(repair_client=NoLLM()).run(RepairStageInput(
        ssm={},
        generated_code=original,
        source_file="RuleBuilder",
        output_file_path=str(OUTPUT),
        validation_errors=before.validation_errors,
    ))
    if result.provider != "deterministic" or result.repaired_code != normalized:
        raise RuntimeError("Deterministic replay changed unexpectedly")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "experiment": "formal_30_v4_rule_builder_manual_class_fix",
        "classification": "development_manual_repair",
        "status": "automated_candidate_ready",
        "user_observation": "San 基础条件选中样式及新增条件行样式与 Vue 不一致",
        "root_cause": "The frozen San emitted separate static and dynamic class attributes on the group button and rule row.",
        "frozen_source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "frozen_source_sha256": digest(SOURCE),
        "vue_source": str(VUE.relative_to(ROOT)).replace("\\", "/"),
        "vue_source_sha256": digest(VUE),
        "candidate": str(OUTPUT.relative_to(ROOT)).replace("\\", "/"),
        "candidate_sha256": digest(OUTPUT),
        "repair_provider": result.provider,
        "repair_model": result.model,
        "repair_tokens": result.usage["total_tokens"],
        "validation_errors_before": [issue["code"] for issue in before.validation_errors],
        "validation_errors_after": [issue["code"] for issue in after.validation_errors],
        "san_compile": after.san_compile_result,
        "visual_eval_passed": visual.visual_eval_passed,
        "visual_eval_error_codes": [issue["code"] for issue in visual.visual_eval_errors],
        "initial_structure_similarity": visual.structure_similarity,
        "initial_tag_sequence_similarity": visual.tag_sequence_similarity,
        "initial_text_similarity": visual.text_similarity,
        "initial_tree_edit_distance": visual.tree_edit_distance,
        "boundary": "Initial DOM replay is not an interaction test. Frozen snapshot and original batch summary remain unchanged.",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"candidate: {OUTPUT.relative_to(ROOT)}")
    print(f"report: {REPORT.relative_to(ROOT)}")
    print(f"initial visual pass: {visual.visual_eval_passed}; similarity: {visual.structure_similarity}")


if __name__ == "__main__":
    main()
