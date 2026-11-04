from langchain_openai import ChatOpenAI
from threading import Lock

from config import Settings


_llm: ChatOpenAI | None = None
_llm_key: tuple | None = None
_llm_lock = Lock()


def build_llm(settings: Settings) -> ChatOpenAI:
    """Process-wide singleton — avoids rebuilding the HTTP client on
    every chat request."""

    global _llm, _llm_key
    key = (settings.llm_model, settings.llm_base_url, settings.resolved_llm_api_key,
           settings.llm_timeout, settings.llm_max_retries)
    with _llm_lock:
        if _llm is None or _llm_key != key:
            client = ChatOpenAI(
                model=settings.llm_model,
                api_key=settings.resolved_llm_api_key,
                base_url=settings.llm_base_url,
                temperature=0,
                timeout=settings.llm_timeout,
                max_retries=settings.llm_max_retries,
            )
            _llm, _llm_key = client, key
        return _llm
