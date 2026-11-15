"""Freeze all 30 observed development results before diagnosis; never call a model."""
import json
from collections import Counter
from pathlib import Path

from migration_pipeline.run_formal_30_v4_full_regression_v2 import ROOT, BATCH_ID, CONFIG, PROTOCOL
from migration_pipeline.freeze_formal_30_v4_repair_scheduling_results import freeze_results


def main():
    config = json.loads(CONFIG.read_text(encoding='utf-8'))
    summary = json.loads((ROOT / f'data/experiments/batch_reports/{BATCH_ID}_summary.json').read_text(encoding='utf-8'))
    if (len(config['samples']) != 30 or len(summary['samples']) != 30
            or Counter(s['complexity'] for s in config['samples']) != Counter(simple=10, medium=10, complex=10)
            or config['semantic_rule_set'] != 'residual_v2'
            or any(s['status'] == 'completed' and s.get('semantic_rule_set') != 'residual_v2' for s in summary['samples'])):
        raise RuntimeError('Unexpected sample strata or rule set')
    return freeze_results(batch_id=BATCH_ID, config_path=CONFIG, protocol_path=PROTOCOL,
        classification='reused_development_full_30_semantic_closure_regression_v2_raw_result',
        extra_sources=(Path(__file__),))


if __name__ == '__main__':
    main()
