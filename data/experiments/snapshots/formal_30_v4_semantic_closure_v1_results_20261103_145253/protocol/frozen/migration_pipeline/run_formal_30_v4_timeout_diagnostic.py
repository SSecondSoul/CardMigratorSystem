"""Launch the isolated two-sample timeout diagnostic with explicit child env."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BATCH_ID = "formal_30_v4_timeout_diagnostic_v1"
CONFIG = ROOT / f"migration_pipeline/batch_configs/{BATCH_ID}.json"
PROTOCOL = ROOT / f"data/experiments/protocols/{BATCH_ID}_frozen_20261102"
EXPECTED_ENV = {
    "LLM_PROVIDER": "qwen",
    "LLM_MODEL": "qwen-plus",
    "LLM_BASE_URL": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    "LLM_TIMEOUT": "600",
    "LOCAL_SERVER_HOST": "127.0.0.1",
    "LOCAL_SERVER_PORT": "8787",
    "LOCAL_SERVER_DEBUG": "0",
    "MIGRATION_GENERATION_TIMEOUT": "660",
    "MIGRATION_REPAIR_TIMEOUT": "660",
    "MIGRATION_GENERATION_API_URL": "http://127.0.0.1:8787/api/evaluation/generate",
    "MIGRATION_REPAIR_API_URL": "http://127.0.0.1:8787/api/evaluation/repair",
}


def child_environment(parent: dict[str, str]) -> dict[str, str]:
    return {**parent, **EXPECTED_ENV}


def batch_command(*, dry_run: bool = False) -> list[str]:
    command = [sys.executable, "migration_pipeline/run_batch_pipeline.py", "--config-file", CONFIG.relative_to(ROOT).as_posix(), "--include-state"]
    return command + (["--dry-run"] if dry_run else [])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--server", action="store_true", help="Start the local server in this terminal (key inherited from env).")
    modes.add_argument("--dry-run", action="store_true", help="Print plan without contacting the server/model.")
    modes.add_argument("--execute", action="store_true", help="Run the separate two-sample model batch after server restart.")
    args = parser.parse_args()
    env = child_environment(dict(os.environ))
    if args.server or args.execute:
        subprocess.run([sys.executable, str(PROTOCOL / "verify_protocol.py"), "--live"], cwd=ROOT, check=True)
    if args.server and not env.get("LLM_API_KEY"):
        parser.error("Set LLM_API_KEY in this terminal before --server; never store it in the repository")
    print("diagnostic_settings:", json.dumps(EXPECTED_ENV, ensure_ascii=False), flush=True)
    print("server_timeout_requires_restart: true", flush=True)
    command = [sys.executable, "-m", "local_server.app"] if args.server else batch_command(dry_run=args.dry_run)
    return subprocess.run(command, cwd=ROOT, env=env).returncode


if __name__ == "__main__":
    raise SystemExit(main())
