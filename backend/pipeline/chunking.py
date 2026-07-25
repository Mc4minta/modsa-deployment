from __future__ import annotations

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import Settings


def split_documents(settings: Settings, documents: list[Document]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n", "\n", " ", ""],
    )
    # Prepared chunks JSON already chunked — keep as-is; split PDF/text/markdown only.
    prechunked = [doc for doc in documents if doc.metadata.get("_prechunked")]
    to_split = [doc for doc in documents if not doc.metadata.get("_prechunked")]
    for doc in prechunked:
        doc.metadata.pop("_prechunked", None)
    return splitter.split_documents(to_split) + prechunked
