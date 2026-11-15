"""Replay the TaskManager modal/form fix without changing earlier candidates."""

from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / (
    "data/experiments/pipeline/manual_fixes/formal_30_v4_task_manager_manual_followup/"
    "TaskManager_inline_format_methods.san"
)
SOURCE_SHA256 = "baaca5fb8dbe1da32704fd672b54b4e2f2f50f4d5a5ac6046f19ec1544d07cc4"
TARGET = ROOT / (
    "data/experiments/pipeline/manual_fixes/formal_30_v4_task_manager_manual_followup/"
    "TaskManager_form_initialization.san"
)


def replace_once(code: str, old: str, new: str) -> str:
    if code.count(old) != 1:
        raise RuntimeError(f"Expected exactly one occurrence of {old!r}, found {code.count(old)}")
    return code.replace(old, new, 1)


def main() -> None:
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise RuntimeError("Source candidate SHA-256 changed")
    if TARGET.exists():
        raise FileExistsError(TARGET)
    code = SOURCE.read_text(encoding="utf-8")
    code = replace_once(
        code,
        '<div class="modal-overlay" s-if="isModalOpen" on-click="closeModal">',
        '<div class="modal-overlay" s-if="isModalOpen" on-click="onModalOverlayClick($event)">',
    )
    code = replace_once(
        code,
        '<div class="modal-overlay" s-if="showSettings" on-click="closeSettings">',
        '<div class="modal-overlay" s-if="showSettings" on-click="onSettingsOverlayClick($event)">',
    )
    code = replace_once(
        code,
        "function isTaskOverdue(task) {",
        """function createTaskFormData(task) {
  return task ? { ...task, tags: [...(task.tags || [])] } : {
    title: '',
    description: '',
    priority: 'medium',
    dueDate: '',
    tags: [],
    assignee: ''
  };
}

function isTaskOverdue(task) {""",
    )
    code = replace_once(
        code,
        '<textarea rows="3" placeholder="详细描述...">{= formData.description =}</textarea>',
        '<textarea rows="3" placeholder="详细描述..." value="{= formData.description =}"></textarea>',
    )
    code = replace_once(
        code,
        'on-click="fire(\'cancel\')">取消',
        'on-click="cancel">取消',
    )
    code = replace_once(
        code,
        """  initData() {
    const task = this.data.get('task');
    return {
      formData: this.createFormData(task),
      users: this.data.get('users'),
      tags: this.data.get('tags'),
      task: task
    };
  },
  computed: {
    createFormData() {
      const task = this.data.get('task');
      return task ? { ...task, tags: [...(task.tags || [])] } : {
        title: '',
        description: '',
        priority: 'medium',
        dueDate: '',
        tags: [],
        assignee: ''
      };
    }
  },
  toggleTag(tag) {""",
        """  initData() {
    return {
      formData: createTaskFormData(null),
      users: [],
      tags: [],
      task: null
    };
  },
  inited() {
    this.data.set('formData', createTaskFormData(this.data.get('task')));
    this.watch('task', task => {
      this.data.set('formData', createTaskFormData(task));
    });
  },
  toggleTag(tag) {""",
    )
    code = replace_once(
        code,
        """  handleSubmit() {
    const formData = this.data.get('formData');
    if (!formData.title.trim()) return;
    this.fire('submit', formData);
  }
});

const SettingsPanel""",
        """  handleSubmit() {
    const formData = this.data.get('formData');
    if (!formData.title.trim()) return;
    this.fire('submit', formData);
  },
  cancel() {
    this.fire('cancel');
  }
});

const SettingsPanel""",
    )
    code = replace_once(
        code,
        """  closeSettings() {
    this.data.set('showSettings', false);
  },
  onDragOver() {}""",
        """  closeSettings() {
    this.data.set('showSettings', false);
  },
  onModalOverlayClick(event) {
    if (event && event.target === event.currentTarget) this.closeModal();
  },
  onSettingsOverlayClick(event) {
    if (event && event.target === event.currentTarget) this.closeSettings();
  },
  onDragOver() {}""",
    )
    TARGET.write_text(code, encoding="utf-8")
    print(f"candidate: {TARGET.relative_to(ROOT)}")
    print(f"sha256: {hashlib.sha256(TARGET.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
