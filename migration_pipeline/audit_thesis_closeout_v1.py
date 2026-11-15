"""Read-only thesis gap / frozen dynamic-interface inventory; no model calls."""
import ast
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'data/experiments/analysis/thesis_closeout_audit_v1_20261115'
PRIOR = ROOT / 'data/experiments/analysis/formal_30_v4_dynamic_setter_guard_v1_20261115'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_seal(folder):
    entries = {}
    for line in (folder / 'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        digest, relative = line.split('  ', 1)
        if sha(folder / relative) != digest:
            raise RuntimeError('Frozen evidence differs: ' + relative)
        entries[relative] = digest
    if set(entries) != {p.relative_to(folder).as_posix() for p in folder.rglob('*')
                        if p.is_file() and p.name != 'SHA256SUMS.txt'}:
        raise RuntimeError('Frozen evidence inventory differs')
    return entries


def inspect_bodies(vue, san, names):
    result = subprocess.run(['node', str(ROOT / 'migration_pipeline/audit_dynamic_assignment_inventory_v1.cjs')],
                            input=json.dumps({'vue':vue, 'san':san, 'names':names}),
                            text=True, encoding='utf-8', capture_output=True, check=True, timeout=30)
    return json.loads(result.stdout)


def imports_in(path):
    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    result = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.append(node.module)
    return sorted(set(result))


def audit():
    baseline = read(BASE / 'baseline.json')
    verify_seal(PRIOR)
    verify_seal(PRIOR.parent / 'formal_30_v4_dynamic_setter_guard_v1_input_20261115')
    for path, digest in baseline['protected_implementation'].items():
        if sha(ROOT/path) != digest:
            raise RuntimeError('Implementation drift: '+path)
    for path, digest in baseline['manual'].items():
        if sha(ROOT/path) != digest:
            raise RuntimeError('Manual page drift: '+path)
    for path, item in baseline['evidence_files'].items():
        # The progress document is append-only and intentionally updated later.
        if path != 'docs/ir-design/source-migration-scope-20261114.md' and sha(ROOT/path) != item['sha256']:
            raise RuntimeError('Evidence drift: '+path)
    native = read(PRIOR/'native_observations.json')
    cases = ['dotted-literal','late-instance','symbol-literal']
    if not all(not native['variants']['path'][case]['mappedProjectionEqual'] for case in cases):
        raise RuntimeError('Expected sealed method-level counterexamples missing')
    rows = []
    for item in read(PRIOR/'inventory.json'):
        for k in ['input','source']:
            if sha(ROOT/item[k+'_path']) != item[k+'_sha256']:
                raise RuntimeError('Frozen component drift: '+item['id'])
        names = [c['name'] for c in item['dynamic_contracts']]
        body = inspect_bodies((ROOT/item['source_path']).read_text(encoding='utf-8'),
                              (ROOT/item['input_path']).read_text(encoding='utf-8'), names) if names else {'rows':[]}
        for method in body['rows']:
            matched = method['source']['shape']=='dynamic_instance_assignment' and method['target']['shape']=='dynamic_san_data_path_write'
            method['calibration'] = ('recognized_body_matches_existing_counterexample_class' if matched else
                                     'source_interface_missing' if method['target']['shape']=='missing' else 'unassessed')
            method['counterexample_reference'] = {'path':str((PRIOR/'native_observations.json').relative_to(ROOT)).replace('\\','/'),
                                                  'variant':'path','cases':cases} if matched else None
        rows.append({**item,'method_body_audit':body,'new_component_native_execution':False,
                     'whole_component_equivalence_proven':False,'diagnostic_waived':False})
    counts = {'configured':len(rows),'source_dynamic_contracts':sum(bool(x['dynamic_contracts']) for x in rows),
              'new_unproven_diagnostics':sum(bool(x['new_findings']) for x in rows),
              'historically_passed_with_new_diagnostic':sum(bool(x['new_findings']) and x['original_batch_passed'] for x in rows),
              'recognized_path_write_bodies':sum(m['calibration']=='recognized_body_matches_existing_counterexample_class'
                                                 for x in rows for m in x['method_body_audit']['rows']),
              'missing_interfaces':sum(m['calibration']=='source_interface_missing'
                                       for x in rows for m in x['method_body_audit']['rows'])}
    visual_imports = imports_in(ROOT/'migration_pipeline/stages/visual_eval.py')
    imports = []
    for folder in ['migration_pipeline','local_server','SSM']:
        for path in sorted((ROOT/folder).rglob('*.py')):
            if '真正 Vue' in path.parts or '__pycache__' in path.parts:
                continue
            try:
                modules = imports_in(path)
            except (SyntaxError,UnicodeError):
                imports.append({'path':path.relative_to(ROOT).as_posix(),'status':'parse_failed','imports':[]})
                continue
            found=[m for m in modules if m.split('.')[0] in {'langgraph','langsmith','peft'}]
            if found:
                imports.append({'path':path.relative_to(ROOT).as_posix(),'status':'matched','imports':found})
    aggregate=read(ROOT/'data/experiments/analysis/formal_30_v4_full_regression_v2_20261104_214821/summary.json')['aggregate']
    return {'classification':'read_only_thesis_gap_and_method_shape_calibration_not_repair',
            'counts':counts,'methods':rows,
            'implementation_facts':{'visual_eval_imports':visual_imports,
                'screenshot_helper_bytes':(ROOT/'migration_pipeline/utils/screenshot.py').stat().st_size,
                'image_diff_helper_bytes':(ROOT/'migration_pipeline/utils/image_diff.py').stat().st_size,
                'scoped_langgraph_langsmith_peft_import_scan':imports,
                'scan_boundary':'AST imports in three Python trees only; no proof of absence in other paths, dynamic imports or external work',
                'pixel_pipeline_complete':False,'requirements_status_requires_manual_evidence_review':True},
            'original_batch':{k:aggregate[k] for k in ['configured','passed','failed','execution_errors','total_tokens']},
            'scope_decision':'retain_arbitrary_public_keys_and_continue_blocking',
            'shared_notification_boundary_resolved':False,'source_exception_phase_boundary_resolved':False,
            'production_rules_changed':False,'prompt_changed':False,'canonical_written':False,
            'new_model_calls':0,'new_browser_or_manual_acceptance':False,
            'new_full30_run':False,'historical_scores_rewritten':False,
            'native_evidence_reused_not_rerun':True,'compatibility_layer_added':False}


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    print(json.dumps(audit(),ensure_ascii=False))
