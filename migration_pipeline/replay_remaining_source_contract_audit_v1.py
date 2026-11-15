"""Read-only remaining-contract review. No production changes or model calls."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.utils.bounded_semantics import inspect_semantics

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data/experiments/analysis/formal_30_v4_remaining_contract_audit_v1_input_20261115'


def replay():
    baseline=json.loads((BASE/'baseline.json').read_text(encoding='utf-8'));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    for category in ['protected_implementation','manual']:
        for path,digest in baseline[category].items():assert sha(ROOT/path)==digest,path
    for category in ['source','candidate']:assert sha(ROOT/baseline[category]['path'])==baseline[category]['sha256']
    spec=importlib.util.spec_from_file_location('remaining_tests',ROOT/'tests/test_remaining_source_contract_audit_v1.py')
    tests=importlib.util.module_from_spec(spec);spec.loader.exec_module(tests)
    code,vue=tests.fixture();observations=tests.inspect(code,vue,True)
    semantics=inspect_semantics(code,vue,repair=True);assert semantics['code']==code and not semantics['changes']
    state=json.loads((ROOT/'data/experiments/snapshots/formal_30_v4_full_regression_v2_results_20261104_214821/repair_reports/complex/TripItineraryPlanner_repair_history.json').read_text(encoding='utf-8'))['state']
    validation=ValidateStage().run(ValidateStageInput(generated_code=code,ssm=state['ssm'],vue_file_path=str(ROOT/baseline['source']['path'])))
    assert not validation.validation_passed and {e['code'] for e in validation.validation_errors}=={'nested_state_mutation','source_method_interface_not_landed'}
    matched={name:tests.projection(pair['source'])==tests.projection(pair['target']) for name,pair in observations['native']['component_only'].items()}
    assert len(matched)==5 and all(matched.values())
    external=observations['native']['extra_observer'];assert len(external['source']['notices'])==3 and len(external['target']['notices'])==1
    action=observations['native']['additional_call_path_probes']['remove'];assert action['source']['error'] is None and action['target']['error']['name']=='TypeError'
    helper=observations['static'];assert helper['source_call_count']==14 and helper['site_counts_match'] and not helper['rhs_and_timing_equivalence_proven']
    return {'audit':{'date':'2026-11-15','classification':'offline_source_call_scope_and_notifications_audit_not_repair_or_new_acceptance',
        'source':baseline['source'],'candidate':baseline['candidate'],'validation_passed':False,'validation_errors':validation.validation_errors,
        'component_projection_equal':matched,'projection_definition':'Program root commits, notify, event, state, reference identities and nextTick values; raw San computed-store traffic preserved separately.',
        'raw_runtime_traces_equal':False,'all_observers_equivalent':False,'extra_observer_counts':{'source':3,'target':1},
        'source_literal_root_call_count':14,'site_counts_match':True,'all_setter_rhs_or_timing_equivalent':False,
        'arbitrary_setter_interface_preserved':False,'acceptance_scope_changed':False,'validation_exemption_granted':False,
        'supplied_source_remove_click_sparse_failure_confirmed':True,'public_counter_helper_extra_surface_mismatch_confirmed':True,
        'sparse_filter_issue_promoted_to_production_diagnostic':False,
        'production_code_changed':False,'generation_or_repair_prompt_changed':False,'canonical_san_changed':False,'manual_pages_changed':False,
        'protected_implementation_files_verified':len(baseline['protected_implementation']),'previous_233_tests_rerun':False,
        'model_calls':0,'new_manual_confirmation':False,'browser_started':False,'server_started':False,
        'whole_component_equivalence_proven':False,'production_eligible':False,
        'original_batch':{'configured':30,'passed':24,'failed':6,'execution_errors':0,'total_tokens':1821544},
        'next_step':'Close the actual source removeItem/filter path with a source-proven diagnostic, bounded repair and regression; do not first drop the two remaining diagnostics.'},
        'observations':observations}


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');print(json.dumps(replay(),ensure_ascii=False))
