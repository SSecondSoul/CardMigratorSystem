"""Read-only frozen computed collection replay; no model calls or file writes."""
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from migration_pipeline.utils.bounded_semantics import inspect_semantics
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.stages.visual_eval import VisualEvalStage, VisualEvalStageInput
from migration_pipeline.utils.repair_scheduler import candidate_gate

ROOT=Path(__file__).resolve().parents[1]


def replay():
    spec=importlib.util.spec_from_file_location('computed_tests',ROOT/'tests/test_source_computed_collection_closure.py')
    probes=importlib.util.module_from_spec(spec);spec.loader.exec_module(probes)
    baseline=json.loads((probes.BASE/'baseline.json').read_text(encoding='utf-8'))
    for name in ['source','candidate']:
        assert hashlib.sha256((ROOT/baseline[name]['path']).read_bytes()).hexdigest()==baseline[name]['sha256']
    c,v=probes.fixture();result=inspect_semantics(c,v,repair=True);fixed=result['code']
    assert result['changes']==['restored_source_native_computed_collection']
    again=inspect_semantics(fixed,v,repair=True);assert again['code']==fixed and again['changes']==[]
    assert all(x['landed'] for x in again['computed_collection_contracts'])
    history=ROOT/'data/experiments/snapshots/formal_30_v4_full_regression_v2_results_20261104_214821/repair_reports/complex/TripItineraryPlanner_repair_history.json'
    state=json.loads(history.read_text(encoding='utf-8'))['state']
    def assess(text):return {'generated_code':text,'ssm':state['ssm'],'vue_file_path':str(ROOT/baseline['source']['path']),
        **ValidateStage().run(ValidateStageInput(generated_code=text,ssm=state['ssm'],vue_file_path=str(ROOT/baseline['source']['path']))).to_state_update()}
    before,after=assess(c),assess(fixed)
    visual={}
    for label,text in [('before',c),('after',fixed)]:
        r=VisualEvalStage().run(VisualEvalStageInput(generated_code=text,vue_source=v))
        visual[label]={k:getattr(r,k) for k in ['visual_eval_passed','visual_eval_errors','tree_edit_distance','structure_similarity','tag_sequence_similarity','text_similarity']}
    runtime=probes.native(fixed);bodies=probes.body_oracle()
    assert all(runtime['cases'][case]['source']==runtime['cases'][case]['target'] for case in ['normal','sparse','empty','undefined-record','null-record'])
    assert all(r['source']==r['after'] for r in bodies.values())
    for case in ['days-hole','days-null']:
        row=runtime['cases'][case];assert row['source']['computed']['activeDayLabel']['error']=='TypeError' and row['target']['constructorError']=='TypeError'
    assert all(r['source']==r['target'] for r in runtime['reactive'].values())
    javascript=r'''const fs=require('fs'),p=require('@babel/parser'),g=require('@babel/generator').default,x=JSON.parse(fs.readFileSync(0,'utf8'));
function normalized(code){const b=/<script\b[^>]*>([\s\S]*?)<\/script>/.exec(code),a=p.parse(b[1]);
const root=a.program.body.find(n=>n.type==='ExpressionStatement'&&n.expression.left?.object?.name==='module').expression.right.arguments[0];
const computed=root.properties.find(p=>p.key.name==='computed').value;computed.properties=computed.properties.filter(p=>!x.names.includes(p.key.name));
return {ast:g(a,{compact:true,comments:false}).code,outside:code.replace(b[0],'__SCRIPT__')};}
const a=normalized(x.before),b=normalized(x.after);console.log(JSON.stringify({other_script_ast_unchanged:a.ast===b.ast,template_css_unchanged:a.outside===b.outside}));'''
    q=subprocess.run(['node','-e',javascript],cwd=ROOT,input=json.dumps({'before':c,'after':fixed,'names':[p['name'] for p in again['computed_collection_contracts']]}),
        text=True,encoding='utf-8',capture_output=True,check=True,timeout=20)
    protection=json.loads(q.stdout);assert all(protection.values())
    rows=json.loads((ROOT/'data/experiments/analysis/formal_30_v4_parent_initialization_v1_20261114/inventory.json').read_text(encoding='utf-8'));inventory=[]
    for row in rows:
        path=ROOT/baseline['candidate']['path'] if row['id']=='trip_itinerary_planner' else ROOT/row['input_path']
        code=path.read_text(encoding='utf-8');vue=ROOT/row['source_path'];source=vue.read_text(encoding='utf-8');r=inspect_semantics(code,source,repair=True)
        assert 'error' not in r
        inventory.append({'id':row['id'],'original_batch_passed':row['original_batch_passed'],'input_path':path.relative_to(ROOT).as_posix(),
            'input_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'source_path':row['source_path'],'source_sha256':hashlib.sha256(vue.read_bytes()).hexdigest(),
            'code_unchanged':r['code']==code,'changes':r['changes'],'contracts':r['computed_collection_contracts'],
            'new_findings':[f for f in r['findings'] if f['code']=='source_computed_collection_not_landed']})
    assert [r['id'] for r in inventory if not r['code_unchanged']]==['trip_itinerary_planner']
    assert sum(r['original_batch_passed'] and r['code_unchanged'] and not r['new_findings'] for r in inventory)==24
    gate=lambda a,b:{k:v for k,v in candidate_gate(a,b).items() if k in ['should_stop','decision','lost_source_computed_collection_contracts','waived_source_computed_collection_findings','introduced_semantic_findings']}
    compact=lambda a:{'validation_passed':a['validation_passed'],'validation_errors':a['validation_errors']}
    audit={'source':baseline['source'],'candidate_before':baseline['candidate'],'candidate_after_sha256':hashlib.sha256(fixed.encode()).hexdigest(),
        'classification':'offline_source_computed_collection_partial_closure_reused_development','date':'2026-11-15',
        'changes':result['changes'],'contracts':again['computed_collection_contracts'],'before':compact(before),'after':compact(after),
        'forward_gate':gate(before,after),'reverse_gate':gate(after,before),'visual':visual,'protection':protection,
        'model_calls':0,'original_batch':{'configured':30,'passed':24,'failed':6,'execution_errors':0,'total_tokens':1821544},
        'generation_prompt_or_server_changed':False,'repair_prompt_changed':True,'validator_entrypoint_changed':False,'nested_alias_checker_relaxed':False,
        'canonical_generated_files_modified':False,'manual_pages_modified':False,'new_manual_confirmation':False,'server_started':False,'browser_started':False,
        'whole_component_equivalence_proven':False,'production_eligible':False,
        'prior_constructor_only_find_interpretation_corrected':True,
        'remaining_boundary':'days holes/null: source getter also throws TypeError when demanded; San throws at eager construction. Do not invent a fallback or declare lifecycle timing equivalence.'}
    assert len(before['validation_errors'])==4 and len(after['validation_errors'])==2 and not after['validation_passed']
    assert not audit['forward_gate']['should_stop'] and audit['reverse_gate']['should_stop']
    return {'code':fixed,'audit':audit,'runtime':runtime,'body_observations':bodies,'inventory':inventory}


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');print(json.dumps(replay(),ensure_ascii=False))
