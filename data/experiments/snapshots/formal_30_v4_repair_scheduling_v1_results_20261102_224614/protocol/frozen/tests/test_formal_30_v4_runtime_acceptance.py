"""Structural guardrails for the manual-browser development regression scenarios.

This does not replace a browser execution or the user's visual review.
"""

import json
import hashlib
from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "migration_pipeline/interaction_configs/formal_30_v4_runtime_acceptance.json"
PAGE = ROOT / "tests/manual/formal-30-v4-runtime-acceptance.html"
SCRIPT = ROOT / "tests/manual/formal-30-v4-runtime-acceptance.js"
BATCH_CONFIG = ROOT / "migration_pipeline/batch_configs/formal_30_v4_generalization_followup.json"


class RuntimeAcceptanceConfigTests(unittest.TestCase):
    def test_four_development_gap_samples_have_existing_frozen_baselines(self):
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(
            [sample["sample_id"] for sample in config["samples"]],
            ["rule_builder", "analytics_dashboard", "TaskManager", "MonitoringDashboard"],
        )
        self.assertEqual(
            config["classification"],
            "reused_development_regression_not_independent_holdout",
        )
        for sample in config["samples"]:
            with self.subTest(sample=sample["sample_id"]):
                relative = Path(sample["baseline_san_file"])
                self.assertFalse(relative.is_absolute())
                self.assertTrue((ROOT / relative).is_file())
                self.assertIn("formal_30_v4_development_manual_closeout_20261027", relative.parts)
                self.assertTrue(sample["component_tag"])

    def test_scenario_dsl_is_bounded_and_each_action_has_an_observation(self):
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        operations = {"wait_for", "click", "select", "set_checked"}
        expectations = {
            "exists", "absent", "count_at_least", "text_nonempty", "text_includes",
            "text_matches", "class_contains", "class_absent", "value_equals",
            "checked_equals", "attribute_nonempty", "attribute_finite_number",
            "chart_geometry_aligned",
            "background_visible", "background_equals",
        }
        for sample in config["samples"]:
            steps = sample["steps"]
            self.assertGreaterEqual(len(steps), 6)
            self.assertEqual(len({step["name"] for step in steps}), len(steps))
            self.assertEqual(steps[0]["op"], "wait_for")
            for index, step in enumerate(steps):
                with self.subTest(sample=sample["sample_id"], step=step["name"]):
                    self.assertIn(step["op"], operations)
                    self.assertTrue(step["selector"])
                    if step["op"] == "wait_for":
                        self.assertIn(step["expect"], expectations)
                    else:
                        self.assertLess(index + 1, len(steps))
                        self.assertEqual(steps[index + 1]["op"], "wait_for")

    def test_page_and_script_have_valid_local_entry_points(self):
        page = PAGE.read_text(encoding="utf-8")
        self.assertIn('src="formal-30-v4-runtime-acceptance.js"', page)
        self.assertIn('id="component-host"', page)
        self.assertIn('id="report"', page)
        if shutil.which("node"):
            completed = subprocess.run(
                ["node", "--check", str(SCRIPT)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_analytics_chart_points_require_finite_coordinates(self):
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        analytics = next(sample for sample in config["samples"] if sample["sample_id"] == "analytics_dashboard")
        checks = {
            (step.get("selector"), step.get("attribute"))
            for step in analytics["steps"]
            if step.get("expect") == "attribute_finite_number"
        }
        self.assertIn((".trend-chart circle", "cx"), checks)
        self.assertIn((".trend-chart circle", "cy"), checks)
        self.assertIn("Number.isFinite(Number(value))", SCRIPT.read_text(encoding="utf-8"))

    def test_analytics_period_switch_checks_chart_geometry(self):
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        analytics = next(sample for sample in config["samples"] if sample["sample_id"] == "analytics_dashboard")
        steps = analytics["steps"]
        for period, count in (("7d", 7), ("90d", 90)):
            index = next(index for index, step in enumerate(steps)
                         if step.get("op") == "select" and step.get("value") == period)
            self.assertEqual(steps[index + 1]["expect"], "chart_geometry_aligned")
            self.assertEqual(steps[index + 1]["value"], count)
        self.assertIn("Math.abs(point[0] - cx)", SCRIPT.read_text(encoding="utf-8"))

    def test_followup_batch_reuses_only_frozen_development_sources(self):
        from migration_pipeline.run_batch_pipeline import validate_batch_config

        batch = json.loads(BATCH_CONFIG.read_text(encoding="utf-8"))
        validate_batch_config(batch)
        self.assertEqual(batch["batch_id"], "formal_30_v4_generalization_followup")
        self.assertEqual(batch["runtime_acceptance_config"], CONFIG.relative_to(ROOT).as_posix())
        self.assertEqual(
            [sample["id"] for sample in batch["samples"]],
            ["rule_builder", "analytics_dashboard", "TaskManager", "MonitoringDashboard"],
        )
        for sample in batch["samples"]:
            with self.subTest(sample=sample["id"]):
                source_path = ROOT / sample["vue_file"]
                self.assertIn("formal_30_v3_frozen_20261022", source_path.parts)
                self.assertEqual(
                    hashlib.sha256(source_path.read_bytes()).hexdigest(),
                    sample["source_sha256"],
                )


if __name__ == "__main__":
    unittest.main()
