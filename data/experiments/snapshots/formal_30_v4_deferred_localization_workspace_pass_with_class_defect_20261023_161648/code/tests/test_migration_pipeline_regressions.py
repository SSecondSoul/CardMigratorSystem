import os
import subprocess
import sys
import unittest
from pathlib import Path

from SSM.extractors.factory import SSMFactory
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.stages.visual_eval import VisualEvalStage, VisualEvalStageInput
from migration_pipeline.utils.san_render import render_san_component
from migration_pipeline.utils.vue_render import render_vue_component


ROOT = Path(__file__).resolve().parents[1]
VUE = ROOT / "data/datasets/components/02_medium/KanbanColumnBoard/vue/KanbanColumnBoard.vue"
REFERENCE_SAN = ROOT / "data/datasets/components/02_medium/KanbanColumnBoard/san/KanbanColumnBoard.san"
FORM_RULE_VUE = ROOT / "data/datasets/components/02_medium/FormRulePlayground/vue/FormRulePlayground.vue"
FORM_RULE_SAN = ROOT / "data/datasets/components/02_medium/FormRulePlayground/san/FormRulePlayground.san"
REFERENCE_CASES = (
    "KanbanColumnBoard",
    "DataPaginationTable",
    "FormRulePlayground",
)


class MigrationPipelineRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ssm = SSMFactory().build_from_file(str(VUE))

    def test_kanban_reference_render_is_equivalent(self):
        result = VisualEvalStage().run(VisualEvalStageInput(
            vue_file_path=str(VUE),
            generated_file_path=str(REFERENCE_SAN),
        ))

        self.assertTrue(result.visual_eval_passed, result.visual_eval_errors)
        self.assertEqual(result.visual_eval_errors, [])
        self.assertEqual(result.visual_eval_warnings, [])
        self.assertEqual(result.vue_render_result["dom_snapshot"]["node_count"], 19)
        self.assertEqual(result.san_render_result["dom_snapshot"]["node_count"], 19)
        self.assertEqual(result.structure_similarity, 1.0)
        self.assertEqual(result.tag_sequence_similarity, 1.0)
        self.assertEqual(result.text_similarity, 1.0)

    def test_validator_detects_missing_prop_defaults_and_event_arguments(self):
        broken_code = """<template>
<section class="kanban-column-board">
    <button on-click="move">左移</button>
    <button on-click="move">右移</button>
    <button on-click="select">任务</button>
</section>
</template>
<script>
const san = require('san');
const DataTypes = san.DataTypes;
module.exports = san.defineComponent({
    name: 'KanbanColumnBoard',
    dataTypes: {
        initialTasks: DataTypes.array,
        columns: DataTypes.array
    },
    initData() {
        return {tasks: [], selectedId: null, draft: '', nextId: 10};
    },
    emitEvent(name, payload) {
        this.fire(name, payload);
    }
});
</script>
<style>.kanban-column-board{display:block}</style>
"""
        result = ValidateStage().run(ValidateStageInput(
            generated_code=broken_code,
            ssm=self.ssm,
        ))
        error_codes = {issue["code"] for issue in result.validation_errors}

        self.assertFalse(result.validation_passed)
        self.assertIn("missing_prop_defaults", error_codes)
        self.assertIn("event_arguments_not_landed", error_codes)

    def test_reference_satisfies_new_contract_checks(self):
        result = ValidateStage().run(ValidateStageInput(
            generated_file_path=str(REFERENCE_SAN),
            ssm=self.ssm,
        ))
        error_codes = {issue["code"] for issue in result.validation_errors}

        self.assertTrue(result.validation_passed, result.validation_errors)
        self.assertNotIn("missing_prop_defaults", error_codes)
        self.assertNotIn("event_arguments_not_landed", error_codes)

    def test_medium_reference_components_pass_static_and_visual_evaluation(self):
        for component_name in REFERENCE_CASES:
            with self.subTest(component=component_name):
                component_dir = ROOT / "data/datasets/components/02_medium" / component_name
                vue_file = component_dir / "vue" / f"{component_name}.vue"
                san_file = component_dir / "san" / f"{component_name}.san"
                ssm = SSMFactory().build_from_file(str(vue_file))

                validation = ValidateStage().run(ValidateStageInput(
                    generated_file_path=str(san_file),
                    ssm=ssm,
                ))
                visual = VisualEvalStage().run(VisualEvalStageInput(
                    vue_file_path=str(vue_file),
                    generated_file_path=str(san_file),
                ))

                self.assertTrue(validation.validation_passed, validation.validation_errors)
                self.assertTrue(visual.visual_eval_passed, {
                    "errors": visual.visual_eval_errors,
                    "warnings": visual.visual_eval_warnings,
                })
                self.assertEqual(visual.visual_eval_errors, [])
                self.assertEqual(visual.visual_eval_warnings, [])
                self.assertEqual(visual.structure_similarity, 1.0)
                self.assertEqual(visual.tag_sequence_similarity, 1.0)
                self.assertEqual(visual.text_similarity, 1.0)

    def test_validator_rejects_dispatch_as_vue_emit_replacement(self):
        dispatch_code = REFERENCE_SAN.read_text(encoding="utf-8").replace(
            "this.fire(name, payload)",
            "this.dispatch(name, payload)",
        )
        result = ValidateStage().run(ValidateStageInput(
            generated_code=dispatch_code,
            ssm=self.ssm,
        ))
        error_codes = {issue["code"] for issue in result.validation_errors}

        self.assertFalse(result.validation_passed)
        self.assertIn("custom_event_not_fire", error_codes)

    def test_validator_allows_private_instance_timer_fields(self):
        code = self._minimal_san_component(
            '<div>{{ elapsed }}</div>',
            """
    attached() {
        this._timer = setInterval(() => {
            this.data.set('elapsed', this.data.get('elapsed') + 1);
        }, 60000);
    },
    disposed() {
        if (this._timer) {
            clearInterval(this._timer);
            this._timer = null;
        }
    },
""",
        )

        result = ValidateStage().run(ValidateStageInput(
            generated_code=code,
            compile_check=False,
        ))

        self.assertNotIn(
            "vue_this_state",
            {issue["code"] for issue in result.validation_errors},
        )

    def test_validator_allows_nonreactive_instance_timer_fields(self):
        code = self._minimal_san_component(
            '<div>{{ elapsed }}</div>',
            """
    attached() {
        this.refreshInterval = setInterval(() => {
            this.data.set('elapsed', this.data.get('elapsed') + 1);
        }, 60000);
    },
    disposed() {
        clearInterval(this.refreshInterval);
        this.refreshInterval = null;
    },
""",
        )

        result = ValidateStage().run(ValidateStageInput(
            generated_code=code,
            compile_check=False,
        ))

        self.assertNotIn(
            "vue_this_state",
            {issue["code"] for issue in result.validation_errors},
        )

    def test_validator_rejects_destructuring_the_san_data_store(self):
        code = self._minimal_san_component(
            '<div>{{ groups.length }}</div>',
            """
    inited() {
        const { initialGroups, availableFields } = this.data;
        this.data.set('groups', Array.isArray(initialGroups) ? initialGroups : []);
        this.data.set('availableFields', availableFields || []);
    },
""",
        )

        result = ValidateStage().run(ValidateStageInput(
            generated_code=code,
            compile_check=False,
        ))

        self.assertIn(
            "invalid_san_data_destructuring",
            {issue["code"] for issue in result.validation_errors},
        )

    def test_form_defaults_and_critical_dom_attributes_cannot_false_pass(self):
        ssm = SSMFactory().build_from_file(str(FORM_RULE_VUE))
        broken_code = FORM_RULE_SAN.read_text(encoding="utf-8").replace(
            '"age": 18',
            '"age": ""',
        ).replace(
            '"adult",\n        "name"',
            '"adult"',
        )

        validation = ValidateStage().run(ValidateStageInput(
            generated_code=broken_code,
            ssm=ssm,
        ))
        visual = VisualEvalStage().run(VisualEvalStageInput(
            vue_file_path=str(FORM_RULE_VUE),
            generated_code=broken_code,
        ))

        validation_codes = {issue["code"] for issue in validation.validation_errors}
        visual_codes = {issue["code"] for issue in visual.visual_eval_errors}
        self.assertFalse(validation.validation_passed)
        self.assertIn("data_initial_value_mismatch", validation_codes)
        self.assertFalse(visual.visual_eval_passed)
        self.assertIn("dom_critical_attribute_mismatch", visual_codes)

    def test_validator_rejects_two_way_binding_for_derived_attributes(self):
        reference = (ROOT / "data/datasets/components/02_medium/DataPaginationTable/san/DataPaginationTable.san").read_text(encoding="utf-8")
        broken_code = reference.replace(
            'disabled="{{ page === 1 }}"',
            'disabled="{= page === 1 =}"',
        )
        result = ValidateStage().run(ValidateStageInput(generated_code=broken_code))
        error_codes = {issue["code"] for issue in result.validation_errors}

        self.assertFalse(result.validation_passed)
        self.assertIn("invalid_dynamic_attribute_binding", error_codes)

    def test_validator_rejects_two_way_binding_on_custom_component_props(self):
        code = self._minimal_san_component(
            '<stat-card value="{= stat.value =}" loading="{= isLoading =}"/>',
            "",
        )

        result = ValidateStage().run(ValidateStageInput(
            generated_code=code,
            compile_check=False,
        ))

        self.assertIn(
            "invalid_component_prop_two_way_binding",
            {issue["code"] for issue in result.validation_errors},
        )

    def test_validator_allows_assignable_value_two_way_binding(self):
        reference = (ROOT / "data/datasets/components/02_medium/DataPaginationTable/san/DataPaginationTable.san").read_text(encoding="utf-8")
        broken_code = reference.replace(
            'value="{{ pageSize }}"',
            'value="{= pageSize =}"',
        )
        result = ValidateStage().run(ValidateStageInput(generated_code=broken_code))
        error_codes = {issue["code"] for issue in result.validation_errors}

        self.assertNotIn("invalid_dynamic_attribute_binding", error_codes)

    def test_validator_rejects_separate_key_attribute_on_s_for(self):
        reference = (ROOT / "data/datasets/components/02_medium/DataPaginationTable/san/DataPaginationTable.san").read_text(encoding="utf-8")
        broken_code = reference.replace(
            's-for="row in pageRows trackby row.id"',
            's-for="row in pageRows" key="{= row.id =}"',
        )
        result = ValidateStage().run(ValidateStageInput(generated_code=broken_code))
        error_codes = {issue["code"] for issue in result.validation_errors}

        self.assertFalse(result.validation_passed)
        self.assertIn("invalid_s_for_key_binding", error_codes)

    def test_validator_rejects_separate_trackby_attribute_on_s_for(self):
        reference = (ROOT / "data/datasets/components/02_medium/DataPaginationTable/san/DataPaginationTable.san").read_text(encoding="utf-8")
        broken_code = reference.replace(
            's-for="row in pageRows trackby row.id"',
            's-for="row in pageRows" trackby="row.id"',
        )
        result = ValidateStage().run(ValidateStageInput(generated_code=broken_code))
        error_codes = {issue["code"] for issue in result.validation_errors}

        self.assertFalse(result.validation_passed)
        self.assertIn("invalid_s_for_key_binding", error_codes)

    def test_validator_does_not_treat_key_suffix_in_expression_as_key_attribute(self):
        code = self._minimal_san_component(
            (
                '<button s-for="field in fields trackby field.key" '
                'class="{{ field.key === sourceKey ? \'selected\' : \'\' }}">'
                '{{ field.key }}'
                '</button>'
                '<button s-for="field in targets trackby field.key" '
                'class="{{ field.key === targetKey ? \'selected\' : \'\' }}">'
                '{{ field.key }}'
                '</button>'
            ),
            "",
        )

        result = ValidateStage().run(ValidateStageInput(
            generated_code=code,
            compile_check=False,
        ))

        self.assertNotIn(
            "invalid_s_for_key_binding",
            {issue["code"] for issue in result.validation_errors},
        )

    def test_validator_rejects_unbound_loop_index_and_allows_declared_alias(self):
        broken_code = self._minimal_san_component(
            (
                '<span s-for="phase in phases trackby phase.key" '
                'class="{{ index <= phaseIndex ? \'reached\' : \'\' }}"></span>'
            ),
            "",
        )
        fixed_code = broken_code.replace(
            's-for="phase in phases trackby phase.key"',
            's-for="phase, index in phases trackby phase.key"',
        )

        broken = ValidateStage().run(ValidateStageInput(
            generated_code=broken_code,
            compile_check=False,
        ))
        fixed = ValidateStage().run(ValidateStageInput(
            generated_code=fixed_code,
            compile_check=False,
        ))

        broken_codes = {issue["code"] for issue in broken.validation_errors}
        fixed_codes = {issue["code"] for issue in fixed.validation_errors}
        self.assertIn("unbound_loop_scope_variable", broken_codes)
        self.assertNotIn("unbound_loop_scope_variable", fixed_codes)

    def test_validator_detects_delivery_phase_loop_scope_regression(self):
        vue_file = ROOT / "data/datasets/components/01_simple/DeliveryPhaseCard/vue/DeliveryPhaseCard.vue"
        broken_file = ROOT / "data/experiments/snapshots/formal_30_v1_results_20261015_161053/pipeline/simple/DeliveryPhaseCard_repaired.san"
        fixed_file = ROOT / "data/experiments/pipeline/batches/formal_30_v2/simple/DeliveryPhaseCard_repaired.san"

        broken = ValidateStage().run(ValidateStageInput(
            generated_file_path=str(broken_file),
            source_file=str(vue_file),
            compile_check=False,
        ))
        fixed = ValidateStage().run(ValidateStageInput(
            generated_file_path=str(fixed_file),
            source_file=str(vue_file),
            compile_check=False,
        ))

        self.assertIn(
            "unbound_loop_scope_variable",
            {issue["code"] for issue in broken.validation_errors},
        )
        self.assertNotIn(
            "unbound_loop_scope_variable",
            {issue["code"] for issue in fixed.validation_errors},
        )

    def test_validator_rejects_unbalanced_template_interpolation(self):
        reference = (ROOT / "data/datasets/components/02_medium/DataPaginationTable/san/DataPaginationTable.san").read_text(encoding="utf-8")
        broken_code = reference.replace(
            'class="{{ row.id === selectedId ? \'selected\' : \'\' }}"',
            'class="{{ row.id === selectedId ? \'selected\' : \'\' }"',
        )
        result = ValidateStage().run(ValidateStageInput(generated_code=broken_code))
        error_codes = {issue["code"] for issue in result.validation_errors}

        self.assertFalse(result.validation_passed)
        self.assertIn("unbalanced_template_interpolation", error_codes)

    def test_validator_rejects_hidden_reactive_dependencies_in_class_method(self):
        code = self._minimal_san_component(
            '<tr class="{{ rowClass(row) }}"><td>{{ row.name }}</td></tr>',
            """
    rowClass(row) {
        const winnerId = this.data.get('winnerId');
        const leaderId = this.data.get("leaderId");
        return row.id === winnerId ? 'winner' : row.id === leaderId ? 'leader' : '';
    }
""",
        )

        result = ValidateStage().run(ValidateStageInput(
            generated_code=code,
            compile_check=False,
        ))
        hidden_issues = [
            issue for issue in result.validation_errors
            if issue["code"] == "hidden_template_reactive_dependency"
        ]

        self.assertEqual(len(hidden_issues), 1)
        self.assertIn("rowClass", hidden_issues[0]["message"])
        self.assertIn("leaderId", hidden_issues[0]["message"])
        self.assertIn("winnerId", hidden_issues[0]["message"])

    def test_validator_rejects_hidden_schedule_dependency_in_class_method(self):
        code = self._minimal_san_component(
            '<button class="{{ slotClass(device.id, hour) }}">时段</button>',
            """
    slotClass(deviceId, hour) {
        const schedule = this.data.get('schedule');
        return schedule[deviceId] === hour ? 'scheduled' : '';
    }
""",
        )

        result = ValidateStage().run(ValidateStageInput(
            generated_code=code,
            compile_check=False,
        ))
        hidden_issues = [
            issue for issue in result.validation_errors
            if issue["code"] == "hidden_template_reactive_dependency"
        ]

        self.assertEqual(len(hidden_issues), 1)
        self.assertIn("schedule", hidden_issues[0]["message"])

    def test_validator_allows_explicit_reactive_method_arguments_and_event_handlers(self):
        code = self._minimal_san_component(
            (
                '<button class="{{ slotClass(device.id, hour, schedule) }}" '
                'on-click="selectSlot(device.id, hour)">时段</button>'
            ),
            """
    slotClass(deviceId, hour, schedule) {
        return schedule[deviceId] === hour ? 'scheduled' : '';
    },
    selectSlot(deviceId, hour) {
        const selectedIds = this.data.get('selectedIds');
        this.data.set('selectedIds', selectedIds.concat(deviceId + ':' + hour));
    }
""",
        )

        result = ValidateStage().run(ValidateStageInput(
            generated_code=code,
            compile_check=False,
        ))
        error_codes = {issue["code"] for issue in result.validation_errors}

        self.assertNotIn("hidden_template_reactive_dependency", error_codes)

    def test_validator_rejects_hidden_dependencies_in_render_directives_and_text(self):
        code = self._minimal_san_component(
            (
                '<div s-if="isOpen(module.id)">'
                '<span>{{ isOpen(module.id) ? "open" : "closed" }}</span>'
                '<label s-for="lesson in visibleLessons(module.lessons) trackby lesson.id">'
                '{{ lesson.title }}'
                '</label>'
                '</div>'
            ),
            """
    isOpen(id) {
        const openIds = this.data.get('openIds');
        return openIds.indexOf(id) >= 0;
    },
    visibleLessons(lessons) {
        const completedIds = this.data.get('completedIds');
        const unfinishedOnly = this.data.get('unfinishedOnly');
        return unfinishedOnly
            ? lessons.filter(item => completedIds.indexOf(item.id) < 0)
            : lessons;
    }
""",
        )

        result = ValidateStage().run(ValidateStageInput(
            generated_code=code,
            compile_check=False,
        ))
        hidden_messages = [
            issue["message"]
            for issue in result.validation_errors
            if issue["code"] == "hidden_template_reactive_dependency"
        ]

        self.assertTrue(any("isOpen" in message and "openIds" in message for message in hidden_messages))
        self.assertTrue(any(
            "visibleLessons" in message
            and "completedIds" in message
            and "unfinishedOnly" in message
            for message in hidden_messages
        ))

    def test_validator_rejects_nested_mutation_of_computed_state_objects(self):
        code = self._minimal_san_component(
            '<button on-click="setDecision(\'approved\')">批准</button>',
            """
    setDecision(decision) {
        const selectedAsset = this.data.get('selectedAsset');
        selectedAsset.decision = decision;
        const notes = selectedAsset.notes || [];
        notes.push({id: 1, resolved: false});
        const note = notes.find(item => item.id === 1);
        note.resolved = true;
    }
""",
        )

        result = ValidateStage().run(ValidateStageInput(
            generated_code=code,
            compile_check=False,
        ))
        mutation_issues = [
            issue for issue in result.validation_errors
            if issue["code"] == "nested_state_mutation"
        ]

        self.assertEqual(len(mutation_issues), 1)
        self.assertIn("setDecision", mutation_issues[0]["message"])
        self.assertIn("selectedAsset", mutation_issues[0]["message"])

    def test_validator_rejects_array_and_descendant_mutation_from_data_get(self):
        code = self._minimal_san_component(
            '<button on-click="updateTopology">更新</button>',
            """
    updateTopology() {
        const nodes = this.data.get('nodes');
        const node = nodes[0];
        node.status = 'offline';
        nodes.push({id: 2, status: 'online'});
        const edges = this.data.get('edges');
        edges.splice(0, 1);
        this.data.get('eventLog').unshift({message: 'updated'});
    }
""",
        )

        result = ValidateStage().run(ValidateStageInput(
            generated_code=code,
            compile_check=False,
        ))
        mutation_issues = [
            issue for issue in result.validation_errors
            if issue["code"] == "nested_state_mutation"
        ]

        self.assertEqual(len(mutation_issues), 1)
        self.assertIn("edges", mutation_issues[0]["message"])
        self.assertIn("eventLog", mutation_issues[0]["message"])
        self.assertIn("nodes", mutation_issues[0]["message"])

    def test_validator_allows_immutable_state_replacement_and_local_mutation(self):
        code = self._minimal_san_component(
            '<button on-click="setDecision(\'approved\')">批准</button>',
            """
    setDecision(decision) {
        const assets = this.data.get('assets') || [];
        const nextAssets = assets.map(asset =>
            asset.id === 1 ? Object.assign({}, asset, {decision}) : asset
        );
        const audit = [];
        audit.push(decision);
        this.data.set('assets', nextAssets);
    }
""",
        )

        result = ValidateStage().run(ValidateStageInput(
            generated_code=code,
            compile_check=False,
        ))
        error_codes = {issue["code"] for issue in result.validation_errors}

        self.assertNotIn("nested_state_mutation", error_codes)

    def test_validator_allows_mutating_array_literal_with_spread_before_set(self):
        code = self._minimal_san_component(
            '<button on-click="addEvent">添加</button>',
            """
    addEvent() {
        const history = this.data.get('eventHistory');
        const nextHistory = [{id: 2}, ...history];
        if (nextHistory.length > 50) {
            nextHistory.pop();
        }
        this.data.set('eventHistory', nextHistory);
    }
""",
        )

        result = ValidateStage().run(ValidateStageInput(
            generated_code=code,
            compile_check=False,
        ))

        self.assertNotIn(
            "nested_state_mutation",
            {issue["code"] for issue in result.validation_errors},
        )

    def test_validator_allows_mutating_object_literal_with_spread_before_set(self):
        code = self._minimal_san_component(
            '<button on-click="clearCache">清理</button>',
            """
    clearCache() {
        const cache = this.data.get('dataCache');
        const nextCache = {...cache};
        nextCache.current = null;
        this.data.set('dataCache', nextCache);
    }
""",
        )

        result = ValidateStage().run(ValidateStageInput(
            generated_code=code,
            compile_check=False,
        ))

        self.assertNotIn(
            "nested_state_mutation",
            {issue["code"] for issue in result.validation_errors},
        )

    def test_vue_mounted_and_san_attached_share_initial_render_phase(self):
        vue_source = """<template><button :disabled="loading">{{ loading ? 'loading' : 'ready' }}</button></template>
<script>
module.exports = {
    data() { return {loading: false}; },
    mounted() { this.loading = true; }
};
</script>
<style></style>
"""
        san_source = """<template><button disabled="{{loading}}">{{loading ? 'loading' : 'ready'}}</button></template>
<script>
const san = require('san');
module.exports = san.defineComponent({
    initData() { return {loading: false}; },
    attached() { this.data.set('loading', true); }
});
</script>
<style></style>
"""

        vue = render_vue_component(vue_source=vue_source)
        san = render_san_component(san_source=san_source)

        self.assertTrue(vue.passed, vue.diagnostics)
        self.assertTrue(san.passed, san.diagnostics)
        self.assertEqual(vue.dom_snapshot["text_content"], "loading")
        self.assertEqual(vue.dom_snapshot, san.dom_snapshot)

    def test_self_closing_component_loops_expand_in_both_renderers(self):
        vue_source = """<template><section><item-card v-for="item in items" :value="item.value" /></section></template>
<script>module.exports = {data() { return {items: [{id: 1, value: 'A'}, {id: 2, value: 'B'}]}; }};</script>
<style></style>
"""
        san_source = """<template><section><item-card s-for="item in items trackby item.id" value="{{item.value}}" /></section></template>
<script>const san = require('san'); module.exports = san.defineComponent({initData() { return {items: [{id: 1, value: 'A'}, {id: 2, value: 'B'}]}; }});</script>
<style></style>
"""

        vue = render_vue_component(vue_source=vue_source)
        san = render_san_component(san_source=san_source)

        self.assertEqual(vue.dom_snapshot["node_count"], 3)
        self.assertEqual(vue.dom_snapshot, san.dom_snapshot)

    def test_vue_renderer_merges_static_and_dynamic_classes(self):
        vue_source = """<template><button class="grant-cell" :class="{ granted: enabled }">Allow</button></template>
<script>module.exports = {data() { return {enabled: true}; }};</script>
<style></style>
"""

        result = render_vue_component(vue_source=vue_source)

        self.assertTrue(result.passed, result.diagnostics)
        self.assertEqual(
            result.dom_snapshot["tree"]["attrs"]["class"],
            "grant-cell granted",
        )

    def test_critical_form_attributes_ignore_custom_component_props(self):
        stage = VisualEvalStage()
        custom_issues = []
        stage._collect_dom_compare_issues(
            {
                "structure_similarity": 1.0,
                "text_similarity": 1.0,
                "changed_nodes": [{
                    "path": "/stat-card[0]",
                    "reason": "attrs_changed",
                    "vue_node": {"tag": "stat-card", "attrs": {"value": "1"}},
                    "san_node": {"tag": "stat-card", "attrs": {"value": "2"}},
                }],
            },
            VisualEvalStageInput(),
            custom_issues,
        )
        native_issues = []
        stage._collect_dom_compare_issues(
            {
                "structure_similarity": 1.0,
                "text_similarity": 1.0,
                "changed_nodes": [{
                    "path": "/input[0]",
                    "reason": "attrs_changed",
                    "vue_node": {"tag": "input", "attrs": {"value": "1"}},
                    "san_node": {"tag": "input", "attrs": {"value": "2"}},
                }],
            },
            VisualEvalStageInput(),
            native_issues,
        )

        self.assertNotIn("dom_critical_attribute_mismatch", {issue.code for issue in custom_issues})
        self.assertIn("dom_critical_attribute_mismatch", {issue.code for issue in native_issues})

    def test_validator_rejects_lifecycle_hooks_without_source_behavior(self):
        ssm = {
            "script": {
                "options": {
                    "lifecycle_hooks": [
                        {
                            "vue_hook": "created",
                            "san_hook": "inited",
                            "body": "{ this.setValue('crop', Object.assign({}, this.initialCrop)); }",
                        },
                        {
                            "vue_hook": "mounted",
                            "san_hook": "attached",
                            "body": "{ this.runSimulation(); }",
                        },
                        {
                            "vue_hook": "beforeDestroy",
                            "body": "{ clearTimeout(this.simulationTimer); }",
                        },
                    ],
                    "watch": [{"expression": "locked"}],
                }
            }
        }
        code = self._minimal_san_component(
            '<button on-click="runSimulation">运行</button>',
            """
    inited() {},
    attached() {},
    disposed() {},
    watch: {
        locked() {}
    },
    runSimulation() {}
""",
        )

        result = ValidateStage().run(ValidateStageInput(
            generated_code=code,
            ssm=ssm,
            compile_check=False,
        ))
        error_codes = {issue["code"] for issue in result.validation_errors}

        self.assertIn("lifecycle_behavior_not_landed", error_codes)
        self.assertIn("missing_watch_migration", error_codes)
        self.assertIn("vue_watch_option", error_codes)

    def test_validator_allows_lifecycle_behavior_and_registered_watch(self):
        ssm = {
            "script": {
                "options": {
                    "lifecycle_hooks": [
                        {
                            "vue_hook": "created",
                            "san_hook": "inited",
                            "body": "{ this.setValue('crop', Object.assign({}, this.initialCrop)); }",
                        },
                        {
                            "vue_hook": "mounted",
                            "san_hook": "attached",
                            "body": "{ this.runSimulation(); }",
                        },
                        {
                            "vue_hook": "beforeDestroy",
                            "body": "{ clearTimeout(this.simulationTimer); }",
                        },
                    ],
                    "watch": [{"expression": "locked"}],
                }
            }
        }
        code = self._minimal_san_component(
            '<button on-click="runSimulation">运行</button>',
            """
    inited() {
        const initialCrop = this.data.get('initialCrop');
        this.data.set('crop', Object.assign({}, initialCrop));
        this.watch('locked', () => {});
    },
    attached() {
        this.runSimulation();
    },
    disposed() {
        clearTimeout(this.data.get('simulationTimer'));
    },
    runSimulation() {}
""",
        )

        result = ValidateStage().run(ValidateStageInput(
            generated_code=code,
            ssm=ssm,
            compile_check=False,
        ))
        error_codes = {issue["code"] for issue in result.validation_errors}

        self.assertNotIn("missing_lifecycle_mapping", error_codes)
        self.assertNotIn("lifecycle_behavior_not_landed", error_codes)
        self.assertNotIn("missing_watch_migration", error_codes)
        self.assertNotIn("vue_watch_option", error_codes)

    def test_validator_requires_prop_dependent_data_initialization_in_inited(self):
        ssm = {
            "script": {
                "options": {
                    "props": [{"name": "initialAssumptions", "type": "Object"}],
                    "data": [{
                        "name": "assumptions",
                        "default_value_expression": "Object.assign({}, this.initialAssumptions)",
                        "default_value_static": False,
                    }],
                }
            }
        }
        broken_code = self._minimal_san_component('<div></div>', "")
        fixed_code = self._minimal_san_component(
            '<div></div>',
            """
    inited() {
        const initialAssumptions = this.data.get('initialAssumptions');
        this.data.set('assumptions', Object.assign({}, initialAssumptions));
    }
""",
        )

        broken = ValidateStage().run(ValidateStageInput(
            generated_code=broken_code,
            ssm=ssm,
            compile_check=False,
        ))
        fixed = ValidateStage().run(ValidateStageInput(
            generated_code=fixed_code,
            ssm=ssm,
            compile_check=False,
        ))

        self.assertIn(
            "missing_prop_dependent_initialization",
            {issue["code"] for issue in broken.validation_errors},
        )
        self.assertNotIn(
            "missing_prop_dependent_initialization",
            {issue["code"] for issue in fixed.validation_errors},
        )

    def test_validator_rejects_dom_child_order_drift_in_formal_samples(self):
        cases = (
            (
                "GradebookMatrix",
                ROOT / "data/datasets/components/03_complex/GradebookMatrix/vue/GradebookMatrix.vue",
                ROOT / "data/experiments/snapshots/formal_30_v1_results_20261015_161053/pipeline/complex/GradebookMatrix_repaired_repaired_repaired.san",
                ROOT / "data/experiments/pipeline/batches/formal_30_v2/complex/GradebookMatrix_repaired.san",
            ),
            (
                "SupportTicketConsole",
                ROOT / "data/datasets/components/03_complex/SupportTicketConsole/vue/SupportTicketConsole.vue",
                ROOT / "data/experiments/snapshots/formal_30_v1_results_20261015_161053/pipeline/complex/SupportTicketConsole_repaired_repaired_repaired.san",
                ROOT / "data/experiments/pipeline/batches/formal_30_v2/complex/SupportTicketConsole_repaired.san",
            ),
        )

        for component_name, vue_file, broken_file, fixed_file in cases:
            with self.subTest(component=component_name):
                broken = ValidateStage().run(ValidateStageInput(
                    generated_file_path=str(broken_file),
                    source_file=str(vue_file),
                    compile_check=False,
                ))
                fixed = ValidateStage().run(ValidateStageInput(
                    generated_file_path=str(fixed_file),
                    source_file=str(vue_file),
                    compile_check=False,
                ))

                self.assertIn(
                    "dom_child_order_mismatch",
                    {issue["code"] for issue in broken.validation_errors},
                )
                self.assertNotIn(
                    "dom_child_order_mismatch",
                    {issue["code"] for issue in fixed.validation_errors},
                )

    def test_incident_response_frozen_artifact_supports_unparenthesized_loop_index(self):
        vue_file = (
            ROOT
            / "data/datasets/components/03_complex/IncidentResponseBoard/vue/IncidentResponseBoard.vue"
        )
        san_file = (
            ROOT
            / "data/experiments/snapshots/formal_30_v3_results_20261022_200548"
            / "pipeline/complex/IncidentResponseBoard_repaired_repaired.san"
        )

        result = VisualEvalStage().run(VisualEvalStageInput(
            vue_file_path=str(vue_file),
            generated_file_path=str(san_file),
        ))

        ssm = SSMFactory().build_from_file(str(vue_file))
        validation = ValidateStage().run(ValidateStageInput(
            generated_file_path=str(san_file),
            ssm=ssm,
            source_file=str(vue_file),
            compile_check=False,
        ))
        validation_error_codes = {
            issue["code"] for issue in validation.validation_errors
        }

        self.assertTrue(result.visual_eval_passed, {
            "errors": result.visual_eval_errors,
            "warnings": result.visual_eval_warnings,
        })
        self.assertEqual(result.structure_similarity, 1.0)
        self.assertEqual(result.tree_edit_distance, 0.0)
        self.assertNotIn("vue_this_state", validation_error_codes)
        self.assertNotIn("lifecycle_behavior_not_landed", validation_error_codes)

    def test_incident_response_lifecycle_accepts_local_this_alias(self):
        vue_file = (
            ROOT
            / "data/datasets/components/03_complex/IncidentResponseBoard/vue/IncidentResponseBoard.vue"
        )
        san_file = (
            ROOT
            / "data/experiments/snapshots/formal_30_v4_incident_first_run_20261022_225432"
            / "pipeline/complex/IncidentResponseBoard_repaired_repaired_repaired.san"
        )
        ssm = SSMFactory().build_from_file(str(vue_file))

        validation = ValidateStage().run(ValidateStageInput(
            generated_file_path=str(san_file),
            ssm=ssm,
            source_file=str(vue_file),
            compile_check=False,
        ))
        validation_error_codes = {
            issue["code"] for issue in validation.validation_errors
        }

        self.assertNotIn("vue_this_state", validation_error_codes)
        self.assertNotIn("lifecycle_behavior_not_landed", validation_error_codes)

    def test_rule_builder_frozen_artifact_exposes_data_store_destructuring(self):
        vue_file = (
            ROOT
            / "data/datasets/components/03_complex/RuleBuilder/vue/RuleBuilder.vue"
        )
        san_file = (
            ROOT
            / "data/experiments/snapshots/formal_30_v3_results_20261022_200548"
            / "pipeline/complex/RuleBuilder_repaired_repaired_repaired.san"
        )
        ssm = SSMFactory().build_from_file(str(vue_file))

        validation = ValidateStage().run(ValidateStageInput(
            generated_file_path=str(san_file),
            ssm=ssm,
            source_file=str(vue_file),
            compile_check=False,
        ))
        validation_error_codes = {
            issue["code"] for issue in validation.validation_errors
        }

        self.assertIn("missing_prop_defaults", validation_error_codes)
        self.assertIn("invalid_san_data_destructuring", validation_error_codes)

    def test_habit_week_tracker_frozen_artifact_supports_unparenthesized_loop_index(self):
        vue_file = (
            ROOT
            / "data/datasets/components/02_medium/HabitWeekTracker/vue/HabitWeekTracker.vue"
        )
        san_file = (
            ROOT
            / "data/experiments/snapshots/formal_30_v3_results_20261022_200548"
            / "pipeline/medium/HabitWeekTracker_repaired_repaired_repaired.san"
        )
        ssm = SSMFactory().build_from_file(str(vue_file))

        validation = ValidateStage().run(ValidateStageInput(
            generated_file_path=str(san_file),
            ssm=ssm,
            source_file=str(vue_file),
            compile_check=False,
        ))
        visual = VisualEvalStage().run(VisualEvalStageInput(
            vue_file_path=str(vue_file),
            generated_file_path=str(san_file),
        ))

        self.assertTrue(validation.validation_passed, validation.validation_errors)
        self.assertTrue(visual.visual_eval_passed, visual.visual_eval_errors)
        self.assertEqual(visual.structure_similarity, 1.0)
        self.assertEqual(visual.tag_sequence_similarity, 1.0)
        self.assertEqual(visual.text_similarity, 1.0)
        self.assertEqual(visual.tree_edit_distance, 0.0)

    def test_playback_queue_frozen_artifact_supports_unparenthesized_loop_index(self):
        vue_file = (
            ROOT
            / "data/datasets/components/02_medium/PlaybackQueue/vue/PlaybackQueue.vue"
        )
        san_file = (
            ROOT
            / "data/experiments/snapshots/formal_30_v3_results_20261022_200548"
            / "pipeline/medium/PlaybackQueue_repaired_repaired_repaired.san"
        )
        ssm = SSMFactory().build_from_file(str(vue_file))

        validation = ValidateStage().run(ValidateStageInput(
            generated_file_path=str(san_file),
            ssm=ssm,
            source_file=str(vue_file),
            compile_check=False,
        ))
        visual = VisualEvalStage().run(VisualEvalStageInput(
            vue_file_path=str(vue_file),
            generated_file_path=str(san_file),
        ))

        self.assertTrue(validation.validation_passed, validation.validation_errors)
        self.assertTrue(visual.visual_eval_passed, visual.visual_eval_errors)
        self.assertEqual(visual.structure_similarity, 1.0)
        self.assertEqual(visual.tag_sequence_similarity, 1.0)
        self.assertEqual(visual.text_similarity, 1.0)
        self.assertEqual(visual.tree_edit_distance, 0.0)

    def test_default_llm_timeout_fits_inside_pipeline_timeout_budget(self):
        env = os.environ.copy()
        env.pop("LLM_TIMEOUT", None)
        env.pop("MIGRATION_GENERATION_TIMEOUT", None)
        script = (
            "from local_server.config import settings as server; "
            "from migration_pipeline.config import settings as pipeline; "
            "print(server.llm_timeout, pipeline.generation_timeout)"
        )

        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        server_timeout, pipeline_timeout = map(int, completed.stdout.split())

        self.assertEqual(server_timeout, 240)
        self.assertEqual(pipeline_timeout, 300)
        self.assertLess(server_timeout, pipeline_timeout)

    def test_validator_uses_vue_file_path_from_pipeline_state_for_dom_order(self):
        vue_file = (
            ROOT
            / "data/datasets/components/02_medium/CourseModuleAccordion/vue/CourseModuleAccordion.vue"
        )
        broken_file = (
            ROOT
            / "data/experiments/pipeline/batches/formal_30_v4_targeted/medium"
            / "CourseModuleAccordion_repaired_repaired_repaired.san"
        )

        result = ValidateStage().run_from_state({
            "generated_file_path": str(broken_file),
            "source_file": "CourseModuleAccordion",
            "vue_file_path": str(vue_file),
            "validation_compile_check": False,
        })

        self.assertIn(
            "dom_child_order_mismatch",
            {issue["code"] for issue in result["validation_errors"]},
        )

    @staticmethod
    def _minimal_san_component(template_body, methods):
        return f"""<template><section>{template_body}</section></template>
<script>
const san = require('san');
const DataTypes = san.DataTypes;
module.exports = san.defineComponent({{
    dataTypes: {{}},
    initData() {{
        return {{
            winnerId: '',
            leaderId: '',
            schedule: {{}},
            selectedIds: []
        }};
    }},
{methods}
}});
</script>
<style>.winner {{ color: green; }}</style>
"""


if __name__ == "__main__":
    unittest.main()
