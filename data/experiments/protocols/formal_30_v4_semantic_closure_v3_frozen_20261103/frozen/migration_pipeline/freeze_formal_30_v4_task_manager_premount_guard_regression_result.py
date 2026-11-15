"""Freeze the untouched TaskManager pre-mount-guard development regression."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from migration_pipeline import freeze_formal_30_v4_semantic_focus_sample as freezer
from migration_pipeline.freeze_formal_30_v4_task_manager_premount_guard_regression_pre_run import (
    TARGET as PRE_RUN,
    verify,
)


def main() -> None:
    verify(PRE_RUN)
    freezer.BATCH_ID = "formal_30_v4_task_manager_premount_guard_regression_v1"
    freezer.CONFIG = ROOT / f"migration_pipeline/batch_configs/{freezer.BATCH_ID}.json"
    freezer.SUMMARY = ROOT / f"data/experiments/batch_reports/{freezer.BATCH_ID}_summary.json"
    freezer.PRE_RUN = PRE_RUN
    original_argv = sys.argv
    try:
        sys.argv = [original_argv[0], "--sample-id", "TaskManager"]
        freezer.main()
    finally:
        sys.argv = original_argv


if __name__ == "__main__":
    main()
