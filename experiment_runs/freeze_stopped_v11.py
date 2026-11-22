"""Preserve precheck evidence; no repair/model/database work."""
from analyze_coverage import ROOT,RUNS,write_once,hashed
for root in (ROOT/'migration_system/docs/verification/2026-11-20_followup_v11',
             RUNS/'composed_v11_followup_replay_20261120'):
    write_once(root/'STOPPED.json',{'status':'stopped_precheck_not_final_verification',
        'reason':'tighten_array_shape_witness_against_spread_duplicate_and_reserved_fields; preserve_infrastructure_failures_if_any',
        'real_model_calls':0,'cloud_database_access':False,'prior_partial_results_not_counted_as_final':True,
        'successor':'v11_verified'})
    write_once(root/'STOPPED_SHA256SUMS.txt',''.join(hashed(p)+'  '+p.relative_to(root).as_posix()+'\n'
        for p in sorted(root.rglob('*')) if p.is_file() and p.name!='STOPPED_SHA256SUMS.txt'))
print('Stopped precheck payloads preserved')
