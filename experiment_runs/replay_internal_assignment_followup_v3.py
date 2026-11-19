"""Source-internal setter follow-up on every matching frozen record. No models/DB."""
from concurrent.futures import ThreadPoolExecutor,as_completed
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1];PROJECT=ROOT/'migration_system'
sys.path.insert(0,str(PROJECT/'src'))
from analyze_coverage import collect,read,write_once,hashed
from replay_general_repairs_v3 import binding,evaluate
from card_migration_system.adapters.legacy_checks import legacy_stage
from card_migration_system.adapters.syntax import target_syntax
from card_migration_system.adapters.engine import verify_engine
from card_migration_system.config import load_settings
from card_migration_system.runtime import profile

BASE=ROOT/'experiment_runs/general_repairs_v3_final_replay_20261119'
OUT=ROOT/'experiment_runs/general_repairs_v3_internal_assignment_followup_20261119'


def replay(path,settings,runtime,details):
    old=read(path);detail=details[old['run_key']];sample=detail['sample'];artifacts=detail['folder']/'artifacts'
    source=(ROOT/'experiment_runs'/old['batch']/sample['frozen_vue']).read_bytes().decode('utf-8')
    code=(path.parent/'candidate.san').read_bytes().decode('utf-8');ssm=read(artifacts/'ssm.json')['ssm']
    result={'run_key':old['run_key'],'batch':old['batch'],'component':old['component'],
        'baseline_result':path.relative_to(ROOT/'experiment_runs').as_posix(),'scope':'internal_assignment_followup_not_fresh_generation',
        'parent_sha256':old['candidate_sha256'],'model_calls':0}
    analysis=subprocess.run(['node',str(settings.repository_root/'migration_pipeline/utils/bounded_semantics.cjs')],
        input=json.dumps({'vue':source,'code':code,'ssm':ssm,'repair':True}).encode(),capture_output=True,timeout=30)
    ast=json.loads(analysis.stdout)
    contracts=[c for c in ast.get('method_contracts',[]) if c.get('dynamic_assignment')]
    if (not ast.get('error') and ast.get('code')==code and old.get('current_after',{}).get('passed') is True
            and contracts and all(c.get('status')=='proven_for_source_internal_calls' for c in contracts)):
        # Positive controls: repeat the changed proof, do not rerender unchanged
        # code just to count another browser run. Keep the exact evidence origin.
        result.update(changed=False,changes=[],static_after_passed=True,proofs=contracts,
            current_after=old['current_after'],browser_evidence='reused_exact_baseline_source_and_target_positive_control',
            baseline_browser_reference=old['run_key'])
        write_once(OUT/old['batch']/sample['slug']/'result.json',result)
        return result
    static=legacy_stage(settings.repository_root,'validate',source=source,code=code,ssm=ssm)
    rules=legacy_stage(settings.repository_root,'rules',source=source,code=code,ssm=ssm,errors=static['validation_errors'])
    candidate=rules['code'];result.update(changed=candidate!=code,changes=rules['changes'])
    if candidate!=code:static=legacy_stage(settings.repository_root,'validate',source=source,code=candidate,ssm=ssm)
    request=read(artifacts/'request.json')['request'];spec={k:request[k] for k in ('props','actions','thresholds')}
    dest=OUT/old['batch']/sample['slug'];write_once(dest/'candidate.san',candidate);write_once(dest/'static.json',static)
    try:
        after,browser=evaluate(settings,runtime,source,candidate,ssm,spec,static)
        result['current_after']=after
        if browser:
            # Keep browser trees/properties; original screenshot bytes remain
            # in the full replay. New screenshots are independently hashed.
            from hashlib import sha256
            import base64
            for side in ('vue','san'):
                if browser.get(side,{}).get('png'):
                    data=base64.b64decode(browser[side].pop('png'))
                    browser[side]['screenshot_sha256']=sha256(data).hexdigest()
                    with (dest/(side+'.png')).open('xb') as stream:stream.write(data)
            write_once(dest/'browser.json',browser)
    except Exception as exc:result['current_after']={'blocked':str(exc)}
    result['proofs']=[c for c in static.get('source_method_contracts',[]) if c.get('dynamic_assignment')]
    result['static_after_passed']=static['validation_passed']
    write_once(dest/'result.json',result);return result


if __name__=='__main__':
    if OUT.exists():raise SystemExit('Choose a new output; never overwrite evidence')
    rows,details,frozen,_,_=collect();implementation=binding()
    settings=load_settings(project_root=PROJECT,environ={});runtime=profile(settings);verify_engine(settings.repository_root)
    selected=[]
    for path in BASE.rglob('result.json'):
        r=read(path)
        if r.get('syntax_after',{}).get('status')!='pass':continue
        static=read(path.parent/'static.json') if (path.parent/'static.json').is_file() else {}
        if 'source_dynamic_assignment_unproven' in r.get('historical_codes',[]) or any(c.get('dynamic_assignment') for c in static.get('source_method_contracts',[])):
            selected.append(path)
    write_once(OUT/'protocol.json',{'scope':'all_matching_records_from_full_72_replay','records':len(selected),
        'model_calls':0,'implementation_sha256':implementation,'frozen_inputs_sha256':frozen})
    results=[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending=[pool.submit(replay,p,settings,runtime,details) for p in selected]
        for future in as_completed(pending):
            value=future.result();results.append(value)
            print(json.dumps({'completed':len(results),'total':len(selected),'component':value['component'],
                'changed':value['changed'],'static_after_passed':value['static_after_passed']},ensure_ascii=True),flush=True)
    if binding()!=implementation or collect()[2]!=frozen:raise ValueError('implementation_or_inputs_changed_during_followup')
    results.sort(key=lambda r:r['run_key']);write_once(OUT/'results.json',results)
    summary={'scope':'subset_semantic_followup_not_uniform_new_generation_pass_rate','records':len(results),'model_calls':0,
        'changed':sum(r['changed'] for r in results),'static_after_pass':sum(r['static_after_passed'] for r in results),
        'whole_sample_after_pass':sum(r.get('current_after',{}).get('passed') is True for r in results),
        'integrity_unchanged':True}
    write_once(OUT/'summary.json',summary)
    hashes={p.relative_to(OUT).as_posix():hashed(p) for p in sorted(OUT.rglob('*')) if p.is_file()}
    write_once(OUT/'SHA256SUMS.txt',''.join(v+'  '+k+'\n' for k,v in hashes.items()))
    print(json.dumps(summary),flush=True)
