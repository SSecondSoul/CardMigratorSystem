import unittest

from migration_pipeline.orchestrator import MigrationPipelineOrchestrator
from migration_pipeline.run_pipeline import compact_repair_history_entry
from migration_pipeline.stages.generate import GenerateStageInput, GenerateStageResult
from migration_pipeline.utils.repair_prompt import RepairPromptInput, build_repair_prompt


class StaticGenerateStage:
    def run(self, stage_input):
        return GenerateStageResult(
            source_file=stage_input.resolve_source_file(),
            ssm={"script": {"options": {}}},
            generation_code="<template><div>broken</div></template>",
            saved_file_path="generated.san",
            provider="fake",
            model="fake-model",
            usage={},
            raw_response={},
        )


class AlwaysFailValidateStage:
    def run_from_state(self, state):
        result = {
            "validation_passed": False,
            "validation_errors": [{"code": "still_broken"}],
            "validation_warnings": [],
            "validation_checks": [],
            "validation_summary": "failed",
        }
        return {**result, "validate_result": result}


class AlwaysFailVisualEvalStage:
    def run_from_state(self, state):
        result = {
            "visual_eval_passed": False,
            "visual_eval_errors": [{"code": "dom_mismatch"}],
            "visual_eval_warnings": [],
            "visual_eval_summary": "failed",
            "tree_edit_distance": 1.0,
            "structure_similarity": 0.5,
            "tag_sequence_similarity": 0.75,
            "text_similarity": 1.0,
            "dom_compare_result": {
                "tree_edit_distance": 1.0,
                "structure_similarity": 0.5,
                "tag_sequence_similarity": 0.75,
                "text_similarity": 1.0,
            },
        }
        return {**result, "visual_eval_result": result}


class NoChangeRepairStage:
    def __init__(self):
        self.calls = 0

    def run_from_state(self, state):
        self.calls += 1
        attempt = state.get("repair_attempt", 0) + 1
        code = "<template><div>unchanged</div></template>\n"
        result = {
            "repaired_code": code,
            "repaired_file_path": "repaired.san",
            "repair_prompt": "fake",
            "repair_attempt": attempt,
            "source_file": state.get("source_file", ""),
            "provider": "fake",
            "model": "fake-model",
            "usage": {"total_tokens": 10},
            "raw_response": {},
            "repair_summary": "unchanged",
        }
        return {
            "generated_code": code,
            "generated_file_path": "repaired.san",
            "repaired_code": code,
            "repaired_file_path": "repaired.san",
            "repair_prompt": "fake",
            "repair_attempt": attempt,
            "repair_provider": "fake",
            "repair_model": "fake-model",
            "repair_usage": {"total_tokens": 10},
            "repair_raw_response": {},
            "repair_summary": "unchanged",
            "repair_result": result,
        }


class RepairPromptAndLoopTests(unittest.TestCase):
    def test_prompt_makes_computed_defaults_and_binding_direction_explicit(self):
        prompt = build_repair_prompt(RepairPromptInput(
            ssm={
                "script": {
                    "options": {
                        "data": [
                            {"name": "form", "initial_value": {"age": 18}},
                            {"name": "enabled", "initial_value": ["email", "adult", "name"]},
                        ],
                        "computed": [{"name": "sortedRows"}],
                    }
                }
            },
            current_code="<template></template>",
        ))

        self.assertIn("this.data.get('computedName')", prompt)
        self.assertIn("禁止 this.computed.foo()", prompt)
        self.assertIn("Vue data() 的全部初始值", prompt)
        self.assertIn("嵌套对象、数组、数字和启用项集合", prompt)
        self.assertIn("{= assignable.path =}", prompt)
        self.assertIn("checked=\"{{ isEnabled(rule.id, enabled) }}\"", prompt)
        self.assertIn("computed values must be read with this.data.get", prompt)
        self.assertIn("two-way binding only for assignable data paths", prompt)

    def test_loop_stops_after_two_identical_repair_outcomes(self):
        repair_stage = NoChangeRepairStage()
        orchestrator = MigrationPipelineOrchestrator(
            generate_stage=StaticGenerateStage(),
            validate_stage=AlwaysFailValidateStage(),
            visual_eval_stage=AlwaysFailVisualEvalStage(),
            repair_stage=repair_stage,
        )

        result = orchestrator.run_generate_validate_visual_eval_and_repair_loop(
            GenerateStageInput(
                vue_source="<template><div /></template>",
                source_file="NoProgress.vue",
            ),
            max_repair_rounds=5,
        )

        self.assertEqual(repair_stage.calls, 2)
        self.assertEqual(result.state["repair_rounds"], 2)
        self.assertEqual(result.state["stop_reason"], "no_repair_progress")
        self.assertTrue(result.state["no_repair_progress"])
        self.assertEqual(len(result.state["repair_history"]), 2)
        self.assertFalse(result.state["repair_history"][0]["no_progress_detected"])
        self.assertTrue(result.state["repair_history"][1]["no_progress_detected"])
        self.assertEqual(
            result.state["repair_history"][0]["progress_signature"],
            result.state["repair_history"][1]["progress_signature"],
        )

        compact_entry = compact_repair_history_entry(result.state["repair_history"][1])
        self.assertTrue(compact_entry["no_progress_detected"])
        self.assertEqual(
            compact_entry["progress_signature"],
            result.state["repair_history"][1]["progress_signature"],
        )


if __name__ == "__main__":
    unittest.main()
