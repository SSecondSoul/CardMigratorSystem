"""Version-bound stage reuse, not a second orchestrator or hidden model client."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from .ssm import _environment
from ..application.service import ServiceError


def legacy_binding(repository):
    root = Path(repository)
    return {str(p.relative_to(root)).replace('\\', '/'): sha256(p.read_bytes()).hexdigest()
            for directory in ('migration_pipeline', 'SSM') for p in sorted((root / directory).rglob('*'))
            if p.is_file() and p.suffix in ('.py', '.cjs', '.js')}


def legacy_stage(repository, action, *, source, code, ssm, errors=None, visual_errors=None):
    request = dict(action=action, source=source, code=code, ssm=ssm,
                   errors=errors or [], visual_errors=visual_errors or [])
    try:
        proc = subprocess.run([sys.executable, '-s', str(Path(__file__).with_name('legacy_worker.py')), str(repository)],
            input=json.dumps(request).encode(), capture_output=True, timeout=90,
            cwd=repository, env=_environment())
        if proc.returncode or len(proc.stdout) > 12 * 1024 * 1024:
            raise ServiceError('legacy_stage_failed')
        value = json.loads(proc.stdout)
        if value.get('status') != 'completed': raise ServiceError('legacy_stage_failed')
        return value['result']
    except (OSError, ValueError, subprocess.TimeoutExpired):
        raise ServiceError('legacy_stage_unavailable') from None
