"""Read-only frozen-input replay; CLI returns evidence, never writes or runs LLMs."""
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

from migration_pipeline.utils.bounded_semantics import inspect_semantics
from migration_pipeline.utils.repair_scheduler import candidate_gate
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data/experiments/analysis/formal_30_v4_filter_methods_v1_input_20261115'


def replay():
    read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    b=read(BASE/'baseline.json')
    for item in b['prior_seals']:
        path=ROOT/item['path'];assert sha(path)==item['sha256']
        for line in path.read_text(encoding='utf-8').splitlines():
            digest,relative=line.split('  ',1);assert sha(path.parent/relative)==digest
    for k in ['source','candidate']:assert sha(ROOT/b[k]['path'])==b[k]['sha256']
    for p,d in b['manual'].items():assert sha(ROOT/p)==d
    c,v=[(ROOT/b[k]['path']).read_text(encoding='utf-8') for k in ['candidate','source']]
    old=inspect_semantics(c,v);result=inspect_semantics(c,v,repair=True);fixed=result['code'];new=inspect_semantics(fixed,v)
    assert result['changes']==['restored_source_native_filter_method'] and inspect_semantics(fixed,v,repair=True)['changes']==[]
    assert len(new['filter_method_contracts'])==2 and all(x['landed'] for x in new['filter_method_contracts'])
    state=read(ROOT/'data/experiments/snapshots/formal_30_v4_full_regression_v2_results_20261104_214821/repair_reports/complex/TripItineraryPlanner_repair_history.json')['state']
    def assess(code):
        x=ValidateStage().run(ValidateStageInput(generated_code=code,ssm=state['ssm'],vue_file_path=str(ROOT/b['source']['path'])))
        return {'validation_passed':x.validation_passed,'validation_errors':x.validation_errors}
    before,after=assess(c),assess(fixed)
    assert len(before['validation_errors'])==4 and len(after['validation_errors'])==2 and not after['validation_passed']
    assert {e['code'] for e in after['validation_errors']}=={'nested_state_mutation','source_method_interface_not_landed'}
    def item(code,inspection):return {'generated_code':code,'vue_source':v,'ssm':state['ssm'],'validation_errors':inspection['findings']}
    forward=candidate_gate(item(c,old),item(fixed,new));reverse=candidate_gate(item(fixed,new),{**item(c,old),'validation_errors':[],'validation_passed':True})
    assert not forward['should_stop'] and reverse['should_stop'] and reverse['waived_source_filter_method_findings']
    spec=importlib.util.spec_from_file_location('filter_tests',ROOT/'tests/test_source_filter_method_closure.py')
    tests=importlib.util.module_from_spec(spec);spec.loader.exec_module(tests);native=tests.native()
    assert len(native['body'])==22 and all(row['source']==row['after'] for row in native['body'].values())
    remove=native['after']['additional_call_path_probes']['remove'];assert remove['source']==remove['target'] and remove['target']['error'] is None
    assert len(native['after']['extra_observer']['source']['notices'])==3 and len(native['after']['extra_observer']['target']['notices'])==1
    def erase(text):
        for name in ['removeItem','dayCount']:
            text=re.sub(r'    '+name+r'\(id\) \{[\s\S]*?\n    \},',name+'METHOD,',text)
            text=re.sub(r'    '+name+r'\(id\)\{[^\n]*\},',name+'METHOD,',text)
        return text
    assert erase(c)==erase(fixed)
    inventory=[]
    prior=read(ROOT/'data/experiments/analysis/formal_30_v4_computed_collections_v1_20261115/inventory.json')
    for row in prior:
        code=(ROOT/row['input_path']).read_text(encoding='utf-8');vue=(ROOT/row['source_path']).read_text(encoding='utf-8')
        current=inspect_semantics(code,vue)
        inventory.append({'id':row['id'],'original_batch_passed':row['original_batch_passed'],'input_path':row['input_path'],
            'source_path':row['source_path'],'input_sha256':sha(ROOT/row['input_path']),'source_sha256':sha(ROOT/row['source_path']),
            'new_filter_findings':[e for e in current.get('findings',[]) if e['code']=='source_filter_method_not_landed'],
            'filter_contracts':current.get('filter_method_contracts',[]),'canonical_written':False})
    assert len(inventory)==30 and sum(x['original_batch_passed'] and not x['new_filter_findings'] for x in inventory)==24
    return {'code':fixed,'native':native,'inventory':inventory,'audit':{
        'date':'2026-11-15','classification':'offline_source_native_filter_partial_closure_reused_development',
        'source':b['source'],'candidate_before':b['candidate'],'candidate_after_sha256':hashlib.sha256(fixed.encode()).hexdigest(),
        'changes':result['changes'],'before':before,'after':after,'contracts':new['filter_method_contracts'],
        'forward_gate':forward,'reverse_gate':reverse,'only_two_method_bodies_changed':True,'template_css_unchanged':True,'global_helpers_changed':False,
        'generation_prompt_or_server_changed':False,'repair_prompt_changed':True,'validator_entrypoint_changed':False,'independent_gate_changed':True,
        'prior_diagnostics_waived':False,'canonical_generated_files_modified':False,'manual_pages_modified':False,
        'model_calls':0,'server_started':False,'browser_started':False,'new_manual_confirmation':False,
        'whole_component_equivalence_proven':False,'production_eligible':False,'source_days_exception_phase_boundary_resolved':False,
        'external_observer_counts':{'source':3,'target':1},'arbitrary_setter_interface_preserved':False,
        'function_oracle_cases':22,'original_batch':b['original_batch'],
        'next_step':'Review the remaining shared-write observer and dynamic setter source contracts without waiving diagnostics; no paid rerun yet.'}}


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');print(json.dumps(replay(),ensure_ascii=False))
