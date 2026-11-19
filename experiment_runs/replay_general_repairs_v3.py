"""Offline frozen-corpus replay against the real standalone stages. NO model/DB.

Never changes a historical task, report or generated file. This is development
evidence, NOT a fresh-generation pass rate. Versions and repeated rows stay split.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT/'migration_system'
sys.path.insert(0,str(PROJECT/'src'))
from analyze_coverage import collect,read,write_once,hashed
from card_migration_system.adapters.legacy_checks import legacy_stage
from card_migration_system.adapters.syntax import target_syntax
from card_migration_system.adapters.browser import BrowserEvaluator
from card_migration_system.adapters.engine import verify_engine
from card_migration_system.config import load_settings
from card_migration_system.runtime import profile
from card_migration_system.stages.evaluation import assess,candidate_decision
from card_migration_system.stages.syntax import failed_syntax
from card_migration_system.prompts.san_contract import repair_targets,CONSTRAINTS,SHA256


def binding():
    return {p.relative_to(PROJECT).as_posix():hashed(p) for root in ('browser','src/card_migration_system','engine')
            for p in sorted((PROJECT/root).rglob('*')) if p.is_file() and p.suffix in ('.py','.mjs','.cjs','.js','.json')
            and 'node_modules' not in p.parts and '__pycache__' not in p.parts}


def evaluate(settings,runtime,source,code,ssm,spec,static=None):
    syntax=target_syntax(settings,source,code)
    digest=sha256(code.encode()).hexdigest()
    if syntax['status']=='fail':return failed_syntax(syntax,digest),None
    static=static or legacy_stage(settings.repository_root,'validate',source=source,code=code,ssm=ssm)
    browser=BrowserEvaluator(settings,runtime).evaluate(source,code,spec['props'],spec['actions'])
    if browser.get('status')!='completed':return {'blocked':browser.get('diagnostic','target_compile_failed')},browser
    result=assess(static,browser,spec['actions'],spec['thresholds'],ssm)
    result.update(syntax=syntax,revision_sha256=digest)
    return result,browser


def replay(row,detail,settings,runtime,output,browser_checks):
    sample=detail['sample']; folder=detail['folder']; artifact=folder/'artifacts'
    dest=output/row['batch']/sample['slug']
    source=(ROOT/'experiment_runs'/row['batch']/sample['frozen_vue']).read_bytes().decode('utf-8')
    ssm_file=artifact/'ssm.json';assessment=detail['report'].get('assessment') or {}
    revisions=[read(p) for p in (artifact/'revisions').glob('*.json')]
    parent=next((r for r in revisions if r['file']['sha256']==assessment.get('revision_sha256')),None)
    result={'run_key':row['run_key'],'component':row['component'],'batch':row['batch'],
            'source_sha256':sample['vue_sha256'],'historical_passed':row['passed'],
            'scope':'offline_existing_parent_rule_replay_not_fresh_generation','model_calls':0,
            'historical_codes':sorted({d['code'] for d in assessment.get('diagnostics',[])})}
    if not parent:
        result['status']='no_accepted_code_model_output_incomplete_requires_new_generation'
        write_once(dest/'result.json',result);return result
    code=(artifact/'revisions'/f'{parent["number"]}.san').read_bytes().decode('utf-8')
    if sha256(code.encode()).hexdigest()!=parent['file']['sha256']:raise ValueError('parent_hash_mismatch')
    ssm=read(ssm_file)['ssm']; result['parent_sha256']=parent['file']['sha256']
    normalized=target_syntax(settings,source,code,normalize=True)
    candidate=normalized['code'];changes=list(normalized['changes'])
    # Mirror production syntax-first routing: never send an unparsed target to
    # the semantic stage just to produce a flattering offline repair count.
    static=None
    if normalized['after']['status']=='pass':
        static=legacy_stage(settings.repository_root,'validate',source=source,code=candidate,ssm=ssm)
        errors=static['validation_errors']+[d for d in assessment.get('diagnostics',[]) if d['code'].startswith(('rendered_','template_structure','dom_'))]
        rule=legacy_stage(settings.repository_root,'rules',source=source,code=candidate,ssm=ssm,errors=errors)
        if rule['code']!=candidate:
            candidate=rule['code'];changes.extend(rule['changes']);static=None
    after_syntax=target_syntax(settings,source,candidate)
    result.update(status='replayed',changed=candidate!=code,changes=changes,
                  candidate_sha256=sha256(candidate.encode()).hexdigest(),
                  syntax_before=normalized['before'],syntax_after=after_syntax)
    write_once(dest/'candidate.san',candidate)
    if after_syntax['status']=='pass':
        static=static or legacy_stage(settings.repository_root,'validate',source=source,code=candidate,ssm=ssm)
        result['static_after']={'passed':static['validation_passed'],'codes':sorted({e['code'] for e in static['validation_errors']})}
        write_once(dest/'static.json',static)
    result['repair_targets']=repair_targets([{'code':c} for c in result.get('static_after',{}).get('codes',result['historical_codes'])])
    if browser_checks:
        request=read(artifact/'request.json')['request']
        spec={'props':request.get('props',{}),'actions':request.get('actions',[]),
              'thresholds':request['thresholds']}
        for label,text,known in [('before',code,static if candidate==code else None),('after',candidate,static)]:
            if label=='after' and candidate==code:
                result['current_after']=result['current_before'];continue
            try:
                observed,raw=evaluate(settings,runtime,source,text,ssm,spec,known)
                result['current_'+label]=observed
                if raw:
                    for side in ('vue','san'):
                        if raw.get(side,{}).get('png'):
                            import base64
                            image=base64.b64decode(raw[side].pop('png'))
                            path=dest/f'{label}-{side}.png';path.parent.mkdir(parents=True,exist_ok=True)
                            with path.open('xb') as stream:stream.write(image)
                    write_once(dest/(label+'-browser.json'),raw)
            except Exception as exc:
                result['current_'+label]={'blocked':str(exc)}
        before,after=result['current_before'],result['current_after']
        if not before.get('blocked') and not after.get('blocked'):
            result['candidate_gate']=candidate_decision(before,after)
    write_once(dest/'result.json',result);return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='general_repairs_v3_replay_20261119')
    parser.add_argument('--workers',type=int,default=2);parser.add_argument('--browser',action='store_true')
    args=parser.parse_args()
    output=ROOT/'experiment_runs'/args.output
    if output.exists():raise SystemExit('Output already exists; choose a NEW output folder, never overwrite evidence.')
    settings=load_settings(project_root=PROJECT,environ={});runtime=profile(settings)
    verify_engine(settings.repository_root)
    rows,details,frozen,_,_=collect();implementation=binding()
    write_once(output/'implementation_sha256.json',implementation)
    write_once(output/'protocol.json',{'policy':'universal_source_bound_repairs_v3','browser_checks':args.browser,
        'model_calls':0,'data_access':'local_frozen_files_only','runtime':{'browser':runtime['browser']},
        'shared_san_contract_sha256':SHA256,'rows':len(rows),'components':70,
        'max_rule_proposals_per_parent':1,'fresh_generation':False,'input_integrity':frozen})
    completed=[]
    with ThreadPoolExecutor(max_workers=max(1,min(args.workers,3))) as pool:
        pending={pool.submit(replay,row,details[row['run_key']],settings,runtime,output,args.browser):row for row in rows}
        for future in as_completed(pending):
            row=pending[future]
            try:result=future.result()
            except Exception as exc:
                result={'run_key':row['run_key'],'batch':row['batch'],'component':row['component'],'status':'replay_error','error':str(exc)}
                write_once(output/row['batch']/details[row['run_key']]['sample']['slug']/'replay-error.json',result)
            completed.append(result)
            print(json.dumps({'completed':len(completed),'total':len(rows),'component':row['component'],
                'status':result['status'],'changed':result.get('changed'),'static_after':result.get('static_after',{}).get('passed'),
                'current_after':result.get('current_after',{}).get('dimensions',result.get('current_after',{}).get('blocked'))},ensure_ascii=True),flush=True)
    if binding()!=implementation:raise ValueError('runtime_changed_during_replay')
    if collect()[2]!=frozen:raise ValueError('frozen_evidence_changed')
    completed.sort(key=lambda x:x['run_key'])
    summary={'scope':'offline_existing_artifact_replay_NOT_new_70_generation_pass_rate','model_calls':0,
        'records':len(completed),'status':dict(Counter(r['status'] for r in completed)),
        'changed':sum(bool(r.get('changed')) for r in completed),
        'static_after_pass':sum(r.get('static_after',{}).get('passed') is True for r in completed),
        'current_before_pass':sum(r.get('current_before',{}).get('passed') is True for r in completed),
        'current_after_pass':sum(r.get('current_after',{}).get('passed') is True for r in completed),
        'gate_reasons':dict(Counter(r['candidate_gate']['reason'] for r in completed if 'candidate_gate' in r)),
        'before_frozen_file_count':len(frozen),'frozen_integrity_unchanged':True,'implementation_unchanged':True}
    write_once(output/'results.json',completed);write_once(output/'summary.json',summary)
    hashes={p.relative_to(output).as_posix():hashed(p) for p in sorted(output.rglob('*')) if p.is_file()}
    write_once(output/'SHA256SUMS.txt',''.join(v+'  '+k+'\n' for k,v in hashes.items()))
    print(json.dumps(summary,ensure_ascii=True),flush=True)


if __name__=='__main__':main()
