from langchain_openai import ChatOpenAI

from config import Settings


_llm: ChatOpenAI | None = None


def build_llm(settings: Settings) -> ChatOpenAI:
    """Process-wide singleton — avoids rebuilding the HTTP client on
    every chat request."""

    global _llm

    if _llm is None:
        _llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.resolved_llm_api_key,
            base_url=settings.llm_base_url,
            temperature=0,
            timeout=settings.llm_timeout,
            max_retries=settings.llm_max_retries,
        )

    return _llm