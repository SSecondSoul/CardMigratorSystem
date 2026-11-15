from local_server.client.qwen_client import QwenClient
from local_server.config import settings


def create_llm_client():
    provider = settings.llm_provider.strip().lower()
    if provider == "qwen":
        return QwenClient(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            timeout=settings.llm_timeout,
        )
    raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")
