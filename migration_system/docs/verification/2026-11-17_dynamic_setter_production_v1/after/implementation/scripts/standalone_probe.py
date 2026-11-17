"""Verification-only child: real local graph/engine/browser, explicit recorded model double."""
import argparse
import json
from pathlib import Path
import sys

PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT/'src'))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--forbidden-checkout',type=Path,required=True)
    forbidden=parser.parse_args().forbidden_checkout.resolve()
    environment=Path(sys.prefix).resolve()
    def audit(event,args):
        if event=='open' and isinstance(args[0],(str,bytes)):
            try:path=Path(args[0]).resolve()
            except (OSError,ValueError,TypeError):return
            if path.is_relative_to(forbidden) and not path.is_relative_to(environment):
                raise PermissionError('Original checkout access forbidden in standalone probe')
    sys.addaudithook(audit)
    from card_migration_system.config import load_settings
    from card_migration_system.interfaces.cli import check_scaffold
    from card_migration_system.persistence.database import initialize
    from card_migration_system.interfaces.api.app import create_app
    from card_migration_system.application.migrations import MigrationService
    from card_migration_system.adapters.model import ModelExchange
    from card_migration_system.adapters.browser import BrowserEvaluator,SourceParseError
    from card_migration_system.runtime import profile
    from card_migration_system.contracts.production_scope import production_scope
    from card_migration_system.reporting.identity import digest
    from card_migration_system.workers.migration import work_once
    settings=load_settings(project_root=PROJECT,environ={})
    checked=check_scaffold(project_root=PROJECT,environ={})
    assert settings.engine_root.is_relative_to(PROJECT)
    assert settings.artifact_dir.is_relative_to(PROJECT) and settings.runtime_dir.is_relative_to(PROJECT)
    initialize(settings)
    token='standalone-verification-token-not-a-secret'
    app=create_app(settings,write_token=token);client=app.test_client();base=app.extensions['migration_service']
    source='<template><button class="card" @click="increment">{{count}}</button></template><script>export default {name:"CounterCard",data(){return {count:0}},methods:{increment(){this.count++}}}</script><style>.card{color:rgb(20,40,60)}</style>'
    target='<template><button class="card" on-click="increment">{{count}}</button></template><script>const san=require("san");const DataTypes=san.DataTypes;module.exports=san.defineComponent({name:"CounterCard",dataTypes:{},initData(){return {count:0}},increment(){this.data.set("count",this.data.get("count")+1)}});</script><style>.card{color:rgb(20,40,60)}</style>'
    class RecordedModel:
        def __init__(self):self.calls=0
        def preflight(self):pass
        def exchange(self,messages):
            self.calls+=1
            # A single glyph color may legitimately remain within configured
            # pixel/style thresholds. Use an unmistakable layout/background
            # defect to exercise repair without changing evaluation thresholds.
            code=target.replace('.card{color:rgb(20,40,60)}',
                '.card{color:rgb(200,0,0);background:black;font-size:100px;padding:50px}') if self.calls==1 else target
            return ModelExchange(200,json.dumps({'model':'qwen-plus','choices':[{'finish_reason':'stop',
                'message':{'role':'assistant','content':code}}],
                'usage':{'prompt_tokens':10,'completion_tokens':20,'total_tokens':30}}).encode())
    model=RecordedModel()
    service=MigrationService(base,model=model)
    origin=f'http://127.0.0.1:{settings.port}'
    headers={'X-Cardmig-Token':token,'Origin':origin,'Idempotency-Key':'standalone-counter'}
    try:
        assert client.get('/',base_url=origin).status_code==200
        assert client.get('/api/v1/system/readiness',base_url=origin).json['support_scope']==production_scope()
        response=client.post('/api/v1/inputs',base_url=origin,headers=headers,json={'filename':'CounterCard.vue','source':source})
        assert response.status_code==201,response.json
        queued=client.post('/api/v1/migrations',base_url=origin,headers=headers,json={'input_id':response.json['input_id'],
            'name':'standalone-recorded-counter','trusted_source':True,'confirm_model_calls':True,'max_repair_rounds':2,
            'actions':[{'name':'increment','type':'click','selector':'button'}]})
        assert queued.status_code==202,queued.json
        key=queued.json['migration_id'];report=work_once(base,service=service)
        assert report['status']=='finished',{'reason':report['stop_reason'],'assessment':report['assessment']}
        assert 1<=model.calls<=2,model.calls
        fixture_calls=model.calls
        assert report['actual_cloud_model_calls']==0
        assert report['support_scope']==production_scope()
        assert report['request']['support_scope']==production_scope()
        assert report['request_sha256']==digest(report['request'])
        assert report['assessment']['dimensions']['interaction']=='pass'
        assert all(value=='pass' for value in report['assessment']['dimensions'].values()),report['assessment']['dimensions']
        assert any(d['accepted'] for d in report['state']['decisions'])
        downloaded=client.get('/api/v1/migrations/'+key+'/files',base_url=origin,
                              query_string={'path':report['final_artifact']['relative_path']})
        from hashlib import sha256
        assert downloaded.status_code==200 and sha256(downloaded.data).hexdigest()==report['final_artifact']['sha256']
        ssm=next(item for item in report['files'] if item['kind']=='ssm')
        ssm_download=client.get('/api/v1/migrations/'+key+'/files',base_url=origin,
                                query_string={'path':ssm['relative_path']})
        assert ssm_download.status_code==200 and sha256(ssm_download.data).hexdigest()==ssm['sha256']
        saved_report=client.get('/api/v1/migrations/'+key+'/report',base_url=origin).json
        assert saved_report['support_scope']==production_scope() and saved_report['status']=='finished'
        verdict=report['assessment']
        feedback=client.post('/api/v1/migrations/'+key+'/feedback',base_url=origin,headers=headers,
            json={'revision_sha256':report['final_artifact']['sha256'],'passed':True,'notes':'Engineering fixture only, not a human migration acceptance'})
        assert feedback.status_code==201,feedback.json
        assert service.report(key)['assessment']==verdict
        complex_source=(PROJECT/'tests/fixtures/CapacityPlanningBoard.vue').read_bytes().decode('utf-8')
        complex_actions=json.loads((PROJECT/'configs/diagnostics/capacity-planning-actions.json').read_bytes())
        complex_input=base.create_input({'filename':'CapacityPlanningBoard.vue','source':complex_source})
        complex_key=service.create({'input_id':complex_input['input_id'],'trusted_source':True,
            'confirm_model_calls':True,'actions':complex_actions},'standalone-dynamic-complex')['migration_id']
        complex_report=work_once(base,service=service)
        assert complex_report['migration_id']==complex_key
        assert complex_report['status']=='finished',{'reason':complex_report['stop_reason'],'assessment':complex_report['assessment']}
        assert complex_report['generation_origin']=='source_ast_rule_generation'
        assert complex_report['model_calls_started']==0 and model.calls==fixture_calls
        assert all(value=='pass' for value in complex_report['assessment']['dimensions'].values())
        assert len(complex_report['assessment']['interaction'])==9
        complex_download=client.get('/api/v1/migrations/'+complex_key+'/files',base_url=origin,
            query_string={'path':complex_report['final_artifact']['relative_path']})
        assert complex_download.status_code==200
        assert sha256(complex_download.data).hexdigest()==complex_report['final_artifact']['sha256']
        browser=BrowserEvaluator(settings,profile(settings))
        assert browser.preflight(source.replace('{{count}}','<input><img alt="x"><br>{{count}}'))['status']=='completed'
        try:browser.preflight(source.replace('{{count}}','<span>{{count}}'))
        except SourceParseError:pass
        else:raise AssertionError('True missing end tag was accepted')
        unsupported=source.replace('increment(){this.count++}','increment(){this.count++},setValue(k,v){this[k]=v},privateDependency(){return this.$.vnode}')
        input_row=base.create_input({'filename':'Unsupported.vue','source':unsupported})
        blocked_key=service.create({'input_id':input_row['input_id'],'trusted_source':True,'confirm_model_calls':True},'standalone-block')['migration_id']
        blocked=work_once(base,service=service)
        assert blocked['migration_id']==blocked_key and blocked['stop_reason']=='source_dynamic_key_contract_unsupported'
        assert blocked['model_calls_started']==0 and model.calls==fixture_calls
        assert blocked['support_scope']==production_scope() and blocked['assessment'] is None
        loaded=[Path(module.__file__).resolve() for name,module in sys.modules.items()
                if name.startswith('card_migration_system') and getattr(module,'__file__',None)]
        assert loaded and all(p.is_relative_to(PROJECT) for p in loaded)
        print(json.dumps({'status':'standalone_verified','quality_claim':'engineering_fixture_not_real_model_migration_rate',
            'engine_files':checked['engine']['files'],'API_frontend_download':True,'SSM_AST':'real_internal_engine',
            'LangGraph':'actual_persistent_graph','model':'explicit_recorded_response_test_double',
            'fixture_model_exchanges':model.calls,'actual_cloud_model_calls':0,
            'dimensions':report['assessment']['dimensions'],'repair_candidate_accepted':True,
            'support_scope':production_scope(),'source_request_scope_fingerprinted':True,
            'ssm_download_hash_verified':True,'report_scope_verified':True,
            'feedback_does_not_overwrite_automatic_result':True,
            'dynamic_complex_fixture':{'source_sha256':sha256(complex_source.encode()).hexdigest(),
                'dimensions':complex_report['assessment']['dimensions'],'actions':9,
                'origin':complex_report['generation_origin'],'model_calls':complex_report['model_calls_started'],
                'download_hash_verified':True,'static_validation_scope':complex_report['assessment']['static_validation_scope']},
            'void_elements_pass':True,'genuine_syntax_error_blocked':True,'unsupported_contract_blocked_before_model':True,
            'old_checkout_read_guard':'enabled_except_installed_python_environment',
            'all_loaded_system_modules_inside_copy':True,'original_database_updated':False},ensure_ascii=True))
    finally:base.close()


if __name__=='__main__':main()
