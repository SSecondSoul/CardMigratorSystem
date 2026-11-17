"""Test-only child: exit after the durable call-start claim, before any receipt."""
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from card_migration_system.adapters.generation import OfflineGenerationClient
from card_migration_system.application.service import Service
from card_migration_system.config import load_settings
from card_migration_system.graph.generation import execute_generation


class CrashClient(OfflineGenerationClient):
    def generate(self, request):
        os._exit(29)


if __name__ == '__main__':
    service = Service(load_settings(project_root=Path(sys.argv[1]), environ={}))
    try:
        execute_generation(service, client=CrashClient(), generation_id=sys.argv[2])
    finally:
        service.close()
