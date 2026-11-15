"""Replay bounded browser-failure fixes from the frozen TaskManager v1 candidate.

This produces a separate post-hoc development candidate; it never rewrites the
failed automatic batch, the v1 candidate, or their frozen snapshots.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.stages.visual_eval import VisualEvalStage, VisualEvalStageInput


SOURCE = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_remaining_task_manager_bounded_candidate_20261027_200300/candidate.san"
)
SOURCE_SHA256 = "06e1db96c365592fe13f8bd9e92376ae1384ccb3cdc091ffcf612acf3170ca8d"
FAILED = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_generalization_remaining_v1_task_manager_failed_20261027_195349"
)
OUTPUT_DIR = ROOT / (
    "data/experiments/pipeline/manual_fixes/"
    "formal_30_v4_remaining_task_manager_runtime_v2"
)
OUTPUT = OUTPUT_DIR / "TaskManager_repaired.san"
REPORT = OUTPUT_DIR / "repair_report.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_exact(code: str, old: str, new: str, count: int = 1) -> str:
    found = code.count(old)
    if found != count:
        raise RuntimeError(f"Expected {count} occurrences, found {found}: {old[:100]!r}")
    return code.replace(old, new)


def build_candidate(code: str) -> str:
    # San watch(name, listener) takes a callable, not Vue's {handler} object.
    code = replace_exact(
        code,
        """    this.watch('tasks', {
      handler: () => {
        this.updateStatistics();
        if (this.data.get('settings').autoSave) {
          this.saveToLocalStorage();
        }
      }
    });""",
        """    this.watch('tasks', () => {
      this.updateStatistics();
      if (this.data.get('settings').autoSave) {
        this.saveToLocalStorage();
      }
    });""",
    )
    code = replace_exact(
        code,
        """    this.watch('settings', {
      handler: () => {
        if (this.data.get('settings').autoSave) {
          this.saveToLocalStorage();
        }
        this.updateSyncInterval();
      }
    });""",
        """    this.watch('settings', () => {
      if (this.data.get('settings').autoSave) {
        this.saveToLocalStorage();
      }
      this.updateSyncInterval();
    });""",
    )

    # San custom events deliver one payload, and it must be passed explicitly
    # via $event in the parent's binding. This also restores drag indices.
    for old, new in (
        ('on-toggle="toggleTaskStatus"', 'on-toggle="toggleTaskStatus($event)"'),
        ('on-edit="editTask"', 'on-edit="editTask($event)"'),
        ('on-view="selectTask"', 'on-view="selectTask($event)"'),
        ('on-delete="deleteTask"', 'on-delete="deleteTask($event)"'),
        ('on-drag-start="onDragStart"', 'on-drag-start="onDragStart($event)"'),
        ('on-drop-on="onDropOnTask"', 'on-drop-on="onDropOnTask($event)"'),
        ('on-update="updateTask"', 'on-update="updateTask($event)"'),
        ('on-comment="addComment"', 'on-comment="addComment($event)"'),
        ('on-submit="handleTaskSubmit"', 'on-submit="handleTaskSubmit($event)"'),
        ('on-update="updateSettings"',
         'on-update="updateSettings($event.key, $event.value)"'),
    ):
        code = replace_exact(code, old, new)
    code = replace_exact(code, 'on-dragstart="onDragStart"',
                         'on-dragstart="onDragStart($event)"')
    code = replace_exact(
        code,
        """  onDragStart() {
    if (!this.data.get('draggable')) return;
    const index = this.data.get('index');
    this.fire('drag-start', index);
  },""",
        """  onDragStart(event) {
    if (!this.data.get('draggable')) return;
    const index = this.data.get('index');
    if (event && event.dataTransfer) {
      event.dataTransfer.setData('text/plain', String(index));
      event.dataTransfer.effectAllowed = 'move';
    }
    this.fire('drag-start', index);
  },""",
    )

    # Vue's @click.self on each overlay must not close when clicked within
    # modal-content. The close/cancel controls still call the parent methods.
    code = replace_exact(
        code, '<div class="modal-content">',
        '<div class="modal-content" on-click="stop:onModalContentClick">', 2,
    )
    code = replace_exact(
        code, "  closeModal() {", "  onModalContentClick() {},\n  closeModal() {",
    )

    # Vue's TaskForm data() initializes from the current task. A San watch
    # does not run for its initial prop, so do that once in inited().
    code = replace_exact(
        code,
        """      tags: [],
      formData: {}
    };
  },
  inited() {
    this.watch('task', task => {
      this.data.set('formData', this.createFormData(task));
    });
  },""",
        """      tags: [],
      formData: {},
      selectedTagMap: {}
    };
  },
  inited() {
    this.syncTaskForm(this.data.get('task'));
    this.watch('task', task => this.syncTaskForm(task));
  },
  syncTaskForm(task) {
    const formData = this.createFormData(task);
    this.data.set('formData', formData);
    this.data.set('selectedTagMap', createTagSelectionMap(formData.tags));
  },""",
    )
    code = replace_exact(
        code,
        "const TaskForm = san.defineComponent({",
        """function createTagSelectionMap(tags) {
  const selected = {};
  for (const tag of tags || []) selected[tag] = true;
  return selected;
}

