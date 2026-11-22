"""Scoped textarea binding analysis/repair; ambiguous content is never guessed."""

import json
import subprocess
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=64)
def textarea_binding(code, repair=False):
    fallback = {'code': code, 'findings': [], 'changes': []}
    try:
        result = subprocess.run(['node', str(Path(__file__).with_suffix('.cjs'))],
            input=json.dumps({'code': code, 'repair': repair}), capture_output=True,
            text=True, encoding='utf-8', timeout=15, check=True)
        data = json.loads(result.stdout)
        return {**fallback, 'error': data['error']} if 'error' in data else data
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return {**fallback, 'error': type(exc).__name__}
