"""Freeze semantic closure v2 raw outputs before diagnosis; no model call."""

import json
from pathlib import Path

from migration_pipeline.freeze_formal_30_v4_repair_scheduling_results import freeze_results
from migration_pipeline.run_formal_30_v4_semantic_closure_v2 import ROOT, BATCH_ID, CONFIG, PROTOCOL


if __name__ == '__main__':
    summary = json.loads((ROOT / f'data/experiments/batch_reports/{BATCH_ID}_summary.json').read_text(encoding='utf-8'))
    config = json.loads(CONFIG.read_text(encoding='utf-8'))
    if config.get('semantic_rule_set') != 'residual_v2' or any(
            s['status'] == 'completed' and s.get('semantic_rule_set') != 'residual_v2' for s in summary['samples']):
        raise RuntimeError('Unexpected semantic rule set')
    freeze_results(batch_id=BATCH_ID, config_path=CONFIG, protocol_path=PROTOCOL,
                   classification='semantic_recurrence_and_residual_v2_development_regression_raw_result',
                   extra_sources=(Path(__file__),))
