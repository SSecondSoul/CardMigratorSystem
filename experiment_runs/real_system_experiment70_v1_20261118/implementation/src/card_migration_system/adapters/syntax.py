"""Offline syntax diagnostics and narrowly proven edits; no browser/model execution."""
import json
import subprocess
from .ssm import _environment
from ..application.service import ServiceError


def target_syntax(settings, source, code, *, normalize=False):
    request={'repository':str(settings.repository_root),'source':source,'code':code,
             'action':'normalize' if normalize else 'inspect'}
    try:
        proc=subprocess.run(['node',str(settings.project_root/'browser/syntax-cli.mjs')],
            input=json.dumps(request).encode(),capture_output=True,timeout=30,
            cwd=settings.project_root,env=_environment())
        if proc.returncode or len(proc.stdout)>4*1024*1024:raise ServiceError('syntax_checker_failed')
        return json.loads(proc.stdout)
    except (OSError,ValueError,subprocess.TimeoutExpired):raise ServiceError('syntax_checker_unavailable') from None
