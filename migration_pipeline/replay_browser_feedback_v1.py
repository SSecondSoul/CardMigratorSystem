"""Replay sealed S2 recordings into separated feedback. No browser/model calls."""
import argparse
import hashlib
import json
from pathlib import Path

from migration_pipeline.utils.browser_feedback_v1 import convert_recording, verify_seal

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'data/experiments/analysis/browser_feedback_routing_v1_20261115'


def replay(output_dir=None):
    baseline = json.loads((BASE / 'baseline.json').read_text(encoding='utf-8'))
    for path, digest in {**baseline['protected'], **baseline['manual']}.items():
        if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != digest:
            raise RuntimeError('Previous implementation/manual drift: ' + path)
    prior = ROOT / baseline['prior_seal']['path']
    directory = prior.parent
    pin = baseline['prior_seal']['sha256']
    verify_seal(directory, pin)
    packets = {}
    for name in ['corrected_run', 'repeat', 'run', 'gutter_counterfactual', 'controls']:
        binding = 'prepared/manifest.json' if name != 'controls' else None
        packets[name] = convert_recording(directory, pin, name, binding)
    final = packets['corrected_run']
    actions = [scene['recommended_action'] for scene in final['scenes']]
    assert actions == ['visual_match_only'] * 4 + ['review_source_oracle'], actions
    assert len([i for i in final['scenes'][-1]['issues'] if i['channel'] == 'source_oracle']) == 10
    assert all(not s['target_feedback_eligible'] and not s['repair_dispatch_allowed'] for s in final['scenes'])
    assert packets['repeat']['scenes'] == final['scenes'] or [s['recommended_action'] for s in packets['repeat']['scenes']] == actions
    assert all(s['recommended_action'] == 'review_evaluator_or_evidence' for s in packets['gutter_counterfactual']['scenes'])
    assert packets['controls']['scenes'][3]['recommended_action'] == 'review_target_candidate'
    assert not packets['controls']['scenes'][3]['target_feedback_eligible']  # HTML size control, no bound source/target component pair.
    summary = {'classification': 'sealed_recording_feedback_and_offline_admission_not_production_integration',
               'actions': actions, 'source_warning_events': 10, 'observed_analytics_rect_differences': 7,
               'target_repair_previews_for_real_scenes': 0, 'auto_dispatch_allowed': False,
               'source_warning_converted_to_target_failure': False, 'historical_batch': baseline['original_batch'],
               'semantic_block_bypassed': False, 'model_calls': 0, 'browser_started': False,
               'production_or_prompt_changed': False, 'new_manual_confirmation': False}
    if output_dir is not None:
        output = Path(output_dir).resolve()
        output.mkdir(parents=True, exist_ok=False)
        for name, value in [('summary', summary), *packets.items()]:
            with (output / (name + '.json')).open('x', encoding='utf-8') as stream:
                json.dump(value, stream, ensure_ascii=False, indent=2)
    return {'summary': summary, 'packets': packets}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir')
    args = parser.parse_args()
    print(json.dumps(replay(args.output_dir)['summary'], ensure_ascii=False, indent=2))
