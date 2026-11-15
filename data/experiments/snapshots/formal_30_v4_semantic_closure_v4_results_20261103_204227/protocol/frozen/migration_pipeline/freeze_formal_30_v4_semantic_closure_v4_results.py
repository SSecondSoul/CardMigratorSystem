"""Freeze all raw single-sample v4 output before diagnosis; no model call."""

import json
from pathlib import Path

from migration_pipeline.freeze_formal_30_v4_repair_scheduling_results import freeze_results
from migration_pipeline.run_formal_30_v4_semantic_closure_v4 import ROOT, BATCH_ID, CONFIG, PROTOCOL


def main():
    summary = json.loads((ROOT / f'data/experiments/batch_reports/{BATCH_ID}_summary.json').read_text(encoding='utf-8'))
    config = json.loads(CONFIG.read_text(encoding='utf-8'))
    if (config['semantic_rule_set'] != 'residual_v2'
            or [s['id'] for s in config['samples']] != ['MonitoringDashboard']
            or [s['id'] for s in summary['samples']] != ['MonitoringDashboard']
            or any(s['status'] == 'completed' and s.get('semantic_rule_set') != 'residual_v2'
                   for s in summary['samples'])):
        raise RuntimeError('Unexpected sample or semantic rule set')
    return freeze_results(batch_id=BATCH_ID, config_path=CONFIG, protocol_path=PROTOCOL,
        classification='coverage_helper_closure_v4_single_sample_development_raw_result',
        extra_sources=(Path(__file__),))


if __name__ == '__main__':
    main()
