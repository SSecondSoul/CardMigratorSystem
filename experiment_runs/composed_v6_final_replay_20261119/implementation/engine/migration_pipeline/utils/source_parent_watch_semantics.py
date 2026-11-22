"""Source-proven parent async/deep root watcher scheduling and disposal."""
import json
import subprocess
from functools import lru_cache
from pathlib import Path


def source_parent_watch_semantics(code, vue='', *, repair=False):
    return _run(code, vue, repair)


@lru_cache(maxsize=96)
def _run(code, vue, repair):
    fallback = {'code':code,'findings':[],'changes':[],'proofs':[],'reviews':[],'mapped_contracts':[],
                'blocked_boundaries':[]}
    if not vue:
        return fallback
    try:
        proc = subprocess.run(['node',str(Path(__file__).with_suffix('.cjs'))],
            input=json.dumps({'code':code,'vue':vue,'repair':repair}),text=True,encoding='utf-8',
            capture_output=True,check=True,timeout=15)
        data = json.loads(proc.stdout)
        return {**fallback,**data} if 'error' not in data else {**fallback,'error':data['error']}
    except (OSError,subprocess.SubprocessError,ValueError,TypeError) as exc:
        return {**fallback,'error':type(exc).__name__}
