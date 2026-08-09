from langchain_chroma import Chroma

from config import Settings
from core.embeddings import build_embeddings


_vector_store: Chroma | None = None


def get_vector_store(settings: Settings) -> Chroma:
    """Process-wide singleton — avoids rebuilding the Chroma + embeddings
    HTTP client on every request (costly once embeddings go over the
    network, e.g. Hugging Face Inference API)."""

    global _vector_store

    if _vector_store is None:
        _vector_store = Chroma(
            collection_name=settings.chroma_collection,
            persist_directory=str(settings.chroma_dir),
            embedding_function=build_embeddings(settings),
        )

    return _vector_store


def reset_vector_store_cache() -> None:
    """Drop the cached Chroma instance. Must be called after the
    underlying collection is deleted/recreated out-of-band (see
    services.ingestion_service.reset_collection), otherwise the cached
    client keeps pointing at a collection that no longer exists."""

    global _vector_store
    _vector_store = None