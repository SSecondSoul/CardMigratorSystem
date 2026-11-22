"""Nine targeted AST regressions after the metadata-only follow-up.

The earlier 249-test main-version result stays separate; do not manufacture a
same-version total by adding its counts to these tests.
"""
import json
import re
import subprocess
from analyze_coverage import ROOT,write_once,read,hashed
from replay_general_repairs_v3 import binding

dest=ROOT/'migration_system/docs/verification/2026-11-20_followup_v9/scope_verified'
before=binding()
prior_path=dest.parent/'export_verified/test-results.json'
prior=read(prior_path)
if not prior['successful'] or prior['tests_run']!=249:raise ValueError('verified_main_version_required')
changes=sorted(k for k in before if before[k]!=prior['implementation_sha256'].get(k))
if changes!=['engine/MANIFEST.json','engine/migration_pipeline/utils/bounded_semantics.cjs']:
    raise ValueError('metadata_only_followup_expected')
modules={name:hashed(ROOT/'migration_system/tests'/(name+'.py')) for name in
    ('test_parent_hook_metadata_v9','test_parent_hook_scope_v9')}
p=subprocess.run([str(ROOT/'migration_system/.venv/Scripts/python.exe'),'-u','-m','unittest','discover',
    '-s',str(ROOT/'migration_system/tests'),'-p','test_parent_hook*_v9.py','-v'],capture_output=True,timeout=300)
log=p.stdout.decode('utf-8',errors='replace')+p.stderr.decode('utf-8',errors='replace')
count=re.search(r'Ran (\d+) tests? in ',log)
if binding()!=before:raise ValueError('implementation_changed_during_followup')
if modules!={name:hashed(ROOT/'migration_system/tests'/(name+'.py')) for name in modules}:
    raise ValueError('test_assertions_changed')
report={'scope':'metadata_only_followup_targeted_AST_tests_not_same_version_249_total',
    'tests_run':int(count[1]) if count else 0,'successful':p.returncode==0,'real_model_calls':0,
    'implementation_sha256':before,'modules':modules,'script_sha256':hashed(__import__('pathlib').Path(__file__)),
    'prior_main_tests':{'count':249,'sha256':hashed(prior_path),'same_implementation':False},
    'implementation_difference':changes,'old_failure_preserved':'../scope_red/'}
write_once(dest/'output.txt',log);write_once(dest/'test-results.json',report)
write_once(dest/'SHA256SUMS.txt',''.join(hashed(p)+'  '+p.relative_to(dest).as_posix()+'\n'
    for p in sorted(dest.rglob('*')) if p.is_file()))
print(json.dumps({k:report[k] for k in ('tests_run','successful','real_model_calls')}),flush=True)
raise SystemExit(0 if report['successful'] and report['tests_run']==9 else 1)
