from langchain_core.embeddings import Embeddings
from langchain_ollama import OllamaEmbeddings
from langchain_openai import OpenAIEmbeddings

from config import Settings


def build_embeddings(settings: Settings) -> Embeddings:

    if settings.embedding_uses_ollama:
        return OllamaEmbeddings(
            model=settings.embedding_model,
            base_url=settings.resolved_embedding_base_url,
        )

    return OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.resolved_embedding_api_key,
        base_url=settings.embedding_base_url,
    )