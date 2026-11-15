"""Read-only-source replay of the generic inline duplicate-class normalizer.

The frozen automatic output is unchanged. This post-hoc development candidate
is not a new source-to-San batch or an independent-test result.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from migration_pipeline.stages.repair import RepairStage
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.stages.visual_eval import VisualEvalStage, VisualEvalStageInput


SOURCE = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_analytics_chart_reactivity_regression_v1_automatic_pass_20261027_172556/"
    "AnalyticsDashboard_repaired_repaired_repaired.san"
)
SOURCE_SHA256 = "426943b3f79e69480b259b18bc78584b794a9d1d6081c0fd2ba9c91638908fa7"
HISTORY = SOURCE.with_name("repair_history.json")
VUE = ROOT / (
    "data/experiments/protocols/formal_30_v3_frozen_20261022/frozen/"
    "data/datasets/components/03_complex/AnalyticsDashboard/vue/AnalyticsDashboard.vue"
)
OUTPUT_DIR = ROOT / (
    "data/experiments/pipeline/manual_fixes/"
    "formal_30_v4_analytics_auto_regression_inline_class_v1"
)
OUTPUT = OUTPUT_DIR / "AnalyticsDashboard_repaired.san"
REPORT = OUTPUT_DIR / "repair_report.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT.exists() or REPORT.exists():
        raise FileExistsError("Candidate or report already exists; do not overwrite evidence")
    if sha256(SOURCE) != SOURCE_SHA256:
        raise RuntimeError("Frozen automatic output hash mismatch")
    source = SOURCE.read_text(encoding="utf-8")
    history = json.loads(HISTORY.read_text(encoding="utf-8"))
    ssm = history["state"]["ssm"]
    before = ValidateStage().run(ValidateStageInput(
        generated_code=source, ssm=ssm, vue_file_path=str(VUE), compile_check=False,
    ))
    errors = before.validation_errors
    if len(errors) != 4 or {error["code"] for error in errors} != {"duplicate_class_attribute"}:
        raise RuntimeError(f"Expected exactly four inline class errors: {errors}")
    candidate, repairs = RepairStage._deterministic_repair_plan(source, errors, [])
    if repairs != [(
        "san_duplicate_class_normalizer",
        "merged_static_and_dynamic_class_attributes",
    )]:
        raise RuntimeError(f"Unexpected deterministic repair plan: {repairs}")
    if candidate == source or RepairStage._normalize_duplicate_class_attributes(candidate) != candidate:
        raise RuntimeError("Candidate did not change or normalizer is not idempotent")
    validation = ValidateStage().run(ValidateStageInput(
        generated_code=candidate, ssm=ssm, vue_file_path=str(VUE), compile_check=True,
    ))
    if not validation.validation_passed:
        raise RuntimeError(f"Normalized candidate failed static validation: {validation.validation_errors}")
    visual = VisualEvalStage().run(VisualEvalStageInput(
        vue_file_path=str(VUE), generated_code=candidate,
    ))
    if not visual.visual_eval_passed:
        raise RuntimeError(f"Normalized candidate failed lightweight visual evaluation: {visual.visual_eval_errors}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(candidate, encoding="utf-8", newline="")
    report = {
        "sample_id": "analytics_dashboard",
        "classification": "reused_development_posthoc_deterministic_replay",
        "independent_holdout": False,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": SOURCE.relative_to(ROOT).as_posix(),
        "source_sha256": SOURCE_SHA256,
        "candidate": OUTPUT.relative_to(ROOT).as_posix(),
        "candidate_sha256": sha256(OUTPUT),
        "repair": "generic san_duplicate_class_normalizer; merged static and dynamic classes in inline child templates",
        "before_inline_duplicate_class_errors": len(errors),
        "after_validation_passed": True,
        "after_san_compile_passed": True,
        "after_lightweight_visual_passed": True,
        "after_structure_similarity": visual.structure_similarity,
        "browser_runtime": "pending_user_review",
        "boundary": "A post-hoc replay on a frozen batch output; not evidence that the old batch automatically fixed inline classes.",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
