"""Read-only native observer/exception-stage audit. No blanket fix or waiver."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data/experiments/analysis/formal_30_v4_notification_exception_audit_v1_20261115'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify():
    b=read(BASE/'baseline.json')
    for p,digest in {**b['protected'],**b['manual']}.items():
        if sha(ROOT/p)!=digest:
            raise RuntimeError('Protected file differs: '+p)
    for field in ['source','candidate']:
        if sha(ROOT/b[field]['path'])!=b[field]['sha256']:
            raise RuntimeError('Frozen input differs: '+field)
    for p,item in b['evidence_files'].items():
        if p!='docs/ir-design/source-migration-scope-20261114.md' and sha(ROOT/p)!=item['sha256']:
            raise RuntimeError('Evidence differs: '+p)
    for p,digest in b['prior_seals'].items():
        manifest=ROOT/p
        if sha(manifest)!=digest:
            raise RuntimeError('Manifest differs: '+p)
        for line in manifest.read_text(encoding='utf-8').splitlines():
            expected,rel=line.split('  ',1)
            if sha(manifest.parent/rel)!=expected:
                raise RuntimeError('Payload differs: '+rel)
    return b


def projection(row):
    return {k:row[k] for k in ['error','immediate','afterTick','rootChanged','oldStarts','sameRecords','sameNested','commits','notifications','events']}


def replay():
    b=verify()
    runtime=ROOT/'data/experiments/manual_followups/task_manager_async_scope_v7_prepared_20261113/vendor/vue-2.7.16.js'
    payload={'vue':(ROOT/b['source']['path']).read_text(encoding='utf-8'),
             'code':(ROOT/b['candidate']['path']).read_text(encoding='utf-8'),'runtime':str(runtime)}
    result=subprocess.run(['node',str(ROOT/'migration_pipeline/probe_notification_exception_v1.cjs')],
        input=json.dumps(payload),text=True,encoding='utf-8',capture_output=True,check=True,timeout=90)
    native=json.loads(result.stdout)
    shared=native['shared']['proposals']
    equal={name:projection(pair['source'])==projection(pair['target']) for name,pair in shared['unchanged'].items()}
    assert len(equal)==5 and all(equal.values())
    assert len(shared['unchanged']['forward']['source']['notices'])==3
    assert len(shared['unchanged']['forward']['target']['notices'])==1
    invalid=native['phases']['variants']['unchanged']['days-hole']
    assert invalid['source']['constructed'] and invalid['source']['firstRead']=={'kind':'error','name':'TypeError'}
    assert not invalid['target']['constructed'] and invalid['target']['constructorError']=='TypeError'
    assert invalid['source']['recovery']['read']=={'kind':'value','type':'string','value':'one'}
    return {'audit':{'classification':'native_notification_and_exception_phase_audit_no_naive_repair',
        'source':b['source'],'candidate':b['candidate'],'ordinary_projection_equal':equal,
        'external_deep_sync_observer_counts':{'source':3,'target':1},
        'external_observer_is_new_mandatory_feature':False,
        'new_native_shared_cases':5,'in_memory_shared_proposals':5,
        'new_native_phase_inputs':5,'in_memory_phase_proposals':3,
        'shared_status':'source_projection_landed_but_notification_boundary_unresolved',
        'exception_status':'source_getter_error_and_target_constructor_timing_mismatch_unresolved',
        'all_observer_equivalence_proven':False,'exception_phase_equivalence_proven':False,
        'general_impossibility_claimed':False,'automatic_repair_implemented':False,
        'diagnostics_waived':False,'scope_changed':False,'dynamic_public_key_block_retained':True,
        'production_code_or_prompt_changed':False,'canonical_or_manual_files_written':False,
        'model_calls':0,'browser_started':False,'server_started':False,'new_manual_confirmation':False,
        'new_full30_run':False,'historical_scores_rewritten':False,'whole_component_passed':False,
        'original_batch':b['original_batch'],
        'next_step':'Keep both residual boundaries explicit; do not chase callback counts or swallow source exceptions; proceed to controlled browser/pixel evaluator development before any new model batch.'},
        'native':native}


if __name__=='__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    print(json.dumps(replay(),ensure_ascii=False))
