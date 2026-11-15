"""Operator-only MonitoringDashboard fresh regression; verify before paid calls."""

import argparse
import json
import os
import subprocess
import sys

from migration_pipeline.run_formal_30_v4_timeout_diagnostic import ROOT, EXPECTED_ENV


BATCH_ID = 'formal_30_v4_semantic_closure_v4'
CONFIG = ROOT / f'migration_pipeline/batch_configs/{BATCH_ID}.json'
PROTOCOL = ROOT / f'data/experiments/protocols/{BATCH_ID}_frozen_20261103'


def batch_command(*, dry_run=False):
    command = [sys.executable, 'migration_pipeline/run_batch_pipeline.py', '--config-file',
               CONFIG.relative_to(ROOT).as_posix(), '--include-state']
    return command + (['--dry-run'] if dry_run else [])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--server', action='store_true')
    mode.add_argument('--dry-run', action='store_true')
    mode.add_argument('--execute', action='store_true')
    args = parser.parse_args(argv)
    env = {**os.environ, **EXPECTED_ENV}
    if args.server or args.execute:
        subprocess.run([sys.executable, str(PROTOCOL / 'verify_protocol.py'), '--live'], cwd=ROOT, check=True)
    if args.server and not env.get('LLM_API_KEY', '').strip():
        parser.error('Set LLM_API_KEY in this terminal; never put it in the repository')
    print('runtime_settings:', json.dumps(EXPECTED_ENV), flush=True)
    command = [sys.executable, '-m', 'local_server.app'] if args.server else batch_command(dry_run=args.dry_run)
    return subprocess.run(command, cwd=ROOT, env=env).returncode


if __name__ == '__main__':
    raise SystemExit(main())
