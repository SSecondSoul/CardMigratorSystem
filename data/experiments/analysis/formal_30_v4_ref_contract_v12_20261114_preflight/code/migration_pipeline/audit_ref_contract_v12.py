"""Isolated Ref contract experiment; original production admission remains blocked."""
import argparse
import json
import shutil

from migration_pipeline.audit_v7_source_queue_contract import ROOT, NB, sha, seal, verify, write
from migration_pipeline.audit_source_path_assignment_v11 import OUT as V11, regressions
from migration_pipeline.audit_v7_dynamic_shape import payload, node, RUNTIME
from migration_pipeline.audit_shape_input_expansion import RUNTIME as EXPANDED_RUNTIME
from migration_pipeline.audit_shape_observer_v10 import SUPPLEMENT as DESCRIPTOR_RUNTIME
from migration_pipeline.audit_source_path_assignment_v11 import PATH_RUNTIME

BASE = ROOT / 'data/experiments/analysis/formal_30_v4_ref_contract_v12_input_20261114'
OUT = ROOT / 'data/experiments/analysis/formal_30_v4_ref_contract_v12_20261114'
ADAPTER = 'migration_pipeline/probe_ref_contract_adapter_v12.cjs'
REF_RUNTIME = 'migration_pipeline/audit_ref_contract_v12_runtime.cjs'
FILES = ['migration_pipeline/probe_ref_contract_v12.cjs', ADAPTER, REF_RUNTIME,
         'migration_pipeline/audit_ref_contract_v12.py', 'tests/test_ref_contract_v12.py']


def freeze():
    verify(V11)
    a = json.loads((V11 / 'audit.json').read_text(encoding='utf-8'))
    assert a['stats']['expanded']['mismatches'] == 4 and a['cleanup_mismatch_count'] == 1
    protected = {**a['protected_files_sha256'], **a['code_sha256']}
    for name, expected in protected.items(): assert sha(ROOT / name) == expected, name
    BASE.mkdir(exist_ok=False)
    shutil.copy2(NB, BASE / 'notebook_before.ipynb')
    shutil.copy2(V11 / 'expanded_observations.json', BASE / 'v11_expanded_observations.json')
    write(BASE / 'protected_files.json', protected)
    seal(BASE); verify(BASE)
    print('Frozen V11 remaining marker counterexamples and 94-cell Notebook before Ref changes.')


def candidates(data):
    return {name: node(ROOT / ADAPTER, {'code': data[name], 'vue': data['vue' if name == 'san' else 'genericVue'],
                                      'experimental': True}) for name in ['san', 'genericSan']}


def preflight():
    verify(BASE)
    folder = OUT.with_name(OUT.name + '_preflight'); folder.mkdir(exist_ok=False)
    data = payload(); adapted = candidates(data)
    assert all(a['changes'] for a in adapted.values())
    request = {**data, **{n: a['code'] for n, a in adapted.items()}}
    counts = {}
    for name, runtime in [('expanded', EXPANDED_RUNTIME), ('refs', REF_RUNTIME)]:
        observed = node(ROOT / runtime, request); write(folder / (name + '_observations.json'), observed)
        counts[name] = {'pairs': len(observed['pairs']), 'mismatches': [p for p in observed['pairs'] if not p['equal']]}
    for name in FILES:
        if not (ROOT / name).exists(): continue
        dest = folder / 'code' / name; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT / name, dest)
    seal(folder); verify(folder); print(json.dumps(counts))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze-input', action='store_true')
    parser.add_argument('--preflight', action='store_true')
    args = parser.parse_args()
    if args.freeze_input == args.preflight: parser.error('Choose exactly one action')
    freeze() if args.freeze_input else preflight()
