"""Source-matched outer-template repairs; AST inspection never executes a SFC."""
import json
import subprocess
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=128)
def source_template_semantics(code: str, vue: str = '', *, repair: bool = False) -> dict:
    fallback = {'code': code, 'changes': [], 'findings': [], 'proofs': []}
    try:
        proc = subprocess.run(['node', str(Path(__file__).with_suffix('.cjs'))],
            input=json.dumps({'code': code, 'vue': vue, 'repair': repair}),
            text=True, encoding='utf-8', capture_output=True, timeout=15, check=True)
        data = json.loads(proc.stdout)
        return {**fallback, **data}
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return {**fallback, 'error': type(exc).__name__}
