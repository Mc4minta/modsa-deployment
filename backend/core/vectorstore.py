import json
import os
from pathlib import Path
import tempfile

from langchain_chroma import Chroma

from config import Settings
from core.embeddings import build_embeddings


_vector_store: Chroma | None = None
_vector_store_key: tuple | None = None
MANIFEST_FILE = "source_manifest.json"


def load_manifest(settings: Settings) -> dict | None:
    path = settings.chroma_dir / MANIFEST_FILE
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def save_manifest(settings: Settings, manifest: dict) -> None:
    """The manifest is also the active-index pointer; publish both atomically."""
    settings.chroma_dir.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=settings.chroma_dir, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(manifest, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, settings.chroma_dir / MANIFEST_FILE)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def create_vector_store(settings: Settings, collection_name: str, *, create: bool = True) -> Chroma:
    return Chroma(
        collection_name=collection_name,
        persist_directory=str(settings.chroma_dir),
        embedding_function=build_embeddings(settings),
        create_collection_if_not_exists=create,
    )


def get_vector_store(settings: Settings) -> Chroma:
    """Process-wide singleton — avoids rebuilding the Chroma + embeddings
    HTTP client on every request (costly once embeddings go over the
    network, e.g. Hugging Face Inference API)."""

    global _vector_store, _vector_store_key
    manifest = load_manifest(settings) or {}
    active = manifest.get("active_collection") if manifest.get("collection_base") == settings.chroma_collection else None
    name = active or settings.chroma_collection
    key = (str(settings.chroma_dir.resolve()), name, settings.embedding_provider,
           settings.embedding_model, settings.embedding_base_url)
    if _vector_store is None or _vector_store_key != key:
        _vector_store = create_vector_store(settings, name, create=not bool(active))
        _vector_store_key = key

    return _vector_store


def reset_vector_store_cache() -> None:
    """Drop the process-local wrapper without deleting a collection."""
    global _vector_store, _vector_store_key
    _vector_store, _vector_store_key = None, None
