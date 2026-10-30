"""Freeze v2 inputs using the audited v1 pre-run freezer with new paths."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from migration_pipeline import freeze_formal_30_v4_semantic_focus_pre_run as freezer


def main() -> None:
    old_config = freezer.CONFIG
    old_analysis = Path(
        "data/experiments/analysis/formal_30_v4_generalization_gap_audit_20261027/semantic_focus_v1_pre_run.json"
    )
    freezer.BATCH_ID = "formal_30_v4_semantic_focus_v2"
    freezer.SNAPSHOT_ID = f"{freezer.BATCH_ID}_pre_run_20261027"
    freezer.TARGET = freezer.ROOT / "data/experiments/snapshots" / freezer.SNAPSHOT_ID
    freezer.CONFIG = Path("migration_pipeline/batch_configs") / f"{freezer.BATCH_ID}.json"
    freezer.PAYLOADS = [
        item for item in freezer.PAYLOADS if item not in (old_config, old_analysis)
    ] + [
        freezer.CONFIG,
        Path("data/experiments/analysis/formal_30_v4_generalization_gap_audit_20261027/semantic_focus_v2_pre_run.json"),
        Path("migration_pipeline/freeze_formal_30_v4_semantic_focus_v2_pre_run.py"),
    ]
    freezer.main()


if __name__ == "__main__":
    main()
