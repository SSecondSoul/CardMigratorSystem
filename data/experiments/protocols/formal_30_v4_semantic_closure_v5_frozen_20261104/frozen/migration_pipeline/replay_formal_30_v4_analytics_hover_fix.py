"""Create a second immutable-derived AnalyticsDashboard browser-review candidate."""

from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / (
    "data/experiments/pipeline/manual_fixes/formal_30_v4_analytics_runtime_followup/"
    "AnalyticsDashboard_computed_context.san"
)
SOURCE_SHA256 = "7b3ca2361caa5c2a2fe4edb78eb0bcc71db68af6b1703d866d4d4f9100ddecf8"
TARGET = SOURCE.with_name("AnalyticsDashboard_computed_context_and_hover.san")


def replace_once(code: str, old: str, new: str) -> str:
    count = code.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one source fragment, found {count}: {old[:80]!r}")
    return code.replace(old, new, 1)


def main() -> None:
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise RuntimeError("First candidate hash changed")
    if TARGET.exists():
        raise FileExistsError(TARGET)
    code = SOURCE.read_text(encoding="utf-8")
    code = replace_once(
        code,
        'on-mouseenter="hoveredIndex = index" on-mouseleave="hoveredIndex = null"',
        'on-mouseenter="setHoveredIndex(index)" on-mouseleave="clearHoveredIndex"',
    )
    code = replace_once(
        code,
        """  onPointClick(index, point) {
    this.fire('data-point-click', {""",
        """  setHoveredIndex(index) {
    this.data.set('hoveredIndex', index);
  },
  clearHoveredIndex() {
    this.data.set('hoveredIndex', null);
  },
  onPointClick(index, point) {
    this.fire('data-point-click', {""",
    )
    TARGET.write_text(code, encoding="utf-8")
    print(f"candidate: {TARGET.relative_to(ROOT)}")
    print(f"sha256: {hashlib.sha256(TARGET.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