const TaskForm = san.defineComponent({""",
    )
    code = replace_exact(code,
                         "isTagSelected(tag, formData.tags) ? 'selected' : ''",
                         "selectedTagMap[tag] ? 'selected' : ''")
    code = replace_exact(code, 'on-click="toggleTag(tag, formData.tags)"',
                         'on-click="toggleTag(tag)"')
    code = replace_exact(
        code,
        """  isTagSelected(tag, tags) {
    return tags.includes(tag);
  },
  toggleTag(tag, tags) {
    if (tags.includes(tag)) {
      this.data.set('formData.tags', tags.filter(t => t !== tag));
    } else {
      this.data.set('formData.tags', [...tags, tag]);
    }
  },""",
        """  toggleTag(tag) {
    const tags = this.data.get('formData.tags') || [];
    const nextTags = tags.includes(tag) ? tags.filter(t => t !== tag) : [...tags, tag];
    this.data.set('formData.tags', nextTags);
    this.data.set('selectedTagMap', createTagSelectionMap(nextTags));
  },""",
    )

    # SettingsPanel must emit one object and not mutate a prop through
    # two-way binding; the parent receives key/value from that object.
    for old, new in (
        ('value="{= settings.defaultView =}"', 'value="{{ settings.defaultView }}"'),
        ('checked="{= settings.autoSave =}"', 'checked="{{ settings.autoSave }}"'),
        ('checked="{= settings.notifications =}"', 'checked="{{ settings.notifications }}"'),
        ('value="{= settings.syncInterval =}"', 'value="{{ settings.syncInterval }}"'),
        ('on-change="updateDefaultView($event.target.value)"',
         'on-change="updateDefaultView($event)"'),
        ('on-change="updateAutoSave($event.target.checked)"',
         'on-change="updateAutoSave($event)"'),
        ('on-change="updateNotifications($event.target.checked)"',
         'on-change="updateNotifications($event)"'),
        ('on-change="updateSyncInterval($event.target.value)"',
         'on-change="updateSyncInterval($event)"'),
    ):
        code = replace_exact(code, old, new)
    code = replace_exact(
        code,
        """  updateDefaultView(value) {
    this.fire('update', 'defaultView', value);
  },
  updateAutoSave(value) {
    this.fire('update', 'autoSave', value);
  },
  updateNotifications(value) {
    this.fire('update', 'notifications', value);
  },
  updateSyncInterval(value) {
    this.fire('update', 'syncInterval', value);
  }""",
        """  updateDefaultView(event) {
    this.fire('update', { key: 'defaultView', value: event.target.value });
  },
  updateAutoSave(event) {
    this.fire('update', { key: 'autoSave', value: event.target.checked });
  },
  updateNotifications(event) {
    this.fire('update', { key: 'notifications', value: event.target.checked });
  },
  updateSyncInterval(event) {
    this.fire('update', { key: 'syncInterval', value: event.target.value });
  }""",
    )
    return code


def main() -> None:
    if OUTPUT.exists() or REPORT.exists():
        raise FileExistsError("v2 candidate/report already exists; do not overwrite evidence")
    if sha256(SOURCE) != SOURCE_SHA256:
        raise RuntimeError("Frozen v1 TaskManager candidate SHA-256 mismatch")
    state = json.loads((FAILED / "repair_history.json").read_text(encoding="utf-8"))["state"]
    candidate = build_candidate(SOURCE.read_text(encoding="utf-8"))
    validation = ValidateStage().run(ValidateStageInput(
        generated_code=candidate, ssm=state["ssm"],
        vue_file_path=str(FAILED / "source.vue"), compile_check=True,
    ))
    if not validation.validation_passed:
        raise RuntimeError(f"v2 static/compile validation failed: {validation.validation_errors}")
    visual = VisualEvalStage().run(VisualEvalStageInput(
        vue_file_path=str(FAILED / "source.vue"), generated_code=candidate,
    ))
    if not visual.visual_eval_passed:
        raise RuntimeError(f"v2 lightweight visual eval failed: {visual.visual_eval_errors}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(candidate, encoding="utf-8", newline="")
    report = {
        "sample_id": "TaskManager",
        "classification": "reused_development_posthoc_runtime_repair_probe",
        "independent_holdout": False,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": SOURCE.relative_to(ROOT).as_posix(),
        "source_sha256": SOURCE_SHA256,
        "candidate": OUTPUT.relative_to(ROOT).as_posix(),
        "candidate_sha256": sha256(OUTPUT),
        "scope": "Callable San watchers, explicit custom-event payloads, drag index, modal click isolation, task-form initialization, and settings/tag state",
        "validation_passed": True,
        "san_compile_passed": True,
        "lightweight_visual_passed": True,
        "structure_similarity": visual.structure_similarity,
        "browser_runtime": "pending_user_review",
        "boundary": "Original automatic batch failed and v1 browser candidate was rejected; neither is overwritten.",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
