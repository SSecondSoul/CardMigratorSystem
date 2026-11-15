"""Freeze offline startup-phase closure with complete tests; never calls a model."""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from migration_pipeline.analyze_formal_30_v4_full_regression import digest, verify_snapshot
from migration_pipeline.freeze_formal_30_v3_results import VERIFY_SCRIPT
from migration_pipeline.replay_formal_30_v4_semantic_closure import evaluate
from migration_pipeline.utils.bounded_semantics import inspect_semantics
from migration_pipeline.stages.repair import RepairStage
from migration_pipeline.utils.repair_scheduler import candidate_gate


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/experiments/snapshots/formal_30_v4_semantic_closure_v4_results_20261103_204227'
OUTPUT = ROOT / 'data/experiments/analysis/formal_30_v4_startup_phase_closure_v1_20261103'
CHANGED = {
    'migration_pipeline/utils/source_phase_semantics.cjs',
    'migration_pipeline/utils/bounded_semantics.cjs',
    'migration_pipeline/utils/repair_scheduler.py',
    'migration_pipeline/utils/repair_prompt.py', 'migration_pipeline/stages/repair.py',
}
ADDED = (
    'migration_pipeline/utils/startup_phase_semantics.cjs',
    'migration_pipeline/replay_formal_30_v4_startup_phase_closure.py',
    'tests/test_startup_phase_closure.py',
    'migration_pipeline/analyze_formal_30_v4_semantic_closure_v4.py',
    'tests/test_semantic_closure_v4_analysis.py',
)
CODE_PATHS = tuple(sorted(CHANGED | set(ADDED) | {
    'migration_pipeline/utils/bounded_semantics.py', 'migration_pipeline/stages/validate.py',
    'migration_pipeline/utils/repair_regression_guard.py',
    'migration_pipeline/utils/semantic_coverage.py', 'migration_pipeline/utils/semantic_coverage.cjs',
    'migration_pipeline/replay_formal_30_v4_semantic_closure.py',
    'tests/test_source_phase_semantics.py', 'tests/test_coverage_and_helper_closure.py',
}))


def inventory():
    if verify_snapshot(SOURCE) != 342:
        raise RuntimeError('Unexpected source inventory')
    rows = [line.split('  ',1) for line in (SOURCE/'protocol/SHA256SUMS.txt').read_text(encoding='utf-8').splitlines()]
    old = {name.removeprefix('frozen/'):h for h,name in rows if name.startswith('frozen/')}
    changed = {name for name,h in old.items() if digest(ROOT/name) != h}
    if changed != CHANGED:
        raise RuntimeError(f'Unexpected changed boundary: {sorted(changed)}')
    return {name:digest(ROOT/name) for name in set(old) | set(ADDED)}


