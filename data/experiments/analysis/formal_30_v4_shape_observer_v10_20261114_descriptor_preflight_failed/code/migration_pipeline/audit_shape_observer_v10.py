"""Frozen native replay of descriptor/opaque-value observer experiment (not production)."""
import argparse
import json
import shutil

from migration_pipeline.audit_v7_source_queue_contract import ROOT, NB, sha, seal, verify, write
from migration_pipeline.audit_shape_input_expansion import OUT as EXPANDED, RUNTIME as EXPANSION_RUNTIME
from migration_pipeline.audit_v7_dynamic_shape import payload, node, RUNTIME

BASE = ROOT / 'data/experiments/analysis/formal_30_v4_shape_observer_v10_input_20261114'
OUT = ROOT / 'data/experiments/analysis/formal_30_v4_shape_observer_v10_20261114'
ADAPTER = 'migration_pipeline/probe_shape_observer_adapter_v10.cjs'
FILES = ['migration_pipeline/probe_shape_observer_v10.cjs', ADAPTER,
         'migration_pipeline/audit_shape_observer_v10.py', 'tests/test_shape_observer_v10.py',
         'migration_pipeline/audit_shape_descriptors_v10_runtime.cjs']


def freeze():
    verify(EXPANDED)
    audit = json.loads((EXPANDED / 'audit.json').read_text(encoding='utf-8'))
    assert audit['mismatch_pair_count'] == 80 and audit['cleanup_mismatch_count'] == 1
    protected = {**audit['code_sha256'], **audit['protected_files_sha256']}
    for name, expected in protected.items(): assert sha(ROOT / name) == expected, name
    BASE.mkdir(exist_ok=False)
    shutil.copy2(NB, BASE / 'notebook_before.ipynb')
    shutil.copy2(EXPANDED / 'observations.json', BASE / 'v9_expanded_observations.json')
    write(BASE / 'protected_files.json', protected)
    seal(BASE); verify(BASE)
    print('Frozen 80 action differences, one cleanup difference and Notebook before V10 edits.')


def candidates(data):
    return {name: node(ROOT / ADAPTER, {'code': data[name], 'vue': data['vue' if name == 'san' else 'genericVue'],
                                      'experimental': True}) for name in ['san', 'genericSan']}


def preflight():
    verify(BASE)
    folder = OUT.with_name(OUT.name + '_preflight')
    folder.mkdir(exist_ok=False)
    data = payload(); adapted = candidates(data)
    assert all(a['changes'] for a in adapted.values())
    request = {**data, **{n: a['code'] for n, a in adapted.items()}}
    observations = node(ROOT / EXPANSION_RUNTIME, request)
    original = node(ROOT / RUNTIME, request)
    write(folder / 'observations.json', observations)
    write(folder / 'original_observations.json', original)
    for name in FILES:
        if not (ROOT / name).exists(): continue
        dest = folder / 'code' / name; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT / name, dest)
    seal(folder); verify(folder)
    print(json.dumps({'expanded_mismatches': sum(not p['equal'] for p in observations['pairs']),
                      'remaining_scenarios': sorted({p['scenario'] for p in observations['pairs'] if not p['equal']}),
                      'original_mismatches': sum(not p['equal'] for p in original['pairs']),
                      'cleanup_mismatches': sum(not p['equal'] for p in observations['cleanup_pairs'])}))


def descriptor_preflight():
    folder = OUT.with_name(OUT.name + '_descriptor_preflight_failed')
    folder.mkdir(exist_ok=False)
    data = payload(); adapted = candidates(data)
    request = {**data, **{n: a['code'] for n, a in adapted.items()}}
    observed = node(ROOT / 'migration_pipeline/audit_shape_descriptors_v10_runtime.cjs', request)
    write(folder / 'observations.json', observed)
    for name in FILES:
        if not (ROOT / name).exists(): continue
        dest = folder / 'code' / name; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT / name, dest)
    seal(folder); verify(folder)
    print('Frozen supplemental mismatch pairs:', sum(not p['equal'] for p in observed['pairs']))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze-input', action='store_true')
    parser.add_argument('--preflight', action='store_true')
    parser.add_argument('--descriptor-preflight', action='store_true')
    args = parser.parse_args()
    if sum([args.freeze_input, args.preflight, args.descriptor_preflight]) != 1: parser.error('Choose exactly one action')
    freeze() if args.freeze_input else descriptor_preflight() if args.descriptor_preflight else preflight()
