"""Real built Vue frontend → Flask → disposable SQLite. Model never starts."""
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Thread
import unittest
from werkzeug.serving import make_server,WSGIRequestHandler

PROJECT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(PROJECT/'src'))
from card_migration_system.config import load_settings
from card_migration_system.runtime import profile,browser_executable
from card_migration_system.persistence.database import initialize
from card_migration_system.interfaces.api.app import create_app

class Quiet(WSGIRequestHandler):
    def log(self,*args,**kwargs):pass

class WorkbenchSmoke(unittest.TestCase):
    def test_real_frontend_submits_persistent_job_without_paid_call(self):
        with tempfile.TemporaryDirectory() as directory:
            settings=replace(load_settings(project_root=PROJECT,environ={}),runtime_dir=Path(directory)/'runtime',artifact_dir=Path(directory)/'artifacts')
            initialize(settings);token='local-test-token-at-least-24-characters'
            app=create_app(settings,write_token=token)
            server=make_server('127.0.0.1',0,app,request_handler=Quiet)
            app.config['ALLOWED_PORT']=server.server_port
            thread=Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                value={'url':f'http://127.0.0.1:{server.server_port}/','executable':browser_executable(profile(settings)['browser']),
                    'token':token,'source':'<template><div>Local UI test</div></template><script>export default {}</script><style></style>'}
                process=subprocess.run(['node',str(PROJECT/'browser/workbench-smoke.mjs')],input=json.dumps(value).encode(),capture_output=True,timeout=90)
                self.assertEqual(process.returncode,0,process.stderr.decode()[:1000])
                result=json.loads(process.stdout);self.assertEqual(result['page_errors'],[])
                from card_migration_system.application.migrations import MigrationService
                report=MigrationService(app.extensions['migration_service'])
                rows=report.list()['items'];self.assertEqual(len(rows),1)
                self.assertEqual(report.report(rows[0]['migration_id'])['model_calls_started'],0)
            finally:
                server.shutdown();thread.join(timeout=5);server.server_close();app.extensions['migration_service'].close()

if __name__=='__main__':unittest.main()
