"""Fail-closed bridge to AST-backed semantic rewrites; never executes a SFC."""

import json
import subprocess
from functools import lru_cache
from pathlib import Path


def inspect_semantics(code: str, vue: str = "", repair: bool = False, ssm: dict | None = None) -> dict:
    return _inspect(code, vue, repair, json.dumps(ssm or {}, sort_keys=True, ensure_ascii=False))


@lru_cache(maxsize=64)
def _inspect(code: str, vue: str, repair: bool, ssm_json: str) -> dict:
    fallback = {"code": code, "changes": [], "wrappers": {}}
    try:
        result = subprocess.run(
            ["node", str(Path(__file__).with_suffix('.cjs'))],
            input=json.dumps({"code": code, "vue": vue, "repair": repair, "ssm": json.loads(ssm_json)}),
            capture_output=True, text=True, encoding="utf-8", timeout=15, check=True,
        )
        data = json.loads(result.stdout)
        if "error" in data:
            return {**fallback, "error": data["error"]}
        return data
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return {**fallback, "error": type(exc).__name__}
