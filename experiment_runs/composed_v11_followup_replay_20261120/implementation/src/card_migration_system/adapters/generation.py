"""Generation client boundary. Only explicit offline test clients in this increment.

No default client, network transport, credentials, environment lookup or retries.
The marker describes trusted injected test code; it is not a network sandbox.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class GenerationResponse:
    code: str
    provider: str
    model: str
    finish_reason: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class OfflineGenerationClient(ABC):
    @abstractmethod
    def generate(self, request: dict) -> GenerationResponse:
        """A local test double only. Do not implement network calls here."""
