import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from migration_pipeline.run_batch_pipeline import (
    DEFAULT_CONFIG_FILE,
    config_fingerprint,
    execute_batch,
    load_batch_config,
)


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_VUE = ROOT / "data/datasets/components/01_simple/step/vue/step.vue"


class FakeOrchestrator:
    calls: list[str] = []
    failing_ids: set[str] = set()

    def run_generate_validate_visual_eval_and_repair_loop(
        self,
        stage_input,
        max_repair_rounds,
    ):
        sample_id = stage_input.metadata["sample_id"]
        self.calls.append(sample_id)
        if sample_id in self.failing_ids:
            raise RuntimeError(f"planned failure for {sample_id}")

        validate = {
            "validation_passed": True,
            "validation_errors": [],
            "validation_warnings": [],
            "validation_summary": "passed",
        }
        visual = {
            "visual_eval_passed": True,
            "visual_eval_errors": [],
            "visual_eval_warnings": [],
            "tree_edit_distance": 0.0,
            "structure_similarity": 1.0,
            "tag_sequence_similarity": 1.0,
            "text_similarity": 1.0,
            "visual_eval_summary": "passed",
        }
        state = {
            "generate_result": {"saved_file_path": stage_input.output_file_path},
            "generated_file_path": stage_input.output_file_path,
            "final_file_path": stage_input.output_file_path,
            "final_passed": True,
            "stop_reason": "passed",
            "repair_rounds": 0,
            "max_repair_rounds": max_repair_rounds,
            "structure_similarity": 1.0,
            "tree_edit_distance": 0.0,
            "initial_validate_result": validate,
            "initial_visual_eval_result": visual,
            "final_validate_result": validate,
            "final_visual_eval_result": visual,
            "repair_history": [],
            "generation_provider": "fake",
            "generation_model": "fake-model",
            "generation_usage": {"total_tokens": 100},
        }
        return SimpleNamespace(state=state)


