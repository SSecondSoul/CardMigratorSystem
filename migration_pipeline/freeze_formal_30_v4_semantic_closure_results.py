"""Freeze bounded semantic closure results before detailed diagnosis."""

from pathlib import Path

from migration_pipeline.freeze_formal_30_v4_repair_scheduling_results import freeze_results
from migration_pipeline.run_formal_30_v4_semantic_closure import BATCH_ID, CONFIG, PROTOCOL


if __name__ == '__main__':
    freeze_results(batch_id=BATCH_ID, config_path=CONFIG, protocol_path=PROTOCOL,
                   classification='bounded_semantic_closure_development_regression_raw_result',
                   extra_sources=(Path(__file__),))
