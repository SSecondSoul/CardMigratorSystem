"""Late multi-error prompt routing against frozen development failures."""

import json
import unittest
from pathlib import Path

from migration_pipeline.utils.repair_prompt import RepairPromptInput, build_repair_prompt


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOTS = {
    "TaskManager": (
        "formal_30_v4_generalization_integrated_v1_TaskManager_automatic_fail_20261027_223358",
        [
            "invalid_san_event_handler_syntax",
            "invalid_san_init_data_store_access",
            "invalid_san_computed_instance_method_call",
            "hidden_template_reactive_dependency",
        ],
    ),
    "MonitoringDashboard": (
        "formal_30_v4_generalization_integrated_v1_MonitoringDashboard_automatic_fail_20261027_225335",
        [
            "invalid_san_event_handler_syntax",
            "invalid_san_inline_computed_method_invocation",
            "invalid_san_computed_instance_method_call",
            "event_arguments_not_landed",
        ],
    ),
}


class SemanticResidualPromptTests(unittest.TestCase):
    def test_three_error_event_computed_reactivity_prompt_is_bounded(self):
        ssm = {
            "script": {"options": {"methods": [
                {"name": "isOverdue", "body_full": "{ return dueDate < today; }"},
                {"name": "getTaskCount", "body_full": "{ return this.tasks.length; }"},
            ]}},
            "template": {"event_bindings": [
                {"event_name": "dragover", "handler_expression": "", "modifiers": ["prevent"]},
            ]},
        }
        issues = [{"code": code} for code in (
            "invalid_san_event_handler_syntax",
            "invalid_san_computed_instance_method_call",
            "hidden_template_reactive_dependency",
        )]
        prompt = build_repair_prompt(RepairPromptInput(
            ssm=ssm, current_code="<template><div on-dragover=\"\"></div></template>",
            validation_errors=issues,
        ))
        self.assertIn("Repair ONLY these three remaining static error families", prompt)
        self.assertIn("return dueDate < today", prompt)
        self.assertIn("this.tasks.length", prompt)
        self.assertIn("modifier-only", prompt)
        self.assertIn("explicit template arguments", prompt)
        self.assertIn("on-dragover", prompt)
        self.assertNotIn("--- SSM ---", prompt)
        fallback = build_repair_prompt(RepairPromptInput(
            ssm=ssm, current_code="x", validation_errors=issues,
            visual_eval_errors=[{"code": "dom_structure_similarity_low"}],
        ))
        self.assertNotIn("Repair ONLY these three remaining static error families", fallback)

    def test_frozen_two_error_probe_routes_to_minimal_source_grounded_prompt(self):
        source = ROOT / (
            "data/experiments/snapshots/"
            "formal_30_v4_task_manager_boolean_event_regression_v1_"
            "TaskManager_automatic_fail_20261028_220158"
        )
        result = ROOT / (
            "data/experiments/snapshots/"
            "formal_30_v4_task_manager_semantic_residual_probe_v1_result_20261028_230247"
        )
        ssm = json.loads((source / "repair_history.json").read_text(encoding="utf-8"))["state"]["ssm"]
        report = json.loads((result / "probe_report.json").read_text(encoding="utf-8"))
        code = (result / "candidate.san").read_text(encoding="utf-8")
        prompt = build_repair_prompt(RepairPromptInput(
            ssm=ssm, current_code=code,
            validation_errors=report["validation_errors"],
        ))
        self.assertIn("Repair ONLY the two remaining validation error families", prompt)
        self.assertIn("Relevant source children:", prompt)
        self.assertIn("Relevant source methods:", prompt)
        self.assertIn("this.createFormData(this.task)", prompt)
        self.assertIn("isOverdue", prompt)
        self.assertIn("Do not add pre-mount writes", prompt)
        self.assertIn(code.strip(), prompt)
        self.assertNotIn("--- SSM ---", prompt)

    def test_two_error_specialization_is_generic_and_visual_failure_falls_back(self):
        errors = [
            {"code": "invalid_san_init_data_store_access", "message": "ChildForm"},
            {"code": "invalid_san_computed_instance_method_call", "message": "isExpired"},
        ]
        ssm = {"script": {"options": {
            "components": [{"source_name": "ChildForm", "inline_definition": {
                "source_code": "{ data() { return { value: this.item }; } }"
            }}],
            "methods": [{"name": "isExpired", "body_full": "{ return value < 0; }"}],
        }}}
        prompt = build_repair_prompt(RepairPromptInput(
            ssm=ssm, current_code="<template></template>", validation_errors=errors,
        ))
        self.assertIn("ChildForm", prompt)
        self.assertIn("isExpired", prompt)
        self.assertIn("return value < 0", prompt)
        for business_name in ("TaskManager", "TaskForm", "isOverdue", "tasks"):
            self.assertNotIn(business_name, prompt)
        fallback = build_repair_prompt(RepairPromptInput(
            ssm=ssm, current_code="<template></template>", validation_errors=errors,
            visual_eval_errors=[{"code": "dom_structure_similarity_low"}],
        ))
        self.assertNotIn("Repair ONLY the two remaining validation error families", fallback)

    def test_both_frozen_final_failures_route_to_compact_semantic_prompt(self):
        for name, (snapshot_id, error_codes) in SNAPSHOTS.items():
            with self.subTest(sample=name):
                snapshot = ROOT / "data/experiments/snapshots" / snapshot_id
                history = json.loads((snapshot / "repair_history.json").read_text(encoding="utf-8"))
                code = (snapshot / "repair_round_3.san").read_text(encoding="utf-8")
                prompt = build_repair_prompt(RepairPromptInput(
                    ssm=history["state"]["ssm"],
                    current_code=code,
                    validation_errors=[{"code": error} for error in error_codes],
                ))
                self.assertIn("ALL listed semantic validation errors", prompt)
                self.assertIn("Source event expressions:", prompt)
                self.assertIn("Current San code:", prompt)
                self.assertIn(code.strip(), prompt)
                self.assertNotIn("--- SSM ---", prompt)
                self.assertIn("$event", prompt)
                self.assertIn("this.data.get/set", prompt)
                for error in error_codes:
                    self.assertIn(error, prompt)
                if name == "MonitoringDashboard":
                    self.assertIn("onKPIClick(kpi)", prompt)
                    self.assertIn("changePeriod(period.value)", prompt)

    def test_visual_or_unknown_errors_keep_the_full_general_prompt(self):
        issue = [{"code": "invalid_san_event_handler_syntax"},
                 {"code": "event_arguments_not_landed"}]
        for issues, visual in (
            (issue, [{"code": "dom_structure_similarity_low"}]),
            (issue + [{"code": "missing_component_registration"}], []),
        ):
            with self.subTest(issues=issues, visual=visual):
                prompt = build_repair_prompt(RepairPromptInput(
                    ssm={"template": {"event_bindings": []}},
                    current_code="<template></template>",
                    validation_errors=issues,
                    visual_eval_errors=visual,
                ))
                self.assertIn("--- SSM ---", prompt)
                self.assertNotIn("ALL listed semantic validation errors", prompt)

    def test_new_task_manager_failure_routes_after_math_error_is_included(self):
        snapshot = ROOT / "data/experiments/snapshots/formal_30_v4_semantic_focus_v1_TaskManager_automatic_fail_20261027_232128"
        history = json.loads((snapshot / "repair_history.json").read_text(encoding="utf-8"))
        errors = history["state"]["final_validate_result"]["validation_errors"]
        code = (snapshot / "repair_round_3.san").read_text(encoding="utf-8")
        prompt = build_repair_prompt(RepairPromptInput(
            ssm=history["state"]["ssm"],
            current_code=code,
            validation_errors=errors,
        ))
        self.assertIn("ALL listed semantic validation errors", prompt)
        self.assertIn("unsupported_san_inline_template_math_global", prompt)
        self.assertIn(code.strip(), prompt)
        self.assertNotIn("--- SSM ---", prompt)

    def test_v2_task_manager_residual_routes_with_lifecycle_and_nested_state(self):
        snapshot = ROOT / "data/experiments/snapshots/formal_30_v4_semantic_focus_v2_TaskManager_automatic_fail_20261028_140129"
        history = json.loads((snapshot / "repair_history.json").read_text(encoding="utf-8"))
        errors = history["state"]["final_validate_result"]["validation_errors"]
        code = (snapshot / "repair_round_3.san").read_text(encoding="utf-8")
        prompt = build_repair_prompt(RepairPromptInput(
            ssm=history["state"]["ssm"],
            current_code=code,
            validation_errors=errors,
        ))
        self.assertIn("ALL listed semantic validation errors", prompt)
        self.assertIn("nested_state_mutation", prompt)
        self.assertIn("lifecycle_behavior_not_landed", prompt)
        self.assertIn("Never mutate an object or array", prompt)
        self.assertIn("Preserve every source lifecycle action", prompt)
        self.assertIn("same order in San attached()", prompt)
        self.assertIn("do not add a handle- prefix", prompt)
        self.assertIn("on-keyup.enter", prompt)
        self.assertIn('on-keyup="enter:addComment"', prompt)
        self.assertIn("preserve fire(...) event forwarding", prompt)
        self.assertIn(code.strip(), prompt)
        self.assertNotIn("--- SSM ---", prompt)

    def test_existing_single_computed_specialization_still_wins(self):
        prompt = build_repair_prompt(RepairPromptInput(
            ssm={}, current_code="<template></template>",
            validation_errors=[{"code": "invalid_san_computed_instance_method_call"}],
        ))
        self.assertIn("ONLY reported", prompt)
        self.assertNotIn("ALL listed semantic validation errors", prompt)

    def test_semantic_prompt_is_generic_without_business_field_names(self):
        prompt = build_repair_prompt(RepairPromptInput(
            ssm={}, current_code="<template></template>",
            validation_errors=[
                {"code": "invalid_san_event_handler_syntax"},
                {"code": "hidden_template_reactive_dependency"},
            ],
        ))
        for field_name in ("showSettings", "getTaskCount", "onKPIClick", "changePeriod", "isOverdue"):
            self.assertNotIn(field_name, prompt)
        self.assertIn("choose(item.id)", prompt)

    def test_event_only_residual_uses_full_source_bodies_and_preserves_args(self):
        ssm = {
            "template": {"event_bindings": [
                {"event_name": "click", "handler_expression": "choose(item.id)",
                 "arguments": ["item.id"]},
                {"event_name": "click", "handler_expression": "open = true",
                 "arguments": []},
            ]},
            "script": {"options": {"methods": [
                {"name": "choose", "body": "{ truncated",
                 "body_full": "{ this.selected = item.id; }"},
            ]}},
        }
        issues = [{"code": code} for code in (
            "missing_event_handlers", "missing_event_bindings", "event_arguments_not_landed"
        )]
        prompt = build_repair_prompt(RepairPromptInput(
            ssm=ssm, current_code="<template><button></button></template>",
            validation_errors=issues,
        ))
        self.assertIn("repairing ONLY the remaining event contract errors", prompt)
        self.assertIn("A name change alone is NOT proof", prompt)
        self.assertIn("choose(item.id)", prompt)
        self.assertIn("this.selected = item.id", prompt)
        self.assertNotIn("{ truncated", prompt)
        self.assertIn("source assignments", prompt)
        self.assertNotIn("--- SSM ---", prompt)
        for issue in issues:
            self.assertIn(issue["code"], prompt)

        visual_prompt = build_repair_prompt(RepairPromptInput(
            ssm=ssm, current_code="<template></template>",
            validation_errors=issues,
            visual_eval_errors=[{"code": "dom_structure_similarity_low"}],
        ))
        self.assertIn("--- SSM ---", visual_prompt)


if __name__ == "__main__":
    unittest.main()
