"""Read-only UI QA with five frozen jobs restored ONLY to a temporary database."""
import argparse
from contextlib import closing
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Thread
from werkzeug.serving import make_server,WSGIRequestHandler

PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT/'src'))
from card_migration_system.config import load_settings
from card_migration_system.persistence.database import initialize
from card_migration_system.interfaces.api.app import create_app
from card_migration_system.runtime import profile,browser_executable


class Quiet(WSGIRequestHandler):
    def log(self,*args,**kwargs):pass


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();output=args.output.resolve()
    if output.exists() or not output.is_relative_to(PROJECT/'var'):raise ValueError('Choose a NEW output below project/var')
    frozen=PROJECT/'docs/verification/2026-11-18_closed_loop_v2';manifest=json.loads((frozen/'FREEZE.json').read_bytes())
    with TemporaryDirectory(prefix='cardmig-ui-qa-') as temporary:
        root=Path(temporary);settings=replace(load_settings(project_root=PROJECT,environ={}),runtime_dir=root/'runtime',artifact_dir=root/'artifacts')
        initialize(settings)
        with closing(sqlite3.connect(settings.business_database)) as db:
            def insert(table,row):
                columns={r[1] for r in db.execute('PRAGMA table_info('+table+')')}
                if not set(row)<=columns:raise ValueError('Unexpected frozen schema')
                names=list(row);db.execute('INSERT INTO '+table+' ('+','.join('"'+n+'"' for n in names)+') VALUES ('+','.join('?' for _ in names)+')',[row[n] for n in names])
            for key in manifest['job_ids']:
                folder=frozen/'jobs'/key;data=json.loads((folder/'database.json').read_bytes())
                insert('source_inputs',data['source']);insert('migration_jobs',data['job'])
                destination=settings.artifact_dir/data['source']['relative_path'];destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(folder/'source.vue',destination)
                for file in data['registered_files']:
                    insert('migration_files',file)
                    relative=Path(file['relative_path']).relative_to(Path('migrations')/key)
                    destination=settings.artifact_dir/file['relative_path'];destination.parent.mkdir(parents=True,exist_ok=True)
                    if sha256((folder/relative).read_bytes()).hexdigest()!=file['sha256']:raise ValueError('Frozen hash mismatch')
                    shutil.copyfile(folder/relative,destination)
                for call in data['calls']:insert('migration_model_calls',call)
            db.commit()
        app=create_app(settings,write_token='disposable-ui-test-token-no-paid-calls')
        server=make_server('127.0.0.1',0,app,request_handler=Quiet);app.config['ALLOWED_PORT']=server.server_port
        thread=Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            result=subprocess.run(['node',str(PROJECT/'tests/browser/workbench-layout.mjs')],input=json.dumps({
                'url':f'http://127.0.0.1:{server.server_port}','executable':browser_executable(profile(settings)['browser']),
                'ids':manifest['job_ids'],'output':str(output)}).encode(),capture_output=True,timeout=120)
            if result.returncode:raise RuntimeError(result.stderr.decode('utf-8',errors='replace')[-4000:])
            report=json.loads(result.stdout);report.update(database_scope='temporary_copy_of_frozen_jobs_only',actual_user_database_updated=False)
            (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps(report))
        finally:server.shutdown();thread.join(timeout=5);server.server_close();app.extensions['migration_service'].close()


if __name__=='__main__':main()
