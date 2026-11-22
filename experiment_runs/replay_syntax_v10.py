"""Three syntax-blocked frozen parents; real production normalization and browser.

Never a new generation batch or new overall 70-case pass rate. No model or DB.
"""
import json
from pathlib import Path
from analyze_coverage import RUNS, read, write_once, hashed
from replay_general_repairs_v3 import PROJECT, binding, evaluate
from replay_composed_v6 import raw_evidence
from card_migration_system.config import load_settings
from card_migration_system.runtime import profile
from card_migration_system.adapters.browser import BrowserEvaluator
from card_migration_system.adapters.legacy_checks import legacy_stage
from card_migration_system.adapters.engine import verify_engine
from card_migration_system.stages.normalization import normalize_proposal
from card_migration_system.stages.evaluation import candidate_decision

REFERENCE=RUNS/'composed_v9_scope_reassessment_20261120'
OUTPUT=RUNS/'composed_v10_syntax_replay_20261120'
COMPONENTS=('PasswordStrengthMeter','MonitoringDashboard','TopologyEditor')


def main():
    if OUTPUT.exists():raise ValueError('choose_new_immutable_output')
    before=binding();settings=load_settings(project_root=PROJECT,environ={});runtime=profile(settings)
    entries={relative:digest for digest,relative in (line.split('  ',1) for line in (REFERENCE/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines())}
    history=read(REFERENCE/'protocol.json')['historical_input_sha256']
    def integrity():
        for root,files in ((REFERENCE,entries),(RUNS,history)):
            for relative,digest in files.items():
                if hashed(root/relative)!=digest:raise ValueError('frozen_evidence_changed:'+relative)
    integrity()
    write_once(OUTPUT/'protocol.json',{'scope':'three_frozen_syntax_failures_development_replay_NOT_new_generation_or_full70_passrate',
        'components':COMPONENTS,'model_calls':0,'cloud_database_access':False,'browser_captures':'fresh_only_no_reuse',
        'max_proposals_per_case':3,'threshold_or_budget_changes':False,'reference_files_sha256':entries,
        'historical_input_sha256':history,'implementation_sha256':before,'engine':verify_engine(settings.repository_root),
        'runtime':runtime['browser'],'script_sha256':hashed(Path(__file__))})
    for relative in before:
        write_once(OUTPUT/'implementation'/relative,(PROJECT/relative).read_bytes().decode('utf-8'))
    pairs={p['component']:p for p in read(RUNS/'analysis_v3_vs_first70_20261119/pairs.json')}
    results=[]
    for component in COMPONENTS:
        row=pairs[component]['new'];dest=OUTPUT/row['sample_id'];prior=read(REFERENCE/row['sample_id']/'result.json')
        code_file=REFERENCE/row['sample_id']/'effective.san'
        if hashed(code_file)!=prior['effective_sha256']:raise ValueError('invalid_effective_parent')
        code=code_file.read_bytes().decode('utf-8');folder=(RUNS/row['report']).parent;artifacts=folder/'artifacts'
        source=next((RUNS/row['batch']/'inputs'/folder.name).glob('*.vue')).read_bytes().decode('utf-8')
        ssm=read(artifacts/'ssm.json')['ssm'];request=read(artifacts/'request.json')['request']
        spec={key:request[key] for key in ('props','actions','thresholds')}
        write_once(dest/'source.vue',source);write_once(dest/'parent.san',code)
        current,raw=evaluate(settings,runtime,source,code,ssm,spec)
        write_once(dest/'baseline-assessment.json',current);raw_evidence(dest,'baseline',raw)
        result={'component':component,'sample_id':row['sample_id'],'parent_sha256':hashed(code_file),
            'baseline_passed':current.get('passed',False),'baseline_codes':sorted({d['code'] for d in current.get('diagnostics',[])}),
            'model_calls':0,'steps':[]}
        rejected=set();rejected_on_parent=False
        for number in range(1,4):
            if current.get('passed') or current.get('blocked'):break
            normalized=normalize_proposal(settings,legacy_stage,BrowserEvaluator(settings,runtime),source,code,ssm,current,
                prefer_runtime_recovery=not rejected_on_parent)
            candidate=normalized.pop('code')
            if candidate==code:result['stop']='rule_fixed_point';break
            if (code,candidate) in rejected:result['stop']='repeated_rejected_candidate';break
            prefix='step-'+str(number);write_once(dest/(prefix+'.san'),candidate)
            write_once(dest/(prefix+'-normalization.json'),normalized)
            after,raw=evaluate(settings,runtime,source,candidate,ssm,spec)
            raw_evidence(dest,prefix,raw);write_once(dest/(prefix+'-assessment.json'),after)
            gate=candidate_decision(current,after) if not after.get('blocked') else {'accepted':False,'reason':'browser_blocked'}
            step={'number':number,'changes':normalized['changes'],'gate':gate,'passed':after.get('passed',False),
                'codes':sorted({d['code'] for d in after.get('diagnostics',[])}),'blocked':after.get('blocked')}
            result['steps'].append(step)
            print(json.dumps({'component':component,**{k:step[k] for k in ('number','gate','passed','codes','blocked')}},ensure_ascii=True),flush=True)
            if gate['accepted']:code,current=candidate,after;rejected_on_parent=False
            else:rejected.add((code,candidate));rejected_on_parent=True
        write_once(dest/'effective.san',code);write_once(dest/'effective-assessment.json',current)
        result.update(effective_passed=bool(current.get('passed')),effective_dimensions=current.get('dimensions',{}),
            effective_codes=sorted({d['code'] for d in current.get('diagnostics',[])}),blocked=current.get('blocked'))
        write_once(dest/'result.json',result);results.append(result)
        print(json.dumps({'completed':len(results),'component':component,'passed':result['effective_passed'],'codes':result['effective_codes']},ensure_ascii=True),flush=True)
    if before!=binding():raise ValueError('implementation_changed_during_replay')
    integrity();write_once(OUTPUT/'results.json',results)
    write_once(OUTPUT/'summary.json',{'scope':'three_frozen_cases_only_NOT_full70_current_passrate',
        'cases':len(results),'syntax_unblocked':sum(any(s['gate']['reason']=='syntax_unblocked_semantic_checks' for s in r['steps']) for r in results),
        'effective_passed':sum(r['effective_passed'] for r in results),'real_model_calls':0,'cloud_database_access':False,
        'historical_integrity_verified':True,'implementation_unchanged_during_replay':True})
    write_once(OUTPUT/'SHA256SUMS.txt',''.join(hashed(p)+'  '+p.relative_to(OUTPUT).as_posix()+'\n' for p in sorted(OUTPUT.rglob('*')) if p.is_file()))


if __name__=='__main__':main()
