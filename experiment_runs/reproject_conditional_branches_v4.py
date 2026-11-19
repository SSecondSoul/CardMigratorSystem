"""Real parser reprojection with verified unchanged renderer/static evidence.

Only the template projection changed. Raw rendered observations are immutable,
reused explicitly, not rerendered or relabeled as fresh model experiments.
"""
from concurrent.futures import ThreadPoolExecutor,as_completed
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1];PROJECT=ROOT/'migration_system'
sys.path.insert(0,str(PROJECT/'src'))
from analyze_coverage import read,write_once,hashed,collect
from replay_general_repairs_v3 import binding
from card_migration_system.stages.evaluation import assess,candidate_decision
from card_migration_system.stages.syntax import failed_syntax

PREVIOUS=ROOT/'experiment_runs/general_repairs_v3_release_20261119'
BASE=ROOT/'experiment_runs/general_repairs_v3_final_replay_20261119'
FOLLOW=ROOT/'experiment_runs/general_repairs_v3_internal_assignment_followup_20261119'
OUT=ROOT/'experiment_runs/general_repairs_v4_branch_projection_20261119'


def verify(folder):
    for line in (folder/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        digest,name=line.split('  ',1)
        if hashed(folder/name)!=digest:raise ValueError('evidence_changed:'+name)


def projection_only_change(current,old):
    changed={k for k in set(current)|set(old) if current.get(k)!=old.get(k)}
    if changed!={'browser/evaluate.mjs','src/card_migration_system/stages/evaluation.py'}:
        raise ValueError('non_projection_changes_require_new_validation:'+str(changed))
    text=(PROJECT/'browser/evaluate.mjs').read_bytes().decode('utf-8')
    start=text.index('  // San stores elif/else nodes');end=text.index('  function visit(node){',start)
    parent=text[:start]+text[end:]
    parent=parent.replace("for(const [name] of Object.entries(node.directives??{}))attrs.push('directive:'+(name==='elif'?'else-if':name))",
                          "for(const [name] of Object.entries(node.directives??{}))attrs.push('directive:'+name)")
    parent=parent.replace('children:mergeText(sanChildren(node.children))',"children:mergeText((node.children??[]).map(visit).filter(Boolean))")
    parent=parent.replace('template_projection_v4_ordered_conditional_siblings','template_projection_v3_symmetric_boundary_safe_class_tokens')
    if sha256(parent.encode()).hexdigest()!=old['browser/evaluate.mjs']:raise ValueError('renderer_unchanged_proof_failed')
    evaluation=(PROJECT/'src/card_migration_system/stages/evaluation.py').read_bytes().decode('utf-8').replace(
        'ssm_v3_symmetric_class_tokens_ordered_conditional_siblings_v4','ssm_v3_symmetric_class_tokens_element_attributes_events_direct_text_v3')
    if sha256(evaluation.encode()).hexdigest()!=old['src/card_migration_system/stages/evaluation.py']:
        raise ValueError('quality_gate_or_threshold_changed')
    write_once(OUT/'verified_projection_parent.mjs',parent)
    return {'modified_runtime_files':sorted(changed),'previous_source_exactly_recovered_and_hash_verified':True,
            'capture_and_metrics_functions_unchanged':True,'quality_gate_code_unchanged_except_projection_label':True}


def project(path,follow,details):
    old=read(path);detail=details[old['run_key']];sample=detail['sample'];artifact=detail['folder']/'artifacts'
    dest=OUT/old['batch']/sample['slug']
    result={'run_key':old['run_key'],'component':old['component'],'historical_passed':old['historical_passed'],
            'previous_effective_passed':old.get('passed',False),'rule_decisions':[],'new_browser_captures':0,'model_calls':0}
    if old['status']!='reconciled':
        result['status']=old['status'];write_once(dest/'result.json',result);return result
    source=(ROOT/'experiment_runs'/old['batch']/sample['frozen_vue']).read_bytes().decode('utf-8')
    request=read(artifact/'request.json')['request'];ssm=read(artifact/'ssm.json')['ssm']
    static_cache={}
    for assessment_path in path.parent.glob('*-assessment.json'):
        a=read(assessment_path);static_path=assessment_path.with_name(assessment_path.name.replace('-assessment','-static'))
        if static_path.exists():static_cache[a['revision_sha256']]=read(static_path)
    base_record=read(BASE/old['batch']/sample['slug']/'result.json')
    parent=next(read(f) for f in (artifact/'revisions').glob('*.json') if read(f)['file']['sha256']==base_record['parent_sha256'])
    code=(artifact/'revisions'/f'{parent["number"]}.san').read_bytes().decode('utf-8');cache={}
    def inspect(text,raw_path,label):
        digest=sha256(text.encode()).hexdigest()
        if digest in cache:return cache[digest]
        payload={'repository':str(PROJECT/'engine'),'project':str(PROJECT),'source':source,'code':text,'action':'parse'}
        proc=subprocess.run(['node',str(PROJECT/'browser/evaluate.mjs')],input=json.dumps(payload).encode(),capture_output=True,timeout=30)
        pair=json.loads(proc.stdout)
        if pair.get('status')=='target_compile_failed':assessment=failed_syntax(pair['syntax'],digest)
        else:
            if not {'source','target'}<=pair.keys() or not raw_path.is_file():raise ValueError('missing_real_projection_or_capture')
            raw=read(raw_path);static=static_cache.get(digest)
            if static is None:raise ValueError('static_result_missing_for_exact_code:'+digest)
            old_target_nodes=read(raw_path)['target_ast']['tree']
            raw['source_ast']=pair['source'];raw['target_ast']=pair['target']
            assessment=assess(static,raw,request['actions'],request['thresholds'],ssm)
            assessment.update(revision_sha256=digest,
                syntax={'status':'pass','diagnostics':[],'diagnostic_count':0,'policy':'real_syntax_retested_with_projection_v4'},
                evidence_mode='new_real_parser_projection_plus_identical_code_static_and_render_capture_reuse',
                capture_reference=raw_path.relative_to(ROOT/'experiment_runs').as_posix(),
                static_reused=True)
            write_once(dest/(label+'-projection.json'),pair)
        write_once(dest/(label+'-assessment.json'),assessment);cache[digest]=assessment;return assessment
    base_path=BASE/old['batch']/sample['slug'];current=inspect(code,base_path/'before-browser.json','parent')
    candidates=[('base_rules',base_path/'candidate.san',base_path/'after-browser.json',base_record['parent_sha256'])]
    if old['run_key'] in follow:
        fpath=follow[old['run_key']];f=read(fpath)
        if f.get('changed'):candidates.append(('scoped_followup',fpath.parent/'candidate.san',fpath.parent/'browser.json',f['parent_sha256']))
    for label,candidate_path,raw_path,parent_sha in candidates:
        candidate=candidate_path.read_bytes().decode('utf-8')
        if candidate==code:continue
        if sha256(code.encode()).hexdigest()!=parent_sha:
            result['rule_decisions'].append({'label':label,'accepted':False,'reason':'proposal_parent_not_retained'});continue
        observed=inspect(candidate,raw_path,label);decision=candidate_decision(current,observed)
        result['rule_decisions'].append({'label':label,**decision})
        if decision['accepted']:current=observed;code=candidate
    result.update(status='reprojected',effective_assessment=current,passed=current['passed'],effective_sha256=sha256(code.encode()).hexdigest())
    write_once(dest/'result.json',result);return result


if __name__=='__main__':
    if OUT.exists():raise SystemExit('Use a new output, never overwrite')
    for folder in (PREVIOUS,BASE,FOLLOW):verify(folder)
    rows,details,frozen,_,_=collect();implementation=binding()
    proof=projection_only_change(implementation,read(PREVIOUS/'protocol.json')['implementation_sha256'])
    write_once(OUT/'protocol.json',{'scope':'projection_only_retest_all_72_records_not_model_generation',
        'implementation_sha256':implementation,'unchanged_renderer_proof':proof,'frozen_inputs_sha256':frozen,
        'model_calls':0,'new_browser_captures':0})
    follow={read(p)['run_key']:p for p in FOLLOW.rglob('result.json')};results=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs=[pool.submit(project,p,follow,details) for p in PREVIOUS.rglob('result.json')]
        for job in as_completed(jobs):
            r=job.result();results.append(r)
            print(json.dumps({'completed':len(results),'component':r['component'],'passed':r.get('passed')},ensure_ascii=True),flush=True)
    if implementation!=binding() or frozen!=collect()[2]:raise ValueError('source_or_implementation_changed')
    results.sort(key=lambda r:r['run_key']);write_once(OUT/'results.json',results)
    summary={'scope':'all_72_frozen_artifacts_projection_correction_not_new_generation_rate','records':72,'components':70,
        'model_calls':0,'new_browser_captures':0,'historical_passed':12,
        'effective_passed':sum(r.get('passed',False) for r in results),
        'newly_passed':[r['component'] for r in results if not r['historical_passed'] and r.get('passed')],
        'previous_v3_pass_not_reproduced':[r['component'] for r in results if r['previous_effective_passed'] and not r.get('passed')],
        'accepted_rule_proposals':sum(d['accepted'] for r in results for d in r['rule_decisions']),
        'all_issues_fixed':all(r.get('passed') for r in results),'integrity_unchanged':True}
    write_once(OUT/'summary.json',summary)
    hashes={p.relative_to(OUT).as_posix():hashed(p) for p in sorted(OUT.rglob('*')) if p.is_file()}
    write_once(OUT/'SHA256SUMS.txt',''.join(v+'  '+k+'\n' for k,v in hashes.items()))
    print(json.dumps(summary,ensure_ascii=True),flush=True)
