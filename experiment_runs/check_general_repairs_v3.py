"""Repeatable local-only regression verification; no live jobs/model calls."""
import io
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'migration_system/tests'))
from analyze_coverage import write_once,hashed

MODULES=(
    'test_general_repairs_v3','test_semantic_comparison_v1','test_modular_syntax_first',
    'test_modular_evaluator_compatibility','test_modular_empty_class_policy','test_closed_loop_v2',
    'test_repair_context','test_refactor_reuse','test_generation_context_v2',
    'test_modular_safety','test_modular_system',
)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--label',default='');args=parser.parse_args()
    if args.label and not re.fullmatch('[a-z0-9_-]+',args.label):raise ValueError('invalid label')
    if args.label:MODULES=(*MODULES,'test_internal_assignment_v3_followup','test_factory_access_ast_v3')
    if args.label and args.label!='final':MODULES=(*MODULES,'test_template_branches_v3','test_inline_option_shape_v4')
    if args.label and args.label not in ('final','inline_v4'):MODULES=(*MODULES,'test_computed_options_v5')
    from replay_general_repairs_v3 import binding
    implementation=binding()
    entries=[];logs=[]
    for name in MODULES:
        try:
            proc=subprocess.run([str(ROOT/'migration_system/.venv/Scripts/python.exe'),'-u','-m','unittest','discover',
                '-s',str(ROOT/'migration_system/tests'),'-p',name+'.py','-v'],capture_output=True,timeout=240)
            text=proc.stdout.decode('utf-8',errors='replace')+proc.stderr.decode('utf-8',errors='replace')
            match=re.search(r'Ran (\d+) tests? in ',text)
            entry={'module':name,'exit_code':proc.returncode,'tests_run':int(match[1]) if match else 0,'timed_out':False}
        except subprocess.TimeoutExpired as exc:
            text=(exc.stdout or b'').decode('utf-8',errors='replace')+(exc.stderr or b'').decode('utf-8',errors='replace')
            entry={'module':name,'exit_code':None,'tests_run':None,'timed_out':True}
        logs.append('\nMODULE '+name+'\n'+text);entries.append(entry)
        print(json.dumps(entry),flush=True)
    text=''.join(logs)
    report={'scope':'local_unit_parser_browser_and_injected_client_regressions_not_real_model_success',
            'tests_run':sum(e['tests_run'] or 0 for e in entries),'module_results':entries,
            'successful':all(e['exit_code']==0 for e in entries),'real_model_calls':0,
            'modules':{name:hashed(ROOT/'migration_system/tests'/(name+'.py')) for name in MODULES}}
    if binding()!=implementation:raise ValueError('Implementation changed during tests; do not claim one-version results')
    report['implementation_sha256']=implementation
    dest=ROOT/'migration_system/docs/verification/2026-11-19_general_repairs_v1'
    suffix='-'+args.label if args.label else ''
    write_once(dest/('test-results'+suffix+'.json'),report);write_once(dest/('test-results'+suffix+'.txt'),text)
    print(json.dumps({k:report[k] for k in ('scope','tests_run','successful','real_model_calls')},ensure_ascii=True),flush=True)
    raise SystemExit(0 if report['successful'] else 1)
