"""Durable real migration application. The graph owns routing, not this service."""
from hashlib import sha256
import base64
import json
from pathlib import Path
import re
import time
from uuid import uuid4

from sqlalchemy import select

from .service import ServiceError,fields
from ..persistence.database import transaction
from ..persistence.schema_v1 import SourceInput
from ..persistence.migrations import MigrationJob,MigrationFile,ModelCall,ManualFeedback
from ..reporting.identity import digest
from ..runtime import profile
from ..adapters.legacy_checks import legacy_binding,legacy_stage
from ..adapters.ssm import SSMExtractor,source_binding
from ..adapters.model import QwenModel,ModelExchange,inspect_response
from ..adapters.browser import BrowserEvaluator
from ..prompts.migration import generation_messages,examples
from ..stages.evaluation import assess,candidate_decision
from ..stages.syntax import failed_syntax,syntax_repair_messages
from ..contracts.production_scope import production_scope


def binding(settings):
    sources={str(p.relative_to(settings.project_root)).replace('\\','/'):sha256(p.read_bytes()).hexdigest()
        for directory in ('src/card_migration_system','browser') for p in sorted((settings.project_root/directory).rglob('*'))
        if p.is_file() and 'node_modules' not in p.parts and p.suffix in ('.py','.mjs','.json') and '__pycache__' not in p.parts}
    return {'system':digest(sources),'legacy':digest(legacy_binding(settings.repository_root)),
            'ssm':digest(source_binding(settings.repository_root)),'protocol':'modular-migration-v1'}


