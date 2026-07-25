from langchain_openai import ChatOpenAI

from config import Settings



def build_llm(settings: Settings):

    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.resolved_llm_api_key,
        base_url=settings.llm_base_url,
        temperature=0,
    )