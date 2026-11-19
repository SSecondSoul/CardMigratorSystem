"""All 72 frozen records: current rules, real captures for changed code only.

Unchanged code explicitly reuses immutable v4 observations. No models, jobs,
cloud DB writes, historical file edits or cross-version best-result selection.
"""
from concurrent.futures import ThreadPoolExecutor,as_completed
from hashlib import sha256
import json
import argparse
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1];PROJECT=ROOT/'migration_system'
sys.path.insert(0,str(PROJECT/'src'))
from analyze_coverage import collect,read,write_once,hashed
from replay_general_repairs_v3 import binding,evaluate
from reproject_conditional_branches_v4 import verify
from card_migration_system.adapters.legacy_checks import legacy_stage
from card_migration_system.adapters.syntax import target_syntax
from card_migration_system.config import load_settings
from card_migration_system.runtime import profile
from card_migration_system.stages.evaluation import candidate_decision,assess
from card_migration_system.stages.syntax import failed_syntax

PREVIOUS=ROOT/'experiment_runs/general_repairs_v4_branch_projection_20261119'
RELEASE=ROOT/'experiment_runs/general_repairs_v3_release_20261119'
BASE=ROOT/'experiment_runs/general_repairs_v3_final_replay_20261119'
FOLLOW=ROOT/'experiment_runs/general_repairs_v3_internal_assignment_followup_20261119'
OUT=ROOT/'experiment_runs/general_repairs_v4_inline_options_20261119'
REFRESH_CHECKER=False


