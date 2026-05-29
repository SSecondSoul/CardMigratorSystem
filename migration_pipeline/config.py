import os
from dataclasses import dataclass


@dataclass
class MigrationPipelineSettings:
    generation_api_url: str = os.getenv(
        "MIGRATION_GENERATION_API_URL",
        "http://127.0.0.1:8787/api/evaluation/generate",
    )
    generation_timeout: int = int(os.getenv("MIGRATION_GENERATION_TIMEOUT", "300"))


settings = MigrationPipelineSettings()
