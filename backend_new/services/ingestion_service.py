from __future__ import annotations

import logging

import chromadb
from chromadb.errors import NotFoundError

from config import Settings
from core.vectorstore import get_vector_store
from pipeline.chunking import split_documents
from pipeline.loaders import discover_source_files, load_documents
from pipeline.manifest import build_manifest, load_manifest, save_manifest


logger = logging.getLogger(__name__)


def collection_document_count(settings: Settings) -> int:
    vector_store = get_vector_store(settings)
    collection = getattr(vector_store, "_collection", None)
    if collection is None:
        return 0
    return int(collection.count())


def reset_collection(settings: Settings) -> None:
    settings.chroma_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(settings.chroma_dir))
    try:
        client.delete_collection(settings.chroma_collection)
    except (ValueError, NotFoundError):
        pass


def ingest_sources(settings: Settings, force: bool = False) -> dict[str, object]:
    files = discover_source_files(settings.source_paths)
    current_manifest = build_manifest(files)
    previous_manifest = load_manifest(settings)

    if not force and previous_manifest == current_manifest:
        indexed_documents = collection_document_count(settings)
        if files and indexed_documents == 0:
            logger.warning(
                "Source manifest matches but the Chroma collection is empty; "
                "rebuilding index.",
            )
        else:
            return {
                "status": "skipped",
                "reason": "source files unchanged",
                "files": len(files),
            }

    reset_collection(settings)

    if not files:
        save_manifest(settings, current_manifest)
        return {
            "status": "empty",
            "reason": "no supported source files found",
            "files": 0,
            "chunks": 0,
        }

    documents, skipped = load_documents(files)
    if not documents:
        save_manifest(settings, current_manifest)
        return {
            "status": "empty",
            "reason": "no documents could be loaded",
            "files": len(files),
            "chunks": 0,
            "skipped": skipped,
        }

    chunks = split_documents(settings, documents)
    vector_store = get_vector_store(settings)
    vector_store.add_documents(chunks)
    save_manifest(settings, current_manifest)

    return {
        "status": "indexed",
        "files": len(files),
        "documents": len(documents),
        "chunks": len(chunks),
        "skipped": skipped,
    }
