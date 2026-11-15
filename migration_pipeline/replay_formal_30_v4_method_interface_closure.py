"""Offline source API preservation closure; no model or browser permission calls."""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime,timedelta,timezone
from pathlib import Path

from migration_pipeline.analyze_formal_30_v4_full_regression import digest,verify_snapshot
from migration_pipeline.freeze_formal_30_v3_results import VERIFY_SCRIPT
from migration_pipeline.replay_formal_30_v4_semantic_closure import evaluate
from migration_pipeline.utils.bounded_semantics import inspect_semantics
from migration_pipeline.stages.repair import RepairStage
from migration_pipeline.utils.repair_scheduler import candidate_gate

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'data/experiments/snapshots/formal_30_v4_semantic_closure_v4_results_20261103_204227'
PRIOR=ROOT/'data/experiments/analysis/formal_30_v4_startup_phase_closure_v1_20261103'
OUTPUT=ROOT/'data/experiments/analysis/formal_30_v4_method_interface_closure_v1_20261103'
CHANGED={
    'migration_pipeline/utils/source_phase_semantics.cjs','migration_pipeline/utils/bounded_semantics.cjs',
    'migration_pipeline/utils/repair_scheduler.py','migration_pipeline/utils/repair_prompt.py',
    'migration_pipeline/stages/repair.py','migration_pipeline/stages/validate.py',
    'migration_pipeline/utils/semantic_coverage.py','tests/test_startup_phase_closure.py',
    'tests/test_repair_regression_guard.py',
}
ADDED=(
    'migration_pipeline/utils/method_interface_semantics.cjs','tests/test_method_interface_closure.py',
    'migration_pipeline/replay_formal_30_v4_method_interface_closure.py',
    'migration_pipeline/audit_formal_30_v4_notification_method.py','tests/test_notification_method_audit.py',
)


def inventory():
    if verify_snapshot(SOURCE)!=342 or verify_snapshot(PRIOR)!=24:
        raise RuntimeError('Unexpected immutable evidence inventory')
    old=json.loads((PRIOR/'live_inventory.json').read_text(encoding='utf-8'))
    changed={name for name,h in old.items() if digest(ROOT/name)!=h}
    if changed!=CHANGED:
        raise RuntimeError(f'Unexpected changed-file boundary: {sorted(changed)}')
    return {name:digest(ROOT/name) for name in set(old)|set(ADDED)}


