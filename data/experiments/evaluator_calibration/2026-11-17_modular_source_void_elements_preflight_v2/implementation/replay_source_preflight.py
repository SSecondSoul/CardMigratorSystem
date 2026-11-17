"""Freeze and replay source parsing only; no database, browser launch or model calls."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys

PROJECT=Path(__file__).resolve().parents[1];ROOT=PROJECT.parent
sys.path.insert(0,str(PROJECT/'src'))
from card_migration_system.config import load_settings
from card_migration_system.adapters.ssm import _environment


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--output-dir',required=True)
    args=parser.parse_args()
    if not re.fullmatch('[0-9a-f]{32}',args.run_id):parser.error('Invalid migration ID')
    settings=load_settings(project_root=PROJECT,environ={})
    base=settings.artifact_dir/'migrations'/args.run_id;output=Path(args.output_dir).resolve()
    if output.exists() or not output.is_relative_to(ROOT) or output.is_relative_to(settings.artifact_dir.resolve()):
        raise ValueError('Choose a new workspace evidence directory outside live artifacts')
    original={str(p.relative_to(base)).replace('\\','/'):p.read_bytes() for p in base.rglob('*') if p.is_file()}
    request=json.loads(original['request.json'])['request']
    source_path=(settings.artifact_dir/'inputs'/request['input_id']/request['filename']).resolve()
    if not source_path.is_relative_to((settings.artifact_dir/'inputs').resolve()):raise ValueError('Invalid input path')
    source=source_path.read_bytes()
    if sha256(source).hexdigest()!=request['source_sha256']:raise ValueError('Source identity mismatch')
    output.mkdir(parents=True)
    def write(name,data):
        p=output/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    def dump(name,value):write(name,json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False).encode())
    for name,data in original.items():write('frozen/'+name,data)
    write('frozen/source.vue',source)
    dump('FROZEN_SHA256SUMS.json',{**{n:sha256(b).hexdigest() for n,b in original.items()},'source.vue':sha256(source).hexdigest()})
    implementation={}
    for folder in ('src/card_migration_system','browser'):
        for p in (PROJECT/folder).rglob('*'):
            if p.is_file() and p.suffix in ('.py','.mjs') and 'node_modules' not in p.parts:
                implementation[str(p.relative_to(PROJECT)).replace('\\','/')]=sha256(p.read_bytes()).hexdigest()
    for name in ('browser/evaluate.mjs','src/card_migration_system/adapters/browser.py','src/card_migration_system/graph/migration.py'):
        write('implementation/'+name,(PROJECT/name).read_bytes())
    write('implementation/replay_source_preflight.py',Path(__file__).read_bytes())
    body={'repository':str(ROOT),'project':str(PROJECT),'source':source.decode(),'action':'source-preflight'}
    process=subprocess.run(['node',str(PROJECT/'browser/evaluate.mjs')],input=json.dumps(body).encode(),
        capture_output=True,timeout=30,cwd=PROJECT,env=_environment())
    result=json.loads(process.stdout)
    dump('node-result.json',result)
    for name,data in original.items():
        if (base/name).read_bytes()!=data:raise ValueError('Historical artifact changed')
    if source_path.read_bytes()!=source:raise ValueError('Historical source changed')
    for name,expected in implementation.items():
        if sha256((PROJECT/name).read_bytes()).hexdigest()!=expected:raise ValueError('Implementation drift')
    report={'scope':'frozen_source_preflight_only_not_migration_quality','migration_id':args.run_id,
        'filename':request['filename'],'source_sha256':request['source_sha256'],'actual_model_calls':0,
        'browser_launched':False,'database_updated':False,'original_task_updated':False,'langsmith_uploaded':False,
        'historical_files_verified':len(original)+1,'implementation_sha256':implementation,
        'returncode':process.returncode,'preflight_status':result.get('status'),'error':result.get('error'),
        'limitation':'Source parsing success is not target generation, compilation, rendering or migration success.'}
    dump('replay.json',report)
    dump('SHA256SUMS.json',{str(p.relative_to(output)).replace('\\','/'):sha256(p.read_bytes()).hexdigest()
        for p in output.rglob('*') if p.is_file()})
    print(json.dumps({k:report[k] for k in ('migration_id','actual_model_calls','browser_launched','historical_files_verified',
        'preflight_status','error')},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
