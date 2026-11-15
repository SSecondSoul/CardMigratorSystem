"""Replay the scoped computed-context fix from the frozen TaskManager failure."""

from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_task_manager_manual_followup_failed_20261026_203625/"
    "pipeline/complex/TaskManager_repaired_repaired_repaired.san"
)
SOURCE_SHA256 = "c514064153762d3ee3c457d68afb9689618474bdd3f71215399d72088711ef1f"
TARGET = ROOT / (
    "data/experiments/pipeline/manual_fixes/formal_30_v4_task_manager_manual_followup/"
    "TaskManager_computed_pure_helper.san"
)


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"Expected exactly one occurrence of {old!r}")
    return text.replace(old, new, 1)


def main() -> None:
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise RuntimeError("Frozen source SHA-256 changed")
    if TARGET.exists():
        raise FileExistsError(TARGET)
    code = SOURCE.read_text(encoding="utf-8")
    code = replace_once(
        code,
        "const DataTypes = san.DataTypes;\n",
        """const DataTypes = san.DataTypes;

function isTaskOverdue(task) {
  if (task.completed || !task.dueDate) return false;
  const dueDate = new Date(task.dueDate);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return dueDate < today;
}
""",
    )
    code = replace_once(
        code,
        "case 'active': return !task.completed && !this.isOverdue(task);",
        "case 'active': return !task.completed && !isTaskOverdue(task);",
    )
    code = replace_once(
        code,
        "case 'overdue': return this.isOverdue(task) && !task.completed;",
        "case 'overdue': return isTaskOverdue(task) && !task.completed;",
    )
    code = replace_once(
        code,
        """  isOverdue(task) {
    if (task.completed || !task.dueDate) return false;
    const dueDate = new Date(task.dueDate);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return dueDate < today;
  },""",
        """  isOverdue(task) {
    return isTaskOverdue(task);
  },""",
    )
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(code, encoding="utf-8")
    print(f"candidate: {TARGET.relative_to(ROOT)}")
    print(f"sha256: {hashlib.sha256(TARGET.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
