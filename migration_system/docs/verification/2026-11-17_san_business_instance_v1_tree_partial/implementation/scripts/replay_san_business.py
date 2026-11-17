"""Explicit offline replay; does not change the production gate, tasks or usage ledger."""
import argparse
import base64
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import importlib.util
from copy import deepcopy

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'src'))


def run_node(payload):
    process = subprocess.run(['node', str(PROJECT / 'runtime/san_business_v1/cli.cjs')],
                             input=json.dumps(payload).encode(), capture_output=True, cwd=PROJECT, timeout=30)
    result = json.loads(process.stdout)
    if process.returncode or result['status'] != 'completed':
        raise RuntimeError(json.dumps(result, ensure_ascii=False))
    return result


def replay(source, code, output, *, evaluate=False, actions=None, props=None):
    from card_migration_system.adapters.browser import BrowserEvaluator
    from card_migration_system.config import load_settings
    from card_migration_system.runtime import profile
    from card_migration_system.stages.evaluation import assess
    actions, props = actions or [], props or {}
    result = run_node({'action': 'compile', 'source': source, 'code': code})
    validation = run_node({'action': 'verify', 'source': source, 'code': result['code'], 'manifest': result['manifest']})
    if validation['status'] != 'completed':
        raise RuntimeError('business_artifact_verification_failed')
    directory = output.resolve()
    directory.relative_to((PROJECT / 'var').resolve())
    # Output is always a new directory. Never amend a prior experiment.
    directory.mkdir(parents=True, exist_ok=False)
    # Write exact UTF-8 bytes. Windows newline translation would invalidate the
    # manifest's source/code SHA-256 even when the component still renders.
    (directory / 'source.vue').write_bytes(source.encode('utf-8'))
    (directory / 'target.san').write_bytes(result['code'].encode('utf-8'))
    (directory / 'manifest.json').write_text(json.dumps(result['manifest'], indent=2), encoding='utf-8')
    request = {'source_sha256': result['manifest']['source_sha256'],
               'original_target_sha256': sha256(code.encode('utf-8')).hexdigest(),
               'actions': actions, 'props': props, 'evaluate': evaluate,
               'thresholds': {'structure': .95, 'ui': .95, 'pixel_difference': .05}}
    (directory / 'request.json').write_bytes(json.dumps(request, ensure_ascii=False, indent=2).encode('utf-8'))
    report = {'contract_id': 'san-business-instance-v1', 'model_calls': 0, 'production_admission_eligible': False,
              'status': 'compiled_not_evaluated', 'full_contract_complete': False,
              'compiler_static_binding': 'verified', 'scope': 'explicit_offline_replay_not_main_worker_release'}
    if evaluate:
        settings = load_settings(project_root=PROJECT, environ={})
        browser = BrowserEvaluator(settings, profile(settings))
        raw = browser.evaluate(source, result['code'], props, actions)
        if raw['status'] != 'completed':
            report.update(status='runtime_blocked', details=raw)
        else:
            for side in ('vue', 'san'):
                encoded = raw[side].pop('png', None)
                if encoded:
                    (directory / f'{side}.png').write_bytes(base64.b64decode(encoded, validate=True))
            heatmap = raw['image'].pop('heatmap', None)
            if heatmap:
                (directory / 'heatmap.png').write_bytes(base64.b64decode(heatmap, validate=True))
            # This is specifically the canonical source-body/receiver check, not
            # the legacy validator pretending to understand a new export shape.
            static = {'validation_passed': True, 'validation_errors': [],
                      'policy': 'canonical_source_options_and_bundled_receiver_binding_only'}
            projection_spec = importlib.util.spec_from_file_location('san_business_identity_projection',
                PROJECT / 'runtime/san_business_v1/identity_projection.py')
            projection = importlib.util.module_from_spec(projection_spec)
            projection_spec.loader.exec_module(projection)
            comparison = deepcopy(raw)
            identity_changes = {}
            for side, source_side in [('source_ast', True), ('target_ast', False)]:
                tree, changes = projection.project_tree(raw[side]['tree'], result['manifest']['element_policies'], source=source_side)
                comparison[side]['tree'] = tree
                identity_changes[side] = changes
            assessment = assess(static, comparison, actions, {'structure': .95, 'ui': .95, 'pixel_difference': .05})
            report.update(status='passed_configured_replay_checks' if assessment['passed'] else 'replay_checks_failed',
                          assessment=assessment, static_validation_scope=static['policy'],
                          template_identity_policy={'version': 'compiler_verified_for_key_trackby_v1',
                              'changes': identity_changes, 'raw_evidence_modified': False,
                              'precondition': 'canonical artifact verified with exact source/target loop keys'})
            (directory / 'browser.json').write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding='utf-8')
    (directory / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    sums = {file.name: sha256(file.read_bytes()).hexdigest() for file in sorted(directory.iterdir()) if file.is_file()}
    (directory / 'SHA256SUMS.json').write_text(json.dumps(sums, indent=2), encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--evaluate', action='store_true')
    parser.add_argument('--trusted-source', action='store_true')
    parser.add_argument('--actions-file', type=Path)
    args = parser.parse_args()
    if args.evaluate and not args.trusted_source:
        parser.error('--evaluate executes local component code and requires --trusted-source')
    report = replay(args.source.read_bytes().decode('utf-8'), args.target.read_bytes().decode('utf-8'), args.output_dir,
                    evaluate=args.evaluate,
                    actions=json.loads(args.actions_file.read_bytes()) if args.actions_file else [])
    print(json.dumps({key: report[key] for key in ('status', 'contract_id', 'production_admission_eligible', 'model_calls')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
