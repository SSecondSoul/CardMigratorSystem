"""Explicit opt-in LangSmith export. Never leak code, prompts, keys or raw errors."""
from datetime import datetime, timezone
import os
import time
from uuid import uuid4


class Tracer:
    def __init__(self,profile,job_id):
        self.config=profile['tracing'];self.job_id=job_id;self.client=None;self.root=uuid4();self.records=[]
        self.pending=None
        if self.config['enabled']:
            key=os.environ.get(self.config['api_key_env'])
            if not key:self.pending='langsmith_key_missing'
            else:
                try:
                    from langsmith import Client
                    self.client=Client(api_key=key,api_url=self.config['endpoint'],auto_batch_tracing=False)
                    self.client.create_run(id=self.root,name='Vue to San migration',run_type='chain',
                        inputs={'migration_id':job_id},project_name=self.config['project'])
                except Exception:self.client=None;self.pending='langsmith_export_failed'

    def stage(self,name,request_hash,callback,kind='chain',summarize=None):
        key=uuid4();start=time.time();error=None;result=None
        try:
            result=callback();return result
        except Exception as failure:error=type(failure).__name__;raise
        finally:
            record={'id':str(key),'name':name,'parent_run_id':str(self.root),'request_sha256':request_hash,
                'elapsed_seconds':time.time()-start,'error_type':error,'uploaded':False}
            outputs={'error_type':error}
            if summarize is not None and result is not None:
                try:outputs.update(summarize(result))
                except Exception:outputs['summary_unavailable']=True
            record['outputs']=outputs
            if self.client:
                try:
                    self.client.create_run(id=key,parent_run_id=self.root,name=name,run_type=kind,
                        inputs={'request_sha256':request_hash},outputs=outputs,
                        start_time=datetime.fromtimestamp(start,timezone.utc),end_time=datetime.now(timezone.utc),
                        project_name=self.config['project'])
                    record['uploaded']=True
                except Exception:self.pending='langsmith_export_failed'
            self.records.append(record)

    def finish(self,summary):
        if self.client:
            try:self.client.update_run(self.root,outputs=summary,end_time=datetime.now(timezone.utc))
            except Exception:self.pending='langsmith_export_failed'
        return {'root_run_id':str(self.root),'enabled':self.config['enabled'],'export_error':self.pending,
            'records':self.records,'uploaded':bool(self.client) and self.pending is None,
            'data_scope':'hashes_stage_timing_decisions_usage_only'}
