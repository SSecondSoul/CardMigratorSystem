"""Offline, source-grounded replay of the TaskManager self-click/drag fix.

This creates a new development candidate; it never changes the frozen batch.
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


SOURCE = ROOT / "data/experiments/snapshots/formal_30_v4_task_manager_five_residual_regression_v1_TaskManager_automatic_pass_20261029_200650"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(path: Path) -> None:
    for line in (path / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        if digest(path / relative) != expected:
            raise RuntimeError(f"Frozen evidence changed: {path / relative}")


def main() -> None:
    verify(SOURCE)
    vue_path = SOURCE / "source.vue"
    original = (SOURCE / "repair_round_4.san").read_text(encoding="utf-8")
    validator = ValidateStage()
    before = validator.run(ValidateStageInput(
        generated_code=original, vue_file_path=str(vue_path), compile_check=False,
    ))
    before_codes = {item["code"] for item in before.validation_errors}
    required = {"missing_self_click_guard", "native_drag_event_misbound"}
    if not required <= before_codes:
        raise RuntimeError(f"Frozen candidate no longer exhibits expected defects: {before_codes}")
    candidate, repairs = RepairStage._deterministic_repair_plan(
        original, before.validation_errors, [], vue_file_path=str(vue_path),
    )
    if len(repairs) != 1 or candidate == original:
        raise RuntimeError("Bounded event repair did not apply exactly once")
    after = validator.run(ValidateStageInput(
        generated_code=candidate, vue_file_path=str(vue_path),
    ))
    visual = VisualEvalStage().run(VisualEvalStageInput(
        vue_file_path=str(vue_path), generated_code=candidate,
    ))
    if not after.validation_passed or not visual.visual_eval_passed:
        raise RuntimeError("Offline candidate did not pass validation and visual gates")
    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    target = ROOT / "data/experiments/snapshots" / f"formal_30_v4_task_manager_source_events_candidate_{stamp}"
    target.mkdir(parents=True, exist_ok=False)
    (target / "candidate.san").write_text(candidate, encoding="utf-8")
    report = {
        "classification": "reused_development_offline_candidate",
        "independent_holdout": False,
        "source_snapshot": SOURCE.name,
        "source_sha256": digest(vue_path),
        "original_sha256": digest(SOURCE / "repair_round_4.san"),
        "before_validation_error_codes": sorted(before_codes),
        "repair": repairs,
        "after_validation_error_codes": [item["code"] for item in after.validation_errors],
        "san_compile_passed": bool(after.san_compile_result and after.san_compile_result.get("passed")),
        "visual_eval_passed": visual.visual_eval_passed,
        "visual_error_codes": [item["code"] for item in visual.visual_eval_errors],
        "structure_similarity": visual.structure_similarity,
        "automatic_pipeline_passed": False,
        "browser_manual_review": "pending",
    }
    (target / "replay_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    manifest = {
        "snapshot_id": target.name,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        **{key: report[key] for key in (
            "classification", "independent_holdout", "source_snapshot",
            "automatic_pipeline_passed", "browser_manual_review",
        )},
        "candidate_sha256": digest(target / "candidate.san"),
        "integrity_file": "SHA256SUMS.txt",
    }
    (target / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    payloads = sorted(path for path in target.iterdir() if path.is_file())
    (target / "SHA256SUMS.txt").write_text(
        "\n".join(f"{digest(path)}  {path.name}" for path in payloads) + "\n", encoding="utf-8",
    )
    verify(target)
    print(f"candidate: {target.relative_to(ROOT)}")
    print(f"validation: {after.validation_passed}; compile: {report['san_compile_passed']}; visual: {visual.visual_eval_passed}")
    print("browser_manual_review: pending")


if __name__ == "__main__":
    main()
