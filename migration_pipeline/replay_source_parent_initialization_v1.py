"""Read-only frozen parent-initialization replay; emits JSON, never calls a model."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

from migration_pipeline.utils.bounded_semantics import inspect_semantics
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.stages.visual_eval import VisualEvalStage, VisualEvalStageInput
from migration_pipeline.utils.repair_scheduler import candidate_gate

ROOT=Path(__file__).resolve().parents[1]


def replay():
    spec=importlib.util.spec_from_file_location('startup_test',ROOT/'tests/test_source_parent_initialization_closure.py')
    probes=importlib.util.module_from_spec(spec);spec.loader.exec_module(probes)
    baseline=json.loads((probes.BASE/'baseline.json').read_text(encoding='utf-8'))
    for key in ['source','candidate']:
        assert hashlib.sha256((ROOT/baseline[key]['path']).read_bytes()).hexdigest()==baseline[key]['sha256']
    code,vue=probes.fixture();result=inspect_semantics(code,vue,repair=True);fixed=result['code']
    history=ROOT/'data/experiments/snapshots/formal_30_v4_full_regression_v2_results_20261104_214821/repair_reports/complex/TripItineraryPlanner_repair_history.json'
    state=json.loads(history.read_text(encoding='utf-8'))['state']
    def assess(text):
        r=ValidateStage().run(ValidateStageInput(generated_code=text,ssm=state['ssm'],vue_file_path=str(ROOT/baseline['source']['path'])))
        return {'generated_code':text,'ssm':state['ssm'],'vue_file_path':str(ROOT/baseline['source']['path']),**r.to_state_update()}
    before,after=assess(code),assess(fixed)
    visual={}
    for label,text in [('before',code),('after',fixed)]:
        r=VisualEvalStage().run(VisualEvalStageInput(generated_code=text,vue_source=vue))
        visual[label]={k:getattr(r,k) for k in ['visual_eval_passed','visual_eval_errors','tree_edit_distance','structure_similarity','tag_sequence_similarity','text_similarity']}
    native={case:probes.native(case) for case in ['nested','symbol','cycle','empty','empty-days','sparse','days-hole','days-null']}
    isolated={case:probes.native(case,True) for case in ['sparse','days-hole','days-null','empty-days']}
    compact=lambda s:{'validation_passed':s['validation_passed'],'validation_errors':s['validation_errors']}
    gate=lambda a,b:{k:v for k,v in candidate_gate(a,b).items() if k in ['should_stop','decision','lost_source_parent_initialization_contracts','waived_source_parent_initialization_findings','introduced_semantic_findings']}
    assert result['changes']==['restored_source_parent_shallow_initialization']
    assert inspect_semantics(fixed,vue,repair=True)['code']==fixed
    assert all(row['source']==row['after'] for case,row in native.items() if case not in ['sparse','days-hole','days-null'])
    assert all(row['source']==row['after'] for row in isolated.values())
    assert all(native[case]['after']['error']=='TypeError' for case in ['sparse','days-hole','days-null'])
    return {'code':fixed,'audit':{'source':baseline['source'],'candidate_before':baseline['candidate'],
        'candidate_after_sha256':hashlib.sha256(fixed.encode()).hexdigest(),'changes':result['changes'],
        'contracts':inspect_semantics(fixed,vue)['parent_initialization_contracts'],
        'before':compact(before),'after':compact(after),'forward_gate':gate(before,after),'reverse_gate':gate(after,before),
        'visual':visual,'model_calls':0,'original_batch_unchanged':True,'full_browser_interaction':False,
        'remaining_runtime_boundary':'Generated computed helpers still throw on sparse items / null or sparse days; isolated startup proof is not whole component equivalence.'},
        'native':native,'isolated_startup':isolated}


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    print(json.dumps(replay(),ensure_ascii=False))
