"""Version-locked local regressions and original v10 negative/positive witnesses."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from dataclasses import replace
import importlib
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from analyze_coverage import ROOT,read,write_once,hashed
from replay_general_repairs_v3 import binding
from check_general_repairs_v10 import MODULES as PREVIOUS

NEW=('test_container_copy_v11','test_component_literal_props_v11')
MODULES=(*PREVIOUS,*NEW)
DEST=ROOT/'migration_system/docs/verification/2026-11-20_followup_v11_verified'
OLD=ROOT/'experiment_runs/composed_v10_syntax_replay_20261120/implementation'


def red(settings):
    sys.path.insert(0,str(ROOT/'migration_system/tests'))
    with tempfile.TemporaryDirectory(prefix='cardmig-v11-old-engine-') as temp:
        project=Path(temp)
        for folder in ('browser','engine'):shutil.copytree(OLD/folder,project/folder)
        shutil.copytree(ROOT/'migration_system/engine/node_modules',project/'engine/node_modules')
        shutil.copytree(ROOT/'migration_system/browser/node_modules',project/'browser/node_modules')
        shutil.copytree(ROOT/'migration_system/frontend/node_modules/vue',project/'frontend/node_modules/vue')
        (project/'configs').mkdir()
        shutil.copyfile(ROOT/'migration_system/configs/system.toml',project/'configs/system.toml')
        suite=unittest.TestSuite()
        for name in NEW:
            module=importlib.import_module(name);module.PROJECT=project
            module.load_settings=lambda **kw:replace(settings,project_root=project,repository_root=project/'engine')
            suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
        stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
        write_once(DEST/'red/log.txt',stream.getvalue())
        write_once(DEST/'red/result.json',{'scope':'same_new_assertions_on_frozen_v10_engine_and_browser_current_installed_parser_dependencies',
            'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
            'source_snapshot':str(OLD.relative_to(ROOT)),
            'old_files_sha256':{p.relative_to(OLD).as_posix():hashed(p) for folder in ('engine','browser') for p in (OLD/folder).rglob('*') if p.is_file()},
            'models_called':0,'historical_or_production_files_mutated':False})
        print(json.dumps({'phase':'RED','tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors)}),flush=True)
        if not result.failures or result.errors:raise ValueError('expected_red_failures_without_infrastructure_errors')


def run(name):
    try:
        p=subprocess.run([str(ROOT/'migration_system/.venv/Scripts/python.exe'),'-u','-m','unittest','discover',
            '-s',str(ROOT/'migration_system/tests'),'-p',name+'.py','-v'],capture_output=True,timeout=480)
        log=p.stdout.decode('utf-8',errors='replace')+p.stderr.decode('utf-8',errors='replace')
        match=re.search(r'Ran (\d+) tests? in ',log)
        result={'module':name,'exit_code':p.returncode,'tests_run':int(match[1]) if match else 0,'timed_out':False}
    except subprocess.TimeoutExpired as exc:
        log=(exc.stdout or b'').decode('utf-8',errors='replace')+(exc.stderr or b'').decode('utf-8',errors='replace')
        result={'module':name,'exit_code':None,'tests_run':0,'timed_out':True}
    write_once(DEST/('green/'+name+'.txt'),log);print(json.dumps(result),flush=True);return result


def main():
    from card_migration_system.config import load_settings
    if DEST.exists():raise ValueError('choose_new_immutable_verification_directory')
    implementation=binding();tests={n:hashed(ROOT/'migration_system/tests'/(n+'.py')) for n in MODULES}
    write_once(DEST/'protocol.json',{'scope':'local_fixed_version_regressions_NOT_new_model_batch',
        'implementation_sha256':implementation,'tests_sha256':tests,'workers':2,'module_timeout':480,
        'production_timeout_or_budget_changed':False,'real_model_calls':0,'cloud_database_access':False,
        'script_sha256':hashed(Path(__file__))})
    for relative in implementation:write_once(DEST/'implementation'/relative,(ROOT/'migration_system'/relative).read_bytes().decode('utf-8'))
    for name in MODULES:write_once(DEST/'tests'/(name+'.py'),(ROOT/'migration_system/tests'/(name+'.py')).read_bytes().decode('utf-8'))
    red(load_settings(project_root=ROOT/'migration_system',environ={}))
    entries=[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        for f in as_completed([pool.submit(run,n) for n in MODULES]):entries.append(f.result())
    if binding()!=implementation:raise ValueError('production_changed_during_verification')
    if tests!={n:hashed(ROOT/'migration_system/tests'/(n+'.py')) for n in MODULES}:raise ValueError('test_changed')
    entries.sort(key=lambda r:MODULES.index(r['module']))
    report={'successful':all(r['exit_code']==0 for r in entries),'tests_run':sum(r['tests_run'] for r in entries),
        'module_results':entries,'implementation_sha256':implementation,'real_model_calls':0,'cloud_database_access':False}
    write_once(DEST/'test-results.json',report)
    write_once(DEST/'SHA256SUMS.txt',''.join(hashed(p)+'  '+p.relative_to(DEST).as_posix()+'\n' for p in sorted(DEST.rglob('*')) if p.is_file()))
    print(json.dumps({k:report[k] for k in ('successful','tests_run','real_model_calls')}),flush=True)
    raise SystemExit(0 if report['successful'] else 1)


if __name__=='__main__':main()
