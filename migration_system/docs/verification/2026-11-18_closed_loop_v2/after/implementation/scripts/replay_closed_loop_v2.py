"""Offline generic repair replay of frozen jobs. No production DB/model access."""
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
from card_migration_system.stages.evaluation import assess,candidate_decision

FROZEN=PROJECT/'docs/verification/2026-11-18_closed_loop_v2'


def verify_freeze():
    manifest=json.loads((FROZEN/'FREEZE.json').read_bytes())
    for name,digest in manifest['files'].items():
        if sha256((FROZEN/name).read_bytes()).hexdigest()!=digest:raise ValueError('Frozen identity mismatch: '+name)
    return manifest


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-dir',type=Path,required=True)
    output=parser.parse_args().output_dir.resolve()
    if output.exists() or not output.is_relative_to(PROJECT/'var'):raise ValueError('Choose a NEW output below project/var')
    manifest=verify_freeze();verify_engine(PROJECT/'engine')
    settings=load_settings(project_root=PROJECT,environ={});output.mkdir(parents=True)
    summaries=[]
    for key in manifest['job_ids']:
        folder=FROZEN/'jobs'/key
        req=json.loads((folder/'request.json').read_bytes())['request']
        payload=json.loads((folder/'ssm.json').read_bytes());ssm=payload['ssm']
        source_bytes=(folder/'source.vue').read_bytes();source=source_bytes.decode('utf-8')
        if sha256(source_bytes).hexdigest()!=req['source_sha256'] or payload['source_sha256']!=req['source_sha256']:
            raise ValueError('Source mismatch')
        original_report=json.loads((folder/'report.json').read_bytes())
        revision=Path(original_report['final_artifact']['relative_path']).stem
        code=(folder/f'revisions/{revision}.san').read_text(encoding='utf-8')
        if sha256((folder/f'revisions/{revision}.san').read_bytes()).hexdigest()!=original_report['final_artifact']['sha256']:
            raise ValueError('Final target mismatch')
        before=json.loads((folder/f'evaluations/{revision}.json').read_bytes())
        def evaluate(label,target):
            static=legacy_stage(PROJECT/'engine','validate',source=source,code=target,ssm=ssm)
            browser=BrowserEvaluator(settings,req['runtime']).evaluate(source,target,req['props'],req['actions'])
            result=assess(static,browser,req['actions'],req['thresholds'],ssm)
            for side in ('vue','san'):browser[side].pop('png',None)
            browser['image'].pop('heatmap',None)
            write(output/key/(label+'.json'),{'static':static,'browser':browser,'evaluation':result})
            return result,static
        print('Replaying '+key,flush=True)
        after,static=evaluate('unchanged',code)
        item={'job_id':key,'source_sha256':req['source_sha256'],'original_revision':revision,
            'original_revision_sha256':original_report['final_artifact']['sha256'],
            'before':{'dimensions':before['dimensions'],'codes':[d['code'] for d in before['diagnostics']]},
            'unchanged':{'dimensions':after['dimensions'],'codes':[d['code'] for d in after['diagnostics']],
                'contracts':after['source_method_contracts']}}
        # Exercise the REAL generic deterministic repair entry, not a hand patch.
        proposal=legacy_stage(PROJECT/'engine','rules',source=source,code=code,ssm=ssm,errors=static['validation_errors'])
        if proposal['code']!=code:
            # Generated replay artifact only; never overwrite original target.
            (output/key/'rule-proposal.san').write_text(proposal['code'],encoding='utf-8')
            candidate,_=evaluate('rule-proposal',proposal['code'])
            item['rule_proposal']={'changes':proposal['changes'],'decision':candidate_decision(after,candidate),
                'dimensions':candidate['dimensions'],'codes':[d['code'] for d in candidate['diagnostics']],
                'sha256':sha256(proposal['code'].encode()).hexdigest()}
        # Replay historical candidate gates with refreshed diagnostics/witnesses.
        item['historical_candidate_gates']=[]
        for n in range(int(revision)+1,4):
            path=folder/f'evaluations/{n}/raw.json'
            if not path.exists():continue
            raw=json.loads(path.read_bytes())
            old_code=(folder/f'revisions/{n}.san').read_text(encoding='utf-8')
            updated_static=legacy_stage(PROJECT/'engine','validate',source=source,code=old_code,ssm=ssm)
            reassessed=assess(updated_static,raw['browser'],req['actions'],req['thresholds'],ssm)
            write(output/key/f'historical-candidate-{n}.json',reassessed)
            item['historical_candidate_gates'].append({'revision':n,'decision':candidate_decision(after,reassessed),
                'dimensions':reassessed['dimensions'],'codes':[d['code'] for d in reassessed['diagnostics']]})
        summaries.append(item);write(output/'progress.json',summaries)
    verify_freeze()
    report={'scope':'offline_replay_not_new_model_experiment_or_historical_reclassification',
        'actual_model_calls':0,'database_updated':False,'frozen_sources_targets_unchanged':True,
        'thresholds_changed':False,'rules_are_proposals_retested_by_real_browser':True,'results':summaries}
    write(output/'report.json',report)
    print(json.dumps({'scope':report['scope'],'actual_model_calls':0,'results':[
        {'job_id':r['job_id'],'unchanged':r['unchanged']['dimensions'],
         'rule_proposal':r.get('rule_proposal',{}).get('dimensions'),
         'historical_candidate_gates':r['historical_candidate_gates']} for r in summaries]},ensure_ascii=True,indent=2))


if __name__=='__main__':main()
