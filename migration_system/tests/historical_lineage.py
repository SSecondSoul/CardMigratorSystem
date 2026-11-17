"""Old research bytes stay sealed; authorised production development can advance."""
from hashlib import sha256
import json
from pathlib import Path

PROJECT=Path(__file__).resolve().parents[1]
EVIDENCE=PROJECT/'docs/verification'
UPDATED_TESTS={f'test_public_instance_proxy_v{version}.py' for version in range(4,8)}


def assert_current_research_source(case,version,name,expected):
    if not name.endswith(('.cjs','.py')):return
    if name.endswith('.cjs'):current=PROJECT/f'research/public_instance_v{version}'/name
    elif name in UPDATED_TESTS:
        # Keep the exact old test in the pre-change archive instead of asking
        # the live suite to freeze the production Python package forever.
        current=EVIDENCE/'2026-11-17_dynamic_setter_production_v1/before/tests'/name
    else:current=PROJECT/'tests'/name
    case.assertEqual(sha256(current.read_bytes()).hexdigest(),expected,str(current))


def assert_production_lineage(case):
    file=EVIDENCE/'2026-11-17_standalone_refactor/standalone.json'
    case.assertEqual(sha256(file.read_bytes()).hexdigest(),
        'e34a7831ea5239c67561ba121eb4e3db3debceed4af40c1e7dafb666df706b56')
    baseline=json.loads(file.read_bytes())['implementation_sha256']
    case.assertEqual(len(baseline),185)
    changed={name for name,digest in baseline.items() if sha256((PROJECT/name).read_bytes()).hexdigest()!=digest}
    case.assertEqual(changed,{
        'src/card_migration_system/application/migrations.py',
        'src/card_migration_system/interfaces/api/migrations.py',
        'src/card_migration_system/stages/repair.py',
    },'Only scope/admission, API report and repair evidence projection changed; generation, graph and vendored engine exact')
