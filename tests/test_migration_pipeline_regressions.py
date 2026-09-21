import unittest
from pathlib import Path

from SSM.extractors.factory import SSMFactory
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.stages.visual_eval import VisualEvalStage, VisualEvalStageInput


ROOT = Path(__file__).resolve().parents[1]
VUE = ROOT / "data/datasets/components/02_medium/KanbanColumnBoard/vue/KanbanColumnBoard.vue"
REFERENCE_SAN = ROOT / "data/datasets/components/02_medium/KanbanColumnBoard/san/KanbanColumnBoard.san"
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


if __name__ == "__main__":
    unittest.main()
