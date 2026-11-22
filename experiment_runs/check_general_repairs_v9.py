"""Fixed-version related regressions, two isolated modules at most, no model/DB."""
from concurrent.futures import ThreadPoolExecutor,as_completed
import json
from pathlib import Path
import re
import subprocess
from analyze_coverage import ROOT,write_once,hashed
from replay_general_repairs_v3 import binding
from check_general_repairs_v3 import MODULES as BASE

MODULES=(*BASE,'test_internal_assignment_v3_followup','test_factory_access_ast_v3',
 'test_template_branches_v3','test_inline_option_shape_v4','test_computed_options_v5',
 'test_computed_dependency_group_v6','test_normalization_v6','test_native_value_v6',
 'test_post_model_normalization_v6','test_remaining_repairs_v7',
 'test_internal_parameter_flow_v8','test_initialization_phase_v8','test_recovery_sequence_v8','test_native_select_v8',
 'test_parent_hook_metadata_v9','test_initialization_recovery_v9','test_native_binding_whitespace_v9',
 'test_template_fidelity_v9','test_class_string_serialization_v9')
DEST=ROOT/'migration_system/docs/verification/2026-11-20_followup_v9/export_verified'


def run(name):
    try:
        proc=subprocess.run([str(ROOT/'migration_system/.venv/Scripts/python.exe'),'-u','-m','unittest','discover',
            '-s',str(ROOT/'migration_system/tests'),'-p',name+'.py','-v'],capture_output=True,timeout=480)
        log=proc.stdout.decode('utf-8',errors='replace')+proc.stderr.decode('utf-8',errors='replace')
        count=re.search(r'Ran (\d+) tests? in ',log)
        result={'module':name,'exit_code':proc.returncode,'tests_run':int(count[1]) if count else 0,'timed_out':False}
    except subprocess.TimeoutExpired as exc:
        log=(exc.stdout or b'').decode('utf-8',errors='replace')+(exc.stderr or b'').decode('utf-8',errors='replace')
        result={'module':name,'exit_code':None,'tests_run':None,'timed_out':True}
    write_once(DEST/(name+'.txt'),log)
    print(json.dumps(result),flush=True)
    return result


def main():
    if DEST.exists():raise ValueError('choose_new_immutable_verification_directory')
    implementation=binding()
    tests={name:hashed(ROOT/'migration_system/tests'/(name+'.py')) for name in MODULES}
    write_once(DEST/'protocol.json',{'scope':'local_regressions_NOT_real_model_success',
        'workers':2,'module_timeout_seconds':480,'timeout_scope':'verification_process_only_not_production_budget',
        'implementation_sha256':implementation,'modules':tests,'real_model_calls':0,
        'script_sha256':hashed(Path(__file__))})
    entries=[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        for future in as_completed([pool.submit(run,name) for name in MODULES]):entries.append(future.result())
    if binding()!=implementation:raise ValueError('implementation_changed_during_verification')
    if tests!={name:hashed(ROOT/'migration_system/tests'/(name+'.py')) for name in MODULES}:
        raise ValueError('test_source_changed_during_verification')
    entries.sort(key=lambda row:MODULES.index(row['module']))
    report={'scope':'fixed_version_local_unit_parser_browser_and_injected_clients_NOT_real_model_success',
        'successful':all(row['exit_code']==0 for row in entries),
        'tests_run':sum(row['tests_run'] or 0 for row in entries),'real_model_calls':0,
        'module_results':entries,'modules':tests,'implementation_sha256':implementation,
        'workers':2,'module_timeout_seconds':480,'production_timeout_or_budget_changed':False}
    write_once(DEST/'test-results.json',report)
    write_once(DEST/'SHA256SUMS.txt',''.join(hashed(p)+'  '+p.relative_to(DEST).as_posix()+'\n'
        for p in sorted(DEST.rglob('*')) if p.is_file()))
    print(json.dumps({k:report[k] for k in ('tests_run','successful','real_model_calls')}),flush=True)
    raise SystemExit(0 if report['successful'] else 1)


if __name__=='__main__':main()
