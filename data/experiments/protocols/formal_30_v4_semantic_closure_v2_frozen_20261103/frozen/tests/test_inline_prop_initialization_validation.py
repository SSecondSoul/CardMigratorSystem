"""Source-aware checks for initial prop-derived state in inline San children."""

import tempfile
import unittest
from pathlib import Path

from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.utils.repair_prompt import RepairPromptInput, build_repair_prompt


SOURCE = """<template><div /></template>
<script>
const ChildForm = {
  props: ['item'],
  data() {
    return { formData: this.createFormData(this.item) };
  }
};
export default { components: { ChildForm } };
</script>
"""


def san_code(inited: str) -> str:
    return """<template><div></div></template>
<script>
const san = require('san');
const ChildForm = san.defineComponent({
  template: '<form></form>',
  initData() { return { formData: { title: '' } }; },
  inited() {
""" + inited + """
  },
  createFormData(item) { return item ? { ...item } : { title: '' }; }
});
module.exports = san.defineComponent({
  template: '<div></div>',
  components: { 'child-form': ChildForm },
  initData() { return {}; }
});
</script><style></style>
"""


class InlinePropInitializationValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / "source.vue"
        self.source.write_text(SOURCE, encoding="utf-8")

    def error_codes(self, code: str, source: str | None = None) -> list[str]:
        result = ValidateStage().run(ValidateStageInput(
            generated_code=code,
            source_file=source if source is not None else str(self.source),
            compile_check=False,
        ))
        return [issue["code"] for issue in result.validation_errors]

    def test_watcher_only_does_not_initialize_first_prop(self):
        code = san_code("""
    this.watch('item', item => {
      this.data.set('formData', this.createFormData(item));
    });
""")
        self.assertIn("missing_inline_prop_dependent_initialization", self.error_codes(code))

    def test_initial_copy_before_watcher_passes(self):
        code = san_code("""
    this.data.set('formData', this.createFormData(this.data.get('item')));
    this.watch('item', item => {
      this.data.set('formData', this.createFormData(item));
    });
""")
        self.assertNotIn("missing_inline_prop_dependent_initialization", self.error_codes(code))

    def test_unrelated_inline_child_is_out_of_scope(self):
        self.source.write_text(SOURCE.replace("this.createFormData(this.item)", "{ title: '' }"), encoding="utf-8")
        self.assertNotIn(
            "missing_inline_prop_dependent_initialization",
            self.error_codes(san_code("this.watch('item', item => {});")),
        )

    def test_frozen_task_manager_probe_is_detected(self):
        root = Path(__file__).resolve().parents[1]
        candidate = root / (
            "data/experiments/snapshots/"
            "formal_30_v4_task_manager_initdata_computed_probe_v1_result_20261028_233258/"
            "candidate.san"
        )
        source = root / "data/datasets/components/03_complex/TaskManager/vue/TaskManager.vue"
        self.assertIn(
            "missing_inline_prop_dependent_initialization",
            self.error_codes(candidate.read_text(encoding="utf-8"), str(source)),
        )

    def test_single_error_uses_source_focused_prompt(self):
        source_child = "const ChildForm = { props: ['item'], data() { return { formData: this.createFormData(this.item) }; } };"
        prompt = build_repair_prompt(RepairPromptInput(
            ssm={"script": {"options": {"components": [{
                "source_name": "ChildForm",
                "inline_definition": {"source_code": source_child},
            }]}}},
            current_code=san_code("this.watch('item', item => {});"),
            validation_errors=[{
                "code": "missing_inline_prop_dependent_initialization",
                "message": "ChildForm.formData <- item",
            }],
        ))
        self.assertIn("BEFORE this.watch", prompt)
        self.assertIn(source_child, prompt)
        self.assertIn("this.data.get('prop')", prompt)


if __name__ == "__main__":
    unittest.main()
