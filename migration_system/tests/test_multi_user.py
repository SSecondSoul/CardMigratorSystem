"""SQLite users/authorization/quotas using temporary DBs and explicit fake model."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import time
import unittest
from sqlalchemy import select
from test_modular_system import ModularFixture, SOURCE
from card_migration_system.application.accounts import AccountService,DEFAULT_LIMITS
from card_migration_system.application.service import ServiceError
from card_migration_system.interfaces.api.app import create_app
from card_migration_system.persistence.database import transaction
from card_migration_system.persistence.accounts import User,AuthSession,UserLimit,DailyUsage,AuditLog,JobOwner
from card_migration_system.persistence.migrations import ModelCall

BASE='http://127.0.0.1:8790'
PASSWORD='Temporary-test-password-123'

class MultiUserTests(ModularFixture,unittest.TestCase):
    def setUp(self):
        super().setUp();self.settings=replace(self.settings,auth_mode='multi_user')
        self.base.settings=self.settings;self.service.settings=self.settings
        self.accounts=AccountService(self.base)
        self.admin=self.accounts.create_user({'username':'administrator','password':PASSWORD},bootstrap=True)
        self.alice=self.add_user('alice');self.bob=self.add_user('bob')
        self.app=create_app(self.settings,write_token='never-an-online-authentication-bypass')
        self.addCleanup(self.app.extensions['migration_service'].close)

    def add_user(self,name,force=False):
        user=self.accounts.create_user({'username':name,'password':PASSWORD},self.admin['id'])
        if not force:
            with transaction(self.base.engine) as s:s.get(User,user['id']).must_change_password=False
        return user

    def session(self,client):
        return client.get('/api/v1/auth/session',base_url=BASE,headers={'X-Cardmig-Session':'bootstrap'}).json

    def login(self,username='alice',password=PASSWORD):
        client=self.app.test_client();csrf=self.session(client)['csrf_token']
        response=client.post('/api/v1/auth/login',base_url=BASE,json={'username':username,'password':password},headers={'X-Cardmig-CSRF':csrf})
        self.assertEqual(response.status_code,200,response.json);return client

    def post(self,client,path,body,key=None):
        headers={'X-Cardmig-CSRF':self.session(client)['csrf_token']}
        if key:headers['Idempotency-Key']=key
        return client.post(path,base_url=BASE,json=body,headers=headers)

    def upload(self,client):
        response=self.post(client,'/api/v1/inputs',{'filename':'Card.vue','source':SOURCE})
        self.assertEqual(response.status_code,201,response.json);return response.json['input_id']

    def create(self,client,source,key='test-key'):
        return self.post(client,'/api/v1/migrations',{'input_id':source,'trusted_source':True,'confirm_model_calls':True,'name':'Account migration'},key)

    def test_anonymous_reads_and_global_token_are_not_authorization(self):
        client=self.app.test_client()
        for path in ('/api/v1/migrations','/api/v1/runs','/api/v1/admin/users','/api/v1/system/readiness'):
            self.assertEqual(client.get(path,base_url=BASE).status_code,401)
        self.assertEqual(client.post('/api/v1/inputs',base_url=BASE,json={},headers={'X-Cardmig-Token':'never-an-online-authentication-bypass'}).status_code,401)
        self.assertEqual(client.get('/health/live',base_url=BASE).status_code,200)

    def test_login_cookie_csrf_logout_and_restart(self):
        client=self.login();state=self.session(client);self.assertEqual(state['user']['username'],'alice')
        self.assertNotIn('password_hash',str(state));self.assertNotIn('token_sha256',str(state))
        self.assertEqual(client.post('/api/v1/inputs',base_url=BASE,json={'filename':'Card.vue','source':SOURCE}).status_code,403)
        app=create_app(self.settings,write_token='other-test-token-for-restart-only')
        self.addCleanup(app.extensions['migration_service'].close)
        new=app.test_client();value=client.get_cookie('cardmig_auth_8790',domain='127.0.0.1',path='/api/v1').value
        new.set_cookie('cardmig_auth_8790',value,domain='127.0.0.1',path='/api/v1')
        self.assertTrue(self.session(new)['authenticated'])
        self.assertEqual(self.post(client,'/api/v1/auth/logout',{}).status_code,200)
        self.assertFalse(self.session(new)['authenticated'])

    def test_two_users_cannot_read_modify_or_download_each_others_jobs(self):
        a=self.login();b=self.login('bob');source=self.upload(a);result=self.create(a,source)
        self.assertEqual(result.status_code,202,result.json);key=result.json['migration_id']
        self.assertEqual(b.get('/api/v1/migrations',base_url=BASE).json['items'],[])
        for suffix in ('report','artifact','files?path=anything'):
            self.assertEqual(b.get(f'/api/v1/migrations/{key}/{suffix}',base_url=BASE).status_code,404)
        for suffix in ('cancel','resume','feedback'):
            self.assertEqual(self.post(b,f'/api/v1/migrations/{key}/{suffix}',{}).status_code,404)
        self.assertEqual(self.create(b,source).status_code,404)
        self.assertEqual(a.get(f'/api/v1/migrations/{key}/report',base_url=BASE).status_code,200)
        self.assertEqual(self.post(a,f'/api/v1/migrations/{key}/cancel',{}).status_code,200)

    def test_admin_legacy_visibility_does_not_grant_user_permissions(self):
        client=self.login();admin=self.login('administrator')
        for path in ('/api/v1/admin/users','/api/v1/admin/audit','/api/v1/runs','/api/v1/ssm-extractions','/api/v1/migrations?scope=all'):
            self.assertEqual(client.get(path,base_url=BASE).status_code,403,path)
        self.assertEqual(admin.get('/api/v1/admin/users',base_url=BASE).status_code,200)
        self.assertEqual(admin.get('/api/v1/runs',base_url=BASE).status_code,200)
        self.assertNotIn('password_hash',str(admin.get('/api/v1/admin/users',base_url=BASE).json))

    def test_admin_create_force_password_change_and_reset_revoke_sessions(self):
        admin=self.login('administrator')
        response=self.post(admin,'/api/v1/admin/users',{'username':'newuser','password':PASSWORD,'display_name':'New user'})
        self.assertEqual(response.status_code,201,response.json)
        client=self.login('newuser')
        self.assertTrue(self.session(client)['user']['must_change_password'])
        self.assertEqual(client.get('/api/v1/migrations',base_url=BASE).status_code,403)
        self.assertEqual(self.post(client,'/api/v1/auth/password',{'current_password':PASSWORD,'new_password':'A-new-test-password-456'}).status_code,200)
        self.assertFalse(self.session(client)['authenticated'])
        active=self.login('newuser','A-new-test-password-456')
        self.assertEqual(self.post(admin,'/api/v1/admin/users/'+response.json['id'],{'admin_password':PASSWORD,'new_password':'Reset-temporary-pass-789'}).status_code,200)
        self.assertFalse(self.session(active)['authenticated'])
        self.assertTrue(self.session(self.login('newuser','Reset-temporary-pass-789'))['user']['must_change_password'])

    def test_disable_blocks_existing_sessions_and_queued_worker(self):
        alice=self.login();source=self.upload(alice);key=self.create(alice,source).json['migration_id'];admin=self.login('administrator')
        result=self.post(admin,'/api/v1/admin/users/'+self.alice['id'],{'admin_password':PASSWORD,'is_active':False})
        self.assertEqual(result.status_code,200,result.json)
        self.assertFalse(self.session(alice)['authenticated'])
        with self.assertRaisesRegex(ServiceError,'account_disabled'):self.service.guard(key)
        self.assertEqual(self.post(admin,'/api/v1/admin/users/'+self.admin['id'],{'admin_password':PASSWORD,'is_active':False}).status_code,409)

    def test_limits_and_user_scoped_idempotency(self):
        a=self.login();b=self.login('bob');source=self.upload(a);other=self.upload(b)
        first=self.create(a,source);again=self.create(a,source)
        self.assertEqual(first.json,again.json)
        different=self.create(b,other);self.assertEqual(different.status_code,202);self.assertNotEqual(first.json['migration_id'],different.json['migration_id'])
        usage=a.get('/api/v1/auth/usage',base_url=BASE).json;self.assertEqual(usage['used']['jobs'],1)
        admin=self.login('administrator');limits={**DEFAULT_LIMITS,'daily_jobs':1}
        self.assertEqual(self.post(admin,'/api/v1/admin/users/'+self.alice['id']+'/limits',limits).status_code,200)
        self.assertEqual(self.create(a,source,'another-key').status_code,429)
        self.assertEqual(self.create(a,source).status_code,202,'idempotent retry must not spend quota again')

    def test_concurrent_admission_cannot_overspend_job_quota(self):
        source=self.base.create_input({'filename':'Owned.vue','source':SOURCE},owner_id=self.alice['id'])['input_id']
        self.accounts.set_limits(self.admin['id'],self.alice['id'],{**DEFAULT_LIMITS,'daily_jobs':1})
        def create(number):
            try:return self.service.create({'input_id':source,'trusted_source':True,'confirm_model_calls':True},f'parallel-{number}',owner_id=self.alice['id'])['status']
            except ServiceError as e:return e.code
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(create,range(2)))
        self.assertEqual(sorted(results),['daily_job_limit_reached','queued'])

    def test_source_bytes_limit_and_no_credentials_in_audit(self):
        self.accounts.set_limits(self.admin['id'],self.alice['id'],{**DEFAULT_LIMITS,'storage_bytes':1})
        client=self.login();response=self.post(client,'/api/v1/inputs',{'filename':'Card.vue','source':SOURCE})
        self.assertEqual(response.status_code,429)
        self.assertNotIn(PASSWORD,str(self.accounts.audits()))

    def test_invalid_login_throttle_expiry_and_cross_site_protection(self):
        client=self.app.test_client();csrf=self.session(client)['csrf_token']
        for _ in range(5):
            self.assertEqual(client.post('/api/v1/auth/login',base_url=BASE,json={'username':'alice','password':'wrong'},headers={'X-Cardmig-CSRF':csrf}).status_code,401)
        self.assertEqual(client.post('/api/v1/auth/login',base_url=BASE,json={'username':'alice','password':PASSWORD},headers={'X-Cardmig-CSRF':csrf}).status_code,429)
        other=self.app.test_client()
        self.assertEqual(other.get('/api/v1/auth/session',base_url=BASE,headers={'X-Cardmig-Session':'bootstrap','Origin':'https://foreign.example'}).status_code,403)

    def test_call_reservation_settlement_and_replay_do_not_double_charge(self):
        source=self.base.create_input({'filename':'Owned.vue','source':SOURCE},owner_id=self.alice['id'])['input_id']
        key=self.service.create({'input_id':source,'trusted_source':True,'confirm_model_calls':True},'calltest',owner_id=self.alice['id'])['migration_id']
        messages=[{'role':'user','content':'test'}]
        self.service.invoke(key,0,messages);self.service.invoke(key,0,messages)
        usage=self.accounts.usage(self.alice['id']);self.assertEqual(usage['used']['calls'],1);self.assertEqual(usage['used']['known_tokens'],30)
        self.assertEqual(self.model.calls,1)
        self.accounts.set_limits(self.admin['id'],self.alice['id'],{**DEFAULT_LIMITS,'daily_model_calls':1})
        with self.assertRaisesRegex(ServiceError,'daily_model_call_limit_reached'):self.service.invoke(key,1,messages)
        self.assertEqual(self.model.calls,1)

    def test_unknown_call_blocks_user_across_jobs(self):
        source=self.base.create_input({'filename':'Owned.vue','source':SOURCE},owner_id=self.alice['id'])['input_id']
        first=self.service.create({'input_id':source,'trusted_source':True,'confirm_model_calls':True},'unknown-one',owner_id=self.alice['id'])['migration_id']
        self.model.fail=True
        with self.assertRaises(ServiceError):self.service.invoke(first,0,[{'role':'user','content':'x'}])
        second=self.service.create({'input_id':source,'trusted_source':True,'confirm_model_calls':True},'unknown-two',owner_id=self.alice['id'])['migration_id']
        with self.assertRaisesRegex(ServiceError,'user_model_usage_unknown_requires_review'):self.service.invoke(second,0,[{'role':'user','content':'x'}])
        self.assertEqual(self.model.calls,1)

    def test_owned_job_runs_the_existing_graph_without_cloud_calls(self):
        source=self.base.create_input({'filename':'Owned.vue','source':SOURCE},owner_id=self.alice['id'])['input_id']
        key=self.service.create({'input_id':source,'trusted_source':True,'confirm_model_calls':True},'owned-graph',owner_id=self.alice['id'])['migration_id']
        result=self.run_graph(key)
        self.assertEqual(result['status'],'finished');self.assertEqual(result['actual_cloud_model_calls'],0)
        self.assertEqual(self.accounts.usage(self.alice['id'])['used']['calls'],1)

    def test_resume_cannot_bypass_active_job_limit(self):
        client=self.login();key=self.create(client,self.upload(client)).json['migration_id']
        self.service.update(key,status='blocked')
        self.accounts.set_limits(self.admin['id'],self.alice['id'],{**DEFAULT_LIMITS,'max_active_jobs':0})
        self.assertEqual(self.post(client,f'/api/v1/migrations/{key}/resume',{}).status_code,429)

    def test_admin_cli_uses_hidden_password_prompt_and_no_default_credentials(self):
        from card_migration_system.interfaces.accounts_cli import main
        from unittest.mock import patch
        from contextlib import redirect_stdout
        import io
        output=io.StringIO()
        with patch('card_migration_system.interfaces.accounts_cli.load_settings',return_value=self.settings), \
             patch('getpass.getpass',side_effect=['Recovery-password-for-test','Recovery-password-for-test']),redirect_stdout(output):
            self.assertEqual(main(['reset-admin-password','--username','administrator']),0)
        self.assertNotIn('Recovery-password-for-test',output.getvalue())
        self.assertEqual(self.session(self.login('administrator','Recovery-password-for-test'))['user']['role'],'admin')

    def test_expired_session_and_token_header_cannot_bypass_authentication(self):
        client=self.login()
        csrf=self.session(client)['csrf_token']
        response=client.post('/api/v1/inputs',base_url=BASE,json={'filename':'Card.vue','source':SOURCE},
                             headers={'X-Cardmig-CSRF':csrf,'X-Cardmig-Token':'never-an-online-authentication-bypass'})
        self.assertEqual(response.status_code,403)
        with transaction(self.base.engine) as s:
            for row in s.scalars(select(AuthSession).where(AuthSession.user_id==self.alice['id'])):row.expires_at=time.time()-1
        self.assertFalse(self.session(client)['authenticated'])
        self.assertEqual(client.get('/api/v1/migrations',base_url=BASE).status_code,401)

    def test_public_https_origin_requires_same_origin_and_secure_cookies(self):
        settings=replace(self.settings,public_origin='https://migration.example')
        app=create_app(settings,write_token='not-an-online-authentication-bypass');self.addCleanup(app.extensions['migration_service'].close)
        client=app.test_client();url='https://migration.example'
        response=client.get('/api/v1/auth/session',base_url=url,headers={'X-Cardmig-Session':'bootstrap'})
        self.assertEqual(response.status_code,200)
        self.assertTrue(all('Secure' in value for value in response.headers.getlist('Set-Cookie')))
        logged=client.post('/api/v1/auth/login',base_url=url,json={'username':'alice','password':PASSWORD},headers={'Origin':url,'X-Cardmig-CSRF':response.json['csrf_token']})
        self.assertEqual(logged.status_code,200,logged.json)
        self.assertIn('Secure',logged.headers['Set-Cookie']);self.assertIn('HttpOnly',logged.headers['Set-Cookie'])
        self.assertIn('SameSite=Strict',logged.headers['Set-Cookie'])
        self.assertEqual(client.get('/api/v1/migrations',base_url=url).status_code,200)
        self.assertEqual(client.get('/api/v1/migrations',base_url=url,headers={'Origin':'https://other.example'}).status_code,403)
        self.assertEqual(client.get('/api/v1/migrations',base_url=BASE).status_code,403)

    def test_restoring_backup_revokes_historical_login_sessions(self):
        from card_migration_system.persistence.backup import create_backup,restore_backup
        from card_migration_system.application.service import Service
        token,_=self.accounts.login('alice',PASSWORD,'test',BASE)
        self.assertIsNotNone(self.accounts.resolve(token,BASE))
        create_backup(self.settings,backup_id='accounts-test')
        destination=replace(self.settings,runtime_dir=self.project/'var/restored-users',artifact_dir=self.project/'var/artifacts/restored-users')
        restore_backup(destination,'accounts-test')
        restored=Service(destination);self.addCleanup(restored.close)
        self.assertIsNone(AccountService(restored).resolve(token,BASE))
        with transaction(restored.engine) as s:self.assertIsNotNone(s.get(User,self.alice['id']))

if __name__=='__main__':unittest.main()
