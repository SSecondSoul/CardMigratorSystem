import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from migration_pipeline.orchestrator import MigrationPipelineOrchestrator
from migration_pipeline.stages.generate import GenerateStageInput, GenerateStageResult
from migration_pipeline.stages.repair import RepairStage
from migration_pipeline.stages.repair import RepairStageInput
from migration_pipeline.repair_client import RepairResult


class Generate:
    def __init__(self, directory):
        self.path = Path(directory) / "initial.san"

    def run(self, _):
        self.path.write_text("initial", encoding="utf-8")
        return GenerateStageResult(source_file="sample", ssm={"script": {"options": {}}},
                                   generation_code="initial", saved_file_path=str(self.path),
                                   provider="fake", model="fake", usage={}, raw_response={})


class Validate:
    def run_from_state(self, state):
        code = state["generated_code"]
        error = ("missing_event_bindings" if code == "event_bad" else
                 "reserved_init_data_method_collision" if code == "collision" else "semantic_error")
        errors = [] if code == "fixed" else [{"code": error}]
        result = {"validation_passed": not errors, "validation_errors": errors, "validation_warnings": []}
        return {**result, "validate_result": result}


class Visual:
    def run_from_state(self, state):
        passed = state["generated_code"] != "visual_bad"
        result = {"visual_eval_passed": passed, "visual_eval_errors": [] if passed else [{"code": "san_render_failed"}]}
        return {**result, "visual_eval_result": result}


class Repair(RepairStage):
    def __init__(self, directory, response="fixed"):
        self.directory, self.response, self.calls = Path(directory), response, 0

    def run_from_state(self, state):
        if not state["repair_metadata"].get("skip_deterministic_prepass"):
            raise AssertionError("Bounded scheduler must force the LLM-only phase")
        self.calls += 1
        path = self.directory / f"llm_{self.calls}.san"
        path.write_text(self.response, encoding="utf-8")
        result = {"provider": "fake_llm", "model": "fake", "usage": {"total_tokens": 7},
                  "repaired_code": self.response, "repaired_file_path": str(path)}
        return {"generated_code": self.response, "generated_file_path": str(path),
                "repair_provider": "fake_llm", "repair_attempt": self.calls, "repair_result": result,
                "repair_prompt": "no focused-prompt marker"}


class BoundedSchedulerTests(unittest.TestCase):
    def run_case(self, directory, plan, response="fixed", cap=3):
        repair = Repair(directory, response)
        orchestrator = MigrationPipelineOrchestrator(Generate(directory), Validate(), Visual(), repair)
        with patch.object(RepairStage, "_deterministic_repair_plan", side_effect=plan):
            result = orchestrator.run_generate_validate_visual_eval_and_repair_loop(
                GenerateStageInput(metadata={"repair_policy": "bounded_prepass_v1"}), max_repair_rounds=cap,
            )
        return result.state, repair

    def test_normalization_cap_leaves_budget_for_llm(self):
        with tempfile.TemporaryDirectory() as directory:
            state, repair = self.run_case(directory, lambda code, *_: (code + "+", [("fake", "normalize")]), cap=1)
        self.assertTrue(state["final_passed"])
        self.assertEqual((state["deterministic_steps"], state["llm_repair_calls"], state["repair_rounds"]), (4, 1, 1))
        self.assertEqual(repair.calls, 1)
        self.assertIn("step_cap_reached", state["normalization_stop_reasons"])

    def test_cycle_detected_and_llm_gets_control(self):
        def plan(code, *_):
            return ("other" if code == "initial" else "initial"), [("fake", "toggle")]
        with tempfile.TemporaryDirectory() as directory:
            state, _ = self.run_case(directory, plan)
        self.assertTrue(state["final_passed"])
        self.assertEqual(state["deterministic_steps"], 1)
        self.assertIn("cycle_detected", state["normalization_stop_reasons"])

    def test_deterministic_success_uses_zero_llm_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            state, repair = self.run_case(directory, lambda code, *_: ("fixed", [("fake", "normalize")]))
        self.assertTrue(state["final_passed"])
        self.assertEqual((state["deterministic_steps"], repair.calls, state["repair_rounds"]), (1, 0, 0))

    def test_rejected_candidate_keeps_previous_file_and_failed_attempt_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            state, repair = self.run_case(directory, lambda code, *_: (code, []), "visual_bad")
            self.assertEqual(Path(state["final_file_path"]).read_text(encoding="utf-8"), "initial")
            self.assertEqual(Path(state["rejected_candidate_file"]).read_text(encoding="utf-8"), "visual_bad")
        self.assertEqual(repair.calls, 1)
        self.assertFalse(state["final_passed"])
        self.assertTrue(state["retained_previous_candidate"])
        self.assertEqual(state["stop_reason"], "repair_candidate_regression_rolled_back")
        self.assertTrue(state["final_visual_eval_result"]["visual_eval_passed"])
        self.assertFalse(state["repair_history"][0]["visual_eval_passed"])
        self.assertEqual(state["repair_history"][0]["repair_result"]["usage"]["total_tokens"], 7)

    def test_event_gate_applies_without_prompt_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            state, _ = self.run_case(directory, lambda code, *_: (code, []), "event_bad")
        self.assertTrue(state["retained_previous_candidate"])
        self.assertIn("missing_event_bindings", state["repair_regression_gate"]["introduced_event_error_codes"])

    def test_init_data_collision_is_rejected_even_when_visual_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            state, _ = self.run_case(directory, lambda code, *_: (code, []), "collision")
        self.assertTrue(state["retained_previous_candidate"])
        self.assertEqual(state["repair_regression_gate"]["introduced_critical_errors"], ["reserved_init_data_method_collision"])

    def test_bad_normalization_is_logged_and_llm_uses_previous_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            state, repair = self.run_case(directory, lambda code, *_: ("visual_bad", [("fake", "bad")]))
        self.assertTrue(state["final_passed"])
        self.assertEqual(repair.calls, 1)
        self.assertFalse(state["normalization_history"][0]["accepted"])
        self.assertIn("candidate_rejected", state["normalization_stop_reasons"])

    def test_zero_budget_does_not_normalize_or_call_llm(self):
        def forbidden(*_):
            raise AssertionError("No budget")
        with tempfile.TemporaryDirectory() as directory:
            state, repair = self.run_case(directory, forbidden, cap=0)
        self.assertEqual(repair.calls, 0)
        self.assertEqual(state["deterministic_steps"], 0)
        self.assertFalse(state["final_passed"])

    def test_real_repair_stage_llm_only_flag_bypasses_deterministic_plan(self):
        class Client:
            calls = 0

            def repair(self, request):
                self.calls += 1
                return RepairResult(source_file="sample", ssm=request.ssm,
                                    code="<template><div>fixed</div></template><script></script><style></style>",
                                    saved_file_path=request.output_file_path,
                                    provider="fake_llm", model="fake", usage={"total_tokens": 9})

        client = Client()
        with tempfile.TemporaryDirectory() as directory:
            stage_input = RepairStageInput(
                ssm={"script": {"options": {}}}, generated_code="<template><div>broken</div></template>",
                output_file_path=str(Path(directory) / "fixed.san"),
                metadata={"skip_deterministic_prepass": True},
            )
            with patch.object(RepairStage, "_deterministic_repair_plan", side_effect=AssertionError("Must skip")):
                result = RepairStage(client).run(stage_input)
        self.assertEqual(client.calls, 1)
        self.assertEqual(result.provider, "fake_llm")


if __name__ == "__main__":
    unittest.main()
