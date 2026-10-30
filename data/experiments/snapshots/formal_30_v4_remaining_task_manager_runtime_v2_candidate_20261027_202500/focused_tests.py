import json
import subprocess
import unittest
from pathlib import Path

from migration_pipeline.replay_formal_30_v4_remaining_task_manager_bounded_fix import (
    HISTORY,
    SOURCE,
    SOURCE_SHA256,
    build_candidate,
    sha256,
)
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.replay_formal_30_v4_remaining_task_manager_runtime_fix import (
    OUTPUT as RUNTIME_OUTPUT,
    SOURCE as RUNTIME_SOURCE,
    SOURCE_SHA256 as RUNTIME_SOURCE_SHA256,
    build_candidate as build_runtime_candidate,
)


ROOT = Path(__file__).resolve().parents[1]


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


class TaskManagerRuntimeFixTests(unittest.TestCase):
    def test_v2_replay_is_scoped_and_valid(self):
        self.assertEqual(sha256(RUNTIME_SOURCE), RUNTIME_SOURCE_SHA256)
        candidate = build_runtime_candidate(RUNTIME_SOURCE.read_text(encoding="utf-8"))
        self.assertEqual(candidate, RUNTIME_OUTPUT.read_text(encoding="utf-8"))
        self.assertIn("this.watch('tasks', () => {", candidate)
        self.assertIn("this.watch('settings', () => {", candidate)
        self.assertNotIn("this.watch('tasks', {", candidate)
        self.assertIn('on-drag-start="onDragStart($event)"', candidate)
        self.assertIn('on-drop-on="onDropOnTask($event)"', candidate)
        self.assertIn('on-submit="handleTaskSubmit($event)"', candidate)
        self.assertIn('on-update="updateSettings($event.key, $event.value)"', candidate)
        self.assertEqual(candidate.count('on-click="stop:onModalContentClick"'), 2)
        self.assertIn("this.syncTaskForm(this.data.get('task'));", candidate)

    def test_v2_san_instances_restore_watch_drag_form_and_settings(self):
        script = r"""
const assert = require('assert');
const fs = require('fs');
const san = require('san');
const source = fs.readFileSync(process.argv[1], 'utf8');
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1];
const moduleRef = {exports: {}};
new Function('module', 'exports', 'require', script)(moduleRef, moduleRef.exports, require);
global.localStorage = {setItem() {}, getItem() {return null;}};
const Parent = moduleRef.exports;
const parent = new Parent({data: {settings: {autoSave: false, syncInterval: 0}}});
parent.showNotification = () => {};
const tasks = [1, 2, 3].map(id => ({id, title: `T${id}`, completed: false,
  dueDate: '', priority: 'medium', tags: [], comments: []}));
parent.data.set('tasks', tasks);
assert.strictEqual(parent.data.get('statistics')[0].value, 3);
const Item = Parent.prototype.components['task-item'];
const item = new Item({data: {index: 0, draggable: true, task: tasks[0]}});
item.on('drag-start', index => parent.onDragStart(index));
let transferred;
item.onDragStart({dataTransfer: {setData(type, value) {transferred = [type, value];},
  effectAllowed: ''}});
assert.deepStrictEqual(transferred, ['text/plain', '0']);
assert.strictEqual(parent.data.get('dragStartIndex'), 0);
parent.onDropOnTask(2);
assert.deepStrictEqual(parent.data.get('tasks').map(task => task.id), [2, 3, 1]);
const Form = Parent.prototype.components['task-form'];
const form = new Form({data: {task: null, users: [], tags: ['work', 'home']}});
assert.deepStrictEqual(form.data.get('formData'), {
  title: '', description: '', priority: 'medium', dueDate: '', tags: [], assignee: ''
});
form.toggleTag('work');
assert.strictEqual(form.data.get('selectedTagMap.work'), true);
form.data.set('task', {id: 7, title: 'Edit', tags: ['home']});
assert.strictEqual(form.data.get('formData.title'), 'Edit');
assert.strictEqual(form.data.get('selectedTagMap.home'), true);
const Panel = Parent.prototype.components['settings-panel'];
const panel = new Panel({data: {settings: {autoSave: true}}});
const updates = [];
panel.on('update', payload => updates.push(payload));
panel.updateDefaultView({target: {value: 'board'}});
panel.updateAutoSave({target: {checked: false}});
panel.updateAutoSave({target: {checked: true}});
assert.deepStrictEqual(updates, [
  {key: 'defaultView', value: 'board'},
  {key: 'autoSave', value: false},
  {key: 'autoSave', value: true}
]);
"""
        completed = subprocess.run(
            ["node", "-e", script, str(RUNTIME_OUTPUT)],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
