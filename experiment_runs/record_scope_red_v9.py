"""Capture the scoped-name regression before changing its implementation."""
import json
import re
import subprocess
from analyze_coverage import ROOT,write_once,hashed
from replay_general_repairs_v3 import binding

dest=ROOT/'migration_system/docs/verification/2026-11-20_followup_v9/scope_red'
before=binding()
p=subprocess.run([str(ROOT/'migration_system/.venv/Scripts/python.exe'),'-u','-m','unittest','discover',
    '-s',str(ROOT/'migration_system/tests'),'-p','test_parent_hook_scope_v9.py','-v'],capture_output=True,timeout=60)
log=p.stdout.decode('utf-8',errors='replace')+p.stderr.decode('utf-8',errors='replace')
if before!=binding():raise ValueError('implementation_changed_during_RED')
if p.returncode!=1 or 'FAILED (failures=1)' not in log:raise ValueError('expected_one_scoped_name_RED')
write_once(dest/'test-output.txt',log)
write_once(dest/'report.json',{'scope':'intentional_RED_not_passing_verification','tests_run':2,'failures':1,
    'test_sha256':hashed(ROOT/'migration_system/tests/test_parent_hook_scope_v9.py'),
    'implementation_sha256':before,'real_model_calls':0,'changed_production':False})
print(json.dumps({'expected_RED_reproduced':True,'tests':2,'failures':1}))
