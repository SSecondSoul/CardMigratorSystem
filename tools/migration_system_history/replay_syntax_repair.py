"""Freeze a failed job and replay bounded syntax rules offline. Never updates the job."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

PROJECT=Path(__file__).resolve().parents[2]/'migration_system'
ROOT=PROJECT.parent
sys.path.insert(0,str(PROJECT/'src'))
from card_migration_system.config import load_settings
from card_migration_system.runtime import profile
from card_migration_system.adapters.syntax import target_syntax
from card_migration_system.adapters.legacy_checks import legacy_stage
from card_migration_system.adapters.browser import BrowserEvaluator
from card_migration_system.stages.evaluation import assess
from card_migration_system.application.service import ServiceError


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--output-dir',required=True)
    parser.add_argument('--with-browser',action='store_true')
    args=parser.parse_args()
    if not re.fullmatch('[0-9a-f]{32}',args.run_id):parser.error('Invalid run ID')
    settings=load_settings(project_root=PROJECT,environ={})
    base=settings.artifact_dir/'migrations'/args.run_id
    output=Path(args.output_dir).resolve()
    if not output.is_relative_to(ROOT) or output.is_relative_to(settings.artifact_dir.resolve()):
        raise ValueError('Choose a separate workspace evidence directory, outside live artifacts')
    if output.exists():raise FileExistsError('No evidence overwrite allowed')
    request_record=json.loads((base/'request.json').read_bytes());request=request_record['request']
    source_path=(settings.artifact_dir/'inputs'/request['input_id']/request['filename']).resolve()
    if not source_path.is_relative_to((settings.artifact_dir/'inputs').resolve()):raise ValueError('Invalid source path')
    source_bytes=source_path.read_bytes()
    if sha256(source_bytes).hexdigest()!=request['source_sha256']:raise ValueError('Source hash mismatch')
    historical={str(p.relative_to(base)).replace('\\','/'):p.read_bytes() for p in base.rglob('*') if p.is_file()}
    # Verify revision references BEFORE freezing or running any rule.
    revisions=[]
    for name,content in historical.items():
        if re.fullmatch(r'revisions/\d+\.json',name):
            revision=json.loads(content)
            san_name='revisions/'+str(revision['number'])+'.san'
            if sha256(historical[san_name]).hexdigest()!=revision['file']['sha256']:raise ValueError('Revision hash mismatch')
            if historical[san_name].decode()!=revision['code']:raise ValueError('Revision code mismatch')
            revisions.append(revision)
    if not revisions:raise ValueError('No revisions')
    output.mkdir(parents=True)
    for name,content in historical.items():
        destination=output/'frozen'/name;destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(content)
    (output/'frozen/source.vue').write_bytes(source_bytes)
    frozen_manifest={name:sha256(content).hexdigest() for name,content in historical.items()}
    frozen_manifest['source.vue']=sha256(source_bytes).hexdigest()
    (output/'FROZEN_SHA256SUMS.json').write_text(json.dumps(frozen_manifest,indent=2),encoding='utf-8')
    source=source_bytes.decode();ssm=json.loads(historical['ssm.json'])['ssm'];results=[]
    for revision in sorted(revisions,key=lambda r:r['number']):
        result=target_syntax(settings,source,revision['code'],normalize=True)
        code=result.pop('code');number=revision['number']
        destination=output/f'candidate-{number}.san';destination.write_bytes(code.encode())
        result.update(revision=number,original_sha256=revision['file']['sha256'],
                      candidate_sha256=sha256(destination.read_bytes()).hexdigest())
        if result['after']['status']=='pass':
            static=legacy_stage(ROOT,'validate',source=source,code=code,ssm=ssm)
            result['static_after']={'passed':static['validation_passed'],'diagnostics':static['validation_errors']}
            if args.with_browser:
                browser=BrowserEvaluator(settings,profile(settings))
                try:
                    data=browser.evaluate(source,code,request['props'],request['actions'])
                    if data['status']=='completed':
                        observation=assess(static,data,request['actions'],request['thresholds'],ssm)
                        result['assessment_after']=observation
                    else:result['browser_after']=data
                except ServiceError as error:
                    result['browser_after']={'status':'blocked','error':error.code}
        results.append(result)
    # Assert byte-for-byte preservation, including unindexed failure and receipt files.
    for name,content in historical.items():
        if (base/name).read_bytes()!=content:raise ValueError('Historical artifacts changed during replay')
    if source_path.read_bytes()!=source_bytes:raise ValueError('Historical source changed during replay')
    implementation={str(p.relative_to(PROJECT)).replace('\\','/'):sha256(p.read_bytes()).hexdigest()
        for folder in ('browser','src/card_migration_system') for p in (PROJECT/folder).rglob('*')
        if p.is_file() and p.suffix in ('.mjs','.py') and 'node_modules' not in p.parts}
    report={'scope':'frozen_development_failure_syntax_replay_not_new_migration_or_independent_test',
        'migration_id':args.run_id,'policy':'target_syntax_first_v1','actual_model_calls':0,
        'original_task_updated':False,'historical_files_verified':len(historical)+1,
        'source_sha256':request['source_sha256'],'results':results,'implementation_sha256':implementation,
        'limitation':'Syntax success alone does not establish semantic, interaction or arbitrary input equivalence.'}
    (output/'replay.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    manifest={str(p.relative_to(output)).replace('\\','/'):sha256(p.read_bytes()).hexdigest()
        for p in output.rglob('*') if p.is_file()}
    (output/'SHA256SUMS.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps({'actual_model_calls':0,'original_task_updated':False,'historical_files_verified':len(historical)+1,
        'revisions':[{'number':r['revision'],'before':r['before']['status'],'after':r['after']['status'],
            'rules':[c['rule'] for c in r['changes']],
            'static_after':r.get('static_after',{}).get('passed'),
            'dimensions':r.get('assessment_after',{}).get('dimensions')} for r in results]},indent=2))


if __name__=='__main__':main()
