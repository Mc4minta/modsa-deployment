from __future__ import annotations

import logging
from threading import Lock
from uuid import uuid4

from chromadb.errors import NotFoundError

from config import Settings
from core.vectorstore import get_vector_store, create_vector_store, load_manifest, save_manifest
from pipeline.chunking import split_documents
from pipeline.loaders import discover_source_files, load_documents
from pipeline.manifest import build_manifest


logger = logging.getLogger(__name__)
_ingestion_lock = Lock()


def collection_document_count(settings: Settings) -> int:
    try:
        vector_store = get_vector_store(settings)
    except NotFoundError:
        return 0
    collection = getattr(vector_store, "_collection", None)
    if collection is None:
        return 0
    return int(collection.count())


def ingest_sources(settings: Settings, force: bool = False) -> dict[str, object]:
    # shortcut: serialize writers in this API process; use one ingestion worker in multi-worker deployments.
    with _ingestion_lock:
        return _ingest_sources(settings, force)


def _ingest_sources(settings: Settings, force: bool) -> dict[str, object]:
    files = discover_source_files(settings.source_paths)
    if not files:
        return {"status": "error", "reason": "no supported source files; existing index preserved",
                "files": 0, "chunks": 0}
    current_manifest = build_manifest(files)
    current_manifest.update(collection_base=settings.chroma_collection, index_config={
        "embedding_provider":settings.embedding_provider, "embedding_model":settings.embedding_model,
        "embedding_base_url":settings.embedding_base_url,
        "chunk_size":settings.chunk_size, "chunk_overlap":settings.chunk_overlap})
    previous_manifest = load_manifest(settings)

    if not force and previous_manifest and all(previous_manifest.get(k) == v for k,v in current_manifest.items()):
        indexed_documents = collection_document_count(settings)
        if indexed_documents == 0 or indexed_documents != previous_manifest.get("chunks"):
            logger.warning(
                "Source manifest matches but the Chroma collection is incomplete; "
                "rebuilding index.",
            )
        else:
            return {
                "status": "skipped",
                "reason": "source files unchanged",
                "files": len(files),
            }

    documents, skipped = load_documents(files)
    if skipped or not documents:
        return {
            "status": "error",
            "reason": "source loading incomplete; existing index preserved",
            "files": len(files),
            "chunks": 0,
            "skipped": skipped,
        }

    chunks = split_documents(settings, documents)
    if not chunks:
        return {"status": "error", "reason": "no chunks produced; existing index preserved",
                "files": len(files), "chunks": 0}
    name = settings.chroma_collection[:470] + "-build-" + uuid4().hex
    vector_store = create_vector_store(settings, name)
    try:
        # Keep the serving collection intact until every batch is persisted and counted.
        batch_size = 32
        for start in range(0, len(chunks), batch_size):
            vector_store.add_documents(chunks[start : start + batch_size])
            logger.info("Indexed chunks %s-%s / %s", start + 1,
                        min(start + batch_size, len(chunks)), len(chunks))
        if vector_store._collection.count() != len(chunks):
            raise ValueError("Staging index count differs from prepared chunks")
        save_manifest(settings, {**current_manifest, "active_collection":name, "chunks":len(chunks)})
    except Exception:
        try:
            vector_store.delete_collection()
        except Exception:
            logger.warning("Could not remove failed staging collection; active index is unchanged")
        raise

    return {
        "status": "indexed",
        "files": len(files),
        "documents": len(documents),
        "chunks": len(chunks),
        "skipped": skipped,
    }
