"""Create an auditable candidate for the AnalyticsDashboard computed-context defect.

The frozen automatic-pass artifact is read only. This exact-source transform is
sample-specific; the reusable prevention is the validator and prompt rule.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_analytics_runtime_followup_automatic_pass_20261026_160213/"
    "pipeline/complex/AnalyticsDashboard_repaired_repaired_repaired.san"
)
SOURCE_SHA256 = "8114fb79591fef950a79d9e154b65d3e8c7bd3047a4ef6ef31eff279e99dfd41"
TARGET = ROOT / (
    "data/experiments/pipeline/manual_fixes/formal_30_v4_analytics_runtime_followup/"
    "AnalyticsDashboard_computed_context.san"
)


def replace_once(code: str, old: str, new: str) -> str:
    count = code.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one source fragment, found {count}: {old[:80]!r}")
    return code.replace(old, new, 1)


def main() -> None:
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise RuntimeError("Frozen source hash changed")
    if TARGET.exists():
        raise FileExistsError(TARGET)
    code = SOURCE.read_text(encoding="utf-8")
    code = replace_once(
        code,
        "const TrendChart = san.defineComponent({",
        """function trendX(index, length) {
  if (length <= 1) return 400;
  return (index / (length - 1)) * 800;
}

function trendY(value, minValue, maxValue) {
  const range = maxValue - minValue;
  if (range === 0) return 150;
  return 300 - ((value - minValue) / range) * 280;
}

const TrendChart = san.defineComponent({""",
    )
    code = replace_once(
        code,
        """    linePoints() {
      const data = this.data.get('data');
      return data.map((point, idx) => `${this.getX(idx)},${this.getY(point.value)}`).join(' ');
    },
    areaPoints() {
      const data = this.data.get('data');
      const points = data.map((point, idx) => `${this.getX(idx)},${this.getY(point.value)}`);
      return `0,300 ${points.join(' ')} 800,300`;
    }""",
        """    linePoints() {
      const data = this.data.get('data');
      const maxValue = this.data.get('maxValue');
      const minValue = this.data.get('minValue');
      return data.map((point, idx) =>
        `${trendX(idx, data.length)},${trendY(point.value, minValue, maxValue)}`
      ).join(' ');
    },
    areaPoints() {
      const data = this.data.get('data');
      const maxValue = this.data.get('maxValue');
      const minValue = this.data.get('minValue');
      const points = data.map((point, idx) =>
        `${trendX(idx, data.length)},${trendY(point.value, minValue, maxValue)}`
      );
      return `0,300 ${points.join(' ')} 800,300`;
    }""",
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
        """  getX(index) {
    const data = this.data.get('data');
    return trendX(index, data.length);
  },
  getY(value) {
    const maxValue = this.data.get('maxValue');
    const minValue = this.data.get('minValue');
    return trendY(value, minValue, maxValue);
  },""",
    )
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(code, encoding="utf-8")
    print(f"candidate: {TARGET.relative_to(ROOT)}")
    print(f"sha256: {hashlib.sha256(TARGET.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
