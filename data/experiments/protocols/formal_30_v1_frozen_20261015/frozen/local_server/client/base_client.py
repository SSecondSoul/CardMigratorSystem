from abc import ABC, abstractmethod
from typing import Any


class BaseLLMClient(ABC):
    @abstractmethod
    def generate(self, prompt: str, system_prompt: str = "") -> dict[str, Any]:
        """Call the remote LLM and return a normalized response payload."""
