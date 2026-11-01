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

Active code lives in `backend/`; source knowledge lives in `data/chunks/`.
Graph build/check/load tooling lives in `graph/` (see `graph/QUICKSTART.md`).
Do not recreate legacy backend folders; the ignored research archive is optional.

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
* `RAG_SOURCE_PATHS` (comma-separated; local default often `../data/chunks`)
* `CHUNK_SIZE`, `CHUNK_OVERLAP`, `RETRIEVAL_K`
* `CORS_ORIGINS`
* `ADMIN_API_KEY` (required for reindex)

Choose EMBEDDING_PROVIDER explicitly. Docker endpoints use DOCKER_LLM_BASE_URL and DOCKER_EMBEDDING_BASE_URL rather than host-local localhost URLs.

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
5. Preserve the existing Vector API unless an intentional change is requested.
6. Prefer working deployment over new abstractions.

Do not replace LangChain unless necessary.
Do not introduce Redis/auth frameworks/extra services before demo needs them.

---

# Testing Checklist

After changes:

* `python -c "import main"` succeeds from `backend/`
* `GET /health` returns 200 only after nonempty ingestion; 503 when unready
* Startup or `POST /admin/reindex` indexes sources
* `POST /chat/ask` returns answer + sources for a known topic
* Empty question → 422
* Empty index → no-verified-info fallback, `sources: []`

## Graph handoff checks

New documents use `graph/run.py expand` (see `graph/EXPANSION.md`), not the frozen pilot `build`. Reuse the fixed schema; no pilot question list is required. Check is offline; extraction needs an explicit API call budget; loading keeps PENDING/retrieval disabled and isolates each document graph version. Never infer policy approval from validation success.

Use `python graph/run.py check` for offline validation and `build` to replay the frozen pilot. Build stages outputs before publishing; it must preserve previous outputs on failure. Do not call LLMs, start Neo4j, reindex Chroma or enable Hybrid merely to run offline checks. Run `graph/tests` with backend dependencies for runtime integration tests. Changes to source/schema still need explicit revalidation; unrelated corpus inventory is not a new pilot identity.
