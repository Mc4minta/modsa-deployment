---
name: modsa-backend
description: >-
  Architecture and coding rules for the MOD-SA FastAPI RAG backend
  (backend). Use when changing API routes, RAG/ingestion services,
  Chroma indexing, prompts, config, Docker, or KMUTT Student Affairs
  chat retrieval behavior.
---

# MOD-SA Backend Agent Skill

## Purpose

Development rules and architectural constraints for the MOD-SA RAG backend.

Active code lives in `backend/`. `backend_old/` is legacy reference only
(no new logic there). Prepared knowledge lives under `datasets/chunks/`.

The backend is a Retrieval-Augmented Generation chatbot for KMUTT Student Affairs.

## Project Context

Stack:

* FastAPI (`backend/main.py`)
* LangChain orchestration
* ChromaDB vector store
* OpenAI-compatible LLM (Typhoon / OpenAI / Ollama `/v1`)
* OpenAI-compatible or Ollama embeddings
* Preprocessed chunk JSON (and PDF/txt/md fallback)

Responsibilities:

1. Load and index KMUTT knowledge documents.
2. Retrieve relevant chunks.
3. Generate grounded answers.
4. Return source references.

---

# Current Layout

```
backend/
├── main.py                 # FastAPI app, CORS, lifespan ingest
├── config.py               # Settings from env
├── requirements.txt
├── Dockerfile
├── api/
│   ├── chat.py             # POST /chat/ask
│   ├── health.py           # GET /health
│   └── admin.py            # POST /admin/reindex
├── core/
│   ├── llm.py
│   ├── embeddings.py
│   └── vectorstore.py
├── services/
│   ├── rag_service.py
│   └── ingestion_service.py
├── pipeline/
│   ├── loaders.py
│   ├── chunking.py
│   └── manifest.py
├── prompts/
│   └── rag_prompt.py
└── schemas/
    └── chat.py
```

Do **not** add `utils/`, `database/`, or `models/` unless clearly needed.
Do **not** put business logic in `api/`.

---

# Architecture Rules

## Dependency Direction

```
API
 ↓
Services
 ↓
Core / Pipeline
 ↓
External Systems
```

Do not mix layers.

| Layer | Path | Does | Must not |
|-------|------|------|----------|
| API | `api/` | Routes, validation, HTTP errors | LLM init, Chroma, prompts, loaders |
| Services | `services/` | Workflows (ask, ingest) | FastAPI Request/Response types (except unavoidable) |
| Core | `core/` | LLM, embeddings, Chroma clients | Routes, ingest orchestration |
| Pipeline | `pipeline/` | Discover, load, chunk, manifest | Calling LLM or FastAPI |
| Prompts | `prompts/` | Prompt strings/templates | Retrieval logic |
| Schemas | `schemas/` | Pydantic request/response models | Side effects |

## Import Rules

Preferred:

```
api → services → core | pipeline
core → external libraries
pipeline → config + external libraries
```

Avoid:

```
core → api
pipeline → services
services → api
```

---

# API Endpoints

| Method | Path | Notes |
|--------|------|-------|
| GET | `/health` | `{status, ingestion}` |
| POST | `/chat/ask` | Body `{"question":"..."}` → `{answer, sources}` |
| POST | `/admin/reindex` | Force rebuild. If `ADMIN_API_KEY` set, require header `X-Admin-Key` |

Startup lifespan runs `ingest_sources` (skip if manifest unchanged).

---

# Config

Centralize in `config.py` / env. Important keys:

* `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`
* `EMBEDDING_BASE_URL`, `EMBEDDING_API_KEY`, `EMBEDDING_MODEL`
* `CHROMA_DIR`, `CHROMA_COLLECTION`
* `RAG_SOURCE_PATHS` (comma-separated; local default often `../datasets/chunks`)
* `CHUNK_SIZE`, `CHUNK_OVERLAP`, `RETRIEVAL_K`
* `CORS_ORIGINS`
* `ADMIN_API_KEY` (**required** — `/admin/reindex` returns 500 if unset)

`EMBEDDING_PROVIDER` (`ollama` / `huggingface` / `openai`) selects the embedding backend explicitly — dev uses `ollama` (local `bge-m3`), production uses `huggingface` (Hugging Face Inference API, `EMBEDDING_MODEL=BAAI/bge-m3`, requires `EMBEDDING_API_KEY`).

---

# RAG Rules

Answers must:

* Use retrieved context only.
* Avoid inventing unsupported facts.
* Use Thai/English no-verified-info fallback when retrieval empty.
* Preserve source metadata (`source`, `title`, `department`, `url`, `page`).

Ingestion notes:

* Prepared chunk JSON is pre-chunked (`_prechunked`); do not re-split.
* Embed/add to Chroma in batches (see `ingestion_service`) — large single batches can break local Ollama.
* Prefer reindex via `/admin/reindex`; do not hand-edit Chroma files.

---

# Modification Guidelines

1. Pick the correct layer.
2. Reuse `rag_service` / `ingestion_service`.
3. Keep API thin.
4. Keep config centralized in `config.py`.
5. Preserve behavior from `backend_old` unless the change is intentional.
6. Prefer working deployment over new abstractions.

Do not replace LangChain unless necessary.
Do not introduce Redis/auth frameworks/extra services before demo needs them.

---

# Testing Checklist

After changes:

* `python -c "import main"` succeeds from `backend/`
* `GET /health` returns `status: ok`
* Startup or `POST /admin/reindex` indexes sources
* `POST /chat/ask` returns answer + sources for a known topic
* Empty question → 422
* Empty index → no-verified-info fallback, `sources: []`
