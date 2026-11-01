# MOD-SA Backend Architecture

## Overview

MOD-SA is a FastAPI RAG chatbot backend for KMUTT Student Affairs knowledge retrieval.

Active implementation: **`backend/`**.
Prepared knowledge: **`data/chunks/`**. Graph tooling: **`graph/`**. There are no legacy backend folders to recreate.

Stack: FastAPI, LangChain, ChromaDB, OpenAI-compatible LLM/embeddings (including Ollama).

---

# Directory Structure

```
backend/
├── main.py                      # App entry, CORS, lifespan ingest
├── config.py                    # pydantic-settings from .env
├── requirements.txt
├── Dockerfile
├── .dockerignore
├── .env.example
│
├── api/
│   ├── chat.py                  # POST /chat/ask
│   ├── health.py                # GET /health
│   └── admin.py                 # POST /admin/reindex
│
├── core/
│   ├── llm.py                   # ChatOpenAI client
│   ├── embeddings.py            # OpenAI or Ollama embeddings
│   └── vectorstore.py           # Chroma wrapper
│
├── services/
│   ├── rag_service.py           # Retrieve → prompt → LLM → sources
│   └── ingestion_service.py     # Discover → load → chunk → embed → Chroma
│
├── pipeline/
│   ├── loaders.py               # File discovery + document loaders
│   ├── chunking.py              # Split non-prechunked docs
│   └── manifest.py              # Source fingerprint skip-if-unchanged
│
├── prompts/
│   └── rag_prompt.py            # SYSTEM_PROMPT
│
└── schemas/
    └── chat.py                  # AskRequest / AskResponse
```

Not used (do not recreate unless needed): `utils/`, `database/`, `models/`, `retrieval_service.py`.

Repo-level Docker: root `docker-compose.yml` builds `backend`, mounts `data/chunks` read-only, persists Chroma volume.

---

# Component Responsibilities

## main.py

* Create FastAPI app
* CORS from `CORS_ORIGINS`
* Lifespan: run `ingest_sources` on startup (errors recorded, app still starts)
* Register routers

## API

HTTP only. No LLM/Chroma/prompt logic.

| Method | Path | Body / headers | Response |
|--------|------|----------------|----------|
| GET | `/health` | — | 200/ok after nonempty ingestion; 503/not_ready otherwise |
| POST | `/chat/ask` | `{ "question": "..." }` | `{ "answer", "sources" }` |
| POST | `/admin/reindex` | required `X-Admin-Key` | ingest result dict |

## Services

### RAG (`rag_service.py`)

```
Question → similarity_search → format context → SYSTEM_PROMPT → LLM → answer + sources
```

Empty retrieval → Thai/English no-verified-info message, `sources: []`.

### Ingestion (`ingestion_service.py`)

```
RAG_SOURCE_PATHS → loaders → chunking → staging Chroma collection → verify count → atomic active-manifest publication
```

Skips rebuild only when source/config fingerprints and the active collection's expected chunk count match (unless `force=True`). `pipeline/manifest.py` fingerprints source files; `core/vectorstore.py` reads/writes the active manifest and follows its collection pointer. Rebuild failures do not replace the serving collection. Previous successful collections are retained for in-flight readers; see backend/README.md for maintenance and single-writer limits.

## Core

Reusable clients: LLM, embeddings, Chroma. No HTTP.

## Pipeline

Data preparation only. Supports `.json` (MOD-SA chunk schema), `.pdf`, `.txt`, `.md`.

---

# Data Flow

## Indexing

```
Source files (chunks JSON / PDF / text)
        |
        v
   pipeline/loaders
        |
        v
   pipeline/chunking   (skip if _prechunked)
        |
        v
   embeddings (batched)
        |
        v
   Chroma (CHROMA_DIR / CHROMA_COLLECTION)
```

## Question Answering

```
POST /chat/ask
      |
      v
services/rag_service
      |
      +--> core/vectorstore (retrieve)
      |
      +--> prompts/rag_prompt + core/llm
      |
      v
{ answer, sources }
```

---

# Configuration

Driven by environment (see `backend/.env.example`):

| Variable | Role |
|----------|------|
| `LLM_*` | Chat model (OpenAI-compatible) |
| `EMBEDDING_*` | Embedding model; choose EMBEDDING_PROVIDER explicitly |
| `CHROMA_DIR`, `CHROMA_COLLECTION` | Vector persistence |
| `RAG_SOURCE_PATHS` | Comma-separated source dirs/files |
| `CHUNK_SIZE`, `CHUNK_OVERLAP`, `RETRIEVAL_K` | Chunk/retrieve params |
| `CORS_ORIGINS` | Browser frontend origins |
| `ADMIN_API_KEY` | Required secret for `/admin/reindex` |

---

# Design Principles

* Single responsibility per module
* Dependency direction: API → services → core/pipeline
* Configuration-driven providers and paths
* Prefer completing current layers over new abstractions
* Preserve grounded RAG behavior (context-only answers + sources)
