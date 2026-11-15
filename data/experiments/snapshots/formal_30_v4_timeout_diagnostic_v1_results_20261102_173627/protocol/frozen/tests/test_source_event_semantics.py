import tempfile
import unittest
from pathlib import Path

from migration_pipeline.stages.repair import RepairStage
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput


SOURCE = '''<template>
<div class="overlay" @click.self="close"><div>content</div></div>
<div class="row" draggable="true" @dragstart="start" @dragend="end"></div>
</template>'''
BROKEN = '''<template>
<div class="overlay" on-click="close"><div>content</div></div>
<task-item on-drag-start="parentStart" on-drag-end="parentEnd"></task-item>
</template>
<script>
const san = require('san');
const TaskItem = san.defineComponent({
  template: `<div class="row" draggable="true" on-drag-start="start" on-drag-end="end"></div>`,
  start() { this.fire('drag-start'); },
  end() { this.fire('drag-end'); }
});
module.exports = san.defineComponent({
  components: {'task-item': TaskItem},
  close() {}, parentStart() {}, parentEnd() {}
});
</script><style>.overlay { display: block; }</style>'''


class SourceEventSemanticsTests(unittest.TestCase):
    def test_source_grounded_detection_and_bounded_repair(self):
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / "source.vue"
            source_path.write_text(SOURCE, encoding="utf-8")
            before = ValidateStage().run(ValidateStageInput(
                generated_code=BROKEN, vue_file_path=str(source_path), compile_check=False,
            ))
            codes = {issue["code"] for issue in before.validation_errors}
            self.assertTrue({"missing_self_click_guard", "native_drag_event_misbound"} <= codes)
            fixed, repairs = RepairStage._deterministic_repair_plan(
                BROKEN, before.validation_errors, [], vue_file_path=str(source_path),
            )
            self.assertEqual(len(repairs), 1)
            self.assertIn('on-click="onSelfClickClose($event)"', fixed)
            self.assertIn("event.target === event.currentTarget", fixed)
            self.assertIn('on-dragstart="start"', fixed)
            self.assertIn('on-dragend="end"', fixed)
            self.assertIn('on-drag-start="parentStart"', fixed)
            self.assertIn('on-drag-end="parentEnd"', fixed)
            after = ValidateStage().run(ValidateStageInput(
                generated_code=fixed, vue_file_path=str(source_path), compile_check=False,
            ))
            self.assertFalse({issue["code"] for issue in after.validation_errors} &
                             {"missing_self_click_guard", "native_drag_event_misbound"})

    def test_no_source_contract_no_repair(self):
        no_contract = SOURCE.replace("@click.self", "@click").replace("@dragstart", "@mouseover").replace("@dragend", "@mouseout")
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / "source.vue"
            source_path.write_text(no_contract, encoding="utf-8")
            validation = ValidateStage().run(ValidateStageInput(
                generated_code=BROKEN, vue_file_path=str(source_path), compile_check=False,
            ))
            codes = {issue["code"] for issue in validation.validation_errors}
            self.assertNotIn("missing_self_click_guard", codes)
            self.assertNotIn("native_drag_event_misbound", codes)

    def test_custom_drag_event_only_is_valid(self):
        fixed = BROKEN.replace('on-click="close"', 'on-click="onSelfClickClose($event)"')
        fixed = fixed.replace('  close() {},',
            '  onSelfClickClose(event) { if (event && event.target === event.currentTarget) this.close(); },\n  close() {},')
        fixed = fixed.replace('on-drag-start="start"', 'on-dragstart="start"')
        fixed = fixed.replace('on-drag-end="end"', 'on-dragend="end"')
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / "source.vue"
            source_path.write_text(SOURCE, encoding="utf-8")
            validation = ValidateStage().run(ValidateStageInput(
                generated_code=fixed, vue_file_path=str(source_path), compile_check=False,
            ))
            self.assertNotIn("native_drag_event_misbound", {issue["code"] for issue in validation.validation_errors})
            self.assertNotIn("missing_self_click_guard", {issue["code"] for issue in validation.validation_errors})


if __name__ == "__main__":
    unittest.main()
