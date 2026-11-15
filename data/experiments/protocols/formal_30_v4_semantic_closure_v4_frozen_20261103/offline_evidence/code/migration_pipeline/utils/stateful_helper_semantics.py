"""Bounded readonly helper dependency conversion; parsing/proof failures do not edit."""

import json
import subprocess
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=64)
def explicit_helper_dependencies(code):
    fallback = {'code': code, 'changes': [], 'proofs': []}
    try:
        p = subprocess.run(['node', str(Path(__file__).with_suffix('.cjs'))],
            input=json.dumps({'code': code}), capture_output=True, text=True,
            encoding='utf-8', check=True, timeout=15)
        data = json.loads(p.stdout)
        return data if 'error' not in data else {**fallback, 'error': data['error']}
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return {**fallback, 'error': type(exc).__name__}
