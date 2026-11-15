"""Freeze/replay an explicit raw Vue assignment to no-option San path mapping."""
import argparse
import json
import shutil

from migration_pipeline.audit_v7_source_queue_contract import ROOT, NB, sha, seal, verify, write
from migration_pipeline.audit_shape_observer_v10 import OUT as V10
from migration_pipeline.audit_v7_dynamic_shape import payload, node, RUNTIME
from migration_pipeline.audit_shape_input_expansion import RUNTIME as EXPANDED_RUNTIME
from migration_pipeline.audit_shape_observer_v10 import SUPPLEMENT as DESCRIPTOR_RUNTIME

BASE = ROOT / 'data/experiments/analysis/formal_30_v4_source_path_assignment_v11_input_20261114'
OUT = ROOT / 'data/experiments/analysis/formal_30_v4_source_path_assignment_v11_20261114'
ADAPTER = 'migration_pipeline/probe_source_path_assignment_adapter_v11.cjs'
PATH_RUNTIME = 'migration_pipeline/audit_source_path_assignment_v11_runtime.cjs'
FILES = ['migration_pipeline/probe_source_path_assignment_v11.cjs', ADAPTER, PATH_RUNTIME,
         'migration_pipeline/audit_source_path_assignment_v11.py', 'tests/test_source_path_assignment_v11.py']


def freeze():
    verify(V10)
    prior = json.loads((V10 / 'audit.json').read_text(encoding='utf-8'))
    assert prior['remaining_expanded_mismatches'] == 8 and prior['cleanup_mismatch_count'] == 1
    protected = {**prior['protected_files_sha256'], **prior['code_sha256']}
    for name in ['tests/manual/v7-acceptance.html', 'tests/manual/v7-acceptance.js',
                 'migration_pipeline/utils/source_parent_watch_semantics.cjs']:
        protected[name] = sha(ROOT / name)
    for name, expected in protected.items(): assert sha(ROOT / name) == expected, name
    BASE.mkdir(exist_ok=False)
    shutil.copy2(NB, BASE / 'notebook_before.ipynb')
    shutil.copy2(V10 / 'expanded_observations.json', BASE / 'v10_expanded_observations.json')
    write(BASE / 'protected_files.json', protected)
    seal(BASE); verify(BASE)
    print('Frozen V10 negatives, 92-cell Notebook, production and manual-page fingerprints.')


def candidates(data):
    return {name: node(ROOT / ADAPTER, {'code': data[name], 'vue': data['vue' if name == 'san' else 'genericVue'],
                                      'experimental': True}) for name in ['san', 'genericSan']}


def preflight():
    verify(BASE)
    folder = OUT.with_name(OUT.name + '_preflight'); folder.mkdir(exist_ok=False)
    data = payload(); adapted = candidates(data)
    assert all(a['changes'] for a in adapted.values())
    request = {**data, **{n: a['code'] for n, a in adapted.items()}}
    result = {}
    for name, runtime in [('expanded', EXPANDED_RUNTIME), ('paths', PATH_RUNTIME)]:
        observations = node(ROOT / runtime, request)
        write(folder / (name + '_observations.json'), observations)
        result[name] = {'pairs': len(observations['pairs']),
                        'mismatches': [(p['subject'], p['scenario'], p['phase']) for p in observations['pairs'] if not p['equal']]}
    for name in FILES:
        if not (ROOT / name).exists(): continue
        dest = folder / 'code' / name; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT / name, dest)
    seal(folder); verify(folder); print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze-input', action='store_true')
    parser.add_argument('--preflight', action='store_true')
    args = parser.parse_args()
    if args.freeze_input == args.preflight: parser.error('Choose exactly one action')
    freeze() if args.freeze_input else preflight()
