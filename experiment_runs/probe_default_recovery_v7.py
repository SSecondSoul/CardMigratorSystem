"""Real frozen runtime failures; isolate the existing default repair, no model."""
from pathlib import Path
import json
import subprocess
import sys
from analyze_coverage import read,write_once,hashed,RUNS
from replay_composed_v6 import raw_evidence
from replay_general_repairs_v3 import binding,evaluate,PROJECT
from card_migration_system.config import load_settings
from card_migration_system.runtime import profile
from card_migration_system.stages.evaluation import candidate_decision


def main():
    output=RUNS/'default_recovery_v7_20261119'
    if output.exists():raise ValueError('new_immutable_output_required')
    settings=load_settings(project_root=PROJECT,environ={});runtime=profile(settings);version=binding()
    write_once(output/'protocol.json',{'scope':'isolated_existing_default_rule_on_real_frozen_failures_not_fresh_generation',
        'implementation_sha256':version,'script_sha256':hashed(Path(__file__)),'model_calls':0})
    rows=[]
    for pair in read(RUNS/'analysis_v3_vs_first70_20261119/pairs.json'):
        row=pair['new'];folder=(RUNS/row['report']).parent;artifact=folder/'artifacts';assessment=read(folder/'report.json').get('assessment') or {}
        if assessment.get('dimensions',{}).get('compile_runtime')!='fail':continue
        parent=next((read(p) for p in (artifact/'revisions').glob('*.json') if read(p)['file']['sha256']==assessment.get('revision_sha256')),None)
        if not parent:continue
        path=artifact/'revisions'/f'{parent["number"]}.san';code=path.read_bytes().decode('utf-8')
        source_path=next((RUNS/row['batch']/'inputs'/folder.name).glob('*.vue'));source=source_path.read_bytes().decode('utf-8')
        if hashed(path)!=parent['file']['sha256'] or hashed(source_path)!=row['source_sha256']:raise ValueError('historical_hash_changed')
        proc=subprocess.run(['node',str(PROJECT/'engine/migration_pipeline/utils/parent_prop_semantics.cjs')],
            input=json.dumps({'vue':source,'code':code,'repair':True}),capture_output=True,encoding='utf-8',check=True)
        rule=json.loads(proc.stdout)
        if 'restored_source_parent_prop_defaults' not in rule.get('changes',[]):continue
        dest=output/row['sample_id'];write_once(dest/'candidate.san',rule['code'])
        request=read(artifact/'request.json')['request'];ssm=read(artifact/'ssm.json')['ssm']
        spec={k:request[k] for k in ('props','actions','thresholds')}
        result={'component':row['component'],'parent_sha256':hashed(path),'source_sha256':hashed(source_path),
            'candidate_sha256':hashed(dest/'candidate.san'),'changes':rule['changes'],'model_calls':0,'historical_report':row['report']}
        for label,text in [('before',code),('after',rule['code'])]:
            assessment,raw=evaluate(settings,runtime,source,text,ssm,spec)
            result[label]=assessment;raw_evidence(dest,label,raw)
        result['gate']=candidate_decision(result['before'],result['after'])
        write_once(dest/'result.json',result);rows.append(result)
        print(json.dumps({'component':row['component'],'runtime':result['after']['dimensions']['compile_runtime'],'gate':result['gate']},ensure_ascii=True),flush=True)
    if binding()!=version:raise ValueError('implementation_changed')
    write_once(output/'results.json',rows)
    write_once(output/'summary.json',{'records':len(rows),'model_calls':0,'new_migration_passes':sum(r['after']['passed'] and r['gate']['accepted'] for r in rows),
        'runtime_recovered':sum(r['after']['dimensions']['compile_runtime']=='pass' for r in rows),
        'progress_accepted':sum(r['gate']['accepted'] for r in rows),'historical_records_changed':False})
    write_once(output/'SHA256SUMS.txt',''.join(hashed(p)+'  '+p.relative_to(output).as_posix()+'\n' for p in sorted(output.rglob('*')) if p.is_file()))


if __name__=='__main__':main()
