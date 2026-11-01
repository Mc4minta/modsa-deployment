"""Opt-in pilot orchestration; the production /chat/ask route stays vector-only."""
from __future__ import annotations

from hashlib import sha256
from typing import Any

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage

from config import Settings
from core.llm import build_llm
from prompts.rag_prompt import SYSTEM_PROMPT, escape_retrieved_context
from services.query_service import PilotScopeFilter, METHOD, parse_query_intent
from services.rag_service import (
    format_context,
    no_verified_info_response,
    source_summary,
)


def _identity(document: Document) -> tuple[object, ...]:
    metadata = document.metadata
    version, chunk = metadata.get("version_id"), metadata.get("chunk_id")
    if isinstance(version, str) and version and isinstance(chunk, str) and chunk:
        return ("versioned", version, chunk)
    return (
        "legacy",
        metadata.get("source"),
        metadata.get("page"),
        sha256(document.page_content.encode("utf-8")).hexdigest(),
    )


def _unique(documents: list[Document]) -> list[Document]:
    seen: set[tuple[object, ...]] = set()
    result = []
    for document in documents:
        key = _identity(document)
        if key not in seen:
            seen.add(key)
            result.append(document)
    return result


def retrieve_documents(
    vector_store: Any,
    graph: Any | None,
    question: str,
    *,
    k: int = 4,
    graph_limit: int = 4,
    scope_filter: PilotScopeFilter | None = None,
) -> dict[str, Any]:
    """Keep vector order, then append bounded graph evidence without reranking."""
    if type(k) is not int or k < 1 or type(graph_limit) is not int or not 0 <= graph_limit <= 20:
        raise ValueError("k must be positive and graph_limit must be an integer between 0 and 20")
    vector_documents = _unique(vector_store.similarity_search(question, k=k))
    trace: dict[str, Any] = {
        "status": "vector_only",
        "vector_chunk_ids": [d.metadata.get("chunk_id") for d in vector_documents],
        "added_chunk_ids": [],
        "paths": [],
    }
    intent = None
    if scope_filter is not None:
        intent = parse_query_intent(question)
        accepted, decisions = scope_filter.apply(vector_documents, intent)
        trace.update(raw_vector_chunk_ids=trace["vector_chunk_ids"], intent=intent.model_dump(),
                     filter_method=METHOD, filter_decisions=[{"stage": "vector", **row} for row in decisions])
        vector_documents = accepted
        trace["vector_chunk_ids"] = [doc.metadata.get("chunk_id") for doc in accepted]
        if not accepted:
            trace["status"] = "filtered_empty"
    documents = list(vector_documents)
    if vector_documents and graph is not None and graph_limit:
        try:
            candidates, paths = graph.expand(vector_documents, limit=20 if scope_filter is not None else graph_limit)
            if scope_filter is not None:
                candidates, decisions = scope_filter.apply(candidates, intent)
                trace["filter_decisions"].extend({"stage": "graph", **row} for row in decisions)
            merged = _unique(vector_documents + candidates)
            additions = merged[len(vector_documents):][:graph_limit]
            documents.extend(additions)
            if scope_filter is not None:
                keys = {(doc.metadata.get("version_id"), doc.metadata.get("chunk_id")) for doc in additions}
                paths = [path for path in paths if path.get("kind") == "bridge_rejected"
                         or (path.get("version_id"), path.get("chunk_id")) in keys]
            trace.update(
                status="expanded" if additions else "no_expansion",
                added_chunk_ids=[d.metadata.get("chunk_id") for d in additions],
                paths=paths,
            )
        except (ValueError, RuntimeError) as error:
            trace.update(status="graph_unavailable", error_type=type(error).__name__)
    return {
        "documents": documents,
        "vector_documents": vector_documents,
        "trace": trace,
    }


def answer_question(
    settings: Settings,
    question: str,
    retrieval: dict[str, Any],
) -> dict[str, Any]:
    """Answer an already-retrieved pilot context; this does not run retrieval again."""
    documents = retrieval["documents"]
    if not documents:
        return {"answer": no_verified_info_response(question), "sources": []}
    prompt = SYSTEM_PROMPT.format(
        context=escape_retrieved_context(format_context(documents)),
    )
    prompt += (
        "\nExperimental pilot: document policy status is unverified/unknown. "
        "Do not present these documents as current policy. Keep academic year, "
        "round and track scopes separate; current applicability cannot be verified."
        "\nNumeric interpretation: EQ means a stated count/equality; LTE means an upper bound "
        "(Thai 'ไม่เกิน'). EQ and LTE are not interchangeable even when their numbers match. "
        "These operator names describe the source wording; they need not appear literally in the source. "
        "When asked to compare conditions, explain the requested distinction rather than only listing numbers."
        "\nFor procedure questions, cover the required actions and follow-up obligations explicitly present "
        "in the relevant passage, not just the first prerequisite. Do not invent extra steps."
        "\nPreserve logical connectors and complete exception wording. Do not turn AND into OR or split "
        "an ambiguous exception into independently qualifying groups. If ambiguous, quote it verbatim "
        "and say its logical interpretation needs confirmation; do not decide eligibility. "
        "Support year/round claims with the source heading when available, not the filename alone."
    )
    response = build_llm(settings).invoke([
        SystemMessage(content=prompt),
        HumanMessage(content=question),
    ])
    sources = []
    for index, document in enumerate(documents, 1):
        source = {**source_summary([document])[0], "citation_index": index}
        for key in ("source_id", "version_id", "chunk_id"):
            if document.metadata.get(key):
                source[key] = document.metadata[key]
        sources.append(source)
    return {"answer": response.content, "sources": sources}
