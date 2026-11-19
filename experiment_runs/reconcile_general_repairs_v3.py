"""Final checker reconciliation of ALL 72 records, with explicit capture reuse.

Revalidates syntax/static semantics under the final implementation. Identical
Vue/San code reuses hash-verified captured DOM/styles/pixels; it is not a new
browser run, model generation, live task update, or independent experiment.
Rule proposals become effective ONLY after the real candidate gate accepts.
"""
from concurrent.futures import ThreadPoolExecutor,as_completed
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];PROJECT=ROOT/'migration_system'
sys.path.insert(0,str(PROJECT/'src'))
from analyze_coverage import collect,read,write_once,hashed
from replay_general_repairs_v3 import binding
from card_migration_system.adapters.legacy_checks import legacy_stage
from card_migration_system.adapters.syntax import target_syntax
from card_migration_system.config import load_settings
from card_migration_system.stages.evaluation import assess,candidate_decision
from card_migration_system.stages.syntax import failed_syntax

BASE=ROOT/'experiment_runs/general_repairs_v3_final_replay_20261119'
FOLLOW=ROOT/'experiment_runs/general_repairs_v3_internal_assignment_followup_20261119'
OUT=ROOT/'experiment_runs/general_repairs_v3_release_20261119'
RENDER_FILES=('browser/evaluate.mjs','browser/empty-class-policy.mjs','browser/resource-policy.mjs',
              'browser/metrics.mjs','browser/class-projection.mjs')


