"""Fail-closed, read-only V7 structural inspection; no production admission."""
import json
from pathlib import Path
import subprocess


def inspect_v7_source_queue(code, vue):
    fallback = {'queue_lifecycle_structure_matched': False, 'source_equivalence_proven': False,
                'production_eligible': False, 'changes': [], 'reviews': []}
    try:
        proc = subprocess.run(['node', str(Path(__file__).with_suffix('.cjs'))],
                              input=json.dumps({'code': code, 'vue': vue}), capture_output=True,
                              text=True, encoding='utf-8', check=True, timeout=20)
        result = json.loads(proc.stdout)
        if not isinstance(result, dict) or 'error' in result:
            return {**fallback, 'reviews': ['analysis_failed'], 'error': result.get('error') if isinstance(result, dict) else 'invalid_result'}
        return {**fallback, **result}
    except (OSError, subprocess.SubprocessError, ValueError, TypeError) as exc:
        return {**fallback, 'reviews': ['analysis_failed'], 'error': type(exc).__name__}
