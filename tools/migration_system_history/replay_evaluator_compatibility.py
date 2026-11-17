"""Read-only legacy/new evaluator replay; no model requests and no task updates.

Writes a separate evidence directory only when explicitly given --output-dir.
Historical reports and generated code are never overwritten or rebound.
"""
import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

PROJECT=Path(__file__).resolve().parents[2]/'migration_system'
ROOT=PROJECT.parent
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(PROJECT/'src'))
from card_migration_system.adapters.legacy_checks import legacy_binding,legacy_stage
from card_migration_system.adapters.browser import BrowserEvaluator
from card_migration_system.config import load_settings
from card_migration_system.runtime import profile
from card_migration_system.stages.structure import ssm_template_tree,target_template_tree,tree_distance,tree_differences
from card_migration_system.stages.evaluation import assess
from migration_pipeline.stages.validate import ValidateStage,ValidateStageInput
from migration_pipeline.stages.visual_eval import VisualEvalStage,VisualEvalStageInput


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--with-browser',action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--diagnostic-actions',help='Separate local JSON action list; never changes historical request')
    args=parser.parse_args()
    if not re.fullmatch('[0-9a-f]{32}',args.run_id):parser.error('Invalid run ID')
    settings=load_settings(project_root=PROJECT,environ={})
    artifacts=settings.artifact_dir
    base=artifacts/'migrations'/args.run_id
    report_path=base/'report.json'
    original=json.loads(report_path.read_bytes())
    if original['migration_id']!=args.run_id:raise ValueError('Report identity mismatch')
    verified=[]
    def read(relative,expected):
        path=(artifacts/relative).resolve()
        if not path.is_relative_to(artifacts.resolve()):raise ValueError('Evidence path escapes artifact root')
        data=path.read_bytes();actual=sha256(data).hexdigest()
        if actual!=expected:raise ValueError('Historical evidence hash mismatch: '+relative)
        verified.append({'relative_path':relative,'sha256':actual})
        return data
    for item in original['files']:read(item['relative_path'],item['sha256'])
    request=original['request']
    source=read(f"inputs/{request['input_id']}/{request['filename']}",request['source_sha256']).decode('utf-8')
    code=read(original['final_artifact']['relative_path'],original['final_artifact']['sha256']).decode('utf-8')
    ssm=json.loads((base/'ssm.json').read_bytes())['ssm']
    adapted=legacy_stage(ROOT,'validate',source=source,code=code,ssm=ssm)
    with tempfile.TemporaryDirectory(prefix='cardmig-eval-replay-') as directory:
        vue=Path(directory)/'Source.vue';vue.write_text(source,encoding='utf-8')
        direct=asdict(ValidateStage().run(ValidateStageInput(generated_code=code,ssm=ssm,
            vue_file_path=str(vue),source_file=str(vue),compile_check=False)))
    old_visual=asdict(VisualEvalStage().run(VisualEvalStageInput(vue_source=source,generated_code=code,render_props=request['props'])))
    parse_request={'repository':str(ROOT),'project':str(PROJECT),'source':source,'code':code,'action':'parse'}
    p=subprocess.run(['node',str(PROJECT/'browser/evaluate.mjs')],input=json.dumps(parse_request).encode(),capture_output=True,timeout=30)
    if p.returncode:raise RuntimeError('Template parser failed: '+p.stdout.decode()[:500])
    trees=json.loads(p.stdout)
    expected,actual=ssm_template_tree(ssm),target_template_tree(trees['target']['tree'])
    new_structure={'ssm_ted':tree_distance(expected,actual),'source_ast_ted':tree_distance(trees['source']['tree'],trees['target']['tree']),
                   'differences':tree_differences(expected,actual)}
    direct_codes=[x['code'] for x in direct['validation_errors']]
    adapted_codes=[x['code'] for x in adapted['validation_errors']]
    if direct_codes!=adapted_codes or direct['validation_passed']!=adapted['validation_passed']:
        raise AssertionError('Legacy static adapter does not match direct invocation')
    result={'scope':'offline_evaluator_diagnostic_replay_not_new_migration_or_independent_test',
        'original_migration_id':args.run_id,'source_sha256':request['source_sha256'],
        'accepted_artifact_sha256':original['final_artifact']['sha256'],
        'original_report_sha256':sha256(report_path.read_bytes()).hexdigest(),
        'historical_evidence':verified,'historical_status':original['status'],
        'historical_assessment':original['assessment'],
        'current_legacy_static':{'direct_passed':direct['validation_passed'],'adapter_passed':adapted['validation_passed'],
            'direct_error_codes':direct_codes,'adapter_error_codes':adapted_codes,'direct_adapter_equal':True},
        'legacy_visual_stage':{key:old_visual[key] for key in ('visual_eval_passed','visual_eval_errors','structure_similarity','text_similarity')},
        'legacy_visual_scope':'legacy_snapshot_DOM_stage_not_Puppeteer_pixel_or_interaction_equivalence',
        'current_structure':new_structure,'current_browser_assessment':None,'additional_interaction_assessment':None,
        'actual_model_calls':0,'historical_model_usage':original['usage'],'original_task_updated':False,
        'thresholds_changed':False,'prompts_changed':False,
        'implementation_sha256':{'legacy':legacy_binding(ROOT),
            'browser/evaluate.mjs':sha256((PROJECT/'browser/evaluate.mjs').read_bytes()).hexdigest(),
            'browser/empty-class-policy.mjs':sha256((PROJECT/'browser/empty-class-policy.mjs').read_bytes()).hexdigest(),
            **{name:sha256((PROJECT/'src/card_migration_system'/name).read_bytes()).hexdigest()
               for name in ('stages/structure.py','stages/evaluation.py','stages/dom_comparison.py')}}}
    images={}
    if args.with_browser:
        browser=BrowserEvaluator(settings,profile(settings))
        data=browser.evaluate(source,code,request['props'],request['actions'])
        result['current_browser_assessment']=assess(adapted,data,request['actions'],request['thresholds'],ssm)
        for side in ('vue','san'):images[side+'.png']=data[side]['png']
        images['heatmap.png']=data['image']['heatmap']
        # Explicit diagnostic actions, separate from the historical job's empty scene.
        actions=None
        if args.diagnostic_actions:
            actions_path=Path(args.diagnostic_actions).resolve()
            if not actions_path.is_relative_to(ROOT):raise ValueError('Diagnostic action file must be inside workspace')
            actions_bytes=actions_path.read_bytes()
            if len(actions_bytes)>32768:raise ValueError('Diagnostic action file too large')
            actions=json.loads(actions_bytes)
            if not isinstance(actions,list) or not 1<=len(actions)<=20:raise ValueError('Expected 1..20 actions')
            names=set()
            for action in actions:
                if (not isinstance(action,dict) or set(action)-{'name','type','selector','value','target'} or
                    action.get('type') not in ('click','input','select','key','drag') or
                    not all(isinstance(action.get(k),str) and 0<len(action[k])<=300 for k in ('name','selector')) or action['name'] in names):
                    raise ValueError('Invalid diagnostic action')
                names.add(action['name'])
                if action['type'] in ('input','select','key') and not isinstance(action.get('value'),str):raise ValueError('Invalid action value')
                if action['type']=='drag' and not isinstance(action.get('target'),str):raise ValueError('Invalid drag target')
            result['diagnostic_actions_file_sha256']=sha256(actions_bytes).hexdigest()
        elif request['filename']=='FocusCard.vue':
            actions=[{'name':'start_focus','type':'click','selector':'.focus-card'},
                     {'name':'stop_focus','type':'click','selector':'.focus-card'}]
        if actions:
            diagnostic=browser.evaluate(source,code,request['props'],actions)
            result['additional_interaction_assessment']=assess(adapted,diagnostic,actions,request['thresholds'],ssm)
            result['additional_actions']=actions
    if args.output_dir:
        output=Path(args.output_dir).resolve()
        if not output.is_relative_to(ROOT):raise ValueError('Output must be inside workspace')
        if output.exists():raise FileExistsError('Choose a new evidence directory; overwrites are forbidden')
        output.mkdir(parents=True)
        import base64
        for name,encoded in images.items():(output/name).write_bytes(base64.b64decode(encoded,validate=True))
        (output/'source.vue').write_bytes(source.encode('utf-8'))
        (output/'accepted.san').write_bytes(code.encode('utf-8'))
        (output/'historical-report.json').write_bytes(report_path.read_bytes())
        (output/'comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        manifest={p.name:sha256(p.read_bytes()).hexdigest() for p in sorted(output.iterdir()) if p.is_file()}
        (output/'SHA256SUMS.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    summary={key:result[key] for key in ('historical_status','current_legacy_static','current_structure','actual_model_calls','original_task_updated')}
    for name in ('current_browser_assessment','additional_interaction_assessment'):
        value=result[name]
        summary[name]={key:value[key] for key in ('passed','dimensions','structure_ted','dom_ted','ui_restoration')} if value else 'not_run'
    print(json.dumps(summary,ensure_ascii=True,indent=2))


if __name__=='__main__':main()
