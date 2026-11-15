"""Source-event traceability gate for focused repair candidates."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from migration_pipeline.utils.repair_regression_guard import assess_event_contract_regression
from migration_pipeline.orchestrator import MigrationPipelineOrchestrator
from migration_pipeline.stages.repair import RepairStage
from migration_pipeline.stages.generate import GenerateStageInput, GenerateStageResult
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.utils.san_compile import check_san_compile
from migration_pipeline import probe_formal_30_v4_task_manager_semantic_focus_v2 as probe_v2
from migration_pipeline import probe_formal_30_v4_task_manager_event_focus_v3 as probe_v3


ROOT = Path(__file__).resolve().parents[1]


class RepairRegressionGuardTests(unittest.TestCase):
    def test_frozen_semantic_probe_detects_new_pre_mount_tasks_write(self):
        snapshot = ROOT / (
            "data/experiments/snapshots/"
            "formal_30_v4_task_manager_semantic_residual_probe_v1_result_20261028_230247"
        )
        source = ROOT / (
            "data/experiments/snapshots/"
            "formal_30_v4_task_manager_boolean_event_regression_v1_"
            "TaskManager_automatic_fail_20261028_220158"
        )
        ssm = json.loads((source / "repair_history.json").read_text(encoding="utf-8"))["state"]["ssm"]
        before = (snapshot / "prepared_input.san").read_text(encoding="utf-8")
        after = (snapshot / "candidate.san").read_text(encoding="utf-8")
        report = json.loads((snapshot / "probe_report.json").read_text(encoding="utf-8"))
        errors = json.loads((snapshot / "validation_errors.json").read_text(encoding="utf-8"))
        gate = assess_event_contract_regression(
            ssm=ssm, before_code=before, after_code=after,
            before_errors=errors, after_errors=report["validation_errors"],
        )
        self.assertEqual(gate["decision"], "review")
        self.assertTrue(gate["should_stop"])
        self.assertEqual(gate["new_pre_mount_state_writes"], ["tasks"])
        self.assertEqual(gate["unjustified_pre_mount_state_writes"], ["tasks"])
        still_present = assess_event_contract_regression(
            ssm=ssm, before_code=after, after_code=after,
            before_errors=report["validation_errors"],
            after_errors=report["validation_errors"],
        )
        self.assertEqual(still_present["decision"], "review")
        self.assertEqual(still_present["new_pre_mount_state_writes"], [])
        self.assertEqual(still_present["unjustified_pre_mount_state_writes"], ["tasks"])

    def test_pre_mount_write_guard_ignores_prop_derived_and_nested_writes(self):
        ssm = {"script": {"options": {
            "data": [{"name": "tasks"}, {"name": "formData"}],
            "methods": [{"name": "loadTasks", "writes_inferred": ["tasks"]}],
            "lifecycle_hooks": [{"vue_hook": "mounted", "san_hook": "attached",
                                 "body": "{ this.loadTasks(); }"}],
        }}}
        before = '''<template><div></div></template><script>const san = require('san');
module.exports = san.defineComponent({
  inited() {
    this.watch('tasks', () => { this.data.set('tasks', []); });
  },
  attached() { this.loadTasks(); }
});</script><style></style>'''
        after = before.replace(
            "    this.watch('tasks', () => { this.data.set('tasks', []); });",
            "    this.watch('tasks', () => { this.data.set('tasks', []); });\n"
            "    this.data.set('formData', {});",
        )
        gate = assess_event_contract_regression(
            ssm=ssm, before_code=before, after_code=after,
            before_errors=[], after_errors=[],
        )
        self.assertEqual(gate["decision"], "pass")
        self.assertEqual(gate["new_pre_mount_state_writes"], [])
        self.assertEqual(gate["unjustified_pre_mount_state_writes"], [])
        with_created = {"script": {"options": {
            **ssm["script"]["options"],
            "lifecycle_hooks": [
                {"vue_hook": "created", "san_hook": "inited", "body": "{}"},
                *ssm["script"]["options"]["lifecycle_hooks"],
            ],
        }}}
        new_tasks = before.replace(
            "    this.watch('tasks', () => { this.data.set('tasks', []); });",
            "    this.watch('tasks', () => { this.data.set('tasks', []); });\n"
            "    this.data.set('tasks', []);",
        )
        self.assertEqual(assess_event_contract_regression(
            ssm=with_created, before_code=before, after_code=new_tasks,
            before_errors=[], after_errors=[],
        )["new_pre_mount_state_writes"], [])

    def test_event_v3_probe_prepares_only_frozen_event_residuals(self):
        # This historic event-only probe was frozen under an older validator.
        # The current validator correctly discovers a first-mount prop state
        # defect and missing parent callable interfaces, so a fresh event-only
        # preparation must fail closed (the original frozen result is unchanged).
        with self.assertRaisesRegex(RuntimeError, "only the expected event residuals"):
            probe_v3.prepare()
        state = json.loads((probe_v3.SOURCE / "repair_history.json").read_text(encoding="utf-8"))["state"]
        candidate = (probe_v3.CANDIDATE / "candidate.san").read_text(encoding="utf-8")
        prepared = RepairStage._normalize_unresolved_source_event_alias(candidate, state["ssm"])
        prepared = RepairStage._normalize_misplaced_mounted_first_call(prepared, state["ssm"])
        prepared = RepairStage._normalize_terminal_state_array_splice(prepared, state["ssm"])
        validation = ValidateStage().run(ValidateStageInput(
            generated_code=prepared, ssm=state["ssm"],
            source_file=state.get("source_file", ""),
            vue_file_path=state.get("vue_file_path", ""),
        ))
        self.assertEqual(
            {item["code"] for item in validation.validation_errors},
            probe_v3.EXPECTED_ERRORS | {
                "missing_inline_prop_dependent_initialization",
                "missing_self_click_guard",
                "native_drag_event_misbound",
                "source_method_interface_not_landed",
                "source_dom_event_not_landed",
            },
        )
        self.assertEqual({item['location'] for item in validation.validation_errors
                          if item['code'] == 'source_dom_event_not_landed'}, {
            'template/div[0]/div[4]@click',
            'script.task-item.template/div[0]@dragstart',
            'script.task-item.template/div[0]@dragend',
            'script.task-detail.template/div[0]/div[1]/div[5]/div[1]/div[1]/input[0]@keyup',
        })
        missing_api={item['location'] for item in validation.validation_errors
                     if item['code']=='source_method_interface_not_landed'}
        self.assertIn('script.methods.isOverdue',missing_api)
        self.assertIn('script.methods.openTaskModal',missing_api)
        self.assertEqual(
            RepairStage._deterministic_repair_plan(prepared, validation.validation_errors, [], state["ssm"])[0],
            prepared,
        )

    def test_frozen_v3b_boolean_event_replay_is_bounded_and_passes_static_checks(self):
        snapshot = ROOT / (
            "data/experiments/snapshots/"
            "formal_30_v4_task_manager_event_focus_v3b_result_20261028_203015"
        )
        source = ROOT / (
            "data/experiments/snapshots/"
            "formal_30_v4_semantic_focus_v2_TaskManager_automatic_fail_20261028_140129"
        )
        ssm = json.loads((source / "repair_history.json").read_text(encoding="utf-8"))["state"]["ssm"]
        report = json.loads((snapshot / "probe_report.json").read_text(encoding="utf-8"))
        code = (snapshot / "candidate.san").read_text(encoding="utf-8")
        fixed = RepairStage._normalize_source_boolean_assignment_events(code, ssm)
        self.assertTrue(fixed != code)
        self.assertEqual(fixed.count('on-click="__migrationSetShowSettingsTrue"'), 1)
        self.assertEqual(fixed.count('on-click="__migrationSetShowSettingsFalse"'), 2)
        self.assertEqual(fixed.count("this.data.set('showSettings', true);"), 1)
        self.assertEqual(fixed.count("this.data.set('showSettings', false);"), 1)
        self.assertEqual(RepairStage._normalize_source_boolean_assignment_events(fixed, ssm), fixed)
        validation = ValidateStage().run(ValidateStageInput(
            generated_code=fixed, ssm=ssm, compile_check=False,
        ))
        self.assertEqual(validation.validation_errors, [])
        compiled = check_san_compile(san_source=fixed)
        self.assertFalse(compiled.skipped, compiled.reason)
        self.assertTrue(compiled.passed, compiled.diagnostics)
        gate = assess_event_contract_regression(
            ssm=ssm, before_code=code, after_code=fixed,
            before_errors=report["validation_errors"],
            after_errors=validation.validation_errors,
        )
        self.assertEqual(gate["decision"], "pass")
        deterministic, applied = RepairStage._deterministic_repair_plan(
            code, report["validation_errors"], [], ssm,
        )
        self.assertEqual(deterministic, fixed)
        self.assertIn(
            ("san_source_boolean_event_normalizer", "converted_source_boolean_assignment_events"),
            applied,
        )

    def test_boolean_event_normalizer_refuses_uncorroborated_or_ambiguous_cases(self):
        ssm = {
            "template": {"event_bindings": [
                {"event_name": "click", "handler_expression": "flag = true"},
            ]},
            "script": {"options": {"data": [{"name": "flag"}]}},
        }
        code = '''<template><button on-click="flag = true">Go</button></template>
<script>const san = require('san'); const DataTypes = san.DataTypes;
module.exports = san.defineComponent({
  dataTypes: { flag: DataTypes.bool },
  initData() { return { flag: false }; },
  other() {}
});</script><style></style>'''
        fixed = RepairStage._normalize_source_boolean_assignment_events(code, ssm)
        self.assertIn('on-click="__migrationSetFlagTrue"', fixed)
        self.assertIn("this.data.set('flag', true);", fixed)
        self.assertTrue(check_san_compile(san_source=fixed).passed)

        for candidate_ssm, candidate_code in (
            ({"template": {"event_bindings": []}, "script": ssm["script"]}, code),
            ({"template": ssm["template"], "script": {"options": {"data": []}}}, code),
            (ssm, code.replace("DataTypes.bool", "DataTypes.string")),
            (ssm, code.replace("flag: false", "flag: null")),
            (ssm, code.replace('on-click="flag = true"', 'on-click="flag = false"')),
            (ssm, code.replace('on-click="flag = true"', 'on-click="flag = maybe"')),
            (ssm, code.replace('</button>', '</button><button on-click="flag = true">Again</button>')),
            (ssm, code.replace('other() {}', '__migrationSetFlagTrue() { this.data.set(\'flag\', false); }')),
        ):
            with self.subTest(candidate_code=candidate_code[:100]):
                self.assertEqual(
                    RepairStage._normalize_source_boolean_assignment_events(
                        candidate_code, candidate_ssm,
                    ), candidate_code,
                )

        child_only = code.replace('on-click="flag = true"', 'on-click="other"').replace(
            "module.exports = san.defineComponent({",
            "const Child = san.defineComponent({ template: `<button on-click=\"flag = true\"></button>` });\n"
            "module.exports = san.defineComponent({",
        )
        self.assertEqual(
            RepairStage._normalize_source_boolean_assignment_events(child_only, ssm),
            child_only,
        )

        with_existing = code.replace(
            "other() {}", "other() {},\n  openFlag() { this.data.set('flag', true); }"
        )
        reused = RepairStage._normalize_source_boolean_assignment_events(with_existing, ssm)
        self.assertIn('on-click="openFlag"', reused)
        self.assertNotIn("__migrationSetFlagTrue", reused)
        self.assertEqual(reused.count("this.data.set('flag', true);"), 1)

    def test_frozen_probe_distinguishes_aliases_from_unresolved_binding(self):
        snapshots = ROOT / "data/experiments/snapshots"
        before = snapshots / "formal_30_v4_semantic_focus_v2_TaskManager_automatic_fail_20261028_140129"
        after = snapshots / "formal_30_v4_task_manager_semantic_probe_v1_result_20261028_155408"
        history = json.loads((before / "repair_history.json").read_text(encoding="utf-8"))
        report = json.loads((after / "probe_report.json").read_text(encoding="utf-8"))
        assessment = assess_event_contract_regression(
            ssm=history["state"]["ssm"],
            before_code=(before / "repair_round_3.san").read_text(encoding="utf-8"),
            after_code=(after / "candidate.san").read_text(encoding="utf-8"),
            before_errors=history["state"]["final_validate_result"]["validation_errors"],
            after_errors=report["validation_errors"],
        )
        self.assertEqual(assessment["decision"], "reject")
        self.assertTrue(assessment["should_stop"])
        self.assertEqual(assessment["additional_unresolved_source_bindings"], 1)
        self.assertEqual(assessment["after"]["unresolved"], ["click:closeModal"])
        self.assertGreaterEqual(len(assessment["after"]["plausible_aliases"]), 20)
        self.assertIn(
            "click:onStatClick(stat) -> handleStatClick(stat)",
            assessment["after"]["plausible_aliases"],
        )

    def test_plausible_alias_requires_review_not_claimed_missing(self):
        ssm = {"template": {"event_bindings": [
            {"event_name": "click", "handler_expression": "select(item.id)"},
        ]}}
        before = "<template><button on-click=\"select(item.id)\"></button></template><script>select(item) {}</script>"
        after = "<template><button on-click=\"handleSelect(item.id)\"></button></template><script>\n  handleSelect(item) {}\n</script>"
        result = assess_event_contract_regression(
            ssm=ssm, before_code=before, after_code=after,
            before_errors=[], after_errors=[{"code": "missing_event_bindings"}],
        )
        self.assertEqual(result["decision"], "review")
        self.assertEqual(result["additional_unresolved_source_bindings"], 0)
        self.assertEqual(len(result["after"]["plausible_aliases"]), 1)

    def test_unbound_or_invalid_candidate_is_rejected(self):
        ssm = {"template": {"event_bindings": [
            {"event_name": "click", "handler_expression": "select(item.id)"},
        ]}}
        before = "<template><button on-click=\"select(item.id)\"></button></template>"
        after = "<template><button on-click.stop></button></template>"
        result = assess_event_contract_regression(
            ssm=ssm, before_code=before, after_code=after,
            before_errors=[], after_errors=[{"code": "invalid_san_event_handler_syntax"}],
        )
        self.assertEqual(result["decision"], "reject")
        self.assertEqual(result["additional_unresolved_source_bindings"], 1)

    def test_unchanged_source_bindings_pass(self):
        ssm = {"template": {"event_bindings": [
            {"event_name": "click", "handler_expression": "select(item.id)"},
        ]}}
        code = "<template><button on-click=\"select(item.id)\"></button></template>"
        result = assess_event_contract_regression(
            ssm=ssm, before_code=code, after_code=code,
            before_errors=[], after_errors=[],
        )
        self.assertEqual(result["decision"], "pass")
        self.assertFalse(result["should_stop"])

    def test_san_value_modifier_does_not_look_like_lost_binding(self):
        ssm = {"template": {"event_bindings": [
            {"event_name": "click", "handler_expression": "choose(item.id)"},
        ]}}
        before = '<template><button on-click="choose(item.id)"></button></template>'
        after = '<template><button on-click="stop:choose(item.id)"></button></template>'
        result = assess_event_contract_regression(
            ssm=ssm, before_code=before, after_code=after,
            before_errors=[], after_errors=[],
        )
        self.assertEqual(result["decision"], "pass")
        self.assertEqual(result["after"]["unresolved"], [])

    def test_orchestrator_never_promotes_a_rejected_focused_candidate(self):
        orchestrator = object.__new__(MigrationPipelineOrchestrator)
        state = {
            "validation_passed": True,
            "visual_eval_passed": True,
            "repair_regression_rejected": True,
            "repair_attempt": 1,
            "generated_code": "<template></template>",
            "generated_file_path": "candidate.san",
        }
        self.assertFalse(orchestrator._stage_passed(state))
        self.assertFalse(orchestrator._should_continue_repair(state, 3))
        orchestrator._finalize_state(state, 3)
        self.assertFalse(state["final_passed"])
        self.assertEqual(state["stop_reason"], "repair_event_contract_regression")

    def test_bounded_modifier_normalization_preserves_ambiguous_cases(self):
        code = (
            '<template><button on-click.stop="choose(item.id)"></button>'
            '<form on-submit.prevent="save(item.id)"></form>'
            '<form on-submit.prevent="save($event)"></form>'
            '<div on-click.stop></div>'
            '<button on-click.stop="fire(\'edit\', item)"></button>'
            '<input on-keyup.enter="submit" />'
            '<button on-click.enter="submit"></button></template>'
            '<script>const note = "on-click.stop=\\\"choose(item.id)\\\"";</script>'
        )
        fixed = RepairStage._normalize_simple_template_syntax(code)
        self.assertIn('on-click="stop:choose(item.id)"', fixed)
        self.assertIn('on-submit="prevent:save(item.id)"', fixed)
        self.assertIn('on-submit.prevent="save($event)"', fixed)
        self.assertIn('<div on-click.stop>', fixed)
        self.assertIn('on-click="stop:fire(\'edit\', item)"', fixed)
        self.assertIn('on-keyup="enter:submit"', fixed)
        self.assertIn('on-click.enter="submit"', fixed)
        self.assertIn('const note = "on-click.stop=', fixed)

    def test_simple_modifier_normalization_preserves_fire_payload_and_key_filter(self):
        code = '''<template><task-item on-edit="onEdit($event)"></task-item></template>
<script>const san = require('san');
const Child = san.defineComponent({
  template: `<div><button on-click.stop="fire('edit', task)"></button>
  <button on-click.stop="fire('delete', task.id)"></button>
  <input on-keyup.enter="addComment" />
  <button on-click.enter="other"></button></div>`,
  initData() { return {task: {id: 1}}; }, addComment() {}
});
module.exports = san.defineComponent({components: {'task-item': Child}});
</script><style></style>'''
        fixed = RepairStage._normalize_simple_template_syntax(code)
        self.assertIn('on-click="stop:fire(\'edit\', task)"', fixed)
        self.assertIn('on-click="stop:fire(\'delete\', task.id)"', fixed)
        self.assertIn('on-keyup="enter:addComment"', fixed)
        self.assertIn('on-click.enter="other"', fixed)
        self.assertIn('on-edit="onEdit($event)"', fixed)
        self.assertEqual(RepairStage._normalize_simple_template_syntax(fixed), fixed)
        compiled = check_san_compile(san_source=fixed)
        self.assertFalse(compiled.skipped, compiled.reason)
        self.assertTrue(compiled.passed, compiled.diagnostics)

    def test_empty_modifier_handler_normalization_is_scoped_and_idempotent(self):
        code = '''<template><div on-dragover.prevent><button on-click.stop>Close</button></div></template>
<script>
const san = require('san');
const Child = san.defineComponent({
  template: `<div on-dragover.prevent><button on-click.stop="fire('edit', item)">Edit</button></div>`,
  fire(type, item) { this.fire(type, item); }
});
module.exports = san.defineComponent({
  components: {'child': Child},
  initData() { return {}; }
});
</script><style></style>'''
        fixed = RepairStage._normalize_empty_modifier_handlers(code)
        self.assertIn('on-dragover="prevent:__migrationNoopEvent"', fixed)
        self.assertIn('on-click="stop:__migrationNoopEvent"', fixed)
        self.assertEqual(fixed.count('__migrationNoopEvent() {}'), 2)
        self.assertIn('on-click.stop="fire(\'edit\', item)"', fixed)
        self.assertEqual(RepairStage._normalize_empty_modifier_handlers(fixed), fixed)
        compile_result = check_san_compile(san_source=fixed)
        self.assertFalse(compile_result.skipped, compile_result.reason)
        self.assertTrue(compile_result.passed, compile_result.diagnostics)

    def test_empty_modifier_normalizer_ignores_non_attributes_and_valued_handlers(self):
        code = '''<template><div title="plain on-click.stop" data-x=on-click.stop
on-click.stop="fire('select', item)" on-keyup.enter="submit"></div></template>
<script>const san = require('san');
const note = 'on-dragover.prevent';
module.exports = san.defineComponent({initData() { return {}; }});
</script><style>.x { content: "on-click.stop"; }</style>'''
        self.assertEqual(RepairStage._normalize_empty_modifier_handlers(code), code)

    def test_empty_quoted_modifier_handlers_are_normalized_without_touching_text_or_handlers(self):
        code = '''<template><div on-dragover.prevent="" title='on-click.stop=""'>
<button on-click.stop=''>Close</button>
<button on-click.stop="fire('edit', item)">Edit</button></div></template>
<script>const san = require('san');
const Child = san.defineComponent({
  template: `<div on-drag-over.prevent=''></div>`,
  initData() { return {}; }
});
module.exports = san.defineComponent({initData() { return {}; }});
</script><style>.x { content: 'on-click.stop=""'; }</style>'''
        fixed = RepairStage._normalize_empty_modifier_handlers(code)
        self.assertEqual(fixed.count('on-dragover="prevent:__migrationNoopEvent"'), 1)
        self.assertEqual(fixed.count('on-click="stop:__migrationNoopEvent"'), 1)
        self.assertEqual(fixed.count('on-drag-over="prevent:__migrationNoopEvent"'), 1)
        self.assertEqual(fixed.count('__migrationNoopEvent() {}'), 2)
        self.assertIn('title=\'on-click.stop=""\'', fixed)
        self.assertIn('on-click.stop="fire(\'edit\', item)"', fixed)
        self.assertIn("content: 'on-click.stop=\"\"'", fixed)
        self.assertEqual(RepairStage._normalize_empty_modifier_handlers(fixed), fixed)
        compiled = check_san_compile(san_source=fixed)
        self.assertFalse(compiled.skipped, compiled.reason)
        self.assertTrue(compiled.passed, compiled.diagnostics)

    def test_latest_frozen_task_manager_quoted_empty_modifier_replay(self):
        snapshot = ROOT / (
            "data/experiments/snapshots/"
            "formal_30_v4_task_manager_boolean_event_regression_v1_"
            "TaskManager_automatic_fail_20261028_220158"
        )
        original = (snapshot / "repair_round_3.san").read_text(encoding="utf-8")
        state = json.loads((snapshot / "repair_history.json").read_text(encoding="utf-8"))["state"]
        fixed = RepairStage._normalize_empty_modifier_handlers(original)
        self.assertEqual(fixed.count('on-dragover="prevent:__migrationNoopEvent"'), 1)
        self.assertEqual(fixed.count('on-drag-over="prevent:__migrationNoopEvent"'), 1)
        self.assertEqual(fixed.count('__migrationNoopEvent() {}'), 2)
        before = ValidateStage().run(ValidateStageInput(
            generated_code=original, ssm=state["ssm"], compile_check=False,
        ))
        after = ValidateStage().run(ValidateStageInput(
            generated_code=fixed, ssm=state["ssm"], compile_check=False,
        ))
        self.assertIn("invalid_san_event_handler_syntax", {
            issue["code"] for issue in before.validation_errors
        })
        self.assertNotIn("invalid_san_event_handler_syntax", {
            issue["code"] for issue in after.validation_errors
        })
        self.assertEqual((snapshot / "repair_round_3.san").read_text(encoding="utf-8"), original)

    def test_frozen_probe_empty_modifier_replay_removes_only_four_syntax_cases(self):
        snapshot = ROOT / (
            "data/experiments/snapshots/"
            "formal_30_v4_task_manager_semantic_probe_v1_result_20261028_155408"
        )
        original = (snapshot / "candidate.san").read_text(encoding="utf-8")
        source = ROOT / (
            "data/experiments/snapshots/"
            "formal_30_v4_semantic_focus_v2_TaskManager_automatic_fail_20261028_140129"
        )
        ssm = json.loads((source / "repair_history.json").read_text(encoding="utf-8"))["state"]["ssm"]
        fixed = RepairStage._normalize_empty_modifier_handlers(original)
        self.assertEqual(fixed.count('="prevent:__migrationNoopEvent"'), 2)
        self.assertEqual(fixed.count('="stop:__migrationNoopEvent"'), 2)
        self.assertEqual(fixed.count('__migrationNoopEvent() {}'), 2)
        self.assertEqual(RepairStage._normalize_empty_modifier_handlers(fixed), fixed)
        compile_result = check_san_compile(san_source=fixed)
        self.assertFalse(compile_result.skipped, compile_result.reason)
        self.assertTrue(compile_result.passed, compile_result.diagnostics)
        before = ValidateStage().run(ValidateStageInput(
            generated_code=original, ssm=ssm, compile_check=False,
        ))
        after = ValidateStage().run(ValidateStageInput(
            generated_code=fixed, ssm=ssm, compile_check=False,
        ))
        before_codes = {issue["code"] for issue in before.validation_errors}
        after_codes = {issue["code"] for issue in after.validation_errors}
        self.assertEqual(before_codes, after_codes)
        before_syntax = next(issue for issue in before.validation_errors
                             if issue["code"] == "invalid_san_event_handler_syntax")
        after_syntax = next(issue for issue in after.validation_errors
                            if issue["code"] == "invalid_san_event_handler_syntax")
        self.assertIn("7 invalid event binding", before_syntax["message"])
        self.assertIn("3 invalid event binding", after_syntax["message"])

    def test_frozen_probe_combined_modifier_replay_clears_syntax_not_semantics(self):
        snapshot = ROOT / (
            "data/experiments/snapshots/"
            "formal_30_v4_task_manager_semantic_probe_v1_result_20261028_155408"
        )
        original = (snapshot / "candidate.san").read_text(encoding="utf-8")
        source = ROOT / (
            "data/experiments/snapshots/"
            "formal_30_v4_semantic_focus_v2_TaskManager_automatic_fail_20261028_140129"
        )
        ssm = json.loads((source / "repair_history.json").read_text(encoding="utf-8"))["state"]["ssm"]
        fixed = RepairStage._normalize_empty_modifier_handlers(
            RepairStage._normalize_simple_template_syntax(original)
        )
        self.assertIn('on-click="stop:fire(\'edit\', task)"', fixed)
        self.assertIn('on-click="stop:fire(\'delete\', task.id)"', fixed)
        self.assertIn('on-keyup="enter:addComment"', fixed)
        compiled = check_san_compile(san_source=fixed)
        self.assertFalse(compiled.skipped, compiled.reason)
        self.assertTrue(compiled.passed, compiled.diagnostics)
        after = ValidateStage().run(ValidateStageInput(
            generated_code=fixed, ssm=ssm, compile_check=False,
        ))
        after_codes = {issue["code"] for issue in after.validation_errors}
        self.assertNotIn("invalid_san_event_handler_syntax", after_codes)
        self.assertTrue({
            "missing_event_handlers", "event_arguments_not_landed",
            "lifecycle_behavior_not_landed", "missing_event_bindings",
        } <= after_codes)

    def test_v2_probe_frozen_input_stays_immutable_under_new_rules(self):
        frozen = probe_v2.SOURCE / "repair_round_3.san"
        before_sha = probe_v2.sha256(frozen)
        manifest = json.loads((probe_v2.SOURCE / "manifest.json").read_text(encoding="utf-8"))
        state = json.loads((probe_v2.SOURCE / "repair_history.json").read_text(encoding="utf-8"))["state"]
        prepared = (probe_v2.PRE_RUN / "input.san").read_text(encoding="utf-8")
        errors = json.loads((probe_v2.PRE_RUN / "validation_errors.json").read_text(encoding="utf-8"))
        prompt = (probe_v2.PRE_RUN / "prompt.txt").read_text(encoding="utf-8")
        self.assertEqual(manifest["sample_id"], "TaskManager")
        self.assertIn('on-click="stop:fire(\'edit\', task)"', prepared)
        self.assertIn('on-keyup="enter:addComment"', prepared)
        self.assertIn('on-dragover="prevent:__migrationNoopEvent"', prepared)
        self.assertIn("ALL listed semantic validation errors", prompt)
        self.assertIn("lifecycle_behavior_not_landed", {issue["code"] for issue in errors})
        self.assertNotEqual(
            RepairStage._deterministic_repair_plan(prepared, errors, [], state["ssm"])[0],
            prepared,
        )
        self.assertEqual(probe_v2.sha256(frozen), before_sha)

    def test_bounded_source_event_alias_fix_restores_only_missing_parent_handler(self):
        snapshot = ROOT / (
            "data/experiments/snapshots/"
            "formal_30_v4_task_manager_semantic_probe_v2b_result_20261028_181549"
        )
        source = ROOT / (
            "data/experiments/snapshots/"
            "formal_30_v4_semantic_focus_v2_TaskManager_automatic_fail_20261028_140129"
        )
        ssm = json.loads((source / "repair_history.json").read_text(encoding="utf-8"))["state"]["ssm"]
        code = (snapshot / "candidate.san").read_text(encoding="utf-8")
        fixed = RepairStage._normalize_unresolved_source_event_alias(code, ssm)
        self.assertIn('on-click="hideNotification"', fixed)
        self.assertNotIn('on-click="handleHideNotification"', fixed)
        self.assertIn('on-click="handleToggleTheme"', fixed)
        self.assertEqual(RepairStage._normalize_unresolved_source_event_alias(fixed, ssm), fixed)
        compiled = check_san_compile(san_source=fixed)
        self.assertFalse(compiled.skipped, compiled.reason)
        self.assertTrue(compiled.passed, compiled.diagnostics)
        validation = ValidateStage().run(ValidateStageInput(
            generated_code=fixed, ssm=ssm, compile_check=False,
        ))
        gate = assess_event_contract_regression(
            ssm=ssm,
            before_code=(snapshot / "prepared_input.san").read_text(encoding="utf-8"),
            after_code=fixed,
            before_errors=json.loads((snapshot / "validation_errors.json").read_text(encoding="utf-8")),
            after_errors=validation.validation_errors,
        )
        self.assertEqual(gate["decision"], "review")
        self.assertEqual(gate["after"]["unresolved"], [])
        self.assertEqual(len(gate["after"]["plausible_aliases"]), 22)
        self.assertIn("nested_state_mutation", {e["code"] for e in validation.validation_errors})

    def test_source_event_alias_fix_fails_closed_without_parent_method_or_ssm_match(self):
        code = '''<template><button on-click="handleClose">Close</button></template>
<script>const san = require('san');
const Child = san.defineComponent({close() {}});
module.exports = san.defineComponent({
  computed: { close() { return true; } },
  initData() { return {}; }
});</script><style></style>'''
        ssm = {"template": {"event_bindings": [
            {"event_name": "click", "handler_expression": "close"},
        ]}}
        self.assertEqual(RepairStage._normalize_unresolved_source_event_alias(code, ssm), code)
        code_with_parent_method = code.replace("initData() { return {}; }", "close() {}, initData() { return {}; }")
        wrong_ssm = {"template": {"event_bindings": [
            {"event_name": "change", "handler_expression": "close"},
        ]}}
        self.assertEqual(RepairStage._normalize_unresolved_source_event_alias(
            code_with_parent_method, wrong_ssm,
        ), code_with_parent_method)

    def test_frozen_v2b_lifecycle_replay_restores_mounted_call_order(self):
        snapshot = ROOT / (
            "data/experiments/snapshots/"
            "formal_30_v4_task_manager_semantic_probe_v2b_result_20261028_181549"
        )
        source = ROOT / (
            "data/experiments/snapshots/"
            "formal_30_v4_semantic_focus_v2_TaskManager_automatic_fail_20261028_140129"
        )
        ssm = json.loads((source / "repair_history.json").read_text(encoding="utf-8"))["state"]["ssm"]
        code = (snapshot / "candidate.san").read_text(encoding="utf-8")
        fixed = RepairStage._normalize_misplaced_mounted_first_call(code, ssm)
        self.assertNotEqual(fixed, code)
        self.assertIn(
            "attached() {\n    // Initialize from localStorage\n"
            "    this.loadInitialData();\n    this.startAutoSync();", fixed,
        )
        self.assertEqual(RepairStage._normalize_misplaced_mounted_first_call(fixed, ssm), fixed)
        compiled = check_san_compile(san_source=fixed)
        self.assertFalse(compiled.skipped, compiled.reason)
        self.assertTrue(compiled.passed, compiled.diagnostics)
        after = ValidateStage().run(ValidateStageInput(
            generated_code=fixed, ssm=ssm, compile_check=False,
        ))
        codes = {issue["code"] for issue in after.validation_errors}
        self.assertNotIn("lifecycle_behavior_not_landed", codes)
        self.assertIn("nested_state_mutation", codes)

    def test_mounted_first_call_move_fails_closed_if_inited_has_later_work(self):
        ssm = {"script": {"options": {"lifecycle_hooks": [
            {"vue_hook": "mounted", "san_hook": "attached",
             "body": "{ this.load(); this.start(); }"},
        ]}}}
        code = '''<template><div></div></template><script>
const san = require('san'); module.exports = san.defineComponent({
  inited() {
    this.load();
    this.watch('x', () => {});
  },
  attached() {
    this.start();
  },
  load() {}, start() {}
});</script><style></style>'''
        self.assertEqual(RepairStage._normalize_misplaced_mounted_first_call(code, ssm), code)
        source_with_arguments = {"script": {"options": {"lifecycle_hooks": [
            {"vue_hook": "mounted", "san_hook": "attached",
             "body": "{ this.load(value); this.start(); }"},
        ]}}}
        self.assertEqual(RepairStage._normalize_misplaced_mounted_first_call(
            code, source_with_arguments,
        ), code)

    def test_frozen_task_manager_full_mounted_sequence_moves_to_empty_attached(self):
        snapshot = ROOT / (
            "data/experiments/snapshots/"
            "formal_30_v4_task_manager_boolean_event_regression_v1_"
            "TaskManager_automatic_fail_20261028_220158"
        )
        original = (snapshot / "repair_round_3.san").read_text(encoding="utf-8")
        ssm = json.loads((snapshot / "repair_history.json").read_text(encoding="utf-8"))["state"]["ssm"]
        fixed = RepairStage._normalize_misplaced_mounted_first_call(original, ssm)
        self.assertNotEqual(fixed, original)
        self.assertIn(
            "attached() {\n    // Load initial data after init\n"
            "    this.loadInitialData();\n    this.startAutoSync();\n"
            "    this.showNotification(", fixed,
        )
        self.assertNotIn("this.loadInitialData();\n    this.startAutoSync();", fixed.split("attached() {")[0])
        self.assertEqual(RepairStage._normalize_misplaced_mounted_first_call(fixed, ssm), fixed)
        before = ValidateStage().run(ValidateStageInput(
            generated_code=original, ssm=ssm, compile_check=False,
        ))
        after = ValidateStage().run(ValidateStageInput(
            generated_code=fixed, ssm=ssm, compile_check=False,
        ))
        self.assertIn("lifecycle_behavior_not_landed", {e["code"] for e in before.validation_errors})
        self.assertNotIn("lifecycle_behavior_not_landed", {e["code"] for e in after.validation_errors})
        compiled = check_san_compile(san_source=fixed)
        self.assertFalse(compiled.skipped, compiled.reason)
        self.assertTrue(compiled.passed, compiled.diagnostics)
        self.assertEqual((snapshot / "repair_round_3.san").read_text(encoding="utf-8"), original)

    def test_full_mounted_sequence_move_requires_exact_source_and_no_later_work(self):
        ssm = {"script": {"options": {"lifecycle_hooks": [
            {"vue_hook": "mounted", "san_hook": "attached",
             "body": "{ this.load(); this.start(); }"},
        ]}}}
        code = '''<template><div></div></template><script>
const san = require('san'); module.exports = san.defineComponent({
  inited() {
    this.load();
    this.start();
  },
  attached() {},
  load() {}, start() {}
});</script><style></style>'''
        fixed = RepairStage._normalize_misplaced_mounted_first_call(code, ssm)
        self.assertIn("attached() {\n    this.load();\n    this.start();", fixed)
        self.assertEqual(RepairStage._normalize_misplaced_mounted_first_call(fixed, ssm), fixed)
        self.assertEqual(
            RepairStage._normalize_misplaced_mounted_first_call(
                code.replace("this.start();\n  },", "this.start();\n    this.watch('x', () => {});\n  },"), ssm,
            ),
            code.replace("this.start();\n  },", "this.start();\n    this.watch('x', () => {});\n  },"),
        )
        changed_source = {"script": {"options": {"lifecycle_hooks": [
            {"vue_hook": "mounted", "san_hook": "attached",
             "body": "{ this.load(); this.other(); }"},
        ]}}}
        self.assertEqual(RepairStage._normalize_misplaced_mounted_first_call(
            code, changed_source,
        ), code)

    def test_frozen_v2b_terminal_splice_replay_clones_and_commits_once(self):
        snapshot = ROOT / (
            "data/experiments/snapshots/"
            "formal_30_v4_task_manager_semantic_probe_v2b_result_20261028_181549"
        )
        source = ROOT / (
            "data/experiments/snapshots/"
            "formal_30_v4_semantic_focus_v2_TaskManager_automatic_fail_20261028_140129"
        )
        ssm = json.loads((source / "repair_history.json").read_text(encoding="utf-8"))["state"]["ssm"]
        code = (snapshot / "candidate.san").read_text(encoding="utf-8")
        fixed = RepairStage._normalize_terminal_state_array_splice(code, ssm)
        self.assertTrue(fixed != code, "bounded splice normalization did not apply")
        self.assertIn("const tasks = [...this.data.get('tasks')];", fixed)
        self.assertIn("tasks.splice(targetOriginalIndex, 0, movedTask);\n"
                      "      this.data.set('tasks', tasks);", fixed)
        self.assertEqual(fixed.count("this.data.set('tasks', tasks);"), 1)
        self.assertEqual(RepairStage._normalize_terminal_state_array_splice(fixed, ssm), fixed)
        compiled = check_san_compile(san_source=fixed)
        self.assertFalse(compiled.skipped, compiled.reason)
        self.assertTrue(compiled.passed, compiled.diagnostics)
        after = ValidateStage().run(ValidateStageInput(
            generated_code=fixed, ssm=ssm, compile_check=False,
        ))
        codes = {issue["code"] for issue in after.validation_errors}
        self.assertNotIn("nested_state_mutation", codes)
        self.assertIn("lifecycle_behavior_not_landed", codes)

    def test_terminal_splice_replay_refuses_unknown_control_flow(self):
        ssm = {"script": {"options": {"methods": [
            {"name": "reorder", "body": "{ this.items.splice(0, 1); this.items.splice(1, 0, item); }"},
        ]}}}
        code = '''<template><div></div></template><script>
const san = require('san'); module.exports = san.defineComponent({
  reorder() {
    const items = this.data.get('items');
    if (ready) {
      items.splice(0, 1);
      if (stop) return;
      items.splice(1, 0, item);
    }
  }
});</script><style></style>'''
        self.assertEqual(RepairStage._normalize_terminal_state_array_splice(code, ssm), code)
        mismatched = {"script": {"options": {"methods": [
            {"name": "reorder", "body": "{ this.items.splice(0, 1); }"},
        ]}}}
        self.assertEqual(RepairStage._normalize_terminal_state_array_splice(code, mismatched), code)

    def test_frozen_v2b_combined_bounded_replay_keeps_remaining_event_errors_visible(self):
        snapshot = ROOT / (
            "data/experiments/snapshots/"
            "formal_30_v4_task_manager_semantic_probe_v2b_result_20261028_181549"
        )
        source = ROOT / (
            "data/experiments/snapshots/"
            "formal_30_v4_semantic_focus_v2_TaskManager_automatic_fail_20261028_140129"
        )
        ssm = json.loads((source / "repair_history.json").read_text(encoding="utf-8"))["state"]["ssm"]
        code = (snapshot / "candidate.san").read_text(encoding="utf-8")
        code = RepairStage._normalize_unresolved_source_event_alias(code, ssm)
        code = RepairStage._normalize_misplaced_mounted_first_call(code, ssm)
        code = RepairStage._normalize_terminal_state_array_splice(code, ssm)
        compiled = check_san_compile(san_source=code)
        self.assertFalse(compiled.skipped, compiled.reason)
        self.assertTrue(compiled.passed, compiled.diagnostics)
        after = ValidateStage().run(ValidateStageInput(
            generated_code=code, ssm=ssm, compile_check=False,
        ))
        codes = {issue["code"] for issue in after.validation_errors}
        self.assertNotIn("nested_state_mutation", codes)
        self.assertNotIn("lifecycle_behavior_not_landed", codes)
        self.assertIn("missing_event_handlers", codes)

    def test_probe_freeze_preflight_uses_file_hash_and_text_equivalence(self):
        manifest = json.loads((probe_v2.SOURCE / "manifest.json").read_text(encoding="utf-8"))
        prepared = (probe_v2.PRE_RUN / "input.san").read_text(encoding="utf-8")
        errors = json.loads((probe_v2.PRE_RUN / "validation_errors.json").read_text(encoding="utf-8"))
        prompt = (probe_v2.PRE_RUN / "prompt.txt").read_text(encoding="utf-8")
        with TemporaryDirectory() as temporary:
            target = Path(temporary) / "pre_run"
            with (patch.object(probe_v2, "PRE_RUN", target),
                  patch.object(probe_v2, "OUTPUT", Path(temporary) / "output.san"),
                  patch.object(probe_v2, "REPORT", Path(temporary) / "report.json")):
                probe_v2.freeze(manifest, prepared, errors, prompt)
                frozen = probe_v2.verify_frozen_pre_run(manifest, prepared, prompt)
                self.assertEqual(frozen["input_sha256"], probe_v2.sha256(target / "input.san"))
                self.assertEqual(frozen["prompt_sha256"], probe_v2.sha256(target / "prompt.txt"))
                with self.assertRaisesRegex(RuntimeError, "differs from pre-run freeze"):
                    probe_v2.verify_frozen_pre_run(manifest, prepared, prompt + " changed")

    def test_repair_loop_stops_on_new_source_event_traceability_error(self):
        ssm = {"template": {"event_bindings": [
            {"event_name": "click", "handler_expression": "select(item.id)"},
        ]}}
        before = '<template><button on-click="select(item.id)"></button></template>'
        after = '<template><button on-click="handleSelect(item.id)"></button></template><script>\n  handleSelect(item) {}\n</script>'

        class Generate:
            def run(self, _):
                return GenerateStageResult(
                    source_file="example.vue", ssm=ssm, generation_code=before,
                    saved_file_path="before.san", provider="fake", model="fake",
                    usage={}, raw_response={},
                )

        class Validate:
            def run_from_state(self, state):
                candidate = state["generated_code"] == after
                errors = ([{"code": "missing_event_bindings"}] if candidate
                          else [{"code": "invalid_san_event_handler_syntax"}])
                return {
                    "validation_passed": False,
                    "validation_errors": errors,
                    "validate_result": {"validation_passed": False, "validation_errors": errors},
                }

        class Visual:
            def run_from_state(self, _):
                return {"visual_eval_passed": True, "visual_eval_errors": [],
                        "visual_eval_result": {"visual_eval_passed": True}}

        class Repair:
            calls = 0

            def run_from_state(self, _):
                self.calls += 1
                return {
                    "generated_code": after,
                    "generated_file_path": "candidate.san",
                    "repair_attempt": self.calls,
                    "repair_prompt": "ALL listed semantic validation errors",
                    "repair_result": {"repaired_code": after},
                }

        repair = Repair()
        orchestrator = MigrationPipelineOrchestrator(
            generate_stage=Generate(), validate_stage=Validate(),
            visual_eval_stage=Visual(), repair_stage=repair,
        )
        result = orchestrator.run_generate_validate_visual_eval_and_repair_loop(
            GenerateStageInput(ssm=ssm), max_repair_rounds=3,
        )
        self.assertEqual(repair.calls, 1)
        self.assertFalse(result.state["final_passed"])
        self.assertEqual(result.state["stop_reason"], "repair_event_contract_regression")
        self.assertEqual(result.state["repair_history"][0]["repair_regression_gate"]["decision"], "review")

    def test_pair_prompt_repair_loop_stops_on_pre_mount_state_write(self):
        ssm = {"script": {"options": {
            "data": [{"name": "items", "default_value": []}],
            "methods": [{"name": "loadItems", "writes_inferred": ["items"]}],
            "lifecycle_hooks": [{"vue_hook": "mounted", "san_hook": "attached",
                                 "body": "{ this.loadItems(); }"}],
        }}}
        before = '''<template><div></div></template><script>const san = require('san');
module.exports = san.defineComponent({
  inited() { this.watch('items', () => {}); },
  attached() { this.loadItems(); }
});</script><style></style>'''
        after = before.replace(
            "inited() { this.watch('items', () => {}); },",
            "inited() {\n    this.watch('items', () => {});\n"
            "    this.data.set('items', this.sampleItems());\n  },",
        )

        class Generate:
            def run(self, _):
                return GenerateStageResult(
                    source_file="example.vue", ssm=ssm, generation_code=before,
                    saved_file_path="before.san", provider="fake", model="fake",
                    usage={}, raw_response={},
                )

        class Validate:
            def run_from_state(self, state):
                errors = [] if state["generated_code"] == after else [
                    {"code": "invalid_san_init_data_store_access"},
                    {"code": "invalid_san_computed_instance_method_call"},
                ]
                return {
                    "validation_passed": not errors, "validation_errors": errors,
                    "validate_result": {"validation_passed": not errors,
                                        "validation_errors": errors},
                }

        class Visual:
            def run_from_state(self, _):
                return {"visual_eval_passed": True, "visual_eval_errors": [],
                        "visual_eval_result": {"visual_eval_passed": True}}

        class Repair:
            calls = 0

            def run_from_state(self, _):
                self.calls += 1
                return {
                    "generated_code": after, "generated_file_path": "candidate.san",
                    "repair_attempt": self.calls,
                    "repair_prompt": "Repair ONLY the two remaining validation error families",
                    "repair_result": {"repaired_code": after},
                }

        repair = Repair()
        result = MigrationPipelineOrchestrator(
            generate_stage=Generate(), validate_stage=Validate(),
            visual_eval_stage=Visual(), repair_stage=repair,
        ).run_generate_validate_visual_eval_and_repair_loop(
            GenerateStageInput(ssm=ssm), max_repair_rounds=3,
        )
        self.assertEqual(repair.calls, 1)
        self.assertFalse(result.state["final_passed"])
        self.assertEqual(result.state["stop_reason"], "repair_pre_mount_state_regression")
        self.assertEqual(
            result.state["repair_history"][0]["repair_regression_gate"]["new_pre_mount_state_writes"],
            ["items"],
        )


if __name__ == "__main__":
    unittest.main()
