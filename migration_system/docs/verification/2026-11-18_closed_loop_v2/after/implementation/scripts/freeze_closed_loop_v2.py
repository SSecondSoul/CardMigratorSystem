"""Freeze latest completed migration jobs read-only, before generic bug fixes."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sqlite3

PROJECT=Path(__file__).resolve().parents[1]
EVIDENCE=PROJECT/'docs/verification/2026-11-18_closed_loop_v2'


def main():
    if EVIDENCE.exists():raise ValueError('Evidence already exists; never overwrite')
    root=PROJECT/'var/artifacts'
    db=sqlite3.connect((PROJECT/'var/runtime/business.sqlite3').as_uri()+'?mode=ro',uri=True)
    db.row_factory=sqlite3.Row
    db.execute('PRAGMA query_only=ON');db.execute('BEGIN')
    jobs=[dict(r) for r in db.execute('SELECT * FROM migration_jobs ORDER BY created_at DESC,id DESC LIMIT 5')]
    if len(jobs)!=5 or any(j['status'] not in ('failed','completed','blocked') for j in jobs):
        raise ValueError('Expected five terminal jobs')
    EVIDENCE.mkdir(parents=True)
    checked=0
    for job in jobs:
        key=job['id'];folder=EVIDENCE/'jobs'/key;folder.mkdir(parents=True)
        registered=[dict(r) for r in db.execute('SELECT * FROM migration_files WHERE job_id=?',(key,))]
        for item in registered:
            source=(root/item['relative_path']).resolve()
            if not source.is_relative_to(root.resolve()) or sha256(source.read_bytes()).hexdigest()!=item['sha256']:
                raise ValueError('Registered file identity mismatch: '+item['relative_path'])
            relative=source.relative_to(root/'migrations'/key)
            target=folder/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
            checked+=1
        source=dict(db.execute('SELECT * FROM source_inputs WHERE id=?',(job['input_id'],)).fetchone())
        path=(root/source['relative_path']).resolve()
        if not path.is_relative_to(root.resolve()) or sha256(path.read_bytes()).hexdigest()!=source['sha256']:
            raise ValueError('Source identity mismatch')
        shutil.copyfile(path,folder/'source.vue')
        (folder/'database.json').write_text(json.dumps({'job':job,'source':source,'registered_files':registered,
            'calls':[dict(r) for r in db.execute('SELECT * FROM migration_model_calls WHERE job_id=? ORDER BY ordinal',(key,))]},
            ensure_ascii=False,indent=2),encoding='utf-8')
    db.rollback();db.close()
    for directory in ('src','engine'):
        for file in (PROJECT/directory).rglob('*'):
            if file.is_file() and file.suffix in ('.py','.cjs','.json') and '__pycache__' not in file.parts:
                target=EVIDENCE/'before'/file.relative_to(PROJECT)
                target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,target)
    payload={p.relative_to(EVIDENCE).as_posix():sha256(p.read_bytes()).hexdigest()
             for p in sorted(EVIDENCE.rglob('*')) if p.is_file()}
    manifest={'scope':'five_failed_jobs_before_generic_closed_loop_bugfixes','database_read_only':True,
        'actual_new_model_calls':0,'job_ids':[j['id'] for j in jobs],'verified_registered_files':checked,'files':payload}
    (EVIDENCE/'FREEZE.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'jobs':len(jobs),'verified_registered_files':checked,'payload_files':len(payload),
        'evidence':str(EVIDENCE),'actual_new_model_calls':0},ensure_ascii=False))


if __name__=='__main__':main()
