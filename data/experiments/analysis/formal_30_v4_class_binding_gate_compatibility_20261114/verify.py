"""Supplement the already-frozen 207-test closure without rewriting its history."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[4]
FOLDER=Path(__file__).resolve().parent
BASE=ROOT/'data/experiments/analysis/formal_30_v4_class_binding_closure_v1_20261113'
FILES=['migration_pipeline/utils/repair_scheduler.py','tests/test_class_binding_closure_v1.py']
hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in FILES}
modules=['tests.test_class_binding_closure_v1','tests.test_bounded_repair_scheduler','tests.test_semantic_regression_gate']
result=subprocess.run(['python','-m','unittest',*modules,'-v'],cwd=ROOT,text=True,encoding='utf-8',capture_output=True)
log=result.stdout+result.stderr
with (FOLDER/'unittest.log').open('x',encoding='utf-8') as stream: stream.write(log)
count=re.search(r'Ran (\d+) tests? in ([\d.]+)s',log)
assert hashes=={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in FILES}
for name in FILES:
    target=FOLDER/'code'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
data={'classification':'class_gate_compatibility_supplement','prior_closure':BASE.relative_to(ROOT).as_posix(),
      'prior_tests_passed':207,'modules':modules,'tests':int(count[1]) if count else None,'returncode':result.returncode,
      'change':'Preserve unrelated event review classification; class-specific regressions still reject and both review/reject block automatic pass.',
      'code_sha256':hashes,'model_requests':0,'manual_status':'pending','original_scores_modified':False}
with (FOLDER/'audit.json').open('x',encoding='utf-8') as stream: json.dump(data,stream,ensure_ascii=False,indent=2)
with (FOLDER/'SHA256SUMS.txt').open('x',encoding='utf-8') as stream:
    for path in sorted(p for p in FOLDER.rglob('*') if p.is_file() and p.name!='SHA256SUMS.txt'):
        stream.write(hashlib.sha256(path.read_bytes()).hexdigest()+'  '+path.relative_to(FOLDER).as_posix()+'\n')
print(json.dumps(data,ensure_ascii=False))
if result.returncode: raise RuntimeError('Compatibility tests failed; logs retained')
