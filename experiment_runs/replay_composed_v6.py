"""All 70 latest frozen parents, bounded production rules and real browser gate.

No database imports, no model calls, no edits to any historical run. A separate
proposal is NOT a newly generated migration or an independent test result.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from hashlib import sha256
import argparse
import base64
import json
import shutil
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT/'migration_system'
sys.path.insert(0,str(PROJECT/'src'))
from analyze_coverage import read,write_once,hashed,RUNS
from replay_general_repairs_v3 import binding,evaluate
from card_migration_system.adapters.legacy_checks import legacy_stage
from card_migration_system.adapters.browser import BrowserEvaluator
from card_migration_system.adapters.engine import verify_engine
from card_migration_system.config import load_settings
from card_migration_system.runtime import profile
from card_migration_system.stages.normalization import normalize_proposal
from card_migration_system.stages.evaluation import candidate_decision


def raw_evidence(folder,label,raw):
    if not raw:return
    for name,side in [('vue',raw.get('vue',{})),('san',raw.get('san',{})),('heatmap',raw.get('image',{}))]:
        key='heatmap' if name=='heatmap' else 'png'
        if side.get(key):
            data=base64.b64decode(side.pop(key));path=folder/(label+'-'+name+'.png');path.parent.mkdir(parents=True,exist_ok=True)
            if path.exists():
                if path.read_bytes()!=data:raise ValueError('immutable_image_differs')
            else:
                with path.open('xb') as f:f.write(data)
    write_once(folder/(label+'-browser.json'),raw)


def replay(pair,output,settings,runtime,reference=None):
    row=pair['new'];folder=RUNS/row['report'];folder=folder.parent
    report=read(folder/'report.json');artifact=folder/'artifacts'
    dest=output/row['sample_id'];assessment=report.get('assessment') or {}
    if (dest/'result.json').exists():return read(dest/'result.json')
    result={'component':row['component'],'complexity':row['complexity'],'historical_passed':row['passed'],
            'scope':'offline_frozen_artifact_proposal_not_fresh_generation','model_calls':0,'source_report':row['report']}
    revisions=[read(p) for p in (artifact/'revisions').glob('*.json')]
    parent=next((r for r in revisions if r['file']['sha256']==assessment.get('revision_sha256')),None)
    if not parent:
        result.update(status='no_accepted_code_unknown_model_outcome_not_retried',effective_passed=False)
        write_once(dest/'result.json',result);return result
    # Match accepted parent hash, never assume the highest revision was accepted.
    code=(artifact/'revisions'/f'{parent["number"]}.san').read_bytes().decode('utf-8')
    if sha256(code.encode()).hexdigest()!=parent['file']['sha256']:raise ValueError('parent_hash_mismatch')
    source_file=next((RUNS/row['batch']/'inputs'/folder.name).glob('*.vue'))
    source=source_file.read_bytes().decode('utf-8')
    if hashed(source_file)!=row['source_sha256']:raise ValueError('source_hash_mismatch')
    ssm=read(artifact/'ssm.json')['ssm']
    normalized=normalize_proposal(settings,legacy_stage,BrowserEvaluator(settings,runtime),source,code,ssm,assessment)
    candidate=normalized.pop('code')
    write_once(dest/'normalization.json',normalized);write_once(dest/'candidate.san',candidate)
    result.update(status='replayed',changed=code!=candidate,parent_sha256=parent['file']['sha256'],
                  candidate_sha256=sha256(candidate.encode()).hexdigest(),changes=normalized['changes'])
    request=read(artifact/'request.json')['request']
    spec={'props':request['props'],'actions':request['actions'],'thresholds':request['thresholds']}
    prior=read(reference/row['sample_id']/'result.json') if reference and (reference/row['sample_id']/'result.json').exists() else None
    if prior and prior.get('candidate_sha256')==result['candidate_sha256'] and prior.get('parent_sha256')==result['parent_sha256']:
        # EXACT accepted/candidate bytes and unchanged capture logic. Do not
        # fabricate new render witnesses or rerun historical random sources.
        for k in ('before','after','gate','effective_passed'):
            if k in prior:result[k]=prior[k]
        result['render_evidence']='v6_identical_code_capture_reused_NOT_a_new_browser_capture'
        result['reused_result']={'relative_path':str((reference/row['sample_id']/'result.json').relative_to(RUNS)),
                                 'sha256':hashed(reference/row['sample_id']/'result.json')}
    elif candidate!=code:
        for label,text in [('before',code),('after',candidate)]:
            observed,raw=evaluate(settings,runtime,source,text,ssm,spec)
            result[label]=observed;raw_evidence(dest,label,raw)
        if not result['before'].get('blocked') and not result['after'].get('blocked'):
            result['gate']=candidate_decision(result['before'],result['after'])
            result['effective_passed']=(result['after'] if result['gate']['accepted'] else result['before'])['passed']
        else:result['effective_passed']=False
    else:
        result.update(effective_passed=row['passed'],render_evidence='unchanged_parent_historical_capture_reused_no_new_browser_claim')
    write_once(dest/'result.json',result)
    print(json.dumps({k:result.get(k) for k in ('component','changed','effective_passed','gate')},ensure_ascii=True),flush=True)
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='composed_v6_replay_20261119');parser.add_argument('--workers',type=int,default=2)
    parser.add_argument('--policy',choices=['composed_source_proven_rules_v6','composed_source_proven_rules_v7'],default='composed_source_proven_rules_v6')
    parser.add_argument('--reference');parser.add_argument('--seed')
    args=parser.parse_args();output=RUNS/args.output
    if output.exists():raise ValueError('choose_new_immutable_output_directory')
    pairs=read(RUNS/'analysis_v3_vs_first70_20261119/pairs.json')
    inputs=read(RUNS/'analysis_v3_vs_first70_20261119/input_sha256.json')
    for relative,digest in inputs.items():
        if hashed(RUNS/relative)!=digest:raise ValueError('frozen_input_drift:'+relative)
    settings=load_settings(project_root=PROJECT,environ={});runtime=profile(settings);verify_engine(settings.repository_root)
    implementation=binding()
    reuse={};reference=RUNS/args.reference if args.reference else None
    if reference:
        previous=read(reference/'protocol.json')
        if previous['runtime']!=runtime['browser']:raise ValueError('reference_runtime_differs')
        def capture_text(p):return p.read_text(encoding='utf-8').split('async function capture(',1)[1].split('\nlet browser',1)[0]
        if capture_text(reference/'implementation/browser/evaluate.mjs')!=capture_text(PROJECT/'browser/evaluate.mjs'):
            raise ValueError('capture_logic_changed_cannot_reuse')
        for line in (reference/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
            digest,relative=line.split('  ',1)
            if hashed(reference/relative)!=digest:raise ValueError('reference_hash_drift:'+relative)
        reuse['reference']={'directory':args.reference,'protocol_sha256':hashed(reference/'protocol.json'),
                            'sha256sums_sha256':hashed(reference/'SHA256SUMS.txt'),'capture_logic_byte_identical':True}
    if args.seed:
        seed=RUNS/args.seed
        if read(seed/'protocol.json')['implementation_sha256']!=implementation:raise ValueError('seed_implementation_differs')
        reused={}
        for pair in pairs:
            folder=seed/pair['new']['sample_id']
            if not (folder/'result.json').exists():continue
            value=read(folder/'result.json')
            if value['component']!=pair['component']:raise ValueError('seed_row_mismatch')
            if value.get('candidate_sha256') and hashed(folder/'candidate.san')!=value['candidate_sha256']:raise ValueError('seed_code_hash_mismatch')
            for path in folder.rglob('*'):
                if path.is_file():reused[path.relative_to(seed).as_posix()]=hashed(path)
            shutil.copytree(folder,output/pair['new']['sample_id'])
        reuse['seed']={'directory':args.seed,'files_sha256':reused,'scope':'completed_rows_only_same_implementation_no_overwrite'}
    write_once(output/'protocol.json',{'input_sha256':inputs,'implementation_sha256':implementation,'model_calls':0,
        'runtime':runtime['browser'],'rows':70,'policy':args.policy,'replay_script_sha256':hashed(Path(__file__)),
        'reused_evidence':reuse,
        'scope':'offline_frozen_parent_replay_NOT_new_real_model_pass_rate'})
    results=[]
    with ThreadPoolExecutor(max_workers=min(2,max(1,args.workers))) as pool:
        pending={pool.submit(replay,pair,output,settings,runtime,reference):pair for pair in pairs}
        for future in as_completed(pending):
            try:results.append(future.result())
            except Exception as e:
                pair=pending[future];value={'component':pair['component'],'status':'replay_error','error':str(e),'effective_passed':False}
                write_once(output/pair['new']['sample_id']/'error.json',value);results.append(value)
                print(json.dumps(value,ensure_ascii=True),flush=True)
            print(json.dumps({'completed':len(results),'total':70}),flush=True)
    if implementation!=binding():raise ValueError('implementation_changed_during_replay')
    for relative,digest in inputs.items():
        if hashed(RUNS/relative)!=digest:raise ValueError('frozen_input_changed_during_replay')
    results.sort(key=lambda r:r['component'])
    summary={'scope':'offline_frozen_parent_replay_NOT_new_real_model_pass_rate','records':len(results),
        'model_calls':0,'changed':sum(bool(r.get('changed')) for r in results),
        'effective_passed':sum(bool(r.get('effective_passed')) for r in results),
        'statuses':dict(Counter(r['status'] for r in results)),
        'gates':dict(Counter(r['gate']['reason'] for r in results if 'gate' in r)),
        'frozen_files_verified_unchanged':len(inputs),'implementation_unchanged':True}
    write_once(output/'results.json',results);write_once(output/'summary.json',summary)
    write_once(output/'SHA256SUMS.txt',''.join(hashed(p)+'  '+p.relative_to(output).as_posix()+'\n' for p in sorted(output.rglob('*')) if p.is_file()))
    print(json.dumps(summary,ensure_ascii=True),flush=True)


if __name__=='__main__':main()