def verify_bundle(folder):
    for line in (folder/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        expected,name=line.split('  ',1)
        if hashed(folder/name)!=expected:raise ValueError('evidence_bundle_changed:'+name)


def reconcile(path,follow,details,settings):
    prior=read(path);detail=details[prior['run_key']];sample=detail['sample'];artifacts=detail['folder']/'artifacts'
    dest=OUT/prior['batch']/sample['slug']
    result={'run_key':prior['run_key'],'component':prior['component'],'batch':prior['batch'],
        'historical_passed':prior['historical_passed'],'source_sha256':sample['vue_sha256'],
        'model_calls':0,'new_browser_captures':0,'rule_decisions':[]}
    if prior['status'].startswith('no_accepted'):
        result['status']=prior['status'];write_once(dest/'result.json',result);return result
    source=(ROOT/'experiment_runs'/prior['batch']/sample['frozen_vue']).read_bytes().decode('utf-8')
    ssm=read(artifacts/'ssm.json')['ssm'];request=read(artifacts/'request.json')['request']
    revisions=[read(f) for f in (artifacts/'revisions').glob('*.json')]
    parent=next(r for r in revisions if r['file']['sha256']==prior['parent_sha256'])
    code=(artifacts/'revisions'/f'{parent["number"]}.san').read_bytes().decode('utf-8')
    if sha256(code.encode()).hexdigest()!=prior['parent_sha256']:raise ValueError('parent_hash_mismatch')
    cache={}
    def inspect(text,raw_path,label,expected_sha):
        digest=sha256(text.encode()).hexdigest()
        if digest!=expected_sha:raise ValueError('capture_code_binding_mismatch')
        if digest in cache:return cache[digest]
        syntax=target_syntax(settings,source,text)
        if syntax['status']=='fail':assessment=failed_syntax(syntax,digest)
        else:
            if not raw_path or not raw_path.is_file():return {'blocked':'capture_missing_do_not_invent_quality'}
            raw=read(raw_path);static=legacy_stage(settings.repository_root,'validate',source=source,code=text,ssm=ssm)
            assessment=assess(static,raw,request['actions'],request['thresholds'],ssm)
            assessment.update(syntax=syntax,revision_sha256=digest,
                browser_evidence='reused_hash_verified_exact_source_and_target_capture',
                capture_reference=raw_path.relative_to(ROOT/'experiment_runs').as_posix())
            write_once(dest/(label+'-static.json'),static)
        write_once(dest/(label+'-assessment.json'),assessment);cache[digest]=assessment;return assessment
    current=inspect(code,path.parent/'before-browser.json','parent',prior['parent_sha256'])
    initial=deepcopy(current)
    candidates=[('base_rules',path.parent/'candidate.san',path.parent/'after-browser.json',prior['parent_sha256'],prior['candidate_sha256'])]
    if prior['run_key'] in follow:
        fpath=follow[prior['run_key']];f=read(fpath)
        if f.get('changed'):
            candidate_code=fpath.parent/'candidate.san';expected=f['current_after'].get('revision_sha256')
            candidates.append(('scoped_followup',candidate_code,fpath.parent/'browser.json',f['parent_sha256'],expected))
    for label,candidate_path,raw_path,expected_parent,candidate_sha in candidates:
        candidate=candidate_path.read_bytes().decode('utf-8')
        if candidate==code:continue
        if sha256(code.encode()).hexdigest()!=expected_parent:
            result['rule_decisions'].append({'label':label,'accepted':False,'reason':'proposal_parent_not_retained'})
            continue
        observed=inspect(candidate,raw_path,label,candidate_sha)
        decision=({'accepted':False,'reason':'missing_capture_or_prior_block'} if current.get('blocked') or observed.get('blocked')
                  else candidate_decision(current,observed))
        result['rule_decisions'].append({'label':label,**decision})
        if decision['accepted']:code=candidate;current=observed
    result.update(status='reconciled',initial_assessment=initial,effective_assessment=current,
        effective_sha256=sha256(code.encode()).hexdigest(),passed=current.get('passed') is True)
    write_once(dest/'effective.san',code);write_once(dest/'result.json',result);return result


if __name__=='__main__':
    if OUT.exists():raise SystemExit('Release output exists; choose a new version rather than overwrite')
    verify_bundle(BASE);verify_bundle(FOLLOW)
    rows,details,frozen,_,_=collect();implementation=binding();base_binding=read(BASE/'implementation_sha256.json')
    if any(implementation[name]!=base_binding[name] for name in RENDER_FILES):raise ValueError('renderer_changed_recapture_required')
    follow={read(p)['run_key']:p for p in FOLLOW.rglob('result.json')}
    paths=sorted(BASE.rglob('result.json'));settings=load_settings(project_root=PROJECT,environ={})
    write_once(OUT/'protocol.json',{'scope':'final_static_syntax_and_gate_reconciliation_with_capture_reuse',
        'records':72,'components':70,'model_calls':0,'new_browser_captures':0,
        'implementation_sha256':implementation,'capture_runtime_files_verified':list(RENDER_FILES),
        'syntax_retested_before_reusing_capture':True,'input_integrity_sha256':frozen,
        'not_new_generation_or_independent_test':True})
    results=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        tasks=[pool.submit(reconcile,p,follow,details,settings) for p in paths]
        for task in as_completed(tasks):
            r=task.result();results.append(r)
            print(json.dumps({'completed':len(results),'total':72,'component':r['component'],'passed':r.get('passed')},ensure_ascii=True),flush=True)
    if binding()!=implementation or collect()[2]!=frozen:raise ValueError('implementation_or_historical_inputs_changed')
    results.sort(key=lambda r:r['run_key']);write_once(OUT/'results.json',results)
    summary={'scope':'offline_final_checker_and_accepted_rule_reconciliation_NOT_new_generation_rate',
        'records':72,'unique_components':70,'model_calls':0,'new_browser_captures':0,
        'historical_passed':sum(r['historical_passed'] for r in results),'effective_passed':sum(r.get('passed',False) for r in results),
        'newly_passed':[r['component'] for r in results if not r['historical_passed'] and r.get('passed')],
        'historical_pass_regressions':[r['component'] for r in results if r['historical_passed'] and not r.get('passed')],
        'accepted_rule_proposals':sum(d['accepted'] for r in results for d in r['rule_decisions']),
        'rejected_rule_proposals':sum(not d['accepted'] for r in results for d in r['rule_decisions']),
        'all_issues_fixed':all(r.get('passed') for r in results),'frozen_integrity_unchanged':True}
    write_once(OUT/'summary.json',summary)
    write_once(OUT/'remaining.json',[{'run_key':r['run_key'],'status':r['status'],
        'dimensions':r.get('effective_assessment',{}).get('dimensions'),
        'codes':sorted({d['code'] for d in r.get('effective_assessment',{}).get('diagnostics',[])})}
        for r in results if not r.get('passed')])
    hashes={p.relative_to(OUT).as_posix():hashed(p) for p in sorted(OUT.rglob('*')) if p.is_file()}
    write_once(OUT/'SHA256SUMS.txt',''.join(v+'  '+k+'\n' for k,v in hashes.items()))
    print(json.dumps(summary,ensure_ascii=True),flush=True)
