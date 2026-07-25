from langchain_chroma import Chroma

from config import Settings
from core.embeddings import build_embeddings


def get_vector_store(settings: Settings):

    return Chroma(
        collection_name=settings.chroma_collection,
        persist_directory=str(settings.chroma_dir),
        embedding_function=build_embeddings(settings)
    )