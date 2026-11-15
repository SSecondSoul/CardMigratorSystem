"""Replay scoped San template syntax fixes after manual browser parse failure."""

from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / (
    "data/experiments/pipeline/manual_fixes/formal_30_v4_task_manager_manual_followup/"
    "TaskManager_computed_pure_helper.san"
)
SOURCE_SHA256 = "9d3ac701b1556852b646ef52a45bd388a12d3c941bc3d0fbe6368a999503c65f"
TARGET = ROOT / (
    "data/experiments/pipeline/manual_fixes/formal_30_v4_task_manager_manual_followup/"
    "TaskManager_template_syntax.san"
)


def replace_exact(code: str, old: str, new: str, count: int = 1) -> str:
    if code.count(old) != count:
        raise RuntimeError(f"Expected {count} occurrence(s) of {old!r}, found {code.count(old)}")
    return code.replace(old, new, count)


def main() -> None:
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise RuntimeError("Source candidate SHA-256 changed")
    if TARGET.exists():
        raise FileExistsError(TARGET)
    code = SOURCE.read_text(encoding="utf-8")

    # Main template: San event values call methods; s-for aliases are not Vue tuples.
    code = replace_exact(code, 'on-click="showSettings = true"', 'on-click="openSettings"')
    code = replace_exact(code, 'on-click="showSettings = false"', 'on-click="closeSettings"', 2)
    code = replace_exact(code, 'on-dragover=""', 'on-dragover="prevent:onDragOver"')
    code = replace_exact(
        code,
        's-for="(task, index) in filteredTasks trackby task.id"',
        's-for="task, index in filteredTasks trackby task.id"',
    )
    code = replace_exact(
        code,
        '{{getTaskCount(filter.value, tasks, isOverdue)}}',
        '{{getTaskCount(filter.value, tasks)}}',
    )

    # Inline TaskItem: native drag events and San's value-based modifiers.
    code = replace_exact(
        code,
        'draggable="true" on-drag-start="onDragStart"',
        'draggable="true" on-dragstart="onDragStart"',
    )
    code = replace_exact(
        code,
        'on-drop.stop="onDrop" on-drag-end="onDragEnd"',
        'on-drop="stop:onDrop" on-dragend="onDragEnd"',
    )
    code = replace_exact(code, 'on-dragover.prevent', 'on-dragover="prevent:onDragOver"')
    code = replace_exact(code, 'on-click.stop="fire(', 'on-click="stop:fire(', 2)
    code = replace_exact(
        code,
        """  onDragStart() {
    const draggable = this.data.get('draggable');""",
        """  onDragOver() {},
  onDragStart() {
    const draggable = this.data.get('draggable');""",
    )

    # Inline TaskDetail and TaskForm also copied Vue loop/modifier syntax.
    code = replace_exact(
        code,
        's-for="(comment, idx) in task.comments trackby idx"',
        's-for="comment, idx in task.comments trackby idx"',
    )
    code = replace_exact(code, 'on-keyup.enter="addComment"', 'on-keyup="enter:addComment"')
    code = replace_exact(code, 'on-submit.prevent="handleSubmit"', 'on-submit="prevent:handleSubmit"')

    # Keep the shared pure overdue logic, including filter counts.
    code = replace_exact(
        code,
        """  getTaskCount(filterValue, tasks, isOverdueFn) {
    switch (filterValue) {
      case 'all': return tasks.length;
      case 'active': return tasks.filter(t => !t.completed && !isOverdueFn(t)).length;
      case 'completed': return tasks.filter(t => t.completed).length;
      case 'overdue': return tasks.filter(t => isOverdueFn(t) && !t.completed).length;""",
        """  getTaskCount(filterValue, tasks) {
    switch (filterValue) {
      case 'all': return tasks.length;
      case 'active': return tasks.filter(t => !t.completed && !isTaskOverdue(t)).length;
      case 'completed': return tasks.filter(t => t.completed).length;
      case 'overdue': return tasks.filter(t => isTaskOverdue(t) && !t.completed).length;""",
    )
    code = replace_exact(
        code,
        """  openTaskModal() {
    this.data.set('editingTask', null);""",
        """  openSettings() {
    this.data.set('showSettings', true);
  },
  closeSettings() {
    this.data.set('showSettings', false);
  },
  onDragOver() {},
  openTaskModal() {
    this.data.set('editingTask', null);""",
    )

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(code, encoding="utf-8")
    print(f"candidate: {TARGET.relative_to(ROOT)}")
    print(f"sha256: {hashlib.sha256(TARGET.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
