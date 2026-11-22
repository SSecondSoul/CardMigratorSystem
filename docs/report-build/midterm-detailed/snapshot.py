from pathlib import Path
from datetime import datetime,timezone,timedelta
import json,csv,hashlib
R=Path(__file__).resolve().parents[3]
B=Path(__file__).parent
batch=R/'experiment_runs/real_system_experiment70_v3_general_repairs_20261119'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
summary=read(batch/'summary.json')
samples={}
for n in ['001_NotificationCard','003_budget_threshold']:
 p=batch/'samples'/n/'report.json';report=read(p)
 evals=[]
 for q in sorted((p.parent/'artifacts/evaluations').glob('*.json')):
  e=read(q)
  evals.append({'file':q.name,'data':e})
 samples[n]={'report':report,'evaluations':evals}
files=['migration_system/pyproject.toml','migration_system/src/card_migration_system/graph/migration.py','migration_system/src/card_migration_system/stages/evaluation.py','migration_system/src/card_migration_system/stages/structure.py','migration_system/browser/metrics.mjs','migration_system/src/card_migration_system/persistence/migrations.py','migration_system/src/card_migration_system/persistence/accounts.py','experiment_dataset/manifest.json','docs/cardComplexityDimensions.md','scripts/generate_dataset_batch_20260902.js','scripts/validate_dataset_batch_20260902.js','docs/paper/专业学位硕士研究生选题报告4.docx']
evidence={'captured_at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),'batch_summary':summary,'dataset':read(R/'experiment_dataset/manifest.json'),'samples':samples,'files_sha256':{s:hashlib.sha256((R/s).read_bytes()).hexdigest() for s in files}}
(B/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
print('Snapshot:',evidence['captured_at'])
print('Batch:',summary['completed'],summary['passed'],summary['run_status'],summary['updated_at'])
for n,v in samples.items():
 print(n,'evals:',[(x['file'],list(x['data'])[:6]) for x in v['evaluations']])
