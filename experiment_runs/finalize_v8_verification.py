"""Consolidate same-version timeout-only module rerun; never erase first run."""
from copy import deepcopy
import json
from pathlib import Path
import re
from analyze_coverage import read,write_once,hashed,RUNS
from replay_general_repairs_v3 import binding,PROJECT


def main():
    folder=PROJECT/'docs/verification/2026-11-19_general_repairs_v1'
    original_path=folder/'test-results-composed_v8_final.json'
    original=read(original_path)
    replay=read(RUNS/'composed_v8_final_replay_20261120/protocol.json')
    if original['implementation_sha256']!=replay['implementation_sha256'] or binding()!=original['implementation_sha256']:
        raise ValueError('same_implementation_required')
    for name,digest in original['modules'].items():
        if hashed(PROJECT/'tests'/(name+'.py'))!=digest:raise ValueError('test_module_changed')
    failed=[m for m in original['module_results'] if m['exit_code']!=0]
    if len(failed)!=1 or failed[0]['module']!='test_remaining_repairs_v7' or not failed[0]['timed_out']:
        raise ValueError('only_the_recorded_timeout_may_be_consolidated')
    isolated_path=folder/'composed_v8_isolated_remaining_v7.txt'
    metadata=read(folder/'composed_v8_isolated_remaining_v7.json')
    log=isolated_path.read_text(encoding='utf-8')
    match=re.search(r'Ran (\d+) tests? in ([0-9.]+)s',log)
    if metadata['exit_code']!=0 or not match or '\nOK' not in log or 'FAILED (' in log:
        raise ValueError('isolated_module_did_not_pass')
    count=int(match[1]);entry={'module':failed[0]['module'],'exit_code':0,'tests_run':count,
        'timed_out':False,'isolated_after_parallel_replay':True,'seconds':float(match[2])}
    result=deepcopy(original)
    result['module_results']=[entry if m['module']==entry['module'] else m for m in result['module_results']]
    result.update(tests_run=sum(m['tests_run'] for m in result['module_results']),successful=True,
        initial_parallel_verification={'report_sha256':hashed(original_path),'tests_completed':original['tests_run'],
            'timed_out_modules':[m['module'] for m in failed],'successful':False},
        isolated_timeout_rerun={'log_sha256':hashed(isolated_path),'exit_receipt_sha256':hashed(folder/'composed_v8_isolated_remaining_v7.json'),
            'same_code_same_assertions':True,'parallel_replay_finished':True},
        evidence_policy='same_version_module_consolidation_with_original_timeout_retained_not_a_clean_first_run')
    write_once(folder/'test-results-composed_v8_verified.json',result)
    print(json.dumps({k:result[k] for k in ('tests_run','successful','real_model_calls','initial_parallel_verification','isolated_timeout_rerun')},ensure_ascii=True))


if __name__=='__main__':main()