class BatchPipelineRunnerTests(unittest.TestCase):
    def setUp(self):
        FakeOrchestrator.calls = []
        FakeOrchestrator.failing_ids = set()

    def test_pilot_config_has_three_existing_samples_per_complexity(self):
        _, config = load_batch_config(DEFAULT_CONFIG_FILE)
        self.assertEqual(config["batch_id"], "pilot_9_v6")
        counts = {level: 0 for level in ("simple", "medium", "complex")}
        for sample in config["samples"]:
            counts[sample["complexity"]] += 1
            self.assertTrue(sample["coverage_focus"])
            self.assertTrue(all(isinstance(item, str) for item in sample["coverage_focus"]))
        self.assertEqual(counts, {"simple": 3, "medium": 3, "complex": 3})
        self.assertEqual(len({sample["id"] for sample in config["samples"]}), 9)

    def test_dry_run_validates_plan_without_writing_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            summary_file = Path(temp_dir) / "summary.json"
            plan, exit_code = execute_batch(
                config_file=DEFAULT_CONFIG_FILE,
                summary_file=summary_file,
                sample_ids=["simple_step"],
                dry_run=True,
            )
            self.assertEqual(exit_code, 0)
            self.assertEqual([item["id"] for item in plan["samples"]], ["simple_step"])
            self.assertIn("basic state and click event", plan["samples"][0]["coverage_focus"])
            self.assertFalse(summary_file.exists())

    def test_failure_isolation_and_resume_retry_only_execution_errors(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_file = temp_path / "batch.json"
            config_file.write_text(
                json.dumps({
                    "batch_id": "test_batch",
                    "max_repair_rounds": 2,
                    "expected_counts": {"simple": 3},
                    "samples": [
                        {
                            "id": sample_id,
                            "component_name": component_name,
                            "complexity": "simple",
                            "vue_file": str(SAMPLE_VUE),
                        }
                        for sample_id, component_name in (
                            ("sample_one", "SampleOne"),
                            ("sample_two", "SampleTwo"),
                            ("sample_three", "SampleThree"),
                        )
                    ],
                }),
                encoding="utf-8",
            )
            summary_file = temp_path / "summary.json"
            output_dir = temp_path / "outputs"
            report_dir = temp_path / "reports"

            FakeOrchestrator.failing_ids = {"sample_two"}
            first, first_exit = execute_batch(
                config_file=config_file,
                output_dir=output_dir,
                report_dir=report_dir,
                summary_file=summary_file,
                skip_health_check=True,
                orchestrator_factory=FakeOrchestrator,
            )
            self.assertEqual(first_exit, 2)
            self.assertEqual(
                FakeOrchestrator.calls,
                ["sample_one", "sample_two", "sample_three"],
            )
            self.assertEqual(first["aggregate"]["completed"], 2)
            self.assertEqual(first["aggregate"]["execution_errors"], 1)

            FakeOrchestrator.calls = []
            FakeOrchestrator.failing_ids = set()
            second, second_exit = execute_batch(
                config_file=config_file,
                output_dir=output_dir,
                report_dir=report_dir,
                summary_file=summary_file,
                skip_health_check=True,
                orchestrator_factory=FakeOrchestrator,
            )
            self.assertEqual(second_exit, 0)
            self.assertEqual(FakeOrchestrator.calls, ["sample_two"])
            self.assertEqual(second["aggregate"]["completed"], 3)
            self.assertEqual(second["aggregate"]["passed"], 3)
            self.assertEqual(second["aggregate"]["execution_errors"], 0)
            self.assertEqual(second["aggregate"]["total_tokens"], 300)
            self.assertEqual(second["aggregate"]["stop_reason_counts"], {"passed": 3})
            self.assertEqual(second["aggregate"]["pass_rate_completed"], 1.0)
            self.assertEqual(second["aggregate"]["initial_pass_rate_completed"], 1.0)
            self.assertTrue((report_dir / "simple/SampleTwo_repair_history.json").exists())

    def test_checkpoint_rejects_config_or_repair_round_drift(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_file = temp_path / "batch.json"
            base_config = {
                "batch_id": "stable_batch",
                "max_repair_rounds": 2,
                "samples": [{
                    "id": "stable_sample",
                    "component_name": "StableSample",
                    "complexity": "simple",
                    "vue_file": str(SAMPLE_VUE),
                }],
            }
            config_file.write_text(json.dumps(base_config), encoding="utf-8")
            summary_file = temp_path / "summary.json"
            common = {
                "config_file": config_file,
                "output_dir": temp_path / "outputs",
                "report_dir": temp_path / "reports",
                "summary_file": summary_file,
                "skip_health_check": True,
                "orchestrator_factory": FakeOrchestrator,
            }
            execute_batch(**common)

            with self.assertRaisesRegex(ValueError, "max_repair_rounds changed"):
                execute_batch(**common, max_repair_rounds=1)

            changed_config = dict(base_config)
            changed_config["description"] = "changed"
            config_file.write_text(json.dumps(changed_config), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "batch config changed"):
                execute_batch(**common)

    def test_interaction_reevaluation_updates_checkpoint_without_model_call(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            vue_file = ROOT / "data/datasets/components/02_medium/FormRulePlayground/vue/FormRulePlayground.vue"
            san_file = ROOT / "data/datasets/components/02_medium/FormRulePlayground/san/FormRulePlayground.san"
            config = {
                "batch_id": "interaction_recheck",
                "samples": [{
                    "id": "form",
                    "component_name": "FormRulePlayground",
                    "complexity": "medium",
                    "vue_file": str(vue_file),
                    "interaction_scenarios": [{
                        "name": "invalid_submission",
                        "steps": [
                            {"op": "set", "path": "form", "value": {"name": "ab", "email": "bad", "age": 17}},
                            {"op": "call", "method": "submit", "args": [{"__event": True}]},
                        ],
                    }],
                }],
            }
            config_file = temp_path / "batch.json"
            config_file.write_text(json.dumps(config), encoding="utf-8")
            report_file = temp_path / "report.json"
            report_file.write_text(json.dumps({"summary": {}}), encoding="utf-8")
            summary_file = temp_path / "summary.json"
            summary_file.write_text(json.dumps({
                "batch_id": config["batch_id"],
                "config_sha256": config_fingerprint(config),
                "max_repair_rounds": 3,
                "samples": [{
                    "id": "form",
                    "status": "completed",
                    "final_file_path": str(san_file),
                    "report_file": str(report_file),
                    "final_passed": False,
                    "stop_reason": "interaction_eval_failed",
                }],
            }), encoding="utf-8")

            result, exit_code = execute_batch(
                config_file=config_file,
                summary_file=summary_file,
                reevaluate_interactions=True,
                orchestrator_factory=FakeOrchestrator,
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(FakeOrchestrator.calls, [])
            self.assertTrue(result["samples"][0]["final_passed"])
            self.assertEqual(result["samples"][0]["stop_reason"], "passed")
            self.assertFalse(result["interaction_reevaluation"]["model_called"])


if __name__ == "__main__":
    unittest.main()
