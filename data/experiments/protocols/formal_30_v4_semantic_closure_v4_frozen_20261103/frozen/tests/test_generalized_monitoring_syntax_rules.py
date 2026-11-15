"""Cross-sample positive/negative cases for bounded Monitoring syntax rules."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from local_server.api.evaluation_routes import _build_generation_prompt
from migration_pipeline.repair_client import RepairResult
from migration_pipeline.stages.repair import RepairStage, RepairStageInput
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.utils.repair_prompt import RepairPromptInput, build_repair_prompt


ROOT = Path(__file__).resolve().parents[1]


class FailIfCalledClient:
    def repair(self, request_data):
        raise AssertionError("A bounded deterministic correction should skip the LLM")


class StaticClient:
    def __init__(self, code):
        self.code = code

    def repair(self, request_data):
        return RepairResult(
            source_file=request_data.source_file,
            ssm=request_data.ssm,
            code=self.code,
            saved_file_path=request_data.output_file_path or "repaired.san",
            provider="fake",
            model="fake",
            usage={"total_tokens": 1},
            raw_response={"ok": True},
        )


class GeneralizedMonitoringSyntaxRulesTests(unittest.TestCase):
    def test_simple_modifier_and_tuple_alias_normalize_outer_and_inline_templates(self):
        code = '''<template><form on-submit.prevent="submit">
<button s-for="(item, idx) in items trackby idx" on-click.stop="cancel">{{item}}</button>
</form></template>
<script>
const untouched = 'on-click.stop="cancel"';
const Child = san.defineComponent({
  template: `<div s-for='(row, rowIndex) in rows trackby rowIndex' on-click.stop='select'>{{row}}</div>`
});
</script><style></style>'''
        normalized = RepairStage._normalize_simple_template_syntax(code)
        self.assertIn('on-submit="prevent:submit"', normalized)
        self.assertIn('s-for="item, idx in items trackby idx"', normalized)
        self.assertIn('on-click="stop:cancel"', normalized)
        self.assertIn("s-for='row, rowIndex in rows trackby rowIndex'", normalized)
        self.assertIn("on-click='stop:select'", normalized)
        self.assertIn("const untouched = 'on-click.stop=\"cancel\"'", normalized)
        self.assertEqual(RepairStage._normalize_simple_template_syntax(normalized), normalized)

    def test_ambiguous_events_and_non_tuple_loops_are_unchanged(self):
        code = '''<template><div on-click.enter="submit" on-click.prevent="submit($event)"
on-input="value = 1" on-submit.prevent="" s-for="({id}, idx) in items">
<button on-click.stop.prevent="close" data-on-click.stop="save"
title='on-click.stop="save"'>Close</button>
<p>Literal on-click.stop="save" and s-for="(item, idx) in items"</p>
</div></template>'''
        self.assertEqual(RepairStage._normalize_simple_template_syntax(code), code)
        script_literal = '''<script>const example = '<template><button on-click.stop="go">x</button></template>';</script>'''
        self.assertEqual(RepairStage._normalize_simple_template_syntax(script_literal), script_literal)

    def test_only_simple_syntax_errors_use_deterministic_repair(self):
        code = '''<template><form on-submit.prevent="save">
<div s-for="(item, index) in items trackby index">{{item}}</div>
</form></template><script>module.exports = san.defineComponent({});</script><style></style>'''
        with TemporaryDirectory() as temp_dir:
            result = RepairStage(repair_client=FailIfCalledClient()).run(RepairStageInput(
                ssm={}, generated_code=code,
                output_file_path=str(Path(temp_dir) / "result.san"),
                validation_errors=[
                    {"code": "invalid_san_event_handler_syntax"},
                    {"code": "invalid_san_for_alias_syntax"},
                ],
            ))
        self.assertEqual(result.provider, "deterministic")
        self.assertEqual(result.model, "san_template_syntax_normalizer")
        self.assertIn('on-submit="prevent:save"', result.repaired_code)
        self.assertIn('s-for="item, index in items trackby index"', result.repaired_code)
        self.assertEqual(
            RepairStage._apply_deterministic_repairs(
                code,
                [{"code": "invalid_san_event_handler_syntax"}, {"code": "other_error"}],
                [],
            ),
            code,
        )

    def test_normalized_simple_syntax_compiles_as_san(self):
        code = '''<template><form on-submit.prevent="save">
<button s-for="(item, index) in items trackby index" on-click.stop="select">{{item}}</button>
</form></template>
<script>
const san = require('san'); const DataTypes = san.DataTypes;
module.exports = san.defineComponent({
  dataTypes: {},
  initData() { return {items: ['a', 'b']}; },
  save() {}, select() {}
});
</script><style>button { color: black; }</style>'''
        normalized = RepairStage._normalize_simple_template_syntax(code)
        validation = ValidateStage().run(ValidateStageInput(
            generated_code=normalized, compile_check=True,
        ))
        codes = {issue["code"] for issue in validation.validation_errors}
        self.assertNotIn("invalid_san_event_handler_syntax", codes)
        self.assertNotIn("invalid_san_for_alias_syntax", codes)
        self.assertNotIn("san_script_compile_error", codes)

    def test_llm_output_gets_only_bounded_syntax_postprocessing(self):
        code = '''<template><form on-submit.prevent="submit">
<button s-for="(item, idx) in items trackby idx" on-click.enter="cancel">{{item}}</button>
</form></template><script>module.exports = san.defineComponent({});</script><style></style>'''
        with TemporaryDirectory() as temp_dir:
            result = RepairStage(repair_client=StaticClient(code)).run(RepairStageInput(
                ssm={}, generated_code="<template></template>",
                output_file_path=str(Path(temp_dir) / "result.san"),
                validation_errors=[{"code": "other_error"}],
            ))
        self.assertEqual(result.provider, "fake")
        self.assertIn('on-submit="prevent:submit"', result.repaired_code)
        self.assertIn('s-for="item, idx in items trackby idx"', result.repaired_code)
        self.assertIn('on-click.enter="cancel"', result.repaired_code)
        self.assertIn(
            "normalized_simple_san_template_syntax",
            result.raw_response["pipeline_postprocessing"],
        )

    def test_safe_class_merge_combines_with_simple_syntax_but_not_ambiguous_class(self):
        code = '''<template><button class="base" class="{{ active ? 'selected' : '' }}"
on-click.stop="select" s-for="(item, idx) in items trackby idx">{{item}}</button></template>
<script>module.exports = san.defineComponent({});</script><style></style>'''
        normalized, repairs = RepairStage._deterministic_repair_plan(
            code,
            [
                {"code": "duplicate_class_attribute"},
                {"code": "invalid_san_event_handler_syntax"},
                {"code": "invalid_san_for_alias_syntax"},
            ],
            [],
        )
        self.assertEqual([name for _, name in repairs], [
            "normalized_simple_san_template_syntax",
            "merged_static_and_dynamic_class_attributes",
        ])
        self.assertIn('class="base {{active ? \'selected\' : \'\'}}"', normalized)
        self.assertIn('on-click="stop:select"', normalized)
        self.assertIn('s-for="item, idx in items trackby idx"', normalized)
        ambiguous = code.replace(
            'class="base"', 'class="{{ hovered ? \'hovered\' : \'\' }}"'
        )
        self.assertIn(
            'class="{{ hovered ? \'hovered\' : \'\' }}"',
            RepairStage._normalize_duplicate_class_attributes(ambiguous),
        )
        self.assertIn(
            'class="{{ active ? \'selected\' : \'\' }}"',
            RepairStage._normalize_duplicate_class_attributes(ambiguous),
        )

    def test_identifier_diagnostic_and_prompts_are_generic(self):
        invalid = '''<template><stat-card /></template><script>
const san = require('san'); const DataTypes = san.DataTypes;
const stat-card = san.defineComponent({template: `<div>ok</div>`, initData() {return {};}});
module.exports = san.defineComponent({components: {'stat-card': stat-card}, initData() {return {};}});
</script><style></style>'''
        issues = ValidateStage().run(ValidateStageInput(
            generated_code=invalid, compile_check=False,
        )).validation_errors
        self.assertIn("invalid_inline_component_identifier", {issue["code"] for issue in issues})
        valid = invalid.replace("const stat-card =", "const StatCard =").replace(
            "'stat-card': stat-card", "'stat-card': StatCard"
        )
        valid_issues = ValidateStage().run(ValidateStageInput(
            generated_code=valid, compile_check=False,
        )).validation_errors
        self.assertNotIn("invalid_inline_component_identifier", {issue["code"] for issue in valid_issues})
        self.assertNotIn("invalid_inline_component_identifier", {
            issue["code"] for issue in ValidateStage().run(ValidateStageInput(
                generated_code=valid.replace(
                    "const StatCard =", "const api-client = 1; const StatCard ="
                ), compile_check=False,
            )).validation_errors
        })
        generation_prompt = _build_generation_prompt({}, "")
        repair_prompt = build_repair_prompt(RepairPromptInput(
            ssm={}, current_code=invalid,
            validation_errors=[{"code": "invalid_inline_component_identifier"}],
        ))
        for prompt in (generation_prompt, repair_prompt):
            self.assertIn("const StatCard = san.defineComponent", prompt)
            self.assertIn("'stat-card': StatCard", prompt)
            self.assertIn("$event", prompt)

    def test_frozen_monitoring_failure_has_identifier_diagnostic(self):
        failed = ROOT / (
            "data/experiments/snapshots/"
            "formal_30_v4_generalization_remaining_v1_monitoring_failed_20261027_205900/"
            "MonitoringDashboard_repaired_repaired_repaired.san"
        )
        candidate = ROOT / (
            "data/experiments/snapshots/"
            "formal_30_v4_remaining_monitoring_settings_v2_candidate_20261027_213000/"
            "candidate.san"
        )
        before = ValidateStage().run(ValidateStageInput(
            generated_code=failed.read_text(encoding="utf-8"), compile_check=False,
        ))
        after = ValidateStage().run(ValidateStageInput(
            generated_code=candidate.read_text(encoding="utf-8"), compile_check=False,
        ))
        before_issue = next(issue for issue in before.validation_errors
                            if issue["code"] == "invalid_inline_component_identifier")
        self.assertEqual(before_issue["message"].count(", ") + 1, 7)
        self.assertNotIn("invalid_inline_component_identifier", {
            issue["code"] for issue in after.validation_errors
        })

    def test_frozen_monitoring_replay_only_removes_safe_syntax_errors(self):
        failed = ROOT / (
            "data/experiments/snapshots/"
            "formal_30_v4_generalization_remaining_v1_monitoring_failed_20261027_205900/"
            "MonitoringDashboard_repaired_repaired_repaired.san"
        )
        original = failed.read_text(encoding="utf-8")
        normalized = RepairStage._normalize_duplicate_class_attributes(
            RepairStage._normalize_simple_template_syntax(original)
        )
        before_codes = {issue["code"] for issue in ValidateStage().run(ValidateStageInput(
            generated_code=original, compile_check=False,
        )).validation_errors}
        after_codes = {issue["code"] for issue in ValidateStage().run(ValidateStageInput(
            generated_code=normalized, compile_check=False,
        )).validation_errors}
        self.assertIn("invalid_san_for_alias_syntax", before_codes)
        self.assertIn("duplicate_class_attribute", before_codes)
        self.assertNotIn("invalid_san_for_alias_syntax", after_codes)
        self.assertNotIn("duplicate_class_attribute", after_codes)
        self.assertIn("invalid_inline_component_identifier", after_codes)
        self.assertIn("invalid_san_event_handler_syntax", after_codes)

    def test_watch_descriptor_object_is_rejected_but_function_listener_is_allowed(self):
        script_template = '''<template><div>ready</div></template><script>
const san = require('san'); const DataTypes = san.DataTypes;
module.exports = san.defineComponent({{
  dataTypes: {{}}, initData() {{return {{tasks: []}};}},
  inited() {{ this.watch('tasks', {listener}); }}
}});
</script><style></style>'''
        invalid = script_template.format(listener="{handler() {}, immediate: true}")
        valid = script_template.format(listener="nextTasks => this.data.set('seen', nextTasks.length)")
        invalid_codes = {issue["code"] for issue in ValidateStage().run(ValidateStageInput(
            generated_code=invalid, compile_check=False,
        )).validation_errors}
        valid_codes = {issue["code"] for issue in ValidateStage().run(ValidateStageInput(
            generated_code=valid, compile_check=False,
        )).validation_errors}
        self.assertIn("noncallable_san_watch_listener", invalid_codes)
        self.assertNotIn("noncallable_san_watch_listener", valid_codes)
        self.assertIn("FUNCTION listener", _build_generation_prompt({}, ""))
        self.assertIn("requires a callable", build_repair_prompt(RepairPromptInput(
            ssm={}, current_code=invalid,
            validation_errors=[{"code": "noncallable_san_watch_listener"}],
        )))

    def test_frozen_task_manager_runtime_failure_exposes_watch_descriptor(self):
        before = ROOT / (
            "data/experiments/snapshots/"
            "formal_30_v4_remaining_task_manager_bounded_candidate_20261027_200300/"
            "candidate.san"
        )
        after = ROOT / (
            "data/experiments/snapshots/"
            "formal_30_v4_remaining_task_manager_runtime_v2_candidate_20261027_202500/"
            "candidate.san"
        )
        before_codes = {issue["code"] for issue in ValidateStage().run(ValidateStageInput(
            generated_code=before.read_text(encoding="utf-8"), compile_check=False,
        )).validation_errors}
        after_codes = {issue["code"] for issue in ValidateStage().run(ValidateStageInput(
            generated_code=after.read_text(encoding="utf-8"), compile_check=False,
        )).validation_errors}
        self.assertIn("noncallable_san_watch_listener", before_codes)
        self.assertNotIn("noncallable_san_watch_listener", after_codes)

    def test_multi_argument_fire_is_rejected_without_flagging_object_payload(self):
        skeleton = '''<template><div>ready</div></template><script>
const san = require('san'); const DataTypes = san.DataTypes;
module.exports = san.defineComponent({{
  dataTypes: {{}}, initData() {{return {{}};}},
  update(value) {{ {statement} }}
}});
</script><style></style>'''
        invalid = skeleton.format(statement="this.fire('update', 'key', value);")
        valid = skeleton.format(statement="this.fire('update', {key: 'key', value});")
        invalid_codes = {issue["code"] for issue in ValidateStage().run(ValidateStageInput(
            generated_code=invalid, compile_check=False,
        )).validation_errors}
        valid_codes = {issue["code"] for issue in ValidateStage().run(ValidateStageInput(
            generated_code=valid, compile_check=False,
        )).validation_errors}
        self.assertIn("invalid_san_multi_argument_fire", invalid_codes)
        self.assertNotIn("invalid_san_multi_argument_fire", valid_codes)

        task_v1 = ROOT / (
            "data/experiments/snapshots/"
            "formal_30_v4_remaining_task_manager_bounded_candidate_20261027_200300/"
            "candidate.san"
        )
        task_v2 = ROOT / (
            "data/experiments/snapshots/"
            "formal_30_v4_remaining_task_manager_runtime_v2_candidate_20261027_202500/"
            "candidate.san"
        )
        v1_codes = {issue["code"] for issue in ValidateStage().run(ValidateStageInput(
            generated_code=task_v1.read_text(encoding="utf-8"), compile_check=False,
        )).validation_errors}
        v2_codes = {issue["code"] for issue in ValidateStage().run(ValidateStageInput(
            generated_code=task_v2.read_text(encoding="utf-8"), compile_check=False,
        )).validation_errors}
        self.assertIn("invalid_san_multi_argument_fire", v1_codes)
        self.assertNotIn("invalid_san_multi_argument_fire", v2_codes)


if __name__ == "__main__":
    unittest.main()