def replay():
    verify_snapshot(SOURCE);verify_snapshot(PRIOR)
    report_path=SOURCE/'repair_reports/complex/MonitoringDashboard_repair_history.json'
    state=json.loads(report_path.read_text(encoding='utf-8'))['state']
    vue=SOURCE/'protocol/frozen/data/datasets/components/03_complex/MonitoringDashboard/vue/MonitoringDashboard.vue'
    text=vue.read_text(encoding='utf-8')
    rows,artifacts=[],{}
    cases=(('first_repair',state['repair_history'][0]['repair_result']['repaired_code']),
           ('final_raw',state['generated_code']),
           ('startup_fixed_final',(PRIOR/'final_automatic_pass_offline.san').read_text(encoding='utf-8')))
    for name,code in cases:
        before=evaluate(code,state,vue)
        fixed,rules=RepairStage._deterministic_repair_plan(code,before['validation_errors'],[],state['ssm'],str(vue),enable_residual_v2=True)
        after=evaluate(fixed,state,vue);gate=candidate_gate(before,after)
        if fixed==code or gate['should_stop'] or not after['validation_passed'] or not after['visual_eval_passed']:
            raise RuntimeError(f'Offline closure failed: {name}/{after["validation_errors"]}')
        again,_=RepairStage._deterministic_repair_plan(fixed,after['validation_errors'],after['visual_eval_errors'],state['ssm'],str(vue),enable_residual_v2=True)
        reverse=candidate_gate(after,before)
        if again!=fixed or not reverse['should_stop']:
            raise RuntimeError('Fixed point or reverse regression guard failed')
        inspected=inspect_semantics(fixed,text,ssm=state['ssm'])
        contract=next(c for c in inspected['method_contracts'] if c.get('name')=='requestNotificationPermission')
        if contract['status']!='callable_present' or contract['source_references']['count'] or contract['target_references']['count']:
            raise RuntimeError('Interface or no-new-trigger contract failed')
        startup=inspected['startup_contracts'][0]
        if startup['inited_direct_calls']!=0 or startup['attached_direct_calls']!=1:
            raise RuntimeError('Startup contract regressed')
        compact=lambda s:{k:v for k,v in s.items() if k not in {'generated_code','ssm'}}
        artifacts[name]=fixed
        rows.append({'case':name,'before':compact(before),'after':compact(after),'rules':[r for _,r in rules],
            'gate':gate,'reverse_gate':reverse,'method_contract':contract,'startup_contract':startup})
    summary=SOURCE/'formal_30_v4_semantic_closure_v4_summary.json'
    data={'created_at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'classification':'offline_source_method_interface_preservation_development_closure_not_fresh_model_score',
        'source_snapshot':SOURCE.name,'raw_verified_files':342,'prior_startup_verified_files':24,
        'source_summary_sha256':digest(summary),'source_history_sha256':digest(report_path),
        'original_automatic_passed':True,'original_summary_modified':False,
        'model_requests':0,'browser_interaction_test_performed':False,'browser_permission_request_performed':False,
        'cases':rows,'boundary':'Exported parent callable surface, not complete equivalence of existing method bodies. '
          'Only internally unreferenced, unambiguous, synchronous simple methods with understood expressions '
          'and unshadowed whitelisted dependencies can be restored. Source guards remain unchanged. '
          'No new UI/lifecycle invocation, unknown dependency guessing, global permission execution, '
          'or overwrite of existing options. Reserved initData mapping remains delegated to its existing rules. '
          'Unknown/missing interfaces stay diagnostics; controlled Node permission stubs are unit tests, not browser verification.'}
    verify_snapshot(SOURCE);verify_snapshot(PRIOR)
    return artifacts,data


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-evidence',action='store_true')
    args=parser.parse_args()
    if args.write_evidence and OUTPUT.exists():raise FileExistsError('Never replace frozen evidence')
    hashes=inventory();tests=''
    if args.write_evidence:
        print('Running complete unit tests; no model requests.',flush=True)
        proc=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p','test_*.py'],cwd=ROOT,
            env={**os.environ,'PYTHONIOENCODING':'utf-8'},capture_output=True,text=True,encoding='utf-8')
        tests=proc.stdout+proc.stderr
        if proc.returncode:raise RuntimeError(f'Complete tests failed:\n{tests}')
    print('Replaying three frozen candidates without model calls.',flush=True)
    artifacts,data=replay()
    if hashes!=inventory():raise RuntimeError('Code changed during verification')
    if args.write_evidence:
        match=re.search(r'Ran (\d+) tests in ([\d.]+)s',tests)
        if not match:raise RuntimeError('Unit test count unavailable')
        data['unit_tests']={'passed':int(match[1]),'failed':0,'elapsed_seconds':float(match[2])}
        OUTPUT.mkdir(parents=True)
        for name,code in artifacts.items():
            path=OUTPUT/f'{name}_offline.san';path.write_text(code,encoding='utf-8')
            next(r for r in data['cases'] if r['case']==name)['output_sha256']=digest(path)
        old_code={p.relative_to(PRIOR/'code').as_posix() for p in (PRIOR/'code').rglob('*') if p.is_file()}
        paths=old_code|set(ADDED)|CHANGED
        for name in sorted(paths):
            path=OUTPUT/'code'/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,path)
        data['changed_prior_live_files']=sorted(CHANGED)
        data['frozen_code_files']=len(paths)
        (OUTPUT/'live_inventory.json').write_text(json.dumps(hashes,indent=2)+'\n',encoding='utf-8')
        (OUTPUT/'unit_tests.txt').write_text(tests,encoding='utf-8')
        (OUTPUT/'replay.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (OUTPUT/'verify_snapshot.py').write_text(VERIFY_SCRIPT,encoding='utf-8')
        files=sorted(p for p in OUTPUT.rglob('*') if p.is_file())
        (OUTPUT/'SHA256SUMS.txt').write_text('\n'.join(f'{digest(p)}  {p.relative_to(OUTPUT).as_posix()}' for p in files)+'\n',encoding='utf-8')
        verify_snapshot(OUTPUT)
    print(json.dumps({'model_requests':0,'evidence_written':args.write_evidence,'unit_tests':data.get('unit_tests'),
        'cases':[{'case':r['case'],'validation_passed':r['after']['validation_passed'],
                  'visual_eval_passed':r['after']['visual_eval_passed'],'structure_similarity':r['after']['structure_similarity'],
                  'rules':r['rules']} for r in data['cases']]}))


if __name__=='__main__':main()
