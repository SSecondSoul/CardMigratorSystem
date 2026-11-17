"""Disposable child-process fault probe; exits only inside explicit offline dispatch."""
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from card_migration_system.application.provider_generations import RecordedOfflineTransport
from card_migration_system.application.service import Service
from card_migration_system.config import load_settings
from card_migration_system.graph.provider_generation import execute_recorded_generation


class ExitTransport(RecordedOfflineTransport):
    def exchange(self, plan):
        os._exit(31)


if __name__ == '__main__':
    settings = load_settings(project_root=Path(sys.argv[1]), environ={})
    service = Service(settings)
    try:
        execute_recorded_generation(service, generation_id=sys.argv[2], transport=ExitTransport())
    finally:
        service.close()
