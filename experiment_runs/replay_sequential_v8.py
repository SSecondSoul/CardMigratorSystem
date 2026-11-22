"""Fresh frozen-parent assessments and bounded production rules, no model/DB.

Accepted v7 candidates are development parents, not new generation results.
Every proposed edit goes through the real browser and ordinary regression gate.
Historical files remain immutable. No random-source seeding or threshold waiver.
"""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
import argparse
import json
from pathlib import Path
import shutil

from analyze_coverage import read, write_once, hashed, RUNS
from replay_composed_v6 import raw_evidence
from replay_general_repairs_v3 import binding, evaluate, PROJECT
from card_migration_system.adapters.legacy_checks import legacy_stage
from card_migration_system.adapters.browser import BrowserEvaluator
from card_migration_system.adapters.engine import verify_engine
from card_migration_system.config import load_settings
from card_migration_system.runtime import profile
from card_migration_system.stages.normalization import normalize_proposal
from card_migration_system.stages.evaluation import candidate_decision


def fingerprint(code):
    return sha256(code.encode()).hexdigest()


def replay(pair, output, reference, settings, runtime):
    row = pair['new']
    dest = output/row['sample_id']
    prior = read(reference/row['sample_id']/'result.json')
    folder = (RUNS/row['report']).parent
    artifacts = folder/'artifacts'
    report = read(folder/'report.json')
    result = {'component':row['component'], 'sample_id':row['sample_id'],
        'complexity':row['complexity'], 'historical_real_model_passed':row['passed'],
        'v7_effective_passed':bool(prior.get('effective_passed')), 'source_report':row['report'],
        'scope':'offline_sequential_development_replay_NOT_fresh_generation', 'model_calls':0,
        'steps':[]}
    revisions = [read(p) for p in (artifacts/'revisions').glob('*.json')]
    parent = next((r for r in revisions if r['file']['sha256']==(report.get('assessment') or {}).get('revision_sha256')), None)
    if not parent:
        result.update(status='no_accepted_code_unknown_model_outcome_not_retried', effective_passed=False)
        write_once(dest/'result.json', result)
        return result
    code = (artifacts/'revisions'/f'{parent["number"]}.san').read_bytes().decode('utf-8')
    if fingerprint(code)!=parent['file']['sha256']:
        raise ValueError('accepted_historical_code_hash_mismatch')
    if prior.get('gate',{}).get('accepted'):
        code = (reference/row['sample_id']/'candidate.san').read_bytes().decode('utf-8')
        if fingerprint(code)!=prior['candidate_sha256']:
            raise ValueError('accepted_v7_code_hash_mismatch')
        result['parent_origin'] = 'v7_gate_accepted_candidate'
    else:
        result['parent_origin'] = 'historical_accepted_parent_v7_rejected_or_unchanged'
    result['parent_sha256'] = fingerprint(code)
    write_once(dest/'parent.san', code)
    source_file = next((RUNS/row['batch']/'inputs'/folder.name).glob('*.vue'))
    if hashed(source_file)!=row['source_sha256']:
        raise ValueError('source_hash_mismatch')
    source = source_file.read_bytes().decode('utf-8')
    ssm = read(artifacts/'ssm.json')['ssm']
    request = read(artifacts/'request.json')['request']
    spec = {k:request[k] for k in ('props','actions','thresholds')}
    current, raw = evaluate(settings,runtime,source,code,ssm,spec)
    raw_evidence(dest,'baseline',raw)
    write_once(dest/'baseline-assessment.json',current)
    result['fresh_baseline_passed'] = bool(current.get('passed'))
    result['baseline_dimensions'] = current.get('dimensions',{})
    result['baseline_codes'] = sorted({d['code'] for d in current.get('diagnostics',[])})
    # Same three configured proposal slots, not three extra model repair rounds.
    # This remains retrospective development, never added to original batch stats.
    rejected = set()
    rejected_on_parent = False
    limit = min(3,request.get('max_repair_rounds',3))
    for number in range(1,limit+1):
        if current.get('passed') or current.get('blocked'):
            break
        normalized = normalize_proposal(settings,legacy_stage,BrowserEvaluator(settings,runtime),
            source,code,ssm,current,prefer_runtime_recovery=not rejected_on_parent)
        candidate = normalized.pop('code')
        if candidate==code:
            result['stop'] = 'rule_fixed_point_requires_other_proven_rule_or_model'
            break
        candidate_sha = fingerprint(candidate)
        if (fingerprint(code),candidate_sha) in rejected:
            result['stop'] = 'repeated_rejected_candidate_not_retried'
            break
        prefix = f'step-{number}'
        write_once(dest/(prefix+'-normalization.json'),normalized)
        write_once(dest/(prefix+'.san'),candidate)
        after, raw = evaluate(settings,runtime,source,candidate,ssm,spec)
        raw_evidence(dest,prefix,raw)
        write_once(dest/(prefix+'-assessment.json'),after)
        gate = (candidate_decision(current,after) if not after.get('blocked')
                else {'accepted':False,'reason':'candidate_browser_blocked'})
        step = {'number':number,'parent_sha256':fingerprint(code),'candidate_sha256':candidate_sha,
            'normalization_stop':normalized['stop'],'changes':normalized['changes'], 'gate':gate,
            'passed':bool(after.get('passed')),'codes':sorted({d['code'] for d in after.get('diagnostics',[])})}
        result['steps'].append(step)
        if gate['accepted']:
            code,current = candidate,after
            rejected_on_parent = False
        else:
            rejected.add((fingerprint(code),candidate_sha))
            rejected_on_parent = True
    result.update(status='replayed',effective_passed=bool(current.get('passed')),
        effective_sha256=fingerprint(code),effective_dimensions=current.get('dimensions',{}),
        effective_codes=sorted({d['code'] for d in current.get('diagnostics',[])}))
    write_once(dest/'effective.san',code)
    write_once(dest/'effective-assessment.json',current)
    write_once(dest/'result.json',result)
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default='composed_v8_sequential_replay_20261120')
    parser.add_argument('--workers',type=int,choices=[1,2],default=2)
    args=parser.parse_args()
    output=RUNS/args.output
    if output.exists():raise ValueError('choose_new_immutable_directory')
    reference=RUNS/'composed_v7_verified_replay_20261119'
    historical=read(RUNS/'analysis_v3_vs_first70_20261119/input_sha256.json')
    prior_files={relative:digest for digest,relative in
        (line.split('  ',1) for line in (reference/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines())}
    for relative,digest in historical.items():
        if hashed(RUNS/relative)!=digest:raise ValueError('historical_input_drift:'+relative)
    for relative,digest in prior_files.items():
        if hashed(reference/relative)!=digest:raise ValueError('v7_reference_drift:'+relative)
    settings=load_settings(project_root=PROJECT,environ={});runtime=profile(settings)
    engine=verify_engine(settings.repository_root);implementation=binding()
    write_once(output/'protocol.json',{'scope':'offline_sequential_development_NOT_fresh_generation',
        'policy':'source_proven_sequential_rules_v8','model_calls':0,'cloud_database_access':False,
        'rows':70,'browser_workers':args.workers,'runtime':runtime['browser'],
        'max_proposals_per_row':3,'parent_selection':'only_v7_gate_accepted_candidate_else_historical_accepted_hash',
        'all_baselines_freshly_assessed':True,'threshold_changes':False,'seed_random_sources':False,
        'reference':reference.name,'reference_sha256sums':hashed(reference/'SHA256SUMS.txt'),
        'historical_input_sha256':historical,'reference_files_sha256':prior_files,
        'engine':engine,'implementation_sha256':implementation,'script_sha256':hashed(Path(__file__))})
    results=[]
    pairs=read(RUNS/'analysis_v3_vs_first70_20261119/pairs.json')
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(replay,pair,output,reference,settings,runtime):pair for pair in pairs}
        for future in as_completed(futures):
            pair=futures[future]
            try:result=future.result()
            except Exception as exc:
                result={'component':pair['component'],'sample_id':pair['new']['sample_id'],
                    'status':'replay_error','error':str(exc),'effective_passed':False}
                write_once(output/pair['new']['sample_id']/'error.json',result)
            results.append(result)
            print(json.dumps({'completed':len(results),'component':result['component'],
                'status':result['status'],'before':result.get('fresh_baseline_passed'),
                'passed':result['effective_passed'],'steps':len(result.get('steps',[])),
                'codes':result.get('effective_codes',result.get('error'))},ensure_ascii=True),flush=True)
    if binding()!=implementation:raise ValueError('implementation_changed_during_replay')
    for relative,digest in historical.items():
        if hashed(RUNS/relative)!=digest:raise ValueError('historical_input_changed:'+relative)
    for relative,digest in prior_files.items():
        if hashed(reference/relative)!=digest:raise ValueError('v7_reference_changed:'+relative)
    results.sort(key=lambda r:r['component'])
    summary={'scope':'offline_sequential_development_NOT_new_model_pass_rate','records':len(results),
        'model_calls':0,'effective_passed':sum(r['effective_passed'] for r in results),
        'fresh_baseline_passed':sum(bool(r.get('fresh_baseline_passed')) for r in results),
        'v7_recorded_effective_passed':33,
        'previously_passed_now_failed':[r['component'] for r in results if r.get('v7_effective_passed') and not r['effective_passed']],
        'newly_passed_vs_v7':[r['component'] for r in results if not r.get('v7_effective_passed') and r['effective_passed']],
        'statuses':dict(Counter(r['status'] for r in results)),
        'gates':dict(Counter(s['gate']['reason'] for r in results for s in r.get('steps',[]))),
        'remaining_codes':dict(Counter(c for r in results if not r['effective_passed'] for c in r.get('effective_codes',[]))),
        'historical_files_verified_unchanged':len(historical),'v7_files_verified_unchanged':len(prior_files),
        'implementation_unchanged':True}
    write_once(output/'results.json',results);write_once(output/'summary.json',summary)
    # Snapshot only the exact public implementation, never configs/secrets/DB.
    for relative,digest in implementation.items():
        path=output/'implementation'/relative
        path.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(PROJECT/relative,path)
        if hashed(path)!=digest:raise ValueError('implementation_copy_hash_mismatch')
    write_once(output/'SHA256SUMS.txt',''.join(hashed(p)+'  '+p.relative_to(output).as_posix()+'\n'
        for p in sorted(output.rglob('*')) if p.is_file()))
    print(json.dumps(summary,ensure_ascii=True),flush=True)


if __name__=='__main__':main()
