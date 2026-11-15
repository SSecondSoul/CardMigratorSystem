"""Source-hash-guarded TaskManager failure probe without another LLM request.

The frozen batch output is read-only. The candidate is a post-hoc development
repair, not a new batch pass or an independent formal-test result.
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
    "formal_30_v4_generalization_remaining_v1_task_manager_failed_20261027_195349/"
    "TaskManager_repaired_repaired_repaired.san"
)
SOURCE_SHA256 = "aded6e9a23166cea7eb84cf1f828a34e81411138c782c0bed306093efe56624d"
HISTORY = SOURCE.with_name("repair_history.json")
VUE = SOURCE.with_name("source.vue")
OUTPUT_DIR = ROOT / (
    "data/experiments/pipeline/manual_fixes/"
    "formal_30_v4_remaining_task_manager_bounded_v1"
)
OUTPUT = OUTPUT_DIR / "TaskManager_repaired.san"
REPORT = OUTPUT_DIR / "repair_report.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_exact(code: str, old: str, new: str, count: int = 1) -> str:
    found = code.count(old)
    if found != count:
        raise RuntimeError(f"Expected {count} occurrences, found {found}: {old[:80]!r}")
    return code.replace(old, new)


def build_candidate(code: str) -> str:
    # Preserve the Vue overdue comparison exactly, but put the computed call
    # on a pure helper instead of a component instance method.
    old_method = """  isOverdue(task) {
    if (task.completed || !task.dueDate) return false;
    const dueDate = new Date(task.dueDate);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return dueDate < today;
  },"""
    if code.count(old_method) != 1:
        raise RuntimeError("Expected exactly one parent isOverdue method")
    helper = old_method.replace("  isOverdue(task) {", "function isTaskOverdue(task) {").removesuffix(",")
    code = replace_exact(code, "module.exports = san.defineComponent({", helper + "\n\nmodule.exports = san.defineComponent({")
    code = replace_exact(code, old_method, "  isOverdue(task) {\n    return isTaskOverdue(task);\n  },")
    code = replace_exact(code, "this.isOverdue(task)", "isTaskOverdue(task)", 2)

    # Convert only the frozen output's Vue-style event bindings. Native
    # dragstart/dragend names differ from custom child drag-start/drag-end.
    code = replace_exact(code, 'on-dragover=""', 'on-dragover="prevent:onDragOver"')
    code = replace_exact(
        code,
        'draggable="{{ draggable }}" on-drag-start="onDragStart"',
        'draggable="{{ draggable }}" on-dragstart="onDragStart"',
    )
    code = replace_exact(code, 'on-dragover.prevent=""', 'on-dragover="prevent:onDragOver"')
    code = replace_exact(code, 'on-drop.stop="onDrop"', 'on-drop="stop:onDrop"')
    code = replace_exact(
        code,
        'on-drop="stop:onDrop" on-drag-end="onDragEnd"',
        'on-drop="stop:onDrop" on-dragend="onDragEnd"',
    )
    code = replace_exact(code, 'on-click.stop="fire(', 'on-click="stop:fire(', 2)
    code = replace_exact(code, 'on-keyup.enter="addComment"', 'on-keyup="enter:addComment"')
    code = replace_exact(code, 'on-submit.prevent="handleSubmit"', 'on-submit="prevent:handleSubmit"')
    code = replace_exact(
        code,
        "  onDragStart() {\n    if (!this.data.get('draggable')) return;",
        "  onDragOver() {},\n  onDragStart() {\n    if (!this.data.get('draggable')) return;",
    )
    code = replace_exact(
        code,
        "  onDropToEnd() {\n    const filteredTasks = this.data.get('filteredTasks');",
        "  onDragOver() {},\n  onDropToEnd() {\n    const filteredTasks = this.data.get('filteredTasks');",
    )
    return code


def main() -> None:
    if OUTPUT.exists() or REPORT.exists():
        raise FileExistsError("Candidate/report already exists; do not overwrite evidence")
    if sha256(SOURCE) != SOURCE_SHA256:
        raise RuntimeError("Frozen TaskManager source SHA-256 mismatch")
    source = SOURCE.read_text(encoding="utf-8")
    state = json.loads(HISTORY.read_text(encoding="utf-8"))["state"]
    candidate = build_candidate(source)
    validation = ValidateStage().run(ValidateStageInput(
        generated_code=candidate,
        ssm=state["ssm"],
        vue_file_path=str(VUE),
        compile_check=True,
    ))
    if not validation.validation_passed:
        raise RuntimeError(f"Candidate failed static/compile validation: {validation.validation_errors}")
    visual = VisualEvalStage().run(VisualEvalStageInput(
        vue_file_path=str(VUE), generated_code=candidate,
    ))
    if not visual.visual_eval_passed:
        raise RuntimeError(f"Candidate failed lightweight visual eval: {visual.visual_eval_errors}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(candidate, encoding="utf-8", newline="")
    report = {
        "sample_id": "TaskManager",
        "classification": "reused_development_posthoc_bounded_repair_probe",
        "independent_holdout": False,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": SOURCE.relative_to(ROOT).as_posix(),
        "source_sha256": SOURCE_SHA256,
        "candidate": OUTPUT.relative_to(ROOT).as_posix(),
        "candidate_sha256": sha256(OUTPUT),
        "scope": "Vue-style event syntax and computed overdue helper only",
        "validation_passed": True,
        "san_compile_passed": True,
        "lightweight_visual_passed": True,
        "structure_similarity": visual.structure_similarity,
        "browser_runtime": "pending_user_review",
        "boundary": "This is not a new automatic source-to-San pass; the original failed checkpoint remains unchanged.",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
