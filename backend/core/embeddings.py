from langchain_core.embeddings import Embeddings
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from langchain_ollama import OllamaEmbeddings
from langchain_openai import OpenAIEmbeddings

from config import Settings


def build_embeddings(settings: Settings) -> Embeddings:

    if settings.embedding_provider == "ollama":
        return OllamaEmbeddings(
            model=settings.embedding_model,
            base_url=settings.resolved_embedding_base_url,
        )

    if settings.embedding_provider == "huggingface":
        return HuggingFaceEndpointEmbeddings(
            model=settings.embedding_model,
            huggingfacehub_api_token=settings.resolved_embedding_api_key,
        )

    return OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.resolved_embedding_api_key,
        base_url=settings.embedding_base_url,
        timeout=settings.embedding_timeout,
        max_retries=settings.embedding_max_retries,
    )