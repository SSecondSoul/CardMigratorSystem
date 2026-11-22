"""Fixed production version, old-browser RED and full related GREEN; local only."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
import argparse
import importlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import shutil
import unittest
from analyze_coverage import ROOT, write_once, hashed
from replay_general_repairs_v3 import binding
from check_general_repairs_v9 import MODULES as PREVIOUS

NEW=('test_option_boundary_syntax_v10','test_for_key_grammar_v10',
     'test_scalar_leaf_syntax_v10','test_multi_method_closing_v10')
MODULES=(*PREVIOUS,'test_parent_hook_scope_v9',*NEW)
DEST=ROOT/'migration_system/docs/verification/2026-11-20_followup_v10'
OLD=ROOT/'experiment_runs/composed_v9_verified_replay_20261120/implementation/browser'


def red():
    sys.path.insert(0,str(ROOT/'migration_system/tests'))
    from card_migration_system.config import load_settings
    settings=load_settings(project_root=ROOT/'migration_system',environ={})
    with tempfile.TemporaryDirectory(prefix='cardmig-v10-old-browser-') as temp:
        project=Path(temp);shutil.copytree(OLD,project/'browser')
        suite=unittest.TestSuite()
        for name in NEW:
            module=importlib.import_module(name)
            module.load_settings=lambda **kw:replace(settings,project_root=project)
            suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
        stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
        write_once(DEST/'red/log.txt',stream.getvalue())
        write_once(DEST/'red/result.json',{'scope':'new_regressions_on_frozen_v9_browser_current_unchanged_parser_dependencies',
            'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
            'old_browser':{p.relative_to(OLD).as_posix():hashed(p) for p in OLD.rglob('*') if p.is_file()},
            'models_called':0,'temporary_copy_not_mutated_historical_or_production_files':True})
        print(json.dumps({'phase':'RED','tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors)}),flush=True)
        if not result.failures or result.errors:raise ValueError('expected_clean_red_failures')


def run(name):
    proc=subprocess.run([str(ROOT/'migration_system/.venv/Scripts/python.exe'),'-u','-m','unittest','discover',
        '-s',str(ROOT/'migration_system/tests'),'-p',name+'.py','-v'],capture_output=True,timeout=480)
    log=proc.stdout.decode('utf-8',errors='replace')+proc.stderr.decode('utf-8',errors='replace')
    match=re.search(r'Ran (\d+) tests? in ',log)
    write_once(DEST/('green/'+name+'.txt'),log)
    result={'module':name,'exit_code':proc.returncode,'tests_run':int(match[1]) if match else 0}
    print(json.dumps(result),flush=True);return result


def main():
    if DEST.exists():raise ValueError('choose_new_immutable_evidence_directory')
    implementation=binding();tests={name:hashed(ROOT/'migration_system/tests'/(name+'.py')) for name in MODULES}
    write_once(DEST/'protocol.json',{'scope':'fixed_version_local_unit_parser_browser_and_injected_client_tests',
        'implementation_sha256':implementation,'tests_sha256':tests,'module_timeout':480,'workers':2,
        'real_model_calls':0,'cloud_database_access':False,'script_sha256':hashed(Path(__file__))})
    for relative in implementation:
        write_once(DEST/'implementation'/relative,(ROOT/'migration_system'/relative).read_bytes().decode('utf-8'))
    for name in MODULES:
        write_once(DEST/'tests'/(name+'.py'),(ROOT/'migration_system/tests'/(name+'.py')).read_bytes().decode('utf-8'))
    red()
    entries=[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        for future in as_completed([pool.submit(run,name) for name in MODULES]):entries.append(future.result())
    if binding()!=implementation:raise ValueError('production_code_changed_during_tests')
    if tests!={name:hashed(ROOT/'migration_system/tests'/(name+'.py')) for name in MODULES}:raise ValueError('test_source_changed')
    entries.sort(key=lambda row:MODULES.index(row['module']))
    report={'successful':all(row['exit_code']==0 for row in entries),'tests_run':sum(row['tests_run'] for row in entries),
        'module_results':entries,'implementation_sha256':implementation,'real_model_calls':0,'cloud_database_access':False}
    write_once(DEST/'test-results.json',report)
    write_once(DEST/'SHA256SUMS.txt',''.join(hashed(p)+'  '+p.relative_to(DEST).as_posix()+'\n' for p in sorted(DEST.rglob('*')) if p.is_file()))
    print(json.dumps({key:report[key] for key in ('successful','tests_run','real_model_calls')}),flush=True)
    raise SystemExit(0 if report['successful'] else 1)


if __name__=='__main__':main()
