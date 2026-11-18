"""Real browser/API/SQLite multi-user acceptance, no migration worker or cloud call."""
from dataclasses import replace
import json
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
from threading import Thread
import unittest
from werkzeug.serving import make_server,WSGIRequestHandler

PROJECT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(PROJECT/'src'))
from card_migration_system.config import load_settings
from card_migration_system.runtime import profile,browser_executable
from card_migration_system.persistence.database import initialize,transaction
from card_migration_system.persistence.accounts import User
from card_migration_system.application.service import Service
from card_migration_system.application.accounts import AccountService
from card_migration_system.application.migrations import MigrationService
from card_migration_system.interfaces.api.app import create_app

class Quiet(WSGIRequestHandler):
    def log(self,*args,**kwargs):pass

class MultiUserWorkbenchTests(unittest.TestCase):
    def test_multi_user_login_admin_and_isolation_in_real_browser(self):
        with tempfile.TemporaryDirectory() as directory:
            settings=replace(load_settings(project_root=PROJECT,environ={}),auth_mode='multi_user',runtime_dir=Path(directory)/'runtime',artifact_dir=Path(directory)/'artifacts')
            initialize(settings);base=Service(settings);accounts=AccountService(base);password=secrets.token_urlsafe(20)
            self.addCleanup(base.close)
            admin=accounts.create_user({'username':'administrator','password':password},bootstrap=True)
            second=accounts.create_user({'username':'seconduser','password':password},admin['id'])
            with transaction(base.engine) as s:s.get(User,second['id']).must_change_password=False
            app=create_app(settings,write_token=secrets.token_urlsafe(32));server=make_server('127.0.0.1',0,app,request_handler=Quiet)
            app.config['ALLOWED_PORT']=server.server_port;thread=Thread(target=server.serve_forever,daemon=True);thread.start()
            output=PROJECT/'var/multi-user-ui-20261118'
            try:
                value={'url':f'http://127.0.0.1:{server.server_port}/','executable':browser_executable(profile(settings)['browser']),
                       'password':password,'changed_password':secrets.token_urlsafe(20),'output':str(output),
                       'source':'<template><div>Multi-user local UI test</div></template><script>export default {}</script><style></style>'}
                process=subprocess.run(['node',str(PROJECT/'tests/browser/multi-user-smoke.mjs')],input=json.dumps(value).encode(),capture_output=True,timeout=120)
                self.assertEqual(process.returncode,0,process.stderr.decode(errors='replace')[:4500])
                result=json.loads(process.stdout);self.assertEqual(result['page_errors'],[])
                report=MigrationService(base).report(result['created_job']);self.assertEqual(report['model_calls_started'],0)
                self.assertEqual(report['status'],'queued')
                (output/'report.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
            finally:
                server.shutdown();thread.join(timeout=5);server.server_close();app.extensions['migration_service'].close();base.close()

if __name__=='__main__':unittest.main()
