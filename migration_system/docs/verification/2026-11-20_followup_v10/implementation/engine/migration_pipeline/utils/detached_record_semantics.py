"""Fail-closed proof for local record copies, not an automatic code rewrite."""
import json
import subprocess
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=256)
def proven_record_copies(body: str, script: str) -> frozenset[str]:
    try:
        proc = subprocess.run(['node', str(Path(__file__).with_suffix('.cjs'))],
            input=json.dumps({'body': body, 'script': script}), text=True, encoding='utf-8',
            capture_output=True, check=True, timeout=15)
        return frozenset(json.loads(proc.stdout).get('aliases', []))
    except (OSError, subprocess.SubprocessError, ValueError):
        return frozenset()
