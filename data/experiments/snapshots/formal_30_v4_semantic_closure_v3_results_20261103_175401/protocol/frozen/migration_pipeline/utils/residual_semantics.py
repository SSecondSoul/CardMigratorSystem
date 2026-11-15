"""Opt-in AST rewrites for residual-v2; parse failure never counts as repair."""

import json
import subprocess
from functools import lru_cache
from pathlib import Path


def residual_semantics(code, ssm=None, *, repair=False):
    return _run(code, json.dumps(ssm or {}, sort_keys=True, ensure_ascii=False), repair)


@lru_cache(maxsize=64)
def _run(code, ssm_json, repair):
    fallback = {'code': code, 'changes': [], 'source_prop_contracts': []}
    try:
        result = subprocess.run(['node', str(Path(__file__).with_suffix('.cjs'))],
            input=json.dumps({'code': code, 'ssm': json.loads(ssm_json), 'repair': repair}),
            capture_output=True, text=True, encoding='utf-8', timeout=15, check=True)
        data = json.loads(result.stdout)
        return {**fallback, 'error': data['error']} if 'error' in data else data
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return {**fallback, 'error': type(exc).__name__}
