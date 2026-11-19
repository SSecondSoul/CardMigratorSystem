"""Source-registered syntax recovery; failed proof never changes code."""

import json
import subprocess
from functools import lru_cache
from pathlib import Path


def recover_inline_identifiers(code, ssm=None):
    return _recover(code, json.dumps(ssm or {}, sort_keys=True, ensure_ascii=False))


@lru_cache(maxsize=64)
def _recover(code, ssm_json):
    fallback = {'code': code, 'changes': [], 'mappings': [], 'parse_status': 'unknown'}
    try:
        p = subprocess.run(['node', str(Path(__file__).with_suffix('.cjs'))],
            input=json.dumps({'code': code, 'ssm': json.loads(ssm_json)}), capture_output=True,
            text=True, encoding='utf-8', timeout=15, check=True)
        data = json.loads(p.stdout)
        return {**fallback, **data} if 'error' not in data else {**fallback, 'error': data['error']}
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return {**fallback, 'error': type(exc).__name__}
