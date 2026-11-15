"""Create a third immutable-derived AnalyticsDashboard browser-review candidate."""

from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / (
    "data/experiments/pipeline/manual_fixes/formal_30_v4_analytics_runtime_followup/"
    "AnalyticsDashboard_computed_context_and_hover.san"
)
SOURCE_SHA256 = "08f848ec0157583a94690a23de5e813bb3d508abee3cce0c7ba4159b5a274e79"
TARGET = SOURCE.with_name("AnalyticsDashboard_visual_bindings.san")


def replace_once(code: str, old: str, new: str) -> str:
    count = code.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one source fragment, found {count}: {old[:80]!r}")
    return code.replace(old, new, 1)


def main() -> None:
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise RuntimeError("Second candidate hash changed")
    if TARGET.exists():
        raise FileExistsError(TARGET)
    code = SOURCE.read_text(encoding="utf-8")
    code = replace_once(code, "{{ Math.abs(change) }}%", "{{ formatChange(change) }}%")
    code = replace_once(
        code,
        """  formatValue(value) {
    if (value >= 1000000)""",
        """  formatChange(change) {
    return Math.abs(change);
  },
  formatValue(value) {
    if (value >= 1000000)""",
    )
    code = replace_once(
        code,
        'style="{{ { backgroundColor: insight.color } }}"',
        'style="{{ \'background-color: \' + insight.color + \';\' }}"',
    )
    TARGET.write_text(code, encoding="utf-8")
    print(f"candidate: {TARGET.relative_to(ROOT)}")
    print(f"sha256: {hashlib.sha256(TARGET.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
