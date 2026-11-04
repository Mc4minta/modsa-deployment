from __future__ import annotations

import json
import hashlib
import logging
import math
from pathlib import Path
from typing import Iterable

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document


logger = logging.getLogger(__name__)

SUPPORTED_SUFFIXES = {".pdf", ".txt", ".md", ".json"}


def discover_source_files(paths: Iterable[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if not path.exists():
            continue
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
            files.append(path)
            continue
        if path.is_dir():
            for child in path.rglob("*"):
                if child.is_file() and child.suffix.lower() in SUPPORTED_SUFFIXES:
                    files.append(child)
    return sorted(files)


def load_json_documents(path: Path) -> list[Document]:
    """Load prepared MOD-SA chunks JSON into pre-chunked Documents.

    Expects schema from data pipeline::

        {"doc_id": ..., "metadata": {...}, "chunks": [{content, page, section, ...}]}
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    doc_meta = data.get("metadata", {})
    doc_id = data.get("doc_id", path.stem)
    # Bind the whole source version, not just the retrieved chunk, to the graph contract.
    identity = [{key: chunk.get(key) for key in ("content", "page", "section")} for chunk in data.get("chunks", [])]
    digest = hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True,
                                      separators=(",", ":")).encode()).hexdigest()
    version_id = f"{doc_id}@{digest[:16]}"
    for key, expected in (("source_id", doc_id), ("version_id", version_id), ("content_hash", digest)):
        if doc_meta.get(key) is not None and doc_meta[key] != expected:
            raise ValueError(f"Prepared source has stale {key}")

    documents: list[Document] = []
    for index, chunk in enumerate(data.get("chunks", [])):
        content = chunk.get("content") or ""
        if not isinstance(content, str):
            raise ValueError("Chunk content must be text")
        if not content.strip():
            continue
        metadata: dict[str, object] = {
            "source": doc_meta.get("source_name") or doc_id,
            "doc_id": doc_id,
            "chunk_id": chunk.get("chunk_id", ""),
            "_prechunked": True,
            "source_id": doc_id,
            "version_id": version_id,
            "content_hash": digest,
            "source_index": index,
        }
        for key in (
            "category",
            "title",
            "department",
            "source_url",
            "source_uri",
            "source_id",
            "version_id",
            "content_hash",
            "content_type",
            "language",
            "contact",
            "verified",
            "verification_status",
            "document_status",
            "published_at",
            "effective_from",
            "effective_until",
            "ingested_at",
            # Read compatibility only; do not reinterpret this as a policy date.
            "last_updated",
        ):
            value = doc_meta.get(key)
            if isinstance(value, (str, bool, int, float)) and value != "" and (not isinstance(value, float) or math.isfinite(value)):
                metadata[key] = value
        if chunk.get("section"):
            metadata["section"] = chunk["section"]
        if chunk.get("page") is not None:
            # Pipeline pages are 1-indexed; rag_service displays page + 1, so store 0-indexed.
            metadata["page"] = int(chunk["page"]) - 1
        documents.append(Document(page_content=content, metadata=metadata))
    return documents


def load_documents(
    files: list[Path],
) -> tuple[list[Document], list[dict[str, object]]]:
    documents: list[Document] = []
    skipped: list[dict[str, object]] = []
    for path in files:
        suffix = path.suffix.lower()
        if suffix == ".json":
            try:
                documents.extend(load_json_documents(path))
            except (json.JSONDecodeError, OSError, ValueError) as exc:
                logger.warning("Skipping %s: %s", path, exc)
                skipped.append({"source": str(path), "reason": str(exc)})
            continue
        try:
            if suffix == ".pdf":
                loaded = PyPDFLoader(str(path)).load()
            else:
                loaded = TextLoader(str(path), encoding="utf-8").load()
        except ImportError as exc:
            logger.warning(
                "Skipping %s because a loader dependency is missing: %s",
                path,
                exc,
            )
            skipped.append({"source": str(path), "reason": str(exc)})
            continue
        for document in loaded:
            document.metadata["source"] = str(path)
            documents.append(document)
    return documents, skipped
