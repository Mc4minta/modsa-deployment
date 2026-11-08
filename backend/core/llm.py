from langchain_openai import ChatOpenAI

from config import Settings


_llm: ChatOpenAI | None = None


def build_llm(settings: Settings) -> ChatOpenAI:
    """Process-wide singleton — avoids rebuilding the HTTP client on
    every chat request."""

    global _llm

    if _llm is None:
        kwargs = dict(
            model=settings.llm_model,
            api_key=settings.resolved_llm_api_key,
            base_url=settings.llm_base_url,
            temperature=0,
            timeout=settings.llm_timeout,
            max_retries=settings.llm_max_retries,
        )
        if settings.llm_enable_thinking is not None:
            kwargs["extra_body"] = {
                "chat_template_kwargs": {
                    "enable_thinking": settings.llm_enable_thinking,
                },
            }
        if settings.llm_max_tokens is not None:
            kwargs["model_kwargs"] = {"max_tokens": settings.llm_max_tokens}

        _llm = ChatOpenAI(**kwargs)

    return _llm