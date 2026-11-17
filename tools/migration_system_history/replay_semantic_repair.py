"""Frozen-input rule/candidate/browser replay. No database, model or task updates."""
import argparse
import base64
from hashlib import sha256
import json
from pathlib import Path
import sys

PROJECT=Path(__file__).resolve().parents[2]/'migration_system';ROOT=PROJECT.parent
sys.path.insert(0,str(PROJECT/'src'))
from card_migration_system.config import load_settings
from card_migration_system.runtime import profile
from card_migration_system.adapters.legacy_checks import legacy_binding,legacy_stage
from card_migration_system.adapters.browser import BrowserEvaluator
from card_migration_system.stages.evaluation import assess,candidate_decision
from card_migration_system.stages.syntax import failed_syntax


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-evidence',required=True)
    parser.add_argument('--revision',type=int,default=1)
    parser.add_argument('--diagnostic-actions',required=True)
    parser.add_argument('--output-dir',required=True)
    args=parser.parse_args()
    source_dir=Path(args.source_evidence).resolve();output=Path(args.output_dir).resolve()
    settings=load_settings(project_root=PROJECT,environ={})
    for p in (source_dir,output,Path(args.diagnostic_actions).resolve()):
        if not p.is_relative_to(ROOT):raise ValueError('Paths must stay within workspace')
    if output.exists() or output.is_relative_to(settings.artifact_dir.resolve()):raise ValueError('Choose a new evidence directory outside live artifacts')
    source_manifest=json.loads((source_dir/'SHA256SUMS.json').read_bytes())
    payload={}
    for relative,expected in source_manifest.items():
        path=(source_dir/relative).resolve()
        if not path.is_relative_to(source_dir):raise ValueError('Unsafe evidence path')
        data=path.read_bytes()
        if sha256(data).hexdigest()!=expected:raise ValueError('Evidence hash mismatch: '+relative)
        payload[relative]=data
    prior=json.loads(payload['replay.json']);entry=next(r for r in prior['results'] if r['revision']==args.revision)
    code=payload[f'candidate-{args.revision}.san'].decode()
    if sha256(code.encode()).hexdigest()!=entry['candidate_sha256']:raise ValueError('Candidate identity mismatch')
    source=payload['frozen/source.vue'].decode();request=json.loads(payload['frozen/request.json'])['request']
    if sha256(source.encode()).hexdigest()!=request['source_sha256']:raise ValueError('Source identity mismatch')
    ssm=json.loads(payload['frozen/ssm.json'])['ssm']
    action_bytes=Path(args.diagnostic_actions).read_bytes();actions=json.loads(action_bytes)
    if not isinstance(actions,list) or not 1<=len(actions)<=20:raise ValueError('Require 1..20 diagnostic actions')
    for action in actions:
        if (type(action) is not dict or set(action)-{'name','type','selector','value','target'}
            or action.get('type') not in ('click','input','key','select','drag')
            or not all(type(action.get(k)) is str and 0<len(action[k])<=300 for k in ('name','selector'))):raise ValueError('Invalid diagnostic action')
        if action['type'] in ('input','key','select') and type(action.get('value')) is not str:raise ValueError('Missing action value')
        if action['type']=='drag' and type(action.get('target')) is not str:raise ValueError('Missing drag target')
    if len({a['name'] for a in actions})!=len(actions):raise ValueError('Duplicate action name')
    output.mkdir(parents=True)
    def write(name,data):
        path=output/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    def dump(name,value):write(name,json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False).encode())
    # Freeze before executing any rule. Copy original evidence, not live task files.
    for name,data in payload.items():write('frozen-input/'+name,data)
    dump('FROZEN_INPUT_SHA256SUMS.json',source_manifest)
    write('diagnostic-actions.json',action_bytes)
    implementation=legacy_binding(ROOT)
    for name in ('migration_pipeline/utils/class_binding_semantics.cjs','migration_pipeline/utils/source_phase_semantics.cjs',
                 'migration_pipeline/utils/source_render_dependency_semantics.cjs','migration_pipeline/stages/repair.py',
                 'migration_pipeline/stages/validate.py','tests/test_source_semantic_followup_v1.py'):
        write('implementation/'+name,(ROOT/name).read_bytes())
    for directory in ('src/card_migration_system','browser'):
        for path in (PROJECT/directory).rglob('*'):
            if path.is_file() and path.suffix in ('.py','.mjs') and 'node_modules' not in path.parts:
                implementation['migration_system/'+str(path.relative_to(PROJECT)).replace('\\','/')]=sha256(path.read_bytes()).hexdigest()
    write('implementation/replay_semantic_repair.py',Path(__file__).read_bytes())
    browser=BrowserEvaluator(settings,profile(settings))
    def evaluate(code,name,scene):
        syntax=browser.syntax(source,code)
        if syntax['status']=='fail':return failed_syntax(syntax,sha256(code.encode()).hexdigest())
        static=legacy_stage(ROOT,'validate',source=source,code=code,ssm=ssm)
        data=browser.evaluate(source,code,request['props'],scene)
        if data['status']!='completed':raise RuntimeError('Browser compile failure: '+data.get('diagnostic','unknown'))
        result=assess(static,data,scene,request['thresholds'],ssm);result['syntax']=syntax
        result['revision_sha256']=sha256(code.encode()).hexdigest()
        for filename,value in (('vue',data['vue'].pop('png')),('san',data['san'].pop('png')),('heatmap',data['image'].pop('heatmap'))):
            write(name+'/'+filename+'.png',base64.b64decode(value,validate=True))
        dump(name+'/raw.json',{'static':static,'browser':data})
        dump(name+'/assessment.json',result)
        return result
    before=evaluate(code,'before',request['actions'])
    rule=legacy_stage(ROOT,'rules',source=source,code=code,ssm=ssm,errors=before['diagnostics'],
        visual_errors=[] if before['dimensions']['visual'] in ('pass','not_run') else [{'code':'visual_mismatch'}])
    write('rule-candidate.san',rule['code'].encode())
    after=evaluate(rule['code'],'after',request['actions'])
    gate=candidate_decision(before,after)
    repeat=legacy_stage(ROOT,'rules',source=source,code=rule['code'],ssm=ssm,errors=after['diagnostics'])
    additional=evaluate(rule['code'],'additional-interactions',actions)
    # Verify no source artifact or rule implementation drift while collecting evidence.
    for name,data in payload.items():
        if (source_dir/name).read_bytes()!=data:raise ValueError('Historical evidence changed')
    for name,expected in implementation.items():
        if sha256((ROOT/name).read_bytes()).hexdigest()!=expected:raise ValueError('Implementation drift')
    report={'scope':'frozen_development_semantic_rule_replay_not_new_model_migration_or_independent_test',
        'historical_job':prior['migration_id'],'prepared_revision':args.revision,'prepared_sha256':entry['candidate_sha256'],
        'candidate_sha256':sha256(rule['code'].encode()).hexdigest(),'verified_source_evidence_payloads':len(payload),
        'actual_model_calls':0,'original_task_updated':False,'historical_model_usage_not_rewritten':True,
        'implementation_sha256':implementation,'rule_changes':rule['changes'],'before':before,'after':after,
        'candidate_gate':gate,'rule_idempotent':repeat['code']==rule['code'],
        'additional_actions':actions,'additional_interactions':additional,
        'source_evidence':str(source_dir.relative_to(ROOT)).replace('\\','/'),
        'limitations':['No real model output or focused-prompt success rate measured.',
                       'Only configured props and explicit action observations; not arbitrary functional equivalence.',
                       'Class separator proof does not certify arbitrary runtime object/array class normalization.',
                       'Fresh storage contexts do not establish cross-reload persistence equivalence.']}
    dump('replay.json',report)
    dump('SHA256SUMS.json',{str(p.relative_to(output)).replace('\\','/'):sha256(p.read_bytes()).hexdigest()
        for p in output.rglob('*') if p.is_file()})
    print(json.dumps({'actual_model_calls':0,'original_task_updated':False,'rule_changes':rule['changes'],
        'before':before['dimensions'],'after':after['dimensions'],'candidate_gate':gate,
        'rule_idempotent':report['rule_idempotent'],'additional_interactions':additional['dimensions'],
        'action_count':len(actions),'actions_passed':sum(i['passed'] for i in additional['interaction'])},indent=2))


if __name__=='__main__':main()
