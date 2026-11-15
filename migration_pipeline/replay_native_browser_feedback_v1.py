"""Read-only pinned schema-3 replay into NEW offline feedback files; no model/browser."""
import argparse
import hashlib
import json
from pathlib import Path

from migration_pipeline.utils.native_browser_feedback_v1 import convert_recording

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data/experiments/analysis/native_browser_feedback_v1_20261115'


def execute(output_dir):
    baseline=json.loads((BASE/'baseline.json').read_text(encoding='utf-8'))
    for path,pin in {**baseline['protected'],**baseline['manual']}.items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=pin:
            raise RuntimeError('Protected baseline changed: '+path)
    output=Path(output_dir).resolve()
    if output.exists():raise FileExistsError('Never overwrite feedback evidence')
    previous=ROOT/baseline['prior_seal']['path']
    ref={**baseline['binding_reference'],'bundle_directory':str(ROOT/baseline['binding_reference']['bundle_directory'])}
    packets={}
    for name in ['controls','context_smoke','controls_retry','controls_final','controls_verified','frozen_components']:
        packets[name]=convert_recording(previous.parent,baseline['prior_seal']['sha256'],name,ref if name=='frozen_components' else None)
    output.mkdir(parents=True)
    for name,packet in packets.items():
        with (output/(name+'.json')).open('x',encoding='utf-8') as stream:
            json.dump(packet,stream,ensure_ascii=False,indent=2)
    actions={name:[s['recommended_action'] for s in packet['scenes']] for name,packet in packets.items()}
    summary={'actions':actions,'recordings':6,'model_calls':0,'browser_runs':0,'production_auto_dispatch':False,
             'actual_component_repair_previews':0,'old_scores_changed':False,'provenance':'native registry independently checked, no legacy schema downgrade'}
    with (output/'summary.json').open('x',encoding='utf-8') as stream:
        json.dump(summary,stream,ensure_ascii=False,indent=2)
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',default=str(BASE/'replay'))
    print(json.dumps(execute(parser.parse_args().output_dir),indent=2))