class MigrationService:
    def __init__(self,base,*,model=None,browser=None,extractor=None,checks=None):
        self.base=base;self.settings=base.settings;self.engine=base.engine;self.storage=base.storage
        self.model=model;self.browser=browser;self.extractor=extractor;self.checks=checks or legacy_stage
        self.tracer=None

    def job(self,key):
        if not isinstance(key,str) or not re.fullmatch('[0-9a-f]{32}',key):raise ServiceError('invalid_migration_id',400)
        with transaction(self.engine) as s:return self.base.get(s,MigrationJob,key)

    def create(self,payload,idempotency_key):
        fields(payload,('input_id','name','max_repair_rounds','props','actions','trusted_source','source_group','strategy','excluded_example_groups','confirm_model_calls'),('input_id','trusted_source'))
        if not isinstance(idempotency_key,str) or not re.fullmatch('[A-Za-z0-9_-]{1,80}',idempotency_key):raise ServiceError('idempotency_key_required',400)
        if payload['trusted_source'] is not True:raise ServiceError('trusted_local_component_required',400)
        rounds=payload.get('max_repair_rounds',3)
        if type(rounds) is not int or not 0<=rounds<=3:raise ServiceError('invalid_repair_budget',400)
        props=payload.get('props',{});actions=payload.get('actions',[])
        if type(props) is not dict or len(json.dumps(props))>32768 or type(actions) is not list or len(actions)>20:raise ServiceError('invalid_evaluation_configuration',400)
        names=set()
        for action in actions:
            fields(action,('type','selector','value','target','name'),('type','selector','name'))
            if action['type'] not in ('click','input','select','key','drag') or not all(type(action[k]) is str and 0<len(action[k])<=300 for k in ('name','selector')) or action['name'] in names:raise ServiceError('invalid_interaction_action',400)
            names.add(action['name'])
            if action['type'] in ('input','select','key') and type(action.get('value')) is not str:raise ServiceError('invalid_interaction_value',400)
            if action['type']=='drag' and type(action.get('target')) is not str:raise ServiceError('invalid_drag_target',400)
        group=payload.get('source_group',payload['input_id']);strategy=payload.get('strategy','ssm')
        excluded=payload.get('excluded_example_groups',[])
        if type(group) is not str or len(group)>120 or strategy not in ('ssm','direct','ssm_no_repair') or type(excluded) is not list or not all(type(x) is str for x in excluded):raise ServiceError('invalid_experiment_configuration',400)
        conf=profile(self.settings)
        if conf['model']['network_enabled'] and payload.get('confirm_model_calls') is not True:
            raise ServiceError('explicit_model_call_and_soft_budget_confirmation_required',400)
        if strategy in ('direct','ssm_no_repair'):rounds=0
        name=payload.get('name','Vue to San migration')
        if type(name) is not str or not 1<=len(name.strip())<=120:raise ServiceError('invalid_task_name',400)
        with transaction(self.engine) as session:
            source=self.base.get(session,SourceInput,payload['input_id'])
            spec={'input_id':source.id,'source_sha256':source.sha256,'filename':source.filename,'name':name,
                'max_repair_rounds':rounds,'props':props,'actions':actions,'source_group':group,'strategy':strategy,
                'excluded_example_groups':excluded,'runtime':conf,'trusted_source':True,
                'support_scope':production_scope(),
                'thresholds':{'structure':.95,'ui':.95,'pixel_difference':.05},
                'evidence_class':'development_or_disclosed_exploratory_not_independent_test',
                'authorization':{'max_calls':min(rounds+1,conf['model']['max_calls']),
                    'max_output_tokens_per_call':conf['model']['max_output_tokens'],
                    'usage_stop_tokens':conf['model']['usage_stop_tokens'],'billing_cap':'not_guaranteed',
                    'scope':'one_generation_and_bounded_repairs','network_enabled':conf['model']['network_enabled']}}
            spec['few_shot_examples']=[] if strategy=='direct' else examples(self.settings,conf,source.sha256,group,excluded)
            fingerprint=digest(spec)
            prior=session.scalar(select(MigrationJob).where(MigrationJob.idempotency_key==idempotency_key))
            if prior:
                if prior.request_sha256!=fingerprint:raise ServiceError('idempotency_conflict')
                return {'migration_id':prior.id,'status':prior.status}
            key=uuid4().hex
            row=MigrationJob(id=key,input_id=source.id,idempotency_key=idempotency_key,request=spec,request_sha256=fingerprint,
                binding=binding(self.settings),status='queued',stage='queued',stop_reason='',state={},cancel_requested=False,
                created_at=time.time(),updated_at=time.time())
            session.add(row)
        self.put_json(key,'request.json','request',{'request':spec,'request_sha256':fingerprint,'binding':row.binding})
        return {'migration_id':key,'status':'queued'}

    def list(self):
        with transaction(self.engine) as s:
            rows=s.scalars(select(MigrationJob).order_by(MigrationJob.created_at.desc()).limit(100)).all()
            return {'items':[{'migration_id':r.id,'name':r.request['name'],'filename':r.request['filename'],
                'status':r.status,'stage':r.stage,'stop_reason':r.stop_reason,'created_at':r.created_at} for r in rows]}

    def update(self,key,**values):
        with transaction(self.engine) as s:
            row=self.base.get(s,MigrationJob,key)
            for field,value in values.items():setattr(row,field,value)
            row.updated_at=time.time()

    def guard(self,key):
        row=self.job(key)
        if row.cancel_requested:raise ServiceError('migration_cancel_requested')
        if row.request_sha256!=digest(row.request) or row.binding!=binding(self.settings):raise ServiceError('migration_binding_drift')
        if profile(self.settings)!=row.request['runtime']:raise ServiceError('migration_runtime_profile_drift')
        return row

    def source(self,key):
        row=self.job(key)
        with transaction(self.engine) as s:source=self.base.get(s,SourceInput,row.input_id)
        return self.storage.read(source.relative_path,row.request['source_sha256']).decode('utf-8')

    def put(self,key,name,kind,content):
        relative=f'migrations/{key}/{name}';fingerprint=self.storage.put(relative,content)
        with transaction(self.engine) as s:
            prior=s.get(MigrationFile,relative)
            if prior and (prior.sha256!=fingerprint or prior.job_id!=key):raise ServiceError('migration_artifact_conflict')
            if not prior:s.add(MigrationFile(relative_path=relative,sha256=fingerprint,job_id=key,kind=kind))
        return {'relative_path':relative,'sha256':fingerprint,'kind':kind}

    def put_json(self,key,name,kind,value):return self.put(key,name,kind,json.dumps(value,ensure_ascii=True,sort_keys=True,indent=2,allow_nan=False).encode())

    def cached(self,key,name):
        relative=f'migrations/{key}/{name}'
        with transaction(self.engine) as s:row=s.get(MigrationFile,relative)
        return json.loads(self.storage.read(row.relative_path,row.sha256)) if row else None

    def extract(self,key):
        self.guard(key);cached=self.cached(key,'ssm.json')
        if cached:return cached
        row=self.job(key);source=self.source(key)
        extractor=self.extractor or SSMExtractor(self.settings.repository_root)
        result=extractor.extract(source.encode(),row.request['filename'],row.request['source_sha256'])
        self.put_json(key,'ssm.json','ssm',result)
        return result

    def preflight(self,key):
        row=self.guard(key)
        browser=self.browser or BrowserEvaluator(self.settings,row.request['runtime'])
        if hasattr(browser,'preflight'):browser.preflight(self.source(key))
        if hasattr(browser,'source_contracts'):browser.source_contracts(self.source(key))
        model=self.model or (QwenModel(row.request['runtime']) if row.request['runtime']['model']['backend']=='qwen' else self.local_model(row.request['runtime']))
        model.preflight()
        return {}

    def verify_local_model(self,key):
        row=self.job(key)
        if row.request['runtime']['model']['backend']=='local_lora':
            from ..training.lora import model_manifest
            learning=row.request['runtime']['learning']
            assets={name:digest(model_manifest(learning[name])) for name in ('base_model_path','adapter_path')}
            prior=self.cached(key,'model-assets.json')
            if prior and prior!=assets:raise ServiceError('local_model_artifact_drift')
            if not prior:self.put_json(key,'model-assets.json','model_assets',assets)

    def invoke(self,key,ordinal,messages):
        row=self.guard(key);spec=row.request;request_hash=digest(messages)
        if len(json.dumps(messages).encode())>4*1024*1024-1024:raise ServiceError('model_request_too_large')
        if type(ordinal) is not int or not 0<=ordinal<=spec['max_repair_rounds']:raise ServiceError('invalid_model_round')
        model=self.model or (QwenModel(spec['runtime']) if spec['runtime']['model']['backend']=='qwen' else self.local_model(spec['runtime']))
        call_id=f'{key}:{ordinal}'
        with transaction(self.engine) as s:
            previous=s.get(ModelCall,call_id)
            all_calls=s.scalars(select(ModelCall).where(ModelCall.job_id==key)).all()
            if not previous and len(all_calls)>=spec['authorization']['max_calls']:raise ServiceError('model_call_budget_exhausted')
            if previous:
                if previous.request_sha256!=request_hash:raise ServiceError('model_request_replay_mismatch')
                if previous.status!='returned':raise ServiceError('model_response_unknown_no_automatic_retry')
                receipt=previous.receipt
            else:receipt=None
            if not previous and any(r.status in ('started','unknown') for r in all_calls):raise ServiceError('model_response_unknown_no_automatic_retry')
            if not previous and all_calls and any(r.receipt is None or r.receipt.get('usage') is None for r in all_calls):raise ServiceError('model_usage_unknown_requires_review')
            used=sum(((r.receipt or {}).get('usage') or {}).get('total_tokens',0) for r in all_calls)
            if not previous and used>=spec['authorization']['usage_stop_tokens']:raise ServiceError('model_usage_stop_reached')
        if receipt:
            if not receipt['valid']:raise ServiceError(receipt['error'])
            response=self.read_file(key,receipt['response']['relative_path'])
            result=inspect_response(ModelExchange(receipt['http_status'],response),spec['runtime']['model']['model'])
            if not result['valid']:raise ServiceError(result['error'])
            return result
        # Preflight (no network) before durable start; missing credentials do not spend a slot.
        model.preflight()
        self.verify_local_model(key)
        self.put_json(key,f'calls/{ordinal}/request.json','model_request',{'messages':messages,
            'sha256':request_hash,'model':spec['runtime']['model']['model'],'authorization':spec['authorization']})
        self.guard(key)
        with transaction(self.engine) as s:
            if s.get(ModelCall,call_id):raise ServiceError('concurrent_model_attempt')
            s.add(ModelCall(id=call_id,job_id=key,ordinal=ordinal,status='started',request_sha256=request_hash,
                receipt=None,started_at=time.time()))
        try:
            exchange=self.tracer.stage('model_call_'+str(ordinal),request_hash,lambda:model.exchange(messages),'llm',
                summarize=lambda response:{'http_status':response.status,
                    'usage':inspect_response(response,spec['runtime']['model']['model'])['usage']}) if self.tracer else model.exchange(messages)
            response=self.put(key,f'calls/{ordinal}/response.json','model_response',exchange.body)
            result=inspect_response(exchange,spec['runtime']['model']['model'])
            if result['usage'] and result['usage']['completion_tokens']>spec['authorization']['max_output_tokens_per_call']:
                result.update(valid=False,error='provider_output_budget_exceeded',code=None)
            receipt={'http_status':exchange.status,'response':response,'usage':result['usage'],
                     'valid':result['valid'],'error':result['error'],'request_sha256':request_hash,
                     'provenance':'injected_test_client' if self.model is not None else spec['runtime']['model']['backend']}
            self.put_json(key,f'calls/{ordinal}/receipt.json','model_receipt',receipt)
            with transaction(self.engine) as s:
                call=self.base.get(s,ModelCall,call_id);call.status='returned';call.receipt=receipt;call.finished_at=time.time()
        except Exception:
            with transaction(self.engine) as s:
                call=self.base.get(s,ModelCall,call_id)
                if call.status=='started':call.status='unknown'
            raise
        if not result['valid']:raise ServiceError(result['error'])
        self.guard(key)
        return result

    @staticmethod
    def local_model(conf):
        from ..training.lora import LocalLoraModel
        return LocalLoraModel(conf)

    def generate(self,key):
        from ..stages.generate import generate_initial
        return generate_initial(self,key,generation_messages)

    def evaluate(self,key,revision):
        self.guard(key);number=revision['number'];cached=self.cached(key,f'evaluations/{number}.json')
        if cached:return cached
        source=self.source(key);row=self.job(key);ssm=self.extract(key)['ssm']
        browser=self.browser or BrowserEvaluator(self.settings,row.request['runtime'])
        syntax=browser.syntax(source,revision['code']) if hasattr(browser,'syntax') else None
        if syntax and syntax['status']=='fail':
            result=failed_syntax(syntax,revision['file']['sha256'])
            self.put_json(key,f'evaluations/{number}.json','evaluation',result);return result
        # Run semantic analyzers only after parsing, avoiding a cascade of analysis_unavailable.
        static=self.checks(self.settings.repository_root,'validate',source=source,code=revision['code'],ssm=ssm)
        data=browser.evaluate(source,revision['code'],row.request['props'],row.request['actions'])
        if data.get('status')=='target_compile_failed':
            if data.get('syntax'):
                result=failed_syntax(data['syntax'],revision['file']['sha256'])
                self.put_json(key,f'evaluations/{number}.json','evaluation',result);return result
            result={'dimensions':{'static':'fail','compile_runtime':'fail','structure':'not_run','visual':'not_run',
                'interaction':'not_run','source_baseline':'not_run'},'required':['static','compile_runtime','structure','visual','source_baseline'],
                'passed':False,'source_blocked':False,'structure_ted':{'similarity':0},'dom_ted':{'similarity':0},
                'ui_restoration':0,'different_pixel_ratio':1,'ssim':0,'styles':{},'interaction':[],
                'diagnostics':static['validation_errors']+[{'code':'target_compile_failed','message':data['diagnostic']}],
                'coverage':'target_did_not_compile','images':{},'revision_sha256':revision['file']['sha256']}
            self.put_json(key,f'evaluations/{number}.json','evaluation',result);return result
        result=assess(static,data,row.request['actions'],row.request['thresholds'],ssm)
        if syntax:result['syntax']=syntax
        images={}
        for name,value in [('vue',data['vue'].pop('png')),('san',data['san'].pop('png')),('heatmap',data['image'].pop('heatmap'))]:
            images[name]=self.put(key,f'evaluations/{number}/{name}.png','screenshot',base64.b64decode(value,validate=True))
        from ..adapters.embedding import similarity
        embedding=similarity(row.request['runtime']['learning']['embedding_model_path'],
            self.read_file(key,images['vue']['relative_path']),self.read_file(key,images['san']['relative_path']))
        result['embedding_similarity']=embedding
        self.put_json(key,f'evaluations/{number}/raw.json','browser_evidence',{'static':static,'browser':data})
        result.update(revision_sha256=revision['file']['sha256'],images=images)
        self.put_json(key,f'evaluations/{number}.json','evaluation',result)
        return result

    def repair_feedback(self,key,current):
        attempts=[]
        for decision in self.job(key).state.get('decisions',[]):
            if decision['accepted'] or decision['previous']!=current['file']['sha256']:continue
            candidate=self.cached(key,f'revisions/{decision["round"]}.json')
            observed=self.cached(key,f'evaluations/{decision["round"]}.json')
            if not candidate or not observed or candidate['file']['sha256']!=decision['candidate'] or observed.get('revision_sha256')!=decision['candidate']:
                raise ServiceError('repair_feedback_binding_mismatch')
            diagnostics=[]
            for item in observed.get('diagnostics',[])[:8]:
                diagnostics.append({'code':str(item.get('code',''))[:120],'message':str(item.get('message',''))[:500],
                    'location':item.get('location'),'excerpt':str(item.get('excerpt',''))[:300]})
            attempts.append({'round':decision['round'],'candidate_sha256':decision['candidate'],
                'reason':decision['reason'],'syntax_status':observed.get('syntax',{}).get('status'),
                'diagnostic_count':observed.get('syntax',{}).get('diagnostic_count',len(observed.get('diagnostics',[]))),
                'diagnostics':diagnostics})
        return attempts[-3:]

    def repair(self,key,current,evaluation,number):
        from ..stages.repair import propose_repair
        return propose_repair(self,key,current,evaluation,number,BrowserEvaluator=BrowserEvaluator,
                              syntax_repair_messages=syntax_repair_messages)

    def decide(self,key,previous,candidate,old,new):
        decision=candidate_decision(old,new)
        decision.update(previous=previous['file']['sha256'],candidate=candidate['file']['sha256'],round=candidate['number'])
        self.put_json(key,f'decisions/{candidate["number"]}.json','decision',decision)
        return decision

    def read_file(self,key,relative):
        with transaction(self.engine) as s:row=s.get(MigrationFile,relative)
        if row is None or row.job_id!=key:raise ServiceError('migration_file_not_found',404)
        return self.storage.read(row.relative_path,row.sha256)

    def report(self,key):
        row=self.job(key)
        if row.request_sha256!=digest(row.request):raise ServiceError('migration_request_hash_mismatch')
        self.source(key)
        with transaction(self.engine) as s:
            files=s.scalars(select(MigrationFile).where(MigrationFile.job_id==key)).all()
            calls=s.scalars(select(ModelCall).where(ModelCall.job_id==key).order_by(ModelCall.ordinal)).all()
            feedback=s.scalars(select(ManualFeedback).where(ManualFeedback.job_id==key).order_by(ManualFeedback.created_at,ManualFeedback.id)).all()
        # Audit all indexed bytes, including failed candidates and raw responses.
        for item in files:self.storage.read(item.relative_path,item.sha256)
        known=[c.receipt['usage'] for c in calls if c.receipt and c.receipt.get('usage')]
        state=row.state;assessment=state.get('evaluation')
        return {'schema_version':1,'migration_id':row.id,'name':row.request['name'],'status':row.status,'stage':row.stage,
            'stop_reason':row.stop_reason,'request_sha256':row.request_sha256,'request':row.request,'binding':row.binding,
            'support_scope':row.request.get('support_scope'),
            'state':{k:v for k,v in state.items() if k not in ('current','candidate')},
            'final_artifact':state.get('current',{}).get('file'),'assessment':assessment,
            'model_calls_started':len(calls),'model_calls_returned':sum(c.status=='returned' for c in calls),
            'actual_cloud_model_calls':None if any(c.status!='returned' for c in calls) else sum((c.receipt or {}).get('provenance')=='qwen' for c in calls),
            'unknown_calls':sum(c.status!='returned' for c in calls),
            'usage':{'known_total_tokens':sum(u['total_tokens'] for u in known),'complete':len(known)==len(calls)},
            'calls':[{'ordinal':c.ordinal,'status':c.status,'receipt':c.receipt} for c in calls],
            'files':[{'relative_path':f.relative_path,'sha256':f.sha256,'kind':f.kind} for f in files],
            'manual_feedback':[{'id':f.id,'passed':f.passed,'revision_sha256':f.revision_sha256,
                'changed_lines':f.changed_lines,'elapsed_seconds':f.elapsed_seconds,'notes':f.notes} for f in feedback],
            'coverage':assessment.get('coverage') if assessment else 'not_run',
            'production_ready':False,'scope':'real_migration_local_single_user','created_at':row.created_at}

    def cancel(self,key):
        row=self.job(key)
        if row.status in ('finished','failed','cancelled','blocked','review_required'):raise ServiceError('migration_already_stopped')
        self.update(key,cancel_requested=True,status='cancelled' if row.status=='queued' else row.status)

    def feedback(self,key,payload):
        fields(payload,('revision_sha256','passed','changed_lines','elapsed_seconds','notes'),('revision_sha256','passed','notes'))
        report=self.report(key);artifact=report['final_artifact']
        if report['status'] in ('queued','running'):raise ServiceError('manual_feedback_requires_stopped_run')
        if not artifact or payload['revision_sha256']!=artifact['sha256']:raise ServiceError('feedback_revision_mismatch')
        if type(payload['passed']) is not bool or type(payload['notes']) is not str or len(payload['notes'])>4000:raise ServiceError('invalid_feedback',400)
        lines=payload.get('changed_lines');elapsed=payload.get('elapsed_seconds')
        if lines is not None and (type(lines) is not int or not 0<=lines<=100000):raise ServiceError('invalid_changed_lines',400)
        if elapsed is not None and (type(elapsed) not in (int,float) or not 0<=elapsed<=604800):raise ServiceError('invalid_manual_duration',400)
        key_feedback=uuid4().hex
        with transaction(self.engine) as s:s.add(ManualFeedback(id=key_feedback,job_id=key,revision_sha256=artifact['sha256'],passed=payload['passed'],changed_lines=lines,elapsed_seconds=elapsed,notes=payload['notes'],created_at=time.time()))
        return {'feedback_id':key_feedback,'automatic_result_unchanged':True}
