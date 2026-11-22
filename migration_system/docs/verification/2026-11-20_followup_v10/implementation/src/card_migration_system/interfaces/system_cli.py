"""Real migration and offline training commands, no implicit service start or calls."""
import argparse
import json
from pathlib import Path
import sys
from uuid import uuid4

from ..config import load_settings
from ..application.service import Service,ServiceError
from ..application.migrations import MigrationService
from ..runtime import readiness
from ..persistence.database import transaction
from ..persistence.schema_v1 import SourceInput
from sqlalchemy import select
from hashlib import sha256

COMMANDS={'system-status','migration-worker','submit-migration','migration-report','submit-migration-batch',
          'build-training-data','train-lora','migration-statistics'}


def main(argv):
    parser=argparse.ArgumentParser(description='Modular Vue → SSM → San system')
    parser.add_argument('command',choices=sorted(COMMANDS));parser.add_argument('--project-root',type=Path)
    parser.add_argument('--config',type=Path);parser.add_argument('--once',action='store_true')
    parser.add_argument('--source',type=Path);parser.add_argument('--manifest',type=Path)
    parser.add_argument('--run-id');parser.add_argument('--idempotency-key');parser.add_argument('--name',default='CLI migration')
    parser.add_argument('--max-repair-rounds',type=int,default=3);parser.add_argument('--evaluation-config',type=Path)
    parser.add_argument('--strategy',choices=['ssm','direct','ssm_no_repair'],default='ssm')
    parser.add_argument('--trust-local-source',action='store_true');parser.add_argument('--confirm-model-calls',action='store_true')
    parser.add_argument('--output',type=Path);parser.add_argument('--training-config',type=Path);parser.add_argument('--execute',action='store_true')
    args=parser.parse_args(argv)
    base=None
    try:
        settings=load_settings(project_root=args.project_root,config_file=args.config)
        if args.command=='system-status':result=readiness(settings)
        elif args.command=='build-training-data':
            if not args.manifest or not args.output:raise ServiceError('manifest_and_output_required')
            from ..training.data import build_dataset
            result=build_dataset(settings,args.manifest,args.output)
        elif args.command=='train-lora':
            if not args.training_config:raise ServiceError('training_config_required')
            from ..training.lora import train
            result=train(settings,args.training_config,execute=args.execute)
        else:
            base=Service(settings);service=MigrationService(base)
            def register_source(source_path):
                content=source_path.read_text(encoding='utf-8');fingerprint=sha256(content.encode()).hexdigest()
                with transaction(base.engine) as session:
                    prior=session.scalar(select(SourceInput).where(SourceInput.filename==source_path.name,SourceInput.sha256==fingerprint).limit(1))
                return {'input_id':prior.id} if prior else base.create_input({'filename':source_path.name,'source':content})
            if args.command=='migration-worker':
                from ..workers.migration import run_migration_worker
                result=run_migration_worker(base,once=args.once)
            elif args.command=='migration-report':result=service.report(args.run_id)
            elif args.command=='migration-statistics':
                from ..reporting.statistics import statistics
                result=statistics(service)
            elif args.command=='submit-migration':
                if not args.source or not args.trust_local_source or not args.confirm_model_calls:raise ServiceError('source_trust_and_call_confirmation_required')
                source=register_source(args.source)
                config=json.loads(args.evaluation_config.read_text(encoding='utf-8')) if args.evaluation_config else {}
                result=service.create({'input_id':source['input_id'],'name':args.name,'trusted_source':True,'confirm_model_calls':True,
                    'max_repair_rounds':args.max_repair_rounds,'strategy':args.strategy,**config},args.idempotency_key or uuid4().hex)
            else:
                if not args.manifest or not args.trust_local_source or not args.confirm_model_calls:raise ServiceError('batch_trust_and_call_confirmation_required')
                manifest=json.loads(args.manifest.read_text(encoding='utf-8'));items=manifest['samples']
                if len(items)>100 or len({r['id'] for r in items})!=len(items):raise ServiceError('invalid_batch_samples')
                groups=[r['group'] for r in items];results=[]
                for sample in items:
                    source_path=(args.manifest.resolve().parent/sample['vue']).resolve()
                    source=register_source(source_path)
                    results.append(service.create({'input_id':source['input_id'],'name':sample['id'],'trusted_source':True,'confirm_model_calls':True,
                        'source_group':sample['group'],'excluded_example_groups':groups,'strategy':args.strategy,
                        'props':sample.get('props',{}),'actions':sample.get('actions',[]),'max_repair_rounds':args.max_repair_rounds},
                        manifest['batch_id']+'-'+sample['id']))
                result={'batch_id':manifest['batch_id'],'queued':results,'evidence_class':'disclosed_exploratory'}
        print(json.dumps(result,ensure_ascii=True,indent=2));return 0
    except (ValueError,OSError,KeyError) as error:
        code=error.code if isinstance(error,ServiceError) else type(error).__name__
        print(json.dumps({'status':'blocked','error':code}),file=sys.stderr);return 2
    finally:
        if base:base.close()
