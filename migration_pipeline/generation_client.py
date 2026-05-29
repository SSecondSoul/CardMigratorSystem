import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from urllib import error, request

from migration_pipeline.config import settings


@dataclass
class GenerationRequest:
    ssm: dict[str, Any]
    source_file: str = ""
    instruction: str = ""
    output_file_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ssm": self.ssm,
            "source_file": self.source_file,
            "instruction": self.instruction,
        }
        if self.output_file_path:
            payload["output_file_path"] = self.output_file_path
        if self.metadata:
            payload["metadata"] = self.metadata
        return payload


@dataclass
class GenerationResult:
    source_file: str
    ssm: dict[str, Any]
    code: str
    saved_file_path: str
    provider: str
    model: str
    usage: dict[str, Any] = field(default_factory=dict)
    raw_response: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_response(cls, response: dict[str, Any]) -> "GenerationResult":
        generation = response["generation"]
        return cls(
            source_file=response.get("source_file", ""),
            ssm=response["ssm"],
            code=generation["code"],
            saved_file_path=generation["saved_file_path"],
            provider=generation["provider"],
            model=generation["model"],
            usage=generation.get("usage", {}),
            raw_response=response,
        )

    def to_state_update(self) -> dict[str, Any]:
        return {
            "source_file": self.source_file,
            "ssm": self.ssm,
            "generated_code": self.code,
            "generated_file_path": self.saved_file_path,
            "generation_provider": self.provider,
            "generation_model": self.model,
            "generation_usage": self.usage,
            "generation_raw_response": self.raw_response,
        }


class BaseGenerationClient(ABC):
    @abstractmethod
    def generate(self, request_data: GenerationRequest) -> GenerationResult:
        """Generate San code from SSM using a unified backend interface."""


class HTTPGenerationClient(BaseGenerationClient):
    def __init__(self, api_url: str, timeout: int = 300):
        self.api_url = api_url
        self.timeout = timeout

    def generate(self, request_data: GenerationRequest) -> GenerationResult:
        data = json.dumps(request_data.to_payload()).encode("utf-8")
        req = request.Request(
            self.api_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Generation request failed: HTTP {exc.code} {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Generation request failed: {exc.reason}") from exc

        decoded = json.loads(body)
        if not decoded.get("ok"):
            raise RuntimeError(decoded.get("error", "Generation request failed"))
        return GenerationResult.from_response(decoded)


def create_generation_client() -> BaseGenerationClient:
    return HTTPGenerationClient(
        api_url=settings.generation_api_url,
        timeout=settings.generation_timeout,
    )
