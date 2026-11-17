"""Class map syntax and source contracts; read-only unless repair is explicit."""
import json
import subprocess
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=128)
def class_binding_semantics(code: str, vue: str = '', *, repair: bool = False) -> dict:
    fallback = {'code': code, 'findings': [], 'changes': [], 'proofs': [], 'reviews': [], 'mapped_bindings': []}
    try:
        proc = subprocess.run(['node', str(Path(__file__).with_suffix('.cjs'))],
            input=json.dumps({'code': code, 'vue': vue, 'repair': repair}),
            text=True, encoding='utf-8', capture_output=True, timeout=20, check=True)
        payload = json.loads(proc.stdout)
        if not isinstance(payload, dict):
            raise ValueError('Invalid analyzer response')
        if not payload.get('error') and (
                not isinstance(payload.get('code'), str)
                or any(not isinstance(payload.get(k), list) for k in ('findings', 'changes', 'proofs', 'reviews', 'mapped_bindings'))):
            raise ValueError('Incomplete analyzer response')
        return {**fallback, **payload}
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return {**fallback, 'error': type(exc).__name__}


def class_binding_regression(before_code: str, after_code: str, vue: str = '', after_errors=()) -> dict:
    """Independent of prompt/profile and claimed validation success."""
    before = class_binding_semantics(before_code, vue)
    after = class_binding_semantics(after_code, vue)
    reported = {(e.get('code'), e.get('location')) for e in after_errors}
    lost = sorted(set(before['mapped_bindings']) - set(after['mapped_bindings']))
    waived = [f for f in after['findings'] if (f['code'], f['location']) not in reported]
    # Compare full finding identities, not total error counts. Existing reported
    # class defects may be repaired incrementally; new/reintroduced ones cannot.
    identity = lambda f: (f['code'], f['location'])
    old = {identity(f) for f in before['findings']}
    introduced = [f for f in after['findings'] if identity(f) not in old]
    failed = bool(after.get('error'))
    stop = bool(lost or waived or introduced or failed)
    return {'should_stop': stop, 'decision': 'reject' if stop else 'pass',
            'lost_source_class_bindings': lost, 'waived_class_binding_findings': waived,
            'introduced_class_binding_findings': introduced, 'class_binding_analysis_failed': failed}
