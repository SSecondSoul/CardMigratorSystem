"""Bounded replay of the frozen MonitoringDashboard syntax failure.

The failed batch and source snapshot remain immutable. This script writes a
separate post-hoc development candidate only after read-only checks pass.
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


FAILED = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_generalization_remaining_v1_monitoring_failed_20261027_205900"
)
SOURCE = FAILED / "MonitoringDashboard_repaired_repaired_repaired.san"
SOURCE_SHA256 = "aad664bed0f484018d09e2760e8481529bcf864736fa1b83131af9d8f1f5101f"
OUTPUT_DIR = ROOT / (
    "data/experiments/pipeline/manual_fixes/"
    "formal_30_v4_remaining_monitoring_syntax_v1"
)
OUTPUT = OUTPUT_DIR / "MonitoringDashboard_repaired.san"
REPORT = OUTPUT_DIR / "repair_report.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_exact(code: str, old: str, new: str, count: int = 1) -> str:
    found = code.count(old)
    if found != count:
        raise RuntimeError(f"Expected {count} occurrences, found {found}: {old[:100]!r}")
    return code.replace(old, new)


def build_candidate(code: str) -> str:
    # Identifiers must be valid JavaScript. Keep the original tag keys and
    # component name metadata; only rewrite declarations and registry values.
    child_identifiers = {
        "kpi-card": "KpiCard",
        "real-time-chart": "RealTimeChart",
        "request-chart": "RequestChart",
        "alert-list": "AlertList",
        "log-list": "LogList",
        "service-grid": "ServiceGrid",
        "settings-form": "SettingsForm",
    }
    for tag, identifier in child_identifiers.items():
        code = replace_exact(code, f"const {tag} = san.defineComponent({{",
                             f"const {identifier} = san.defineComponent({{")
        code = replace_exact(code, f"'{tag}': {tag}", f"'{tag}': {identifier}")

    code = replace_exact(code, 's-for="(point, idx) in dataPoints trackby idx"',
                         's-for="point, idx in dataPoints trackby idx"')
    code = replace_exact(code, 's-for="(item, idx) in data trackby idx"',
                         's-for="item, idx in data trackby idx"')
    code = replace_exact(code,
                         '<div class="notification" s-if="notification.show" class="{{notification.type}}">',
                         '<div class="notification {{notification.type}}" s-if="notification.show">')
    code = replace_exact(code, 'on-submit.prevent="handleSubmit"',
                         'on-submit="prevent:handleSubmit"')
    code = replace_exact(code, 'on-click="showSettings = true"',
                         'on-click="openSettings"')
    code = replace_exact(code, 'on-click="showSettings = false"',
                         'on-click="closeSettings"', 2)
    code = replace_exact(code, 'on-cancel="showSettings = false"',
                         'on-cancel="closeSettings"')

    # San dispatches one custom-event payload; the parent's method only
    # receives it when the binding explicitly mentions $event.
    for name, method in (
        ("bar-click", "onBarClick"),
        ("acknowledge", "acknowledgeAlert"),
        ("resolve", "resolveAlert"),
        ("log-click", "onLogClick"),
        ("service-click", "onServiceClick"),
        ("save", "saveSettings"),
    ):
        code = replace_exact(code, f'on-{name}="{method}"',
                             f'on-{name}="{method}($event)"')

    # Vue's @click.self must not close the settings modal for inner clicks.
    code = replace_exact(code, '<div class="modal-content">',
                         '<div class="modal-content" on-click="stop:onModalContentClick">')
    code = replace_exact(
        code,
        "  toggleTheme() {",
        """  openSettings() {
    this.data.set('showSettings', true);
  },
  closeSettings() {
    this.data.set('showSettings', false);
  },
  onModalContentClick() {},
  toggleTheme() {""",
    )

    # Once the script compiles, the validator can see four hidden reactive
    # chart dependencies. Expose those values in template calls and pass them
    # through unchanged so dots, lines, and request bars update together.
    code = replace_exact(code, 'cx="{{getX(idx)}}"',
                         'cx="{{getX(idx, dataPoints, width)}}"')
    code = replace_exact(code, 'cy="{{getY(point)}}"',
                         'cy="{{getY(point, height, maxValue, minValue)}}"')
    code = replace_exact(code, 'x="{{getX(idx)}}"',
                         'x="{{getX(idx, data)}}"')
    code = replace_exact(code, 'x="{{getX(idx) + barWidth / 2}}"',
                         'x="{{getX(idx, data) + barWidth / 2}}"')
    code = replace_exact(code, 'height="{{getHeight(item.count)}}"',
                         'height="{{getHeight(item.count, maxCount)}}"')
    code = replace_exact(
        code,
        """  getX(index) {
    const points = this.data.get('dataPoints') || [];
    const width = this.data.get('width') || 600;
    if (points.length <= 1) return width / 2;
    return (index / (points.length - 1)) * width;
  },
  getY(value) {
    const points = this.data.get('dataPoints') || [];
    const height = this.data.get('height') || 250;
    const maxValue = this.data.get('maxValue') || 100;
    const minValue = this.data.get('minValue') || 0;
    const range = maxValue - minValue;
    if (range === 0) return height / 2;
    return height - ((value - minValue) / range) * height;
  }""",
        """  getX(index, points, width) {
    if (points.length <= 1) return width / 2;
    return (index / (points.length - 1)) * width;
  },
  getY(value, height, maxValue, minValue) {
    const range = maxValue - minValue;
    if (range === 0) return height / 2;
    return height - ((value - minValue) / range) * height;
  }""",
    )
    code = replace_exact(
        code,
        """  getX(index) {
    const data = this.data.get('data') || [];
    return (index * 800) / data.length + 2;
  },
  getHeight(count) {
    const maxCount = this.data.get('maxCount') || 100;
    return (count / maxCount) * 280;
  },""",
        """  getX(index, data) {
    return (index * 800) / data.length + 2;
  },
  getHeight(count, maxCount) {
    return (count / maxCount) * 280;
  },""",
    )
    return code


def check_candidate(candidate: str) -> tuple[object, object]:
    state = json.loads((FAILED / "repair_history.json").read_text(encoding="utf-8"))["state"]
    validation = ValidateStage().run(ValidateStageInput(
        generated_code=candidate,
        ssm=state["ssm"],
        vue_file_path=str(FAILED / "source.vue"),
        compile_check=True,
    ))
    visual = VisualEvalStage().run(VisualEvalStageInput(
        vue_file_path=str(FAILED / "source.vue"),
        generated_code=candidate,
    ))
    return validation, visual


def main() -> None:
    if OUTPUT.exists() or REPORT.exists():
        raise FileExistsError("Candidate/report already exists; do not overwrite evidence")
    if sha256(SOURCE) != SOURCE_SHA256:
        raise RuntimeError("Frozen MonitoringDashboard source SHA-256 mismatch")
    candidate = build_candidate(SOURCE.read_text(encoding="utf-8"))
    validation, visual = check_candidate(candidate)
    if not validation.validation_passed:
        raise RuntimeError(f"Static/compile errors: {validation.validation_errors}")
    if not visual.visual_eval_passed:
        raise RuntimeError(f"Lightweight visual errors: {visual.visual_eval_errors}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(candidate, encoding="utf-8", newline="")
    report = {
        "sample_id": "MonitoringDashboard",
        "classification": "reused_development_posthoc_bounded_syntax_probe",
        "independent_holdout": False,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": SOURCE.relative_to(ROOT).as_posix(),
        "source_sha256": SOURCE_SHA256,
        "candidate": OUTPUT.relative_to(ROOT).as_posix(),
        "candidate_sha256": sha256(OUTPUT),
        "scope": "Seven inline component identifiers and registrations, five invalid events, two loop aliases, one duplicate class, explicit custom-event payloads, modal click isolation, and four chart reactive dependencies",
        "validation_passed": True,
        "san_compile_passed": True,
        "lightweight_visual_passed": True,
        "structure_similarity": visual.structure_similarity,
        "browser_runtime": "pending_user_review",
        "boundary": "Not a fresh automatic batch pass; the frozen failed checkpoint is unchanged.",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
