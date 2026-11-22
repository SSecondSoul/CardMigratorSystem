"""Read-only investigation of ALL residual dynamic-call owners, not a waiver."""
import json
import subprocess
from pathlib import Path
from analyze_coverage import RUNS,read,write_once,hashed

ROOT=RUNS.parent


def main():
    reference=RUNS/'composed_v8_final_replay_20261120'
    pairs={p['component']:p for p in read(RUNS/'analysis_v3_vs_first70_20261119/pairs.json')}
    inputs=[];evidence=[]
    for row in read(reference/'results.json'):
        if 'source_dynamic_assignment_unproven' not in row.get('effective_codes',[]):continue
        folder=reference/row['sample_id'];pair=pairs[row['component']]
        original=(RUNS/pair['new']['report']).parent
        source=next((RUNS/pair['new']['batch']/'inputs'/original.name).glob('*.vue'))
        if hashed(source)!=pair['new']['source_sha256']:raise ValueError('source_hash_changed')
        assessment=read(folder/'effective-assessment.json')
        for diagnostic in assessment.get('diagnostics',[]):
            if diagnostic['code']!='source_dynamic_assignment_unproven':continue
            setter=diagnostic['location'].rsplit('.',1)[-1]
            inputs.append({'component':row['component'],'setter':setter,
                'source':source.read_bytes().decode('utf-8'),'code':(folder/'effective.san').read_bytes().decode('utf-8')})
            evidence.append({'component':row['component'],'source_sha256':hashed(source),
                'target_sha256':hashed(folder/'effective.san'),'source':str(source.relative_to(ROOT)),
                'assessment':str((folder/'effective-assessment.json').relative_to(ROOT)),
                'refusals':diagnostic.get('details',{}).get('refusals',[])})
    proc=subprocess.run(['node',str(Path(__file__).with_suffix('.cjs'))],input=json.dumps(inputs).encode(),
        capture_output=True,timeout=30,cwd=ROOT,check=True)
    rows=json.loads(proc.stdout)
    dest=RUNS/'composed_v9_call_owner_audit_20261120'
    report={'scope':'parser_only_investigation_not_a_fix_or_equivalence_proof','real_model_calls':0,
        'cloud_database_access':False,'records':len(rows),'input_bindings':evidence,'rows':rows,
        'interpretation':'Watch option methods and private timer writes need their own owner/transfer proof. Complete caller/body/key multiplicity findings stay errors until a source-bound repair and regression gate prove them.'}
    write_once(dest/'audit.json',report)
    write_once(dest/'SHA256SUMS.txt',hashed(dest/'audit.json')+'  audit.json\n')
    print(json.dumps({'records':len(rows),'source_watch_owners':{
        r['component']:sorted({o['method'] for o in r['source'].get('owners',[]) if o['container']=='watch'})
        for r in rows},'real_model_calls':0},ensure_ascii=True))


if __name__=='__main__':main()
