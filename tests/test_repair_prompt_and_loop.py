import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from SSM.extractors.factory import SSMFactory
from local_server.api.evaluation_routes import _build_generation_prompt
from migration_pipeline.orchestrator import MigrationPipelineOrchestrator
from migration_pipeline.repair_client import RepairResult
from migration_pipeline.run_pipeline import compact_repair_history_entry
from migration_pipeline.stages.generate import GenerateStageInput, GenerateStageResult
from migration_pipeline.stages.repair import RepairStage, RepairStageInput
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.utils.repair_prompt import RepairPromptInput, build_repair_prompt


ROOT = Path(__file__).resolve().parents[1]


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


class FailIfCalledRepairClient:
    def repair(self, request_data):
        raise AssertionError("LLM repair should not run for a deterministic correction")


class StaticRepairClient:
    def __init__(self, code):
        self.code = code

    def repair(self, request_data):
        return RepairResult(
            source_file=request_data.source_file,
            ssm=request_data.ssm,
            code=self.code,
            saved_file_path=request_data.output_file_path or "repaired.san",
            provider="fake",
            model="fake-model",
            usage={"total_tokens": 10},
            raw_response={"ok": True},
        )


class RepairPromptAndLoopTests(unittest.TestCase):
    def test_repair_normalizer_unwraps_only_structural_directives(self):
        code = '''<template>
  <div s-if="{{ showSettings }}"></div>
  <div s-else-if="{= showFallback =}"></div>
  <li s-for="{{ item in items trackby item.id }}">{{item.name}}</li>
  <button disabled="{{ isDisabled }}">Save</button>
</template>
'''

        normalized = RepairStage._normalize_wrapped_san_directives(code)

        self.assertIn('s-if="showSettings"', normalized)
        self.assertIn('s-else-if="showFallback"', normalized)
        self.assertIn('s-for="item in items trackby item.id"', normalized)
        self.assertIn('disabled="{{ isDisabled }}"', normalized)

    def test_repair_stage_skips_llm_for_wrapped_san_directives(self):
        code = '''<template><div s-if="{{ visible }}"></div></template>
<script>module.exports = san.defineComponent({});</script>
<style></style>
'''
        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "Directive_repaired.san"
            result = RepairStage(repair_client=FailIfCalledRepairClient()).run(
                RepairStageInput(
                    ssm={},
                    generated_code=code,
                    output_file_path=str(output_path),
                    validation_errors=[
                        {"code": "invalid_san_directive_interpolation"},
                    ],
                    visual_eval_errors=[{"code": "dom_structure_similarity_low"}],
                )
            )

            self.assertEqual(result.provider, "deterministic")
            self.assertEqual(result.model, "san_directive_expression_normalizer")
            self.assertEqual(
                result.raw_response["normalization"],
                "unwrapped_san_directive_expression",
            )
            self.assertIn('s-if="visible"', result.repaired_code)

    def test_llm_result_records_wrapped_directive_postprocessing(self):
        current_code = '<template><div></div></template>'
        repaired_code = '<template><div s-if="{{ visible }}"></div></template>'
        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "Directive_repaired.san"
            result = RepairStage(repair_client=StaticRepairClient(repaired_code)).run(
                RepairStageInput(
                    ssm={},
                    generated_code=current_code,
                    output_file_path=str(output_path),
                    validation_errors=[{"code": "missing_prop_defaults"}],
                )
            )

            self.assertIn('s-if="visible"', result.repaired_code)
            self.assertEqual(
                result.raw_response["pipeline_postprocessing"],
                ["unwrapped_san_directive_expression"],
            )

    def test_repair_normalizer_moves_watch_registration_into_inited(self):
        code = '''<script>
module.exports = san.defineComponent({
  inited() {
    this.loadSettings();
  },
  watch() {
    this.watch('settings', (newVal) => {
      this.data.set('changed', Boolean(newVal));
    });
  },
  loadSettings() {}
});
</script>
'''

        normalized = RepairStage._normalize_misplaced_watch_registration(code)
        inited_body = normalized[
            normalized.index("inited()") : normalized.index("\n  loadSettings()")
        ]

        self.assertIn("this.watch('settings'", inited_body)
        self.assertNotIn("\n  watch() {", normalized)
        self.assertIn("this.loadSettings();", inited_body)

    def test_repair_normalizer_keeps_ordinary_watch_method(self):
        code = '''<script>
module.exports = san.defineComponent({
  inited() {},
  watch() {
    return 'business method';
  }
});
</script>
'''

        self.assertEqual(
            RepairStage._normalize_misplaced_watch_registration(code),
            code,
        )

    def test_repair_stage_skips_llm_for_misplaced_watch_registration(self):
        code = '''<script>
module.exports = san.defineComponent({
  inited() {},
  watch() {
    this.watch('settings', () => {});
  }
});
</script>
'''
        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "Watch_repaired.san"
            result = RepairStage(repair_client=FailIfCalledRepairClient()).run(
                RepairStageInput(
                    ssm={},
                    generated_code=code,
                    output_file_path=str(output_path),
                    validation_errors=[
                        {"code": "watch_registration_not_in_lifecycle"},
                    ],
                )
            )

            self.assertEqual(result.provider, "deterministic")
            self.assertEqual(result.model, "san_watch_lifecycle_normalizer")
            self.assertEqual(
                result.raw_response["normalization"],
                "moved_watch_registration_into_lifecycle",
            )
            self.assertNotIn("\n  watch() {", result.repaired_code)

    def test_llm_result_records_watch_lifecycle_postprocessing(self):
        current_code = '<script>module.exports = san.defineComponent({});</script>'
        repaired_code = '''<script>
module.exports = san.defineComponent({
  inited() {},
  watch() {
    this.watch('settings', () => {});
  }
});
</script>
'''
        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "Watch_repaired.san"
            result = RepairStage(repair_client=StaticRepairClient(repaired_code)).run(
                RepairStageInput(
                    ssm={},
                    generated_code=current_code,
                    output_file_path=str(output_path),
                    validation_errors=[{"code": "missing_prop_defaults"}],
                )
            )

            self.assertNotIn("\n  watch() {", result.repaired_code)
            self.assertEqual(
                result.raw_response["pipeline_postprocessing"],
                ["moved_watch_registration_into_lifecycle"],
            )

    def test_repair_normalizer_removes_redundant_loop_key_attributes(self):
        code = '''<template>
  <stat-card
    s-for="stat in statistics trackby stat.id"
    key="{{stat.id}}"
    trackby="stat.id"
    value="{{stat.value}}"
  />
</template>
'''

        normalized = RepairStage._normalize_redundant_s_for_attributes(code)

        self.assertIn('s-for="stat in statistics trackby stat.id"', normalized)
        self.assertNotIn('key="{{stat.id}}"', normalized)
        self.assertNotIn('trackby="stat.id"', normalized)
        self.assertIn('value="{{stat.value}}"', normalized)

    def test_repair_normalizer_keeps_key_until_inline_trackby_exists(self):
        code = '''<template>
  <li s-for="item in items" key="{{item.id}}">{{item.name}}</li>
</template>
'''

        normalized = RepairStage._normalize_redundant_s_for_attributes(code)

        self.assertEqual(normalized, code)

    def test_repair_normalizer_keeps_non_equivalent_loop_key(self):
        code = '''<template>
  <li
    s-for="item in items trackby item.id"
    key="{{item.version}}"
  >{{item.name}}</li>
</template>
'''

        normalized = RepairStage._normalize_redundant_s_for_attributes(code)

        self.assertEqual(normalized, code)

    def test_deterministic_repair_requires_single_static_error_and_clean_visual_eval(self):
        code = '''<template>
  <li s-for="item in items trackby item.id" key="{{item.id}}">{{item.name}}</li>
</template>
'''
        invalid_loop_error = {"code": "invalid_s_for_key_binding"}

        with_other_static_error = RepairStage._apply_deterministic_repairs(
            code,
            [invalid_loop_error, {"code": "missing_prop_defaults"}],
            [],
        )
        with_visual_error = RepairStage._apply_deterministic_repairs(
            code,
            [invalid_loop_error],
            [{"code": "dom_structure_similarity_low"}],
        )

        self.assertEqual(with_other_static_error, code)
        self.assertEqual(with_visual_error, code)

    def test_repair_stage_skips_llm_for_redundant_loop_key(self):
        code = '''<template>
  <stat-card s-for="stat in statistics trackby stat.id" key="{{stat.id}}" />
</template>
<script>module.exports = san.defineComponent({});</script>
<style></style>
'''
        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "AnalyticsDashboard_repaired.san"
            result = RepairStage(repair_client=FailIfCalledRepairClient()).run(
                RepairStageInput(
                    ssm={},
                    generated_code=code,
                    output_file_path=str(output_path),
                    validation_errors=[{"code": "invalid_s_for_key_binding"}],
                )
            )

            self.assertEqual(result.provider, "deterministic")
            self.assertEqual(result.model, "san_loop_binding_normalizer")
            self.assertNotIn('key="{{stat.id}}"', result.repaired_code)
            self.assertEqual(output_path.read_text(encoding="utf-8"), result.repaired_code)

    def test_repair_normalizer_unwraps_final_top_level_methods_option(self):
        code = '''<template><button on-click="save">Save</button></template>
<script>
const san = require('san');
module.exports = san.defineComponent({
  initData() { return {saved: false}; },
  methods: {
    save() {
      this.data.set('saved', true);
    },
    format(value) {
      return `${value}`;
    }
  }
});
</script>
<style></style>
'''

        normalized = RepairStage._normalize_vue_methods_wrapper(code)

        self.assertNotIn("methods: {", normalized)
        self.assertIn("  save() {", normalized)
        self.assertIn("  format(value) {", normalized)
        self.assertIn("module.exports = san.defineComponent({", normalized)
        self.assertIn("\n});\n</script>", normalized)

    def test_repair_stage_skips_llm_for_top_level_methods_wrapper(self):
        code = '''<template><button on-click="save">Save</button></template>
<script>
const san = require('san');
module.exports = san.defineComponent({
  initData() { return {saved: false}; },
  methods: {
    save() { this.data.set('saved', true); }
  }
});
</script>
<style></style>
'''
        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "Methods_repaired.san"
            result = RepairStage(repair_client=FailIfCalledRepairClient()).run(
                RepairStageInput(
                    ssm={},
                    generated_code=code,
                    output_file_path=str(output_path),
                    validation_errors=[
                        {"code": "vue_methods_wrapper"},
                        {"code": "nested_state_mutation"},
                    ],
                    visual_eval_errors=[{"code": "san_render_failed"}],
                )
            )

            self.assertEqual(result.provider, "deterministic")
            self.assertEqual(result.model, "san_methods_wrapper_normalizer")
            self.assertNotIn("methods: {", result.repaired_code)
            self.assertEqual(output_path.read_text(encoding="utf-8"), result.repaired_code)

    def test_deterministic_repair_combines_directive_and_methods_fixes(self):
        code = '''<template><div s-if="{{ visible }}"></div></template>
<script>
module.exports = san.defineComponent({
  methods: {
    show() { this.data.set('visible', true); }
  }
});
</script>
<style></style>
'''
        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "Combined_repaired.san"
            result = RepairStage(repair_client=FailIfCalledRepairClient()).run(
                RepairStageInput(
                    ssm={},
                    generated_code=code,
                    output_file_path=str(output_path),
                    validation_errors=[
                        {"code": "invalid_san_directive_interpolation"},
                        {"code": "vue_methods_wrapper"},
                    ],
                    visual_eval_errors=[{"code": "san_render_failed"}],
                )
            )

            self.assertEqual(result.model, "san_combined_structural_normalizer")
            self.assertEqual(
                result.raw_response["normalizations"],
                [
                    "unwrapped_san_directive_expression",
                    "unwrapped_final_top_level_methods_option",
                ],
            )
            self.assertIn('s-if="visible"', result.repaired_code)
            self.assertNotIn("methods: {", result.repaired_code)

    def test_monitoring_dashboard_frozen_initial_repairs_structural_errors_together(self):
        snapshot = (
            ROOT
            / "data/experiments/snapshots"
            / "formal_30_v4_deferred_monitoring_dashboard_post_watch_fix_failed_20261023_203528"
        )
        vue_file = snapshot / "source/MonitoringDashboard.vue"
        san_file = snapshot / "pipeline/complex/MonitoringDashboard.san"
        ssm = SSMFactory().build_from_file(str(vue_file))
        validation = ValidateStage().run(ValidateStageInput(
            generated_file_path=str(san_file),
            vue_file_path=str(vue_file),
            ssm=ssm,
        ))
        original = san_file.read_text(encoding="utf-8")

        normalized, repairs = RepairStage._deterministic_repair_plan(
            original,
            validation.validation_errors,
            [],
        )

        self.assertNotEqual(normalized, original)
        self.assertEqual(
            [item[1] for item in repairs],
            [
                "unwrapped_san_directive_expression",
                "unwrapped_final_top_level_methods_option",
            ],
        )

    def test_repair_normalizer_clones_state_array_before_local_mutation(self):
        code = '''<script>
module.exports = san.defineComponent({
  moveTask() {
    const tasks = this.data.get('tasks');
    const moved = tasks.splice(0, 1)[0];
    tasks.push(moved);
    this.data.set('tasks', tasks);
  }
});
</script>
'''

        normalized = RepairStage._normalize_mutated_state_array_aliases(code)

        self.assertIn("const tasks = [...this.data.get('tasks')];", normalized)
        self.assertIn("tasks.splice(0, 1)", normalized)
        self.assertIn("this.data.set('tasks', tasks)", normalized)

    def test_repair_normalizer_keeps_mutation_without_state_writeback(self):
        code = '''<script>
module.exports = san.defineComponent({
  inspectTasks() {
    const tasks = this.data.get('tasks');
    tasks.sort();
    return tasks;
  }
});
</script>
'''

        normalized = RepairStage._normalize_mutated_state_array_aliases(code)

        self.assertEqual(normalized, code)

    def test_repair_stage_skips_llm_for_only_nested_array_mutation(self):
        code = '''<script>
module.exports = san.defineComponent({
  moveTask() {
    const tasks = this.data.get('tasks') || [];
    tasks.splice(0, 1);
    this.data.set('tasks', tasks);
  }
});
</script>
'''
        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "Tasks_repaired.san"
            result = RepairStage(repair_client=FailIfCalledRepairClient()).run(
                RepairStageInput(
                    ssm={},
                    generated_code=code,
                    output_file_path=str(output_path),
                    validation_errors=[{"code": "nested_state_mutation"}],
                )
            )

            self.assertEqual(result.provider, "deterministic")
            self.assertEqual(result.model, "san_state_array_clone_normalizer")
            self.assertIn(
                "const tasks = [...(this.data.get('tasks') || [])];",
                result.repaired_code,
            )
            self.assertEqual(output_path.read_text(encoding="utf-8"), result.repaired_code)

    def test_llm_result_records_nested_array_postprocessing(self):
        current_code = '''<script>
module.exports = san.defineComponent({
  moveTask() { this.data.get('tasks').splice(0, 1); }
});
</script>
'''
        repaired_code = '''<script>
module.exports = san.defineComponent({
  moveTask() {
    const tasks = this.data.get('tasks');
    tasks.splice(0, 1);
    this.data.set('tasks', tasks);
  }
});
</script>
'''
        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "Tasks_repaired.san"
            result = RepairStage(repair_client=StaticRepairClient(repaired_code)).run(
                RepairStageInput(
                    ssm={},
                    generated_code=current_code,
                    output_file_path=str(output_path),
                    validation_errors=[
                        {"code": "nested_state_mutation"},
                        {"code": "missing_prop_defaults"},
                    ],
                )
            )

            self.assertEqual(result.provider, "fake")
            self.assertIn("const tasks = [...this.data.get('tasks')];", result.repaired_code)
            self.assertEqual(
                result.raw_response["pipeline_postprocessing"],
                ["cloned_state_array_before_local_mutation"],
            )

    def test_generation_prompt_requires_one_way_derived_attributes(self):
        prompt = _build_generation_prompt({"metadata": {"component_name": "Example"}})

        self.assertIn('disabled="{{ expression }}"', prompt)
        self.assertIn('disabled="{= expression =}"', prompt)
        self.assertIn("只用于源 Vue v-model 对应的原生", prompt)
        self.assertIn("普通自定义组件 props 必须使用 {{ ... }} 单向插值", prompt)
        self.assertIn('s-for="task in tasks trackby task.id"', prompt)
        self.assertIn("循环项和索引别名必须完整迁移", prompt)
        self.assertIn("禁止独立 key 属性", prompt)
        self.assertIn('禁止写成独立 trackby="task.id" 属性', prompt)
        self.assertIn('s-if="isOpen(module.id, openIds)"', prompt)
        self.assertIn(
            'visibleLessons(module.lessons, completedIds, unfinishedOnly)',
            prompt,
        )
        self.assertIn('select 的 :disabled="previewMode"', prompt)
        self.assertIn('!canConnect || previewMode', prompt)
        self.assertIn("never destructure this.data", prompt)
        self.assertIn("this.data.get('initialGroups')", prompt)
        self.assertIn("exactly one class attribute", prompt)
        self.assertIn("merge static and dynamic classes", prompt)
        self.assertIn("San s-if/s-else-if/s-for directive values use raw expressions", prompt)
        self.assertIn('s-if="{{showSettings}}"', prompt)
        self.assertIn('s-for="{{item in items}}"', prompt)
        self.assertIn("this.watch(...) directly inside San inited() or attached()", prompt)
        self.assertIn("uncalled top-level watch() method", prompt)
        self.assertIn("inline_definition.source_code", prompt)
        self.assertIn("never invent an undefined camelCase replacement", prompt)
        self.assertIn("business method is named initData", prompt)

    def test_prompt_makes_computed_defaults_and_binding_direction_explicit(self):
        prompt = build_repair_prompt(RepairPromptInput(
            ssm={
                "script": {
                    "options": {
                        "data": [
                            {
                                "name": "form",
                                "default_value_expression": "{age: 18}",
                                "default_value": {"age": 18},
                                "default_value_static": True,
                            },
                            {
                                "name": "enabled",
                                "default_value_expression": "['email', 'adult', 'name']",
                                "default_value": ["email", "adult", "name"],
                                "default_value_static": True,
                            },
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
        self.assertIn('disabled=\"{{ expression }}\"', prompt)
        self.assertIn('disabled=\"{= expression =}\"', prompt)
        self.assertIn("computed values must be read with this.data.get", prompt)
        self.assertIn("two-way binding only for native form assignable paths", prompt)
        self.assertIn(
            "Object-style Vue :class bindings must be converted to a San string expression",
            prompt,
        )
        self.assertIn('class="{{{ selected: condition }}}"', prompt)
        self.assertIn("普通自定义组件 props 必须保持单向", prompt)
        self.assertIn("插值必须完整闭合", prompt)
        self.assertIn("s-for 内联 trackby", prompt)
        self.assertIn('trackby="task.id" 属性', prompt)
        self.assertIn('s-for="phase, index in phases trackby phase.key"', prompt)
        self.assertIn("模板中使用的 index/idx/$index 是否已在对应 s-for 中显式声明", prompt)
        self.assertIn('"data_initial_values_to_preserve"', prompt)
        self.assertIn("['email', 'adult', 'name']", prompt)
        self.assertIn("computed_logic_to_preserve", prompt)
        self.assertIn("method_logic_to_preserve", prompt)
        self.assertIn("不得把响应式依赖只隐藏在方法内部", prompt)
        self.assertIn('rowClass(row, winnerId, leaderId)', prompt)
        self.assertIn('slotClass(device.id, hour, schedule)', prompt)
        self.assertIn('isSelected(row.id, selectedIds)', prompt)
        self.assertIn('s-if=\"isOpen(module.id, openIds)\"', prompt)
        self.assertIn(
            'visibleLessons(module.lessons, completedIds, unfinishedOnly)',
            prompt,
        )
        self.assertIn(
            "reactive values used by class/style/checked/selected/disabled/s-if/s-for/text",
            prompt,
        )
        self.assertIn("禁止直接修改 this.data.get(...) 或 computed 返回的对象/数组", prompt)
        self.assertIn("selectedAsset.decision = value", prompt)
        self.assertIn("nodes.push(node)", prompt)
        self.assertIn("this.data.set('assets', nextAssets)", prompt)
        self.assertIn("nested objects and arrays from this.data.get", prompt)
        self.assertIn("created 中的 prop 派生状态初始化放入 inited", prompt)
        self.assertIn("mounted 中的初始方法调用和副作用放入 attached", prompt)
        self.assertIn("beforeDestroy/destroyed 中的定时器或监听清理放入 disposed", prompt)
        self.assertIn("不能只保留空钩子", prompt)
        self.assertIn("this.watch('field', handler)", prompt)
        self.assertIn("lifecycle behavior preserved in inited/attached/disposed", prompt)
        self.assertIn("必须保留 Vue template 的 DOM 子节点顺序", prompt)
        self.assertIn("input 或 checkbox 与相邻文字、百分号、按钮的先后关系", prompt)
        self.assertIn("DOM child order preserved exactly", prompt)
        self.assertIn(
            "critical value/checked/selected/disabled expressions remain attached to the same source element",
            prompt,
        )

    def test_repair_prompt_includes_inline_components_and_reserved_method_collision(self):
        prompt = build_repair_prompt(RepairPromptInput(
            ssm={
                "script": {
                    "options": {
                        "components": [{
                            "registered_name": "status-chip",
                            "source_name": "StatusChip",
                            "definition_location": "inline",
                            "inline_definition": {
                                "source_name": "StatusChip",
                                "source_code": "{template: '<strong>{{label}}</strong>'}",
                            },
                        }],
                        "methods": [{"name": "initData", "body_full": "{}"}],
                    }
                }
            },
            current_code="<template></template>",
        ))

        self.assertIn("components_to_define_and_register", prompt)
        self.assertIn("reserved_san_method_collisions", prompt)
        self.assertIn("StatusChip", prompt)
        self.assertIn("inline_definition.source_code", prompt)
        self.assertIn("mounted calls in attached()", prompt)
        self.assertIn("every loop item/index alias referenced by a loop element is declared in s-for", prompt)
        self.assertIn("never destructure this.data", prompt)
        self.assertIn("this.data.get('initialGroups')", prompt)
        self.assertIn("exactly one class attribute", prompt)
        self.assertIn("merge static and dynamic classes", prompt)
        self.assertIn("San s-if/s-else-if/s-for directive values use raw expressions", prompt)
        self.assertIn('s-if="{{showSettings}}"', prompt)
        self.assertIn('s-for="{{item in items}}"', prompt)
        self.assertIn("directly inside San inited() or attached()", prompt)
        self.assertIn("uncalled top-level watch() method", prompt)

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
