"""Read-only assignment guard replay; never mutates a generated component."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

from migration_pipeline.stages.validate import ValidateStage,ValidateStageInput
from migration_pipeline.utils.bounded_semantics import inspect_semantics
from migration_pipeline.utils.repair_scheduler import candidate_gate

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data/experiments/analysis/formal_30_v4_dynamic_setter_guard_v1_input_20261115'


def replay():
    read=lambda p:json.loads(p.read_text(encoding='utf-8'));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    b=read(BASE/'baseline.json');manifest=ROOT/b['prior_manifest']['path'];assert sha(manifest)==b['prior_manifest']['sha256']
    for line in manifest.read_text(encoding='utf-8').splitlines():
        digest,rel=line.split('  ',1);assert sha(manifest.parent/rel)==digest
    for k in ['source','candidate']:assert sha(ROOT/b[k]['path'])==b[k]['sha256']
    for p,d in b['manual'].items():assert sha(ROOT/p)==d
    c,v=[(ROOT/b[k]['path']).read_text(encoding='utf-8') for k in ['candidate','source']]
    spec=importlib.util.spec_from_file_location('setter_tests',ROOT/'tests/test_source_dynamic_assignment_guard.py')
    tests=importlib.util.module_from_spec(spec);spec.loader.exec_module(tests)
    variants=tests.variants();native=tests.native();prior=read(BASE/'before.json')
    assert native==prior['native']
    state=read(ROOT/'data/experiments/snapshots/formal_30_v4_full_regression_v2_results_20261104_214821/repair_reports/complex/TripItineraryPlanner_repair_history.json')['state']
    def assess(code):
        r=ValidateStage().run(ValidateStageInput(generated_code=code,ssm=state['ssm'],vue_file_path=str(ROOT/b['source']['path'])))
        return {'generated_code':code,'vue_source':v,'ssm':state['ssm'],**r.to_state_update()}
    before=assess(c);assert {e['code'] for e in before['validation_errors']}=={'nested_state_mutation','source_method_interface_not_landed'}
    rows={}
    for name,code in variants.items():
        current=assess(code);gate=candidate_gate(before,current)
        forged=candidate_gate(before,{**current,'validation_passed':True,'validation_errors':[]})
        inspected=inspect_semantics(code,v);fixed=inspect_semantics(code,v,repair=True)
        assert fixed['code']==code and not fixed['changes'] and forged['should_stop']
        if name!='missing':
            assert any(x['code']=='source_dynamic_assignment_unproven' for x in current['validation_errors']) and gate['should_stop']
            assert not prior['validator_before'][name]['gate_should_stop']
        rows[name]={'validation_passed':current['validation_passed'],'errors':current['validation_errors'],
            'gate_should_stop':gate['should_stop'],'forged_gate_should_stop':forged['should_stop'],
            'waived_findings':forged['waived_source_dynamic_assignment_findings'],
            'contracts':[r for r in inspected['method_contracts'] if r.get('dynamic_assignment')],'code_unchanged':fixed['code']==code}
    inventory=[]
    for row in read(ROOT/'data/experiments/analysis/formal_30_v4_filter_methods_v1_20261115/inventory.json'):
        code=(ROOT/row['input_path']).read_text(encoding='utf-8');vue=(ROOT/row['source_path']).read_text(encoding='utf-8')
        r=inspect_semantics(code,vue)
        inventory.append({k:row[k] for k in ['id','original_batch_passed','input_path','input_sha256','source_path','source_sha256']})
        inventory[-1].update({'dynamic_contracts':[x for x in r.get('method_contracts',[]) if x.get('dynamic_assignment')],
            'new_findings':[x for x in r.get('findings',[]) if x['code']=='source_dynamic_assignment_unproven'],'canonical_written':False})
    return {'audit':{'date':'2026-11-15','classification':'dynamic_assignment_validation_gate_hardening_not_setter_repair',
        'source':b['source'],'candidate':b['candidate'],'validation_passed':False,'current_errors':before['validation_errors'],
        'variant_checks':rows,'new_diagnostic':'source_dynamic_assignment_unproven',
        'no_op_can_clear_interface_error_alone_before':True,'previous_whole_component_passed':False,
        'known_bad_or_unproven_callable_proposals_rejected':5,'native_case_count':15,'native_variant_count':6,
        'production_implementation_changed':True,'repair_prompt_changed':True,'generation_prompt_or_server_changed':False,
        'automatic_setter_repair_implemented':False,'acceptance_scope_changed':False,'compatibility_layer_added':False,
        'canonical_generated_files_modified':False,'manual_pages_modified':False,'model_calls':0,
        'new_manual_confirmation':False,'browser_started':False,'server_started':False,'whole_component_equivalence_proven':False,
        'production_eligible':False,'original_batch':b['original_batch'],
        'next_step':'User must explicitly decide source-reachable calls versus arbitrary external-key interface before any narrowing; keep old failures and do not install an adapter to force a pass.'},
        'native':native,'inventory':inventory}


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');print(json.dumps(replay(),ensure_ascii=False))
