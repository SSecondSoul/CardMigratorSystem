"""Copy a terminal migration and registered source before diagnosis; no DB/model writes."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

PROJECT=Path(__file__).resolve().parents[1]
ROOT=PROJECT.parent
sys.path.insert(0,str(PROJECT/'src'))
from card_migration_system.config import load_settings


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--output-dir',required=True)
    args=parser.parse_args()
    if not re.fullmatch('[0-9a-f]{32}',args.run_id):raise ValueError('Invalid run ID')
    settings=load_settings(project_root=PROJECT,environ={})
    root=settings.artifact_dir.resolve();base=root/'migrations'/args.run_id
    output=Path(args.output_dir).resolve()
    if not output.is_relative_to(ROOT) or output.is_relative_to(root) or output.exists():
        raise ValueError('Choose a new workspace evidence directory outside live artifacts')
    original={str(p.relative_to(base)).replace('\\','/'):p.read_bytes() for p in base.rglob('*') if p.is_file()}
    report=json.loads(original['report.json'])
    if report['migration_id']!=args.run_id or report['status'] not in ('failed','blocked','finished','cancelled'):
        raise ValueError('Require matching terminal report')
    for entry in report['files']:
        path=(root/entry['relative_path']).resolve()
        if not path.is_relative_to(base) or sha256(path.read_bytes()).hexdigest()!=entry['sha256']:
            raise ValueError('Historical file identity mismatch')
    request=report['request']
    source_path=(root/'inputs'/request['input_id']/request['filename']).resolve()
    if not source_path.is_relative_to(root/'inputs'):raise ValueError('Invalid source path')
    source=source_path.read_bytes()
    if sha256(source).hexdigest()!=request['source_sha256']:raise ValueError('Source identity mismatch')
    output.mkdir(parents=True)
    payload={'frozen/'+name:data for name,data in original.items()}
    payload['frozen/source.vue']=source
    payload['freeze.json']=json.dumps({'migration_id':args.run_id,'source_sha256':request['source_sha256'],
        'scope':'historical_failure_evidence_not_new_quality_result','status':report['status'],
        'stop_reason':report['stop_reason'],'usage':report['usage'],'actual_model_calls':0,
        'original_task_updated':False,'historical_files':len(original)},ensure_ascii=False,indent=2).encode()
    for name,data in payload.items():
        path=output/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    manifest={name:sha256(data).hexdigest() for name,data in payload.items()}
    (output/'SHA256SUMS.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    if source_path.read_bytes()!=source or any((base/name).read_bytes()!=data for name,data in original.items()):
        raise ValueError('Original files changed during freeze')
    print(json.dumps({'payloads':len(payload),'historical_files':len(original),'source_verified':True,
        'original_task_updated':False,'actual_model_calls':0}))


if __name__=='__main__':main()
