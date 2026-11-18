"""Read-only replay of frozen targets; no model, DB, queue or old report writes."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT/'src'))
from card_migration_system.adapters.legacy_checks import legacy_stage
from card_migration_system.adapters.browser import BrowserEvaluator
from card_migration_system.adapters.engine import verify_engine
from card_migration_system.config import load_settings
from card_migration_system.stages.evaluation import assess


def hashes(folder):
    return {p.relative_to(folder).as_posix():sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob('*')) if p.is_file()}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-dir',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args();frozen=args.evidence_dir.resolve();output=args.output_dir.resolve()
    if output.exists() or not output.is_relative_to(PROJECT/'var'):
        raise ValueError('Choose a NEW output directory below project/var')
    original=hashes(frozen)
    verify_engine(PROJECT/'engine')
    settings=load_settings(project_root=PROJECT,environ={})
    output.mkdir(parents=True)
    summaries=[]
    for folder in sorted(p for p in frozen.iterdir() if p.is_dir()):
        request=json.loads((folder/'request.json').read_bytes())['request']
        payload=json.loads((folder/'ssm.json').read_bytes());ssm=payload['ssm']
        source_bytes=(folder/'source.vue').read_bytes();source=source_bytes.decode('utf-8')
        if sha256(source_bytes).hexdigest()!=request['source_sha256'] or payload['source_sha256']!=request['source_sha256']:
            raise ValueError('Frozen source identity mismatch')
        code=(folder/'revisions/1.san').read_text(encoding='utf-8')
        old=json.loads((folder/'evaluations/1.json').read_bytes())
        static=legacy_stage(PROJECT/'engine','validate',source=source,code=code,ssm=ssm)
        browser=BrowserEvaluator(settings,request['runtime']).evaluate(source,code,request['props'],request['actions'])
        result=assess(static,browser,request['actions'],request['thresholds'],ssm)
        for side in ('vue','san'):browser[side].pop('png',None)
        browser['image'].pop('heatmap',None)
        target=output/folder.name;target.mkdir()
        for name,value in [('static',static),('browser',browser),('evaluation',result)]:
            (target/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
        summaries.append({'historical_run_id':folder.name,'source_sha256':request['source_sha256'],
            'revision_sha256':sha256((folder/'revisions/1.san').read_bytes()).hexdigest(),
            'before':{'dimensions':old['dimensions'],'codes':[d['code'] for d in old['diagnostics']],
                'structure_ted':old['structure_ted'],'dom_ted':old['dom_ted']},
            'after':{'dimensions':result['dimensions'],'codes':[d['code'] for d in result['diagnostics']],
                'structure_ted':result['structure_ted'],'dom_ted':result['dom_ted'],
                'representation_difference_count':len(result['dom_representation_differences']),
                'dynamic_contracts':[c for c in result['source_method_contracts'] if c.get('dynamic_assignment')]}})
    if hashes(frozen)!=original:raise ValueError('Frozen evidence was modified')
    summary={'scope':'offline_reassessment_of_unchanged_frozen_targets_not_a_new_model_experiment',
        'support_scope':'san-supported-migration-v4','actual_model_calls':0,'database_updated':False,
        'generation_prompt_changed':False,'thresholds_changed':False,'source_or_target_rewritten':False,
        'historical_results_reclassified':False,'frozen_sha256':original,'results':summaries}
    (output/'report.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'scope':summary['scope'],'actual_model_calls':0,'results':[
        {'run_id':r['historical_run_id'],'before':r['before']['codes'],'after':r['after']['codes'],
         'dimensions':r['after']['dimensions'],'template_similarity':r['after']['structure_ted']['similarity']}
        for r in summaries]},ensure_ascii=True,indent=2))


if __name__=='__main__':main()
