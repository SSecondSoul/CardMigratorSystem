"""Test-only abrupt process exit after a committed fixture receipt, before graph checkpoint."""
from pathlib import Path
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from card_migration_system.application.service import Service
from card_migration_system.config import load_settings
from card_migration_system.workers.runner import work_once


if __name__ == "__main__":
    service = Service(load_settings(project_root=sys.argv[1], environ={}))
    original = service.generate_stub

    def receipt_then_exit(*args, **kwargs):
        original(*args, **kwargs)
        os._exit(37)  # Only this disposable worker; no paid clients or user databases.

    service.generate_stub = receipt_then_exit
    work_once(service)
    raise SystemExit("Probe did not reach its exit point")
