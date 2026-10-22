import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from urllib import error, request

from migration_pipeline.config import settings


@dataclass
class RepairRequest:
    ssm: dict[str, Any]
    repair_prompt: str
    source_file: str = ""
    current_code: str = ""
    output_file_path: str | None = None
    repair_report: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ssm": self.ssm,
            "repair_prompt": self.repair_prompt,
            "source_file": self.source_file,
            "current_code": self.current_code,
            "repair_report": self.repair_report,
        }
        if self.output_file_path:
            payload["output_file_path"] = self.output_file_path
        if self.metadata:
            payload["metadata"] = self.metadata
        return payload


@dataclass
class RepairResult:
    source_file: str
    ssm: dict[str, Any]
    code: str
    saved_file_path: str
    provider: str
    model: str
    usage: dict[str, Any] = field(default_factory=dict)
    raw_response: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_response(cls, response: dict[str, Any]) -> "RepairResult":
        repair = response["repair"]
        return cls(
            source_file=response.get("source_file", ""),
            ssm=response["ssm"],
            code=repair["code"],
            saved_file_path=repair["saved_file_path"],
            provider=repair["provider"],
            model=repair["model"],
            usage=repair.get("usage", {}),
            raw_response=response,
        )


class BaseRepairClient(ABC):
    @abstractmethod
    def repair(self, request_data: RepairRequest) -> RepairResult:
        """Repair generated San code using a unified backend interface."""


class HTTPRepairClient(BaseRepairClient):
    def __init__(self, api_url: str, timeout: int = 300):
        self.api_url = api_url
        self.timeout = timeout

    def repair(self, request_data: RepairRequest) -> RepairResult:
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
            raise RuntimeError(f"Repair request failed: HTTP {exc.code} {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Repair request failed: {exc.reason}") from exc

        decoded = json.loads(body)
        if not decoded.get("ok"):
            raise RuntimeError(decoded.get("error", "Repair request failed"))
        return RepairResult.from_response(decoded)


def create_repair_client() -> BaseRepairClient:
    return HTTPRepairClient(
        api_url=settings.repair_api_url,
        timeout=settings.repair_timeout,
    )
