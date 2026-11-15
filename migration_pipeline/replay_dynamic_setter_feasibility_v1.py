"""Conditional direct-San namespace feasibility replay; never edits components."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data/experiments/analysis/formal_30_v4_dynamic_setter_feasibility_v1_20261115'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_inputs():
    b=read(BASE/'baseline.json')
    for path,digest in {**b['protected'],**b['manual']}.items():
        if sha(ROOT/path)!=digest:
            raise RuntimeError('Protected file differs: '+path)
    for field in ['source','candidate']:
        if sha(ROOT/b[field]['path'])!=b[field]['sha256']:
            raise RuntimeError('Frozen input differs: '+field)
    for path,item in b['evidence_files'].items():
        if path not in {'docs/ir-design/source-migration-scope-20261114.md','docs/paper/论文实验收尾计划_20261115.md'} and sha(ROOT/path)!=item['sha256']:
            raise RuntimeError('Runtime evidence differs: '+path)
    for path,digest in b['prior_seals'].items():
        manifest=ROOT/path
        if sha(manifest)!=digest:
            raise RuntimeError('Previous manifest differs: '+path)
        for line in manifest.read_text(encoding='utf-8').splitlines():
            expected,relative=line.split('  ',1)
            if sha(manifest.parent/relative)!=expected:
                raise RuntimeError('Previous payload differs: '+relative)
    return b


def replay():
    b=verify_inputs()
    runtime='data/experiments/manual_followups/task_manager_async_scope_v7_prepared_20261113/vendor/vue-2.7.16.js'
    payload={'vue':(ROOT/b['source']['path']).read_text(encoding='utf-8'),
             'code':(ROOT/b['candidate']['path']).read_text(encoding='utf-8'),'runtime':str(ROOT/runtime)}
    result=subprocess.run(['node',str(ROOT/'migration_pipeline/probe_dynamic_setter_namespace_v1.cjs')],
        input=json.dumps(payload),text=True,encoding='utf-8',capture_output=True,check=True,timeout=60)
    native=json.loads(result.stdout)
    source=native['variants']['path']['data-null']['source']
    assert source['publicDataMatchesInput'] and source['nativeStorePointerIntact']
    assert source['budgetAfterBusinessCall']==321 and source['setterError'] is source['businessError'] is source['watchError'] is None
    path=native['variants']['path']['data-null']['target']
    assert not path['publicDataMatchesInput'] and path['nativeStorePointerIntact']
    for name in ['instance','coerced_finite_fallback']:
        row=native['variants'][name]['data-null']['target']
        assert row['publicDataMatchesInput'] and not row['nativeStorePointerIntact']
        assert row['businessError']=='TypeError' and row['watchError']=='TypeError'
    assert native['variants']['reject_data_then_finite']['data-null']['target']['setterError']=='RangeError'
    assert native['variants']['path']['root-control']['declaredObservationEqual']
    assert native['variants']['coerced_finite_fallback']['root-control']['declaredObservationEqual']
    assert native['variants']['reject_data_then_finite']['root-control']['declaredObservationEqual']
    for variant in native['variants'].values():
        assert not variant['data-null']['declaredObservationEqual']
    return {'audit':{'classification':'conditional_namespace_conflict_under_current_direct_instance_contract',
        'source':b['source'],'candidate':b['candidate'],'scope_decision':b['scope_decision'],
        'assumptions':['public property read is on the same returned San component instance',
                       'arbitrary public keys include the ordinary source key data',
                       'standard San runtime and its data slot remain unmodified',
                       'no separate facade, runtime provider, engine fork or new caller protocol'],
        'source_obligation':'after setValue(data,null), public instance.data is null; subsequent native framework operations remain usable',
        'target_runtime_obligation':'the same instance.data remains the native San Data store for unchanged San operations',
        'conditional_conflict':'the same property cannot simultaneously be null and the native non-null San Data object',
        'decision':'unsupported_under_current_combined_constraints_keep_blocked_no_automatic_setter_restore',
        'general_impossibility_for_all_architectures_claimed':False,
        'new_native_cases':5,'in_memory_target_proposals':5,'new_full_component_pass':False,
        'source_public_business_method_exercised':'updateBudget',
        'new_component_browser_acceptance':False,'automatic_repair_implemented':False,
        'production_code_or_prompt_changed':False,'diagnostics_waived':False,'scope_narrowed':False,
        'runtime_fork_or_compatibility_layer_added':False,'canonical_or_manual_files_changed':False,
        'shared_notification_resolved':False,'exception_phase_resolved':False,
        'new_model_calls':0,'new_full30_run':False,'historical_scores_rewritten':False,
        'original_batch':b['original_batch']},'native':native}


if __name__=='__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    print(json.dumps(replay(),ensure_ascii=False))
