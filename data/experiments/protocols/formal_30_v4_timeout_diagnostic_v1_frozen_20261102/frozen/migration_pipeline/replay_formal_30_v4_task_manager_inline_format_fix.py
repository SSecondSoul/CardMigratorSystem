"""Replay display-formatting fixes for inline TaskManager San child components."""

from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / (
    "data/experiments/pipeline/manual_fixes/formal_30_v4_task_manager_manual_followup/"
    "TaskManager_template_syntax.san"
)
SOURCE_SHA256 = "9db0ec7696b95accb5f538bf98f220c6a7ed6cd07efc8e476f45596fbb4746c6"
TARGET = ROOT / (
    "data/experiments/pipeline/manual_fixes/formal_30_v4_task_manager_manual_followup/"
    "TaskManager_inline_format_methods.san"
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
        """  computed: {
    formatTrend() {
      const trend = this.data.get('trend');
      return Math.abs(trend) + '%';
    }
  }
});

const TaskItem""",
        """  formatTrend(trend) {
    return Math.abs(trend) + '%';
  }
});

const TaskItem""",
    )
    code = replace_once(
        code,
        """  computed: {
    getPriorityLabel() {
      const priority = this.data.get('task.priority');
      const labels = { high: '高优先级', medium: '中优先级', low: '低优先级' };
      return labels[priority] || priority;
    },
    formatDate() {
      const date = this.data.get('task.dueDate');
      if (!date) return '无截止日期';
      const d = new Date(date);
      return `${d.getMonth() + 1}/${d.getDate()}`;
    }
  },
  onDragOver()""",
        """  getPriorityLabel(priority) {
    const labels = { high: '高优先级', medium: '中优先级', low: '低优先级' };
    return labels[priority] || priority;
  },
  formatDate(date) {
    if (!date) return '无截止日期';
    const d = new Date(date);
    return `${d.getMonth() + 1}/${d.getDate()}`;
  },
  onDragOver()""",
    )
    code = replace_once(
        code,
        """  computed: {
    getPriorityLabel() {
      const priority = this.data.get('task.priority');
      const labels = { high: '高优先级', medium: '中优先级', low: '低优先级' };
      return labels[priority] || priority;
    },
    formatDate() {
      const date = this.data.get('task.dueDate');
      if (!date) return '无截止日期';
      const d = new Date(date);
      return `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`;
    },
    formatTime() {
      const time = this.data.get('comment.time');
      const d = new Date(time);
      return d.toLocaleTimeString();
    }
  },
  addComment()""",
        """  getPriorityLabel(priority) {
    const labels = { high: '高优先级', medium: '中优先级', low: '低优先级' };
    return labels[priority] || priority;
  },
  formatDate(date) {
    if (!date) return '无截止日期';
    const d = new Date(date);
    return `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`;
  },
  formatTime(time) {
    const d = new Date(time);
    return d.toLocaleTimeString();
  },
  addComment()""",
    )
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(code, encoding="utf-8")
    print(f"candidate: {TARGET.relative_to(ROOT)}")
    print(f"sha256: {hashlib.sha256(TARGET.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
