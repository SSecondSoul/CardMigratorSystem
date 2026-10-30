import json
import unittest

from migration_pipeline.replay_formal_30_v4_remaining_task_manager_bounded_fix import (
    HISTORY,
    SOURCE,
    SOURCE_SHA256,
    build_candidate,
    sha256,
)
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput


class TaskManagerRemainingBoundedFixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text(encoding="utf-8")
        cls.candidate = build_candidate(cls.source)
        cls.ssm = json.loads(HISTORY.read_text(encoding="utf-8"))["state"]["ssm"]

    def test_frozen_source_and_scoped_static_repair(self):
        self.assertEqual(sha256(SOURCE), SOURCE_SHA256)
        before = ValidateStage().run(ValidateStageInput(
            generated_code=self.source, ssm=self.ssm, compile_check=True,
        ))
        after = ValidateStage().run(ValidateStageInput(
            generated_code=self.candidate, ssm=self.ssm, compile_check=True,
        ))
        before_codes = {issue["code"] for issue in before.validation_errors}
        self.assertIn("invalid_san_event_handler_syntax", before_codes)
        self.assertIn("invalid_san_computed_instance_method_call", before_codes)
        self.assertTrue(after.validation_passed, after.validation_errors)

    def test_native_and_custom_drag_events_remain_distinct(self):
        self.assertIn('on-dragstart="onDragStart"', self.candidate)
        self.assertIn('on-dragend="onDragEnd"', self.candidate)
        self.assertIn('on-dragover="prevent:onDragOver"', self.candidate)
        self.assertIn('on-drop="stop:onDrop"', self.candidate)
        self.assertIn('on-drag-start="onDragStart"', self.candidate)
        self.assertIn('on-drag-end="onDragEnd"', self.candidate)
        self.assertIn('on-drop="onDropToEnd"', self.candidate)

    def test_keyboard_form_and_overdue_logic_are_retained(self):
        self.assertIn('on-keyup="enter:addComment"', self.candidate)
        self.assertIn('on-submit="prevent:handleSubmit"', self.candidate)
        self.assertEqual(self.candidate.count('on-click="stop:fire('), 2)
        self.assertEqual(self.candidate.count('isTaskOverdue(task)'), 4)
        for statement in (
            'if (task.completed || !task.dueDate) return false;',
            'today.setHours(0, 0, 0, 0);',
            'return dueDate < today;',
        ):
            self.assertIn(statement, self.candidate)
        self.assertNotIn('this.isOverdue(task)', self.candidate)


if __name__ == "__main__":
    unittest.main()