def replay():
    verify_snapshot(SOURCE)
    report_path = SOURCE/'repair_reports/complex/MonitoringDashboard_repair_history.json'
    state = json.loads(report_path.read_text(encoding='utf-8'))['state']
    vue = SOURCE/'protocol/frozen/data/datasets/components/03_complex/MonitoringDashboard/vue/MonitoringDashboard.vue'
    text = vue.read_text(encoding='utf-8')
    rows, artifacts = [], {}
    for name, code in (('first_repair',state['repair_history'][0]['repair_result']['repaired_code']),
                       ('final_automatic_pass',state['generated_code'])):
        before = evaluate(code,state,vue)
        codes = {e['code'] for e in before['validation_errors']}
        if 'source_startup_phase_not_landed' not in codes:
            raise RuntimeError('New checker did not diagnose source startup contract')
        fixed, rules = RepairStage._deterministic_repair_plan(code,before['validation_errors'],[],state['ssm'],
                                                            str(vue),enable_residual_v2=True)
        after = evaluate(fixed,state,vue)
        gate = candidate_gate(before,after)
        if (fixed == code or gate['should_stop'] or not after['validation_passed']
                or not after['visual_eval_passed']):
            raise RuntimeError(f'Closure failed: {name}')
        again, _ = RepairStage._deterministic_repair_plan(fixed,after['validation_errors'],after['visual_eval_errors'],
                                                        state['ssm'],str(vue),enable_residual_v2=True)
        if again != fixed or not candidate_gate(after,before)['should_stop']:
            raise RuntimeError('Fixed point or regression protection failed')
        observed = inspect_semantics(fixed,text,ssm=state['ssm'])['startup_contracts']
        if len(observed) != 1 or observed[0]['inited_direct_calls'] != 0 or observed[0]['attached_direct_calls'] != 1:
            raise RuntimeError('Incorrect retained initializer counts')
        compact = lambda s:{k:v for k,v in s.items() if k not in {'generated_code','ssm'}}
        artifacts[name] = fixed
        rows.append({'case':name,'before':compact(before),'after':compact(after),'rules':[label for _,label in rules],
            'gate':gate,'regression_gate':candidate_gate(after,before),'after_startup_contract':observed[0]})
    summary = SOURCE/'formal_30_v4_semantic_closure_v4_summary.json'
    data = {'created_at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'classification':'offline_source_proven_startup_phase_development_closure_not_fresh_model_score',
        'source_snapshot':SOURCE.name,'verified_files':342,'source_summary_sha256':digest(summary),
        'source_repair_history_sha256':digest(report_path),'original_automatic_passed':True,
        'original_summary_modified':False,'model_requests':0,'browser_interaction_test_performed':False,
        'cases':rows,'boundary':'Only a unique parent alias of a source first-mounted, zero-argument wrapper '
          'consisting of known zero-argument calls is assessed. Early source hooks, ambiguous names, '
          'computed access and unknown uses fail closed. Only the proven inited suffix is removed or '
          'relocated; watcher registrations stay intact. Not arbitrary call-graph equivalence. '
          'Removed notification permission method remains a separate review item, not restored here.'}
    verify_snapshot(SOURCE)
    return artifacts,data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-evidence',action='store_true')
    args = parser.parse_args()
    if args.write_evidence and OUTPUT.exists():
        raise FileExistsError('Never overwrite frozen evidence')
    hashes = inventory()
    tests = ''
    if args.write_evidence:
        print('Running complete tests; no model requests.',flush=True)
        proc = subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p','test_*.py'],cwd=ROOT,
            env={**os.environ,'PYTHONIOENCODING':'utf-8'},capture_output=True,text=True,encoding='utf-8')
        tests = proc.stdout + proc.stderr
        if proc.returncode:
            raise RuntimeError(f'Complete tests failed:\n{tests}')
    print('Replaying both frozen candidates without model calls.',flush=True)
    artifacts,data = replay()
    if hashes != inventory():
        raise RuntimeError('Code changed during verification')
    if args.write_evidence:
        match = re.search(r'Ran (\d+) tests in ([\d.]+)s',tests)
        if not match:
            raise RuntimeError('Test count unavailable')
        data['unit_tests'] = {'passed':int(match[1]),'failed':0,'elapsed_seconds':float(match[2])}
        OUTPUT.mkdir(parents=True)
        for name,code in artifacts.items():
            path = OUTPUT/f'{name}_offline.san'
            path.write_text(code,encoding='utf-8')
            next(r for r in data['cases'] if r['case']==name)['output_sha256'] = digest(path)
        for name in CODE_PATHS:
            path = OUTPUT/'code'/name
            path.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(ROOT/name,path)
        data['baseline_relative_code_changes'] = sorted(CHANGED)
        (OUTPUT/'live_inventory.json').write_text(json.dumps(hashes,indent=2)+'\n',encoding='utf-8')
        (OUTPUT/'unit_tests.txt').write_text(tests,encoding='utf-8')
        (OUTPUT/'replay.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (OUTPUT/'verify_snapshot.py').write_text(VERIFY_SCRIPT,encoding='utf-8')
        files = sorted(p for p in OUTPUT.rglob('*') if p.is_file())
        (OUTPUT/'SHA256SUMS.txt').write_text('\n'.join(f'{digest(p)}  {p.relative_to(OUTPUT).as_posix()}' for p in files)+'\n',encoding='utf-8')
        verify_snapshot(OUTPUT)
    print(json.dumps({'model_requests':0,'evidence_written':args.write_evidence,
        'unit_tests':data.get('unit_tests'),'cases':[{'case':r['case'],
          'validation_passed':r['after']['validation_passed'],'visual_eval_passed':r['after']['visual_eval_passed'],
          'structure_similarity':r['after']['structure_similarity'],'rules':r['rules']} for r in data['cases']]}))


if __name__ == '__main__':
    main()
