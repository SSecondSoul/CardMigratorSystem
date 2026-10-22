import os
from dataclasses import dataclass


@dataclass
class Settings:
    host: str = os.getenv("LOCAL_SERVER_HOST", "127.0.0.1")
    port: int = int(os.getenv("LOCAL_SERVER_PORT", "8787"))
    debug: bool = os.getenv("LOCAL_SERVER_DEBUG", "0") == "1"
    llm_provider: str = os.getenv("LLM_PROVIDER", "qwen")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_base_url: str = os.getenv(
        "LLM_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    )
    llm_model: str = os.getenv("LLM_MODEL", "qwen-plus")
    llm_timeout: int = int(os.getenv("LLM_TIMEOUT", "120"))


settings = Settings()
