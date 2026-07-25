# MOD-SA Backend Architecture

## Overview

MOD-SA is a FastAPI RAG chatbot backend for KMUTT Student Affairs knowledge retrieval.

Active implementation: **`backend/`**.  
Legacy reference: **`backend_old/`** (no new logic there).  
Prepared chunks (ingestion source): **`datasets/chunks/`**.

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

Repo-level Docker: root `docker-compose.yml` builds `backend`, mounts `datasets/chunks` read-only, persists Chroma volume.

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
| GET | `/health` | — | `{ "status": "ok", "ingestion": {...} }` |
| POST | `/chat/ask` | `{ "question": "..." }` | `{ "answer", "sources" }` |
| POST | `/admin/reindex` | optional `X-Admin-Key` | ingest result dict |

## Services

### RAG (`rag_service.py`)

```
Question → similarity_search → format context → SYSTEM_PROMPT → LLM → answer + sources
```

Empty retrieval → Thai/English no-verified-info message, `sources: []`.

### Ingestion (`ingestion_service.py`)

```
RAG_SOURCE_PATHS → loaders → chunking → batched Chroma add → save manifest
```

Skips rebuild when source fingerprints unchanged (unless `force=True`).

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
| `EMBEDDING_*` | Embedding model; Ollama auto if host:11434 |
| `CHROMA_DIR`, `CHROMA_COLLECTION` | Vector persistence |
| `RAG_SOURCE_PATHS` | Comma-separated source dirs/files |
| `CHUNK_SIZE`, `CHUNK_OVERLAP`, `RETRIEVAL_K` | Chunk/retrieve params |
| `CORS_ORIGINS` | Browser frontend origins |
| `ADMIN_API_KEY` | Optional lock on `/admin/reindex` |

---

# Design Principles

* Single responsibility per module
* Dependency direction: API → services → core/pipeline
* Configuration-driven providers and paths
* Prefer completing current layers over new abstractions
* Preserve grounded RAG behavior (context-only answers + sources)
