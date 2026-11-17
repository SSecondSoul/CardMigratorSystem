"""Reproducible offline evidence for the partial San business runtime, not admission."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'src'))
from card_migration_system.runtime import browser_executable


def fingerprint(file):
    return sha256(file.read_bytes()).hexdigest()


def write_json(file, value):
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(json.dumps(value, ensure_ascii=False, indent=2).encode('utf-8'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--actions-file', type=Path, required=True)
    parser.add_argument('--trusted-source', action='store_true')
    args = parser.parse_args()
    if not args.trusted_source:
        parser.error('Local browser execution requires --trusted-source')
    directory = args.output_dir.resolve()
    directory.relative_to((PROJECT / 'var').resolve())
    directory.mkdir(parents=True, exist_ok=False)
    started = datetime.now(timezone.utc).isoformat()
    runtime = PROJECT / 'runtime/san_business_v1'
    sources = [file for file in runtime.iterdir() if file.suffix in ('.cjs', '.py', '.md')]
    sources += [PROJECT / name for name in (
        'scripts/replay_san_business.py', 'scripts/verify_san_business.py',
        'tests/test_san_business_runtime.py', 'tests/test_san_business_contract_policy.py',
        'docs/SAN_BUSINESS_INSTANCE_CONTRACT_V1.json', 'docs/SAN_BUSINESS_INSTANCE_CONTRACT_V1.md')]
    sources.append(args.actions_file.resolve())
    source_hashes = {str(file.relative_to(PROJECT)).replace('\\', '/'): fingerprint(file) for file in sources}
    # Copy exact bytes before execution. A later workspace edit invalidates this
    # run, rather than quietly binding the reports to a different implementation.
    for file in sources:
        destination = directory / 'implementation' / file.relative_to(PROJECT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(file, destination)
    for name, file in [('source.vue', args.source), ('original-target.san', args.target), ('actions.json', args.actions_file)]:
        shutil.copyfile(file, directory / name)
    input_hashes = {name: fingerprint(directory / name) for name in ('source.vue', 'original-target.san', 'actions.json')}
    results = []
    for pattern in ('test_san_business*.py', 'test_public_instance_proxy*.py', 'test_modular_public_key_contract.py'):
        print('tests:', pattern, flush=True)
        begin = time.monotonic()
        process = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', str(PROJECT / 'tests'), '-p', pattern, '-v'],
                                 cwd=PROJECT, capture_output=True, timeout=600)
        filename = 'tests-' + pattern.replace('*', 'all').replace('.py', '.txt')
        (directory / filename).write_bytes(process.stdout + process.stderr)
        results.append({'pattern': pattern, 'exit_code': process.returncode,
                        'seconds': round(time.monotonic() - begin, 3), 'log': filename})
        if process.returncode:
            raise RuntimeError('Regression failed; evidence retained in ' + str(directory / filename))
    executable = browser_executable({})
    if not executable:
        raise RuntimeError('Real local browser required')
    for name in ('legacy_business_cases', 'browser_probe', 'public_api_probe', 'value_probe', 'controls'):
        print('probe:', name, flush=True)
        process = subprocess.run(['node', str(runtime / (name + '.cjs'))], cwd=PROJECT,
                                 input=json.dumps({'executable': executable}).encode(), capture_output=True, timeout=120)
        if process.returncode:
            (directory / (name + '-error.txt')).write_bytes(process.stderr)
            raise RuntimeError('Probe failed: ' + name)
        report = json.loads(process.stdout)
        write_json(directory / (name + '.json'), report)
        if report.get('errors') or (name == 'browser_probe' and not report['equal']) or any(not row['equal'] for row in report.get('cases', [])):
            raise RuntimeError('Observed difference: ' + name)
        for relative, expected in report.get('fingerprints', {}).items():
            if fingerprint(PROJECT / relative) != expected:
                raise RuntimeError('Probe fingerprint mismatch: ' + relative)
    print('replay: explicit frozen source / configured actions', flush=True)
    from replay_san_business import replay
    replay_result = replay((directory / 'source.vue').read_bytes().decode('utf-8'),
                           (directory / 'original-target.san').read_bytes().decode('utf-8'), directory / 'replay',
                           evaluate=True, actions=json.loads((directory / 'actions.json').read_bytes()))
    if replay_result['status'] != 'passed_configured_replay_checks':
        raise RuntimeError('Frozen replay failed; retained in ' + str(directory / 'replay'))
    for name, expected in source_hashes.items():
        if fingerprint(PROJECT / name) != expected:
            raise RuntimeError('Implementation drift during verification: ' + name)
    summary = {'contract_id': 'san-business-instance-v1', 'status': 'partial_implementation_checks_passed',
               'started_at': started, 'finished_at': datetime.now(timezone.utc).isoformat(),
               'tests': results, 'implementation_sha256': source_hashes, 'input_sha256': input_hashes,
               'replay_status': replay_result['status'], 'replay_actions': len(json.loads((directory / 'actions.json').read_bytes())),
               'full_contract_complete': False, 'production_admission_eligible': False,
               'default_worker_changed': False, 'actual_model_calls': 0,
               'old_results_reclassified': False,
               'remaining': ['main generation/validation/repair integration', 'automatic source component trees',
                             'parent event argument routing and ancestor error capture', 'slots/attrs/ref coverage',
                             'side-effectful coercion/accessor order and recursive watcher scheduling']}
    write_json(directory / 'summary.json', summary)
    write_json(directory / 'SHA256SUMS.json', {str(file.relative_to(directory)).replace('\\', '/'): fingerprint(file)
               for file in sorted(directory.rglob('*')) if file.is_file() and file != directory / 'SHA256SUMS.json'})
    print(json.dumps({'status': summary['status'], 'output': str(directory), 'model_calls': 0,
                      'full_contract_complete': False, 'production_admission_eligible': False}))


if __name__ == '__main__':
    main()
