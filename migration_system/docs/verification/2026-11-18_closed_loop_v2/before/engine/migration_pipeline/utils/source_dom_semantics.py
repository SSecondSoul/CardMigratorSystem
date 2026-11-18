"""Source-scoped native event and loop normalization; never execute SFC code."""
import json
import subprocess
from functools import lru_cache
from pathlib import Path


def source_dom_semantics(code, vue='', ssm=None, *, repair=False):
    return _run(code, vue, json.dumps(ssm or {}, sort_keys=True, ensure_ascii=False), repair)


@lru_cache(maxsize=96)
def _run(code, vue, ssm_json, repair):
    fallback = {'code': code, 'findings': [], 'changes': [], 'proofs': [], 'reviews': [], 'mapped_scopes': [], 'mapped_nodes': []}
    try:
        p = subprocess.run(['node', str(Path(__file__).with_suffix('.cjs'))],
            input=json.dumps({'code': code, 'vue': vue, 'ssm': json.loads(ssm_json), 'repair': repair}),
            text=True, encoding='utf-8', capture_output=True, check=True, timeout=15)
        data = json.loads(p.stdout)
        return {**fallback, **data} if 'error' not in data else {**fallback, 'error': data['error']}
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return {**fallback, 'error': type(exc).__name__}
