import json
import unittest
from pathlib import Path

from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.replay_formal_30_v4_remaining_monitoring_syntax_fix import (
    OUTPUT,
    SOURCE_SHA256,
    build_candidate,
    check_candidate,
    sha256,
)


ROOT = Path(__file__).resolve().parents[1]
FAILED = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_generalization_remaining_v1_monitoring_failed_20261027_205900"
)
SOURCE = FAILED / "MonitoringDashboard_repaired_repaired_repaired.san"
HISTORY = FAILED / "repair_history.json"


class MonitoringRemainingBoundedFixTests(unittest.TestCase):
    def test_frozen_failure_reproduces_four_error_classes(self):
        state = json.loads(HISTORY.read_text(encoding="utf-8"))["state"]
        result = ValidateStage().run(ValidateStageInput(
            generated_file_path=str(SOURCE),
            ssm=state["ssm"],
            vue_file_path=str(FAILED / "source.vue"),
            compile_check=True,
        ))
        self.assertEqual(
            {issue["code"] for issue in result.validation_errors},
            {
                "invalid_san_event_handler_syntax",
                "invalid_san_for_alias_syntax",
                "duplicate_class_attribute",
                "san_script_compile_error",
            },
        )
        self.assertIn(
            "Missing initializer in const declaration",
            str(result.san_compile_result),
        )

    def test_bounded_v1_replay_compiles_and_exposes_chart_dependencies(self):
        self.assertEqual(sha256(SOURCE), SOURCE_SHA256)
        candidate = build_candidate(SOURCE.read_text(encoding="utf-8"))
        self.assertEqual(candidate, OUTPUT.read_text(encoding="utf-8"))
        validation, visual = check_candidate(candidate)
        self.assertTrue(validation.validation_passed, validation.validation_errors)
        self.assertTrue(visual.visual_eval_passed, visual.visual_eval_errors)
        self.assertEqual(candidate.count("= san.defineComponent({"), 8)
        self.assertNotIn("const kpi-card =", candidate)
        self.assertIn("cx=\"{{getX(idx, dataPoints, width)}}\"", candidate)
        self.assertIn("cy=\"{{getY(point, height, maxValue, minValue)}}\"", candidate)
        self.assertIn("on-save=\"saveSettings($event)\"", candidate)


if __name__ == "__main__":
    unittest.main()