def run(old,detail,settings,runtime):
    batch=detail['batch'] if 'batch' in detail else old['run_key'].split('/')[0]
    # The inventory carries the actual batch independently of component names.
    folder=detail['folder'];batch=folder.parents[1].name;sample=detail['sample'];dest=OUT/batch/sample['slug']
    result={k:old[k] for k in ('run_key','component','historical_passed','status')}
    result.update(batch=batch,model_calls=0,new_browser_captures=0,rule_decisions=[])
    if 'effective_assessment' not in old:
        write_once(dest/'result.json',result);return result
    expected=old['effective_sha256'];artifact=folder/'artifacts'
    candidates=[PREVIOUS/batch/sample['slug']/'effective.san',RELEASE/batch/sample['slug']/'effective.san',BASE/batch/sample['slug']/'candidate.san',FOLLOW/batch/sample['slug']/'candidate.san',
                *(artifact/'revisions').glob('*.san')]
    path=next((p for p in candidates if p.is_file() and hashed(p)==expected),None)
    if path is None:raise ValueError('exact_effective_code_not_found:'+old['run_key'])
    code=path.read_bytes().decode('utf-8');source=(ROOT/'experiment_runs'/batch/sample['frozen_vue']).read_bytes().decode('utf-8')
    ssm=read(artifact/'ssm.json')['ssm'];spec=read(artifact/'request.json')['request'];before=old['effective_assessment']
    before_static=legacy_stage(settings.repository_root,'validate',source=source,code=code,ssm=ssm)
    write_once(dest/'before-static.json',before_static)
    if REFRESH_CHECKER:
        syntax=target_syntax(settings,source,code)
        if syntax['status']=='fail':before=failed_syntax(syntax,expected)
        else:
            raw_path=(ROOT/'experiment_runs'/before['capture_reference']) if before.get('capture_reference') else PREVIOUS/batch/sample['slug']/'browser.json'
            if not raw_path.is_file():raise ValueError('no_exact_parent_capture:'+old['run_key'])
            raw=read(raw_path)
            payload={'repository':str(settings.repository_root),'project':str(PROJECT),'source':source,'code':code,'action':'parse'}
            parsed=subprocess.run(['node',str(PROJECT/'browser/evaluate.mjs')],input=json.dumps(payload).encode(),capture_output=True,check=True,timeout=30)
            pair=json.loads(parsed.stdout);raw['source_ast']=pair['source'];raw['target_ast']=pair['target']
            before=assess(before_static,raw,spec['actions'],spec['thresholds'],ssm)
            before.update(syntax=syntax,revision_sha256=expected,capture_reference=raw_path.relative_to(ROOT/'experiment_runs').as_posix(),
                evidence_mode='fresh_static_and_parse_exact_code_with_explicit_unchanged_renderer_capture_reuse')
        write_once(dest/'before-assessment.json',before)
    normalized=target_syntax(settings,source,code,normalize=True);candidate=normalized['code'];changes=list(normalized['changes'])
    if normalized['after']['status']=='pass':
        interim=before_static if candidate==code else legacy_stage(settings.repository_root,'validate',source=source,code=candidate,ssm=ssm)
        errors=interim['validation_errors']+[d for d in before.get('diagnostics',[]) if d['code'].startswith(('rendered_','template_structure','dom_'))]
        rule=legacy_stage(settings.repository_root,'rules',source=source,code=candidate,ssm=ssm,errors=errors)
        candidate=rule['code'];changes.extend(rule['changes'])
    write_once(dest/'parent.san',code);write_once(dest/'candidate.san',candidate)
    current=before;result.update(parent_sha256=expected,changed=candidate!=code,changes=changes,
        candidate_sha256=sha256(candidate.encode()).hexdigest(),before_assessment=before)
    if candidate!=code:
        observed,raw=evaluate(settings,runtime,source,candidate,ssm,spec)
        result.update(candidate_assessment=observed,new_browser_captures=int(raw is not None))
        if raw:
            import base64
            for side in ('vue','san'):
                if raw.get(side,{}).get('png'):
                    image=base64.b64decode(raw[side].pop('png'));p=dest/(side+'.png');p.parent.mkdir(parents=True,exist_ok=True)
                    with p.open('xb') as stream:stream.write(image)
            write_once(dest/'browser.json',raw)
        decision=({'accepted':False,'reason':'evaluation_blocked'} if observed.get('blocked') else candidate_decision(before,observed))
        result['rule_decisions'].append(decision)
        if decision['accepted']:code=candidate;current=observed
    result.update(status='replayed',effective_assessment=current,passed=current.get('passed') is True,effective_sha256=sha256(code.encode()).hexdigest(),
        prior_version_passed=old.get('passed') is True,
        evidence_mode='fresh_capture_if_code_changed_otherwise_explicit_v4_observation_reuse')
    write_once(dest/'effective.san',code);write_once(dest/'result.json',result);return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--computed-v5',action='store_true');args=parser.parse_args()
    if args.computed_v5:
        PREVIOUS=ROOT/'experiment_runs/general_repairs_v4_inline_options_20261119'
        OUT=ROOT/'experiment_runs/general_repairs_v5_computed_options_complete_20261119';REFRESH_CHECKER=True
    if OUT.exists():raise SystemExit('Choose a new evidence directory, never overwrite')
    for folder in (PREVIOUS,RELEASE,BASE,FOLLOW):verify(folder)
    _,details,frozen,_,_=collect();implementation=binding();settings=load_settings(project_root=PROJECT,environ={});runtime=profile(settings)
    old_binding=read(PREVIOUS/'protocol.json')['implementation_sha256']
    changed={k for k in set(old_binding)|set(implementation) if old_binding.get(k)!=implementation.get(k)}
    allowed={'engine/MANIFEST.json','engine/migration_pipeline/stages/repair.py','engine/migration_pipeline/utils/residual_semantics.cjs'}
    if REFRESH_CHECKER:allowed={'engine/MANIFEST.json','engine/migration_pipeline/stages/repair.py','engine/migration_pipeline/utils/bounded_semantics.cjs',
        'src/card_migration_system/prompts/san_contract.py'}
    if changed!=allowed:raise ValueError('unexpected_checker_or_renderer_change:'+str(changed))
    write_once(OUT/'protocol.json',{'scope':'frozen_72_all_records_rule_followup_not_new_model_success_rate',
        'implementation_sha256':implementation,'prior_runtime_changes':sorted(changed),'input_integrity':frozen,'model_calls':0,
        'renderer_unchanged':True,'validator_refreshed':REFRESH_CHECKER,'thresholds_and_candidate_gate_unchanged':True,
        'replay_script_sha256':hashed(Path(__file__)),'real_parser_and_static_retested':REFRESH_CHECKER,
        'new_browser_capture_policy':'every_changed_candidate_before_real_acceptance_gate'})
    results=[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(run,r,details[r['run_key']],settings,runtime) for r in read(PREVIOUS/'results.json')]
        for job in as_completed(futures):
            result=job.result();results.append(result)
            print(json.dumps({'completed':len(results),'total':72,'component':result['component'],'changed':result.get('changed'),
                'passed':result.get('passed'),'gate':result['rule_decisions']},ensure_ascii=True),flush=True)
    if binding()!=implementation or collect()[2]!=frozen:raise ValueError('runtime_or_frozen_files_changed')
    results.sort(key=lambda r:r['run_key']);write_once(OUT/'results.json',results)
    summary={'scope':'offline_frozen_artifact_followup_not_new_generation_rate','records':72,'unique_components':70,'model_calls':0,
        'new_browser_captures':sum(r['new_browser_captures'] for r in results),'historical_passed':sum(r['historical_passed'] for r in results),
        'effective_passed':sum(r.get('passed',False) for r in results),'changed':sum(r.get('changed',False) for r in results),
        'accepted':sum(d['accepted'] for r in results for d in r['rule_decisions']),
        'rejected':sum(not d['accepted'] for r in results for d in r['rule_decisions']),
        'previous_pass_regressions':[r['component'] for r in results if r.get('prior_version_passed',r.get('before_assessment',{}).get('passed')) and not r.get('passed')],
        'newly_passed':[r['component'] for r in results if not r['historical_passed'] and r.get('passed')],
        'all_issues_fixed':all(r.get('passed') for r in results),'frozen_integrity_unchanged':True}
    write_once(OUT/'summary.json',summary)
    hashes={p.relative_to(OUT).as_posix():hashed(p) for p in sorted(OUT.rglob('*')) if p.is_file()}
    write_once(OUT/'SHA256SUMS.txt',''.join(v+'  '+k+'\n' for k,v in hashes.items()))
    print(json.dumps(summary,ensure_ascii=True),flush=True)
