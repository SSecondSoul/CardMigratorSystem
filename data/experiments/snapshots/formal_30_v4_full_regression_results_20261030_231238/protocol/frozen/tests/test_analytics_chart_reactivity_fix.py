import unittest

from migration_pipeline.replay_formal_30_v4_analytics_chart_reactivity_fix import (
    EXPECTED_SHA256,
    SOURCE,
    build_candidate,
    sha256,
)
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput


class AnalyticsChartReactivityFixTests(unittest.TestCase):
    def test_frozen_v2_exposes_hidden_inline_dependencies_and_v3_removes_them(self):
        self.assertEqual(sha256(SOURCE.read_bytes()), EXPECTED_SHA256)
        source = SOURCE.read_text(encoding="utf-8")
        candidate = build_candidate(source)
        before = ValidateStage().run(ValidateStageInput(
            generated_code=source, compile_check=False,
        ))
        after = ValidateStage().run(ValidateStageInput(
            generated_code=candidate, compile_check=False,
        ))
        before_hidden = [issue for issue in before.validation_errors
                         if issue["code"] == "hidden_template_reactive_dependency"]
        self.assertEqual(len(before_hidden), 4)
        self.assertEqual({issue["location"] for issue in before_hidden},
                         {"script.TrendChart.template"})
        self.assertNotIn("hidden_template_reactive_dependency",
                         {issue["code"] for issue in after.validation_errors})
        self.assertIn("getX(idx, data.length)", candidate)
        self.assertIn("getY(point.value, maxValue, minValue)", candidate)
        self.assertIn("getXForChart(index, dataLength)", candidate)
        self.assertIn("getYForChart(value, maxValue, minValue)", candidate)


if __name__ == "__main__":
    unittest.main()
