"""Full-corpus static reassessment after a metadata-only scope correction.

No code generation/normalization, no model or database. Every available parent
is the prior v9 gate-effective code, never a rejected revision. Exact unchanged
code/render implementation allows explicitly labeled reuse of prior captures;
newly passing lifecycle-only cases additionally receive a fresh browser capture.
Earlier tests/captures are NEVER relabeled as fresh current-version evidence.
"""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor,as_completed
import json
from pathlib import Path
import shutil
import subprocess
from analyze_coverage import RUNS,read,write_once,hashed
from replay_general_repairs_v3 import binding,evaluate,PROJECT
from replay_composed_v6 import raw_evidence
from card_migration_system.config import load_settings
from card_migration_system.runtime import profile
from card_migration_system.adapters.engine import verify_engine
from card_migration_system.adapters.browser import BrowserEvaluator
from card_migration_system.adapters.syntax import target_syntax
from card_migration_system.adapters.legacy_checks import legacy_stage
from card_migration_system.stages.evaluation import assess
from card_migration_system.stages.syntax import failed_syntax

REFERENCE=RUNS/'composed_v9_verified_replay_20261120'
OUTPUT=RUNS/'composed_v9_scope_reassessment_20261120'


def check_files(root,entries):
    for relative,digest in entries.items():
        if hashed(root/relative)!=digest:raise ValueError('frozen_input_changed:'+relative)


def replay(pair,old,settings,runtime,historical):
    dest=OUTPUT/old['sample_id']
    result={'component':old['component'],'sample_id':old['sample_id'],'complexity':old.get('complexity'),
        'v8_effective_passed':old.get('v8_effective_passed',False),'v9_recorded_effective_passed':old['effective_passed'],
        'v9_recorded_codes':old.get('effective_codes',[]),'model_calls':0,
        'v9_rule_evidence':str((REFERENCE/old['sample_id']).relative_to(RUNS)),
        'source_report':old['source_report'],'scope':'fresh_static_same_code_explicit_capture_reuse_no_new_generation_or_rules'}
    if old['status']!='replayed':
        result.update(status=old['status'],effective_passed=False)
        write_once(dest/'result.json',result);return result
    code_file=REFERENCE/old['sample_id']/'effective.san'
    if hashed(code_file)!=old['effective_sha256']:raise ValueError('accepted_code_changed')
    row=pair['new'];folder=(RUNS/row['report']).parent;artifacts=folder/'artifacts'
    source=next((RUNS/row['batch']/'inputs'/folder.name).glob('*.vue'))
    for path in (source,artifacts/'ssm.json',artifacts/'request.json'):
        relative=path.relative_to(RUNS).as_posix()
        if hashed(path)!=historical[relative]:raise ValueError('source_or_spec_changed:'+relative)
    request=read(artifacts/'request.json')['request'];ssm=read(artifacts/'ssm.json')['ssm']
    spec={key:request[key] for key in ('props','actions','thresholds')}
    code=code_file.read_bytes().decode('utf-8')
    vue=source.read_bytes().decode('utf-8');syntax=target_syntax(settings,vue,code)
    raw=None;fresh=False;capture=None
    if syntax['status']=='fail':after=failed_syntax(syntax,hashed(code_file))
    else:
        static=legacy_stage(settings.repository_root,'validate',source=vue,code=code,ssm=ssm)
        prefix='baseline'
        for step in old.get('steps',[]):
            if step['gate']['accepted'] and step['candidate_sha256']==old['effective_sha256']:
                prefix='step-'+str(step['number'])
        captured=REFERENCE/old['sample_id']/(prefix+'-browser.json')
        bound_code=REFERENCE/old['sample_id']/('parent.san' if prefix=='baseline' else prefix+'.san')
        if hashed(bound_code)!=old['effective_sha256']:raise ValueError('capture_code_not_effective_parent')
        raw=read(captured)
        # These old hashes authorize only their original runtime/gate. They
        # are not needed to re-assess identical code and must not masquerade
        # as freshly generated recovery witnesses for this follow-up.
        raw.pop('default_recovery_binding',None);raw.pop('initialization_recovery_binding',None)
        after=assess(static,raw,spec['actions'],spec['thresholds'],ssm)
        capture={'mode':'old_v9_capture_reused_NOT_fresh','browser_json':captured.relative_to(RUNS).as_posix(),
            'sha256':hashed(captured),'identical_target_sha256':hashed(bound_code),
            'render_implementation_unchanged':True,'old_gate_bindings_not_reauthorized':True}
        if after['passed'] and not old['effective_passed'] and old['effective_codes']==['missing_lifecycle_mapping']:
            raw=BrowserEvaluator(settings,runtime).evaluate(vue,code,spec['props'],spec['actions'])
            if raw.get('status')!='completed':raise ValueError('fresh_confirming_browser_blocked')
            after=assess(static,raw,spec['actions'],spec['thresholds'],ssm)
            capture={'mode':'fresh_confirming_browser_capture','identical_target_sha256':hashed(bound_code)};fresh=True
        after.update(syntax=syntax,revision_sha256=hashed(code_file))
    raw_evidence(dest,'current',raw)
    if after.get('blocked'):raise ValueError('assessment_blocked:'+str(after['blocked']))
    result.update(status='reassessed',effective_passed=bool(after['passed']),effective_sha256=hashed(code_file),
        effective_dimensions=after['dimensions'],effective_codes=sorted({d['code'] for d in after['diagnostics']}),
        fresh_browser_capture=fresh,capture_provenance=capture,code_changed=False)
    write_once(dest/'effective.san',code);write_once(dest/'effective-assessment.json',after)
    write_once(dest/'result.json',result);return result


