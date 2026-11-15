"""Bounded native Ref structural dependency experiment; private property deps remain open."""
import argparse
import json
import shutil

from migration_pipeline.audit_v7_source_queue_contract import ROOT, NB, sha, seal, verify, write
from migration_pipeline.audit_ref_contract_v12 import OUT as V12, REF_RUNTIME
from migration_pipeline.audit_v7_dynamic_shape import payload, node, RUNTIME
from migration_pipeline.audit_source_path_assignment_v11 import regressions, PATH_RUNTIME
from migration_pipeline.audit_shape_input_expansion import RUNTIME as EXPANDED_RUNTIME
from migration_pipeline.audit_shape_observer_v10 import SUPPLEMENT as DESCRIPTOR_RUNTIME

BASE = ROOT / 'data/experiments/analysis/formal_30_v4_native_ref_structure_v13_input_20261114'
OUT = ROOT / 'data/experiments/analysis/formal_30_v4_native_ref_structure_v13_20261114'
ADAPTER = 'migration_pipeline/probe_native_ref_structure_adapter_v13.cjs'
STRUCTURE_RUNTIME = 'migration_pipeline/audit_native_ref_structure_v13_runtime.cjs'
FILES = ['migration_pipeline/probe_native_ref_structure_v13.cjs', ADAPTER, STRUCTURE_RUNTIME,
         'migration_pipeline/audit_native_ref_structure_v13.py', 'tests/test_native_ref_structure_v13.py']


def freeze():
    verify(V12)
    a = json.loads((V12 / 'audit.json').read_text(encoding='utf-8'))
    assert a['stats']['refs']['mismatches'] == 6 and a['stats']['expanded']['mismatches'] == 0
    protected = {**a['protected_files_sha256'], **a['code_sha256']}
    for name, expected in protected.items(): assert sha(ROOT / name) == expected, name
    BASE.mkdir(exist_ok=False)
    shutil.copy2(NB, BASE / 'notebook_before.ipynb')
    shutil.copy2(V12 / 'refs_observations.json', BASE / 'v12_ref_observations.json')
    write(BASE / 'protected_files.json', protected)
    seal(BASE); verify(BASE)
    print('Frozen six native deep Ref mismatches and 96-cell Notebook before V13.')


def candidates(data):
    return {n: node(ROOT / ADAPTER, {'code': data[n], 'vue': data['vue' if n == 'san' else 'genericVue'],
                                   'experimental': True}) for n in ['san', 'genericSan']}


def preflight():
    folder = OUT.with_name(OUT.name + '_preflight'); folder.mkdir(exist_ok=False)
    verify(BASE)
    data = payload(); adapted = candidates(data)
    assert all(a['changes'] for a in adapted.values())
    request = {**data, **{n: a['code'] for n, a in adapted.items()}}
    summary = {}
    for name, runtime in [('refs', REF_RUNTIME), ('structure', STRUCTURE_RUNTIME)]:
        observed = node(ROOT / runtime, request); write(folder / (name + '_observations.json'), observed)
        summary[name] = {'pairs': len(observed['pairs']), 'mismatches': [p for p in observed['pairs'] if not p['equal']]}
    for name in FILES:
        if not (ROOT / name).exists(): continue
        dest = folder / 'code' / name; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT / name, dest)
    seal(folder); verify(folder); print(json.dumps(summary))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze-input', action='store_true'); parser.add_argument('--preflight', action='store_true')
    args = parser.parse_args()
    if args.freeze_input == args.preflight: parser.error('Choose exactly one action')
    freeze() if args.freeze_input else preflight()
