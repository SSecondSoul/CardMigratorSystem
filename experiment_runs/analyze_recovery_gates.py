"""Diagnose recovery-gate deadlocks without changing a historical decision."""
from collections import Counter
from pathlib import Path
from hashlib import sha256
import json
import subprocess
from analyze_coverage import read,write_once,RUNS,ROOT


def templates(code):
    # Exact static template bytes, not a tree with expressions anonymized.
    script='''import fs from 'node:fs';import path from 'node:path';import {createRequire} from 'node:module';
import {templateRegions} from './migration_system/browser/attribute-syntax.mjs';
const require=createRequire(path.resolve('migration_system/engine/package.json'));
const code=JSON.parse(fs.readFileSync(0,'utf8'));
process.stdout.write(JSON.stringify(templateRegions(code,require).map(r=>[r.scope,r.text])));'''
    proc=subprocess.run(['node','--input-type=module','-e',script],input=json.dumps(code),encoding='utf-8',capture_output=True,check=True,cwd=ROOT)
    return read_bytes(proc.stdout)


def read_bytes(text):return json.loads(text)


def main():
    pairs=read(RUNS/'analysis_v3_vs_first70_20261119/pairs.json');findings=[]
    for pair in pairs:
        row=pair['new'];artifact=(RUNS/row['report']).parent/'artifacts'
        reports={read(p).get('revision_sha256'):read(p) for p in (artifact/'evaluations').glob('*.json')}
        revisions={read(p)['file']['sha256']:int(p.stem) for p in (artifact/'revisions').glob('*.json')}
        for d in row['decisions']:
            if d.get('added_errors')!=['rendered_control_position_mismatch']:continue
            before,after=(reports.get(d[k],{}) for k in ('previous','candidate'))
            b,a=before.get('dimensions',{}),after.get('dimensions',{})
            controls=after.get('initial_control_state',{});source=before.get('control_gate_evidence',{}).get('source_snapshot')
            if not (b.get('compile_runtime')=='fail' and a.get('compile_runtime')=='pass'
                    and b.get('source_baseline')==a.get('source_baseline')=='pass'
                    and source and source==after.get('control_gate_evidence',{}).get('source_snapshot')
                    and controls.get('values_equal_in_order') is True
                    and controls.get('source_count')==controls.get('target_count')):continue
            first,second=(artifact/'revisions'/f'{revisions[d[k]]}.san' for k in ('previous','candidate'))
            old,new=(templates(p.read_bytes().decode('utf-8')) for p in (first,second))
            findings.append({'component':row['component'],'round':d['round'],'decision':d,
                'source_capture_identical':True,'static_templates_identical':old==new,
                'new_controls_values_match_in_order':True,'migration_passed':after['passed'],
                'historical_decision_unchanged':True,'model_calls':0})
    output=RUNS/'recovery_gate_investigation_20261119'
    write_once(output/'findings.json',findings)
    summary={'scope':'read_only_candidate_gate_causal_investigation_not_a_waiver',
             'records':len(findings),'components':len({f['component'] for f in findings}),
             'unchanged_static_template_records':sum(f['static_templates_identical'] for f in findings),
             'model_calls':0,'historical_decisions_changed':False}
    write_once(output/'summary.json',summary);print(json.dumps(summary,ensure_ascii=True))


if __name__=='__main__':main()