def main():
    if OUTPUT.exists():raise ValueError('choose_new_immutable_output')
    previous=read(REFERENCE/'protocol.json');implementation=binding()
    differences=sorted(set(previous['implementation_sha256'])^set(implementation)|
        {key for key in implementation if previous['implementation_sha256'].get(key)!=implementation[key]})
    if differences!=['engine/MANIFEST.json','engine/migration_pipeline/utils/bounded_semantics.cjs']:
        raise ValueError('metadata_only_followup_expected:'+str(differences))
    proof=subprocess.run(['node',str(Path(__file__).with_suffix('.cjs'))],input=json.dumps({
        'old':str(REFERENCE/'implementation/engine/migration_pipeline/utils/bounded_semantics.cjs'),
        'new':str(PROJECT/'engine/migration_pipeline/utils/bounded_semantics.cjs')}).encode(),
        capture_output=True,timeout=15,check=True)
    proof=json.loads(proof.stdout)
    if not proof['all_other_program_nodes_unchanged']:raise ValueError('unexpected_other_logic_change')
    entries={relative:digest for digest,relative in (line.split('  ',1) for line in
        (REFERENCE/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines())}
    historical=previous['historical_input_sha256'];check_files(REFERENCE,entries);check_files(RUNS,historical)
    settings=load_settings(project_root=PROJECT,environ={});runtime=profile(settings)
    write_once(OUTPUT/'protocol.json',{'scope':'fresh_static_full_corpus_explicit_capture_reuse_NOT_model_success',
        'rows':70,'browser_workers':2,'real_model_calls':0,'cloud_database_access':False,
        'reference':REFERENCE.name,'reference_sha256sums':hashed(REFERENCE/'SHA256SUMS.txt'),
        'reference_files_sha256':entries,'historical_input_sha256':historical,
        'implementation_sha256':implementation,'implementation_difference':differences,
        'metadata_AST_difference_proof':proof,'engine':verify_engine(settings.repository_root),
        'capture_reuse_policy':'identical_code_source_props_actions_thresholds_and_all_renderer_files; only parent metadata changes; old recovery witnesses not reauthorized',
        'script_sha256':hashed(Path(__file__)),'threshold_or_budget_changes':False})
    pairs={p['component']:p for p in read(RUNS/'analysis_v3_vs_first70_20261119/pairs.json')}
    results=[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures={pool.submit(replay,pairs[row['component']],row,settings,runtime,historical):row
            for row in read(REFERENCE/'results.json')}
        for future in as_completed(futures):
            row=futures[future]
            try:result=future.result()
            except Exception as exc:
                result={'component':row['component'],'sample_id':row['sample_id'],'effective_passed':False,
                    'status':'reassessment_error','error':str(exc)}
                write_once(OUTPUT/row['sample_id']/'error.json',result)
            results.append(result)
            print(json.dumps({'completed':len(results),'component':result['component'],
                'passed':result['effective_passed'],'status':result['status'],
                'codes':result.get('effective_codes',result.get('error'))},ensure_ascii=True),flush=True)
    if binding()!=implementation:raise ValueError('implementation_changed_during_reassessment')
    check_files(REFERENCE,entries);check_files(RUNS,historical)
    results.sort(key=lambda row:row['component'])
    summary={'scope':'fresh_static_explicit_capture_reuse_NOT_new_model_or_independent_test',
        'records':len(results),'effective_passed':sum(r['effective_passed'] for r in results),
        'model_calls':0,'new_code_candidates':0,'fresh_browser_captures':sum(bool(r.get('fresh_browser_capture')) for r in results),
        'reused_browser_captures':sum(r.get('capture_provenance',{}).get('mode')=='old_v9_capture_reused_NOT_fresh' for r in results if r.get('capture_provenance')),
        'statuses':dict(Counter(r['status'] for r in results)),
        'newly_passed_vs_v8':[r['component'] for r in results if r['effective_passed'] and not r.get('v8_effective_passed')],
        'previously_passed_now_failed':[r['component'] for r in results if r.get('v8_effective_passed') and not r['effective_passed']],
        'status_changed_vs_v9':[{'component':r['component'],'before':r.get('v9_recorded_effective_passed'),
            'after':r['effective_passed']} for r in results if r.get('status')=='reassessed'
            and r['effective_passed']!=r.get('v9_recorded_effective_passed')],
        'remaining_codes':dict(Counter(c for r in results if not r['effective_passed'] for c in r.get('effective_codes',[]))),
        'historical_files_verified_unchanged':len(historical),'v9_payloads_verified_unchanged':len(entries),
        'implementation_unchanged':True}
    write_once(OUTPUT/'results.json',results);write_once(OUTPUT/'summary.json',summary)
    for relative,digest in implementation.items():
        target=OUTPUT/'implementation'/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(PROJECT/relative,target)
        if hashed(target)!=digest:raise ValueError('snapshot_changed')
    write_once(OUTPUT/'SHA256SUMS.txt',''.join(hashed(p)+'  '+p.relative_to(OUTPUT).as_posix()+'\n'
        for p in sorted(OUTPUT.rglob('*')) if p.is_file()))
    print(json.dumps(summary,ensure_ascii=True),flush=True)


if __name__=='__main__':main()
