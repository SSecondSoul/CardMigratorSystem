import json
from typing import Any
from urllib import error, request

from local_server.client.base_client import BaseLLMClient


class QwenClient(BaseLLMClient):
    def __init__(self, api_key: str, base_url: str, model: str, timeout: int = 120):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.timeout = timeout

    def generate(self, prompt: str, system_prompt: str = "") -> dict[str, Any]:
        if not self.api_key:
            raise ValueError("LLM_API_KEY is not configured")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt or "You are a careful San migration reviewer."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        req = request.Request(self.base_url, data=data, headers=headers, method="POST")

        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"LLM request failed: HTTP {exc.code} {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"LLM request failed: {exc.reason}") from exc

        decoded = json.loads(body)
        choices = decoded.get("choices") or []
        message = choices[0].get("message", {}) if choices else {}
        content = message.get("content", "")
        usage = decoded.get("usage", {})

        return {
            "provider": "qwen",
            "model": decoded.get("model", self.model),
            "content": content,
            "raw": decoded,
            "usage": usage,
        }
