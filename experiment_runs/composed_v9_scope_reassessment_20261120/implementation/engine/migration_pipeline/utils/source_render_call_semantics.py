"""Source-scoped inline render-call lifting with explicit reactive operands."""
import json
import subprocess
from functools import lru_cache
from pathlib import Path


def source_render_call_semantics(code, vue='', ssm=None, *, repair=False):
    return _run(code, vue, json.dumps(ssm or {}, sort_keys=True, ensure_ascii=False), repair)


@lru_cache(maxsize=96)
def _run(code, vue, ssm_json, repair):
    fallback = {'code': code, 'findings': [], 'changes': [], 'proofs': [],
                'reviews': [], 'mapped_bindings': []}
    if not vue:
        return fallback
    try:
        metadata = json.loads(ssm_json)
        options = (metadata.get('script') or {}).get('options') or {}
        if not options.get('components'):
            return fallback
        proc = subprocess.run(['node', str(Path(__file__).with_suffix('.cjs'))],
            input=json.dumps({'code': code, 'vue': vue, 'ssm': metadata, 'repair': repair}),
            text=True, encoding='utf-8', capture_output=True, check=True, timeout=15)
        result = json.loads(proc.stdout)
        return {**fallback, **result} if 'error' not in result else {**fallback, 'error': result['error']}
    except (OSError, subprocess.SubprocessError, ValueError, AttributeError, TypeError) as exc:
        return {**fallback, 'error': type(exc).__name__}
