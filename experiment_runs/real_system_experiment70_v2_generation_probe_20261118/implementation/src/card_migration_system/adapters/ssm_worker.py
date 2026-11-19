"""Short-lived stdlib-only host for the trusted legacy SSM assembler.

Invoked by the adapter, not an API/worker or a runner of uploaded Vue scripts.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    request = json.loads(sys.stdin.buffer.read(1048577))
    repository = Path(sys.argv[1]).resolve()
    for relative, expected in request['files'].items():
        target = (repository / relative).resolve()
        if not target.is_relative_to(repository) or sha256(target.read_bytes()).hexdigest() != expected:
            raise ValueError('ssm_implementation_drift')
    content = request['source'].encode('utf-8')
    if sha256(content).hexdigest() != request['source_sha256']:
        raise ValueError('ssm_source_hash_mismatch')
    bridge = Path(__file__).with_name('ssm_bridge.cjs')
    try:
        result = subprocess.run([sys.argv[2], str(bridge), str(repository), request['filename']],
                                input=content, capture_output=True, timeout=20, check=False,
                                cwd=repository, env=os.environ.copy())
    except subprocess.TimeoutExpired:
        raise ValueError('ssm_node_timeout') from None
    if result.returncode or len(result.stdout) > 8 * 1024 * 1024:
        raise ValueError('ssm_ast_bridge_failed')
    payload = json.loads(result.stdout)
    if payload.get('status') != 'completed':
        print(json.dumps(payload))
        return
    parsed = payload['parsed']
    # A separate process avoids sys.path/module-cache pollution in the API.
    # Empty pycache prefix prevents stale repository bytecode from being reused.
    with tempfile.TemporaryDirectory(prefix='cardmig-ssm-pycache-') as cache:
        sys.pycache_prefix = cache
        sys.dont_write_bytecode = True
        sys.path.insert(0, str(repository))
        from SSM.extractors.factory import SSMFactory
        factory = SSMFactory(use_node_bridge=False, schema_module='v3')
        # Supply the actual AST result, bypassing the old parser's regex fallback.
        factory.vue_parser.parse = lambda source, file_path='': parsed
        ssm = factory.build(request['source'], file_path=request['filename'], source_file=request['filename'])
    payload.pop('parsed')
    payload['ssm'] = ssm
    payload['runtime']['python'] = sys.version.split()[0]
    print(json.dumps(payload, ensure_ascii=True, sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        code = str(error)
        if not (code.startswith('ssm_') and code.replace('_', '').isalnum() and len(code) < 100):
            code = 'ssm_assembly_failed'
        print(json.dumps({'status': 'blocked', 'error': code}))
