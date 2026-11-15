"""Replay TaskManager settings events and task-tag selection fixes."""

from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / (
    "data/experiments/pipeline/manual_fixes/formal_30_v4_task_manager_manual_followup/"
    "TaskManager_form_initialization.san"
)
SOURCE_SHA256 = "7d4a4066419063a350b70e16cd4ea816889b954f9300fade27fad4407ba0ff4c"
TARGET = ROOT / (
    "data/experiments/pipeline/manual_fixes/formal_30_v4_task_manager_manual_followup/"
    "TaskManager_settings_tags.san"
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
        'on-update="updateSettings"></settings-panel>',
        'on-update="updateSettings($event.key, $event.value)"></settings-panel>',
    )
    code = replace_once(
        code,
        "function createTaskFormData(task) {",
        """function createTagSelectionMap(tags) {
  const selected = {};
  for (const tag of tags || []) selected[tag] = true;
  return selected;
}

function createTaskFormData(task) {""",
    )
    code = replace_once(
        code,
        "formData.tags.includes(tag) ? 'selected' : ''",
        "selectedTagMap[tag] ? 'selected' : ''",
    )
    code = replace_once(
        code,
        """      formData: createTaskFormData(null),
      users: [],""",
        """      formData: createTaskFormData(null),
      selectedTagMap: {},
      users: [],""",
    )
    code = replace_once(
        code,
        """  inited() {
    this.data.set('formData', createTaskFormData(this.data.get('task')));
    this.watch('task', task => {
      this.data.set('formData', createTaskFormData(task));
    });
  },
  toggleTag(tag) {
    const formData = this.data.get('formData');
    const tags = formData.tags;
    if (tags.includes(tag)) {
      this.data.set('formData', { ...formData, tags: tags.filter(t => t !== tag) });
    } else {
      this.data.set('formData', { ...formData, tags: [...tags, tag] });
    }
  },""",
        """  inited() {
    this.syncTaskForm(this.data.get('task'));
    this.watch('task', task => this.syncTaskForm(task));
  },
  syncTaskForm(task) {
    const formData = createTaskFormData(task);
    this.data.set('formData', formData);
    this.data.set('selectedTagMap', createTagSelectionMap(formData.tags));
  },
  toggleTag(tag) {
    const formData = this.data.get('formData');
    const tags = formData.tags || [];
    const nextTags = tags.includes(tag) ? tags.filter(t => t !== tag) : [...tags, tag];
    this.data.set('formData', { ...formData, tags: nextTags });
    this.data.set('selectedTagMap', createTagSelectionMap(nextTags));
  },""",
    )
    event_handlers = {
        "on-change=\"fire('update', 'defaultView', event.target.value)\"": 'on-change="updateDefaultView($event)"',
        "on-change=\"fire('update', 'autoSave', event.target.checked)\"": 'on-change="updateAutoSave($event)"',
        "on-change=\"fire('update', 'notifications', event.target.checked)\"": 'on-change="updateNotifications($event)"',
        "on-change=\"fire('update', 'syncInterval', event.target.value)\"": 'on-change="updateSyncInterval($event)"',
    }
    for old, new in event_handlers.items():
        code = replace_once(code, old, new)
    code = replace_once(
        code,
        """  initData() {
    return {
      settings: {}
    };
  }
});

module.exports""",
        """  initData() {
    return {
      settings: {}
    };
  },
  emitUpdate(key, value) {
    this.fire('update', { key, value });
  },
  updateDefaultView(event) {
    this.emitUpdate('defaultView', event.target.value);
  },
  updateAutoSave(event) {
    this.emitUpdate('autoSave', event.target.checked);
  },
  updateNotifications(event) {
    this.emitUpdate('notifications', event.target.checked);
  },
  updateSyncInterval(event) {
    this.emitUpdate('syncInterval', event.target.value);
  }
});

module.exports""",
    )
    TARGET.write_text(code, encoding="utf-8")
    print(f"candidate: {TARGET.relative_to(ROOT)}")
    print(f"sha256: {hashlib.sha256(TARGET.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
