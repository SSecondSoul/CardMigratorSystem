"""Derive an explicit-dependency chart candidate from the frozen v2 probe.

This is a development-only, source-hash-guarded repair; it does not mutate the
frozen source or represent a new independent formal-test result.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput


SOURCE = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_analytics_computed_focus_probe_v2_static_pass_20261027_152434/"
    "candidate.san"
)
EXPECTED_SHA256 = "c0503283250a6467d7a6cb4e8a03caae057197ed9d5b11d82d316994d0d6c647"
OUTPUT_DIR = ROOT / (
    "data/experiments/pipeline/manual_fixes/"
    "formal_30_v4_analytics_chart_reactivity_v3"
)
OUTPUT = OUTPUT_DIR / "AnalyticsDashboard_repaired.san"
REPORT = OUTPUT_DIR / "repair_report.json"


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def replace_once(code: str, old: str, new: str, expected_count: int = 1) -> str:
    count = code.count(old)
    if count != expected_count:
        raise RuntimeError(f"Expected {expected_count} instances, found {count}: {old[:80]}")
    return code.replace(old, new)


def build_candidate(code: str) -> str:
    code = replace_once(code, "getX(idx) }}", "getX(idx, data.length) }}", 2)
    code = replace_once(
        code, "getY(point.value) }}", "getY(point.value, maxValue, minValue) }}"
    )
    code = replace_once(
        code, "getY(point.value) - 10 }}",
        "getY(point.value, maxValue, minValue) - 10 }}",
    )
    code = replace_once(
        code,
        """  getX(index) {
    const data = this.data.get('data');
    if (data.length <= 1) return 400;
    return (index / (data.length - 1)) * 800;
  },
  getY(value) {
    const maxValue = this.data.get('maxValue');
    const minValue = this.data.get('minValue');
    const range = maxValue - minValue;
    if (range === 0) return 150;
    return 300 - ((value - minValue) / range) * 280;
  },""",
        """  getX(index, dataLength) {
    return getXForChart(index, dataLength);
  },
  getY(value, maxValue, minValue) {
    return getYForChart(value, maxValue, minValue);
  },""",
    )
    return code


def main() -> None:
    source_bytes = SOURCE.read_bytes()
    if sha256(source_bytes) != EXPECTED_SHA256:
        raise RuntimeError("Frozen v2 candidate SHA-256 mismatch")
    if OUTPUT.exists() or REPORT.exists():
        raise FileExistsError("v3 candidate/report already exists; preserve the existing evidence")
    source = SOURCE.read_text(encoding="utf-8")
    candidate = build_candidate(source)
    validation = ValidateStage().run(ValidateStageInput(
        generated_code=candidate, compile_check=False,
    ))
    errors = validation.validation_errors
    if errors:
        raise RuntimeError(f"Candidate failed static validation: {errors}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(candidate, encoding="utf-8", newline="")
    report = {
        "sample_id": "analytics_dashboard",
        "classification": "reused_development_manual_repair_candidate",
        "independent_holdout": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": EXPECTED_SHA256,
        "candidate": str(OUTPUT.relative_to(ROOT)).replace("\\", "/"),
        "candidate_sha256": sha256(OUTPUT.read_bytes()),
        "fix_scope": "TrendChart inline template coordinate bindings and matching methods only",
        "validation_passed": True,
        "browser_runtime": "pending_user_recheck",
        "vue_comparison": "not_checked",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
