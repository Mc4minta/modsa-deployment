# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

MOD-SA: KMUTT Student Affairs RAG chatbot.

- `backend/` — FastAPI + LangChain + ChromaDB. LLM is OpenAI-compatible (local Ollama in dev, Ollama Cloud/MiniMax in production). Embeddings are provider-switchable via `EMBEDDING_PROVIDER` (`ollama` local dev / `huggingface` production Hugging Face Inference API / `openai`).
- `backend_old/` — legacy monolithic backend, reference only, don't add new logic there.
- `datasets/chunks/` — prepared knowledge source consumed by `backend/` (via `RAG_SOURCE_PATHS`) — do not delete/move it.
- `frontend/` — empty scaffold (`src/hooks`, `src/pages`, `src/router` dirs only, no `package.json`, no framework chosen yet).
- `datasets/` — raw/processed/eval data backing the knowledge base.
- `.agents/skills/modsa-backend/SKILL.md` and `docs/backend-structure.md` — deeper architecture/rules reference for backend work; read these before non-trivial backend changes. `docs/architecture.md` (referenced from README) is currently empty — ignore it, the real doc is `docs/backend-structure.md`.

## Commands

No CI, no linter config, no automated test suite exists — verification is manual (curl smoke checks + `scripts/test_rag.py`).

```bash
cd backend
python -m venv .venv && pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload --host 127.0.0.1 --port 8000

# smoke checks
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/chat/ask -H "Content-Type: application/json" -d '{"question":"..."}'
curl -X POST http://127.0.0.1:8000/admin/reindex   # add -H "X-Admin-Key: ..." if ADMIN_API_KEY set

python -c "import main"   # import sanity check after changes, run from backend/

# docker (repo root)
docker compose up --build
```

## Architecture

Strict layered dependency direction (`backend/`):

```
api/ → services/ → core/ | pipeline/ → external systems
```

| Layer | Path | Does | Must not |
|-------|------|------|----------|
| API | `api/` | Routes, validation, HTTP errors | LLM init, Chroma, prompts, loaders |
| Services | `services/` | Workflows: `rag_service.py` (ask), `ingestion_service.py` (ingest) | FastAPI Request/Response types (except unavoidable) |
| Core | `core/` | Reusable clients: `llm.py`, `embeddings.py`, `vectorstore.py` | Routes, ingest orchestration |
| Pipeline | `pipeline/` | Data prep: `loaders.py`, `chunking.py`, `manifest.py` | Calling LLM or FastAPI |
| Prompts | `prompts/` | `rag_prompt.py` templates | Retrieval logic |
| Schemas | `schemas/` | Pydantic request/response models | Side effects |

Do not add `utils/`, `database/`, or `models/` unless clearly needed. Do not put business logic in `api/`.

**Indexing data flow:** source files (chunk JSON / PDF / text) → `pipeline/loaders` → `pipeline/chunking` (skipped if already `_prechunked`) → batched embeddings → Chroma (`CHROMA_DIR`/`CHROMA_COLLECTION`).

**Q&A data flow:** `POST /chat/ask` → `services/rag_service` → `core/vectorstore` retrieve → `prompts/rag_prompt` + `core/llm` → `{answer, sources}`.

**API endpoints:**

| Method | Path | Body/headers | Response |
|---|---|---|---|
| GET | `/health` | — | `{status, ingestion}` |
| POST | `/chat/ask` | `{"question": "..."}` | `{answer, sources}` |
| POST | `/admin/reindex` | required `X-Admin-Key` | ingest result dict |

Startup lifespan in `main.py` runs `ingest_sources` (skips rebuild if source manifest fingerprint unchanged, unless `force=True`).

## Config

Centralized in `backend/config.py` via `pydantic-settings`, read from `.env`. Key vars: `LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL`/`LLM_TIMEOUT`/`LLM_MAX_RETRIES`, `EMBEDDING_PROVIDER` (`ollama`/`huggingface`/`openai`) + `EMBEDDING_BASE_URL`/`EMBEDDING_API_KEY`/`EMBEDDING_MODEL`/`EMBEDDING_TIMEOUT`/`EMBEDDING_MAX_RETRIES`, `CHROMA_DIR`, `CHROMA_COLLECTION`, `RAG_SOURCE_PATHS` (comma-separated), `CHUNK_SIZE`, `CHUNK_OVERLAP`, `RETRIEVAL_K`, `CORS_ORIGINS`, `ADMIN_API_KEY` (**required** — `/admin/reindex` refuses to run without it). `EMBEDDING_PROVIDER=huggingface` requires `EMBEDDING_API_KEY` to be set (fails fast at startup otherwise).

## RAG behavior rules

- Answers must use retrieved context only — never invent unsupported facts.
- When retrieval is empty, return the Thai/English no-verified-info fallback with `sources: []`.
- Preserve source metadata (`source`, `title`, `department`, `url`, `page`) through retrieval and response.
- Prepared chunk JSON is pre-chunked (`_prechunked`) — do not re-split it in `pipeline/chunking`.
- Embed/add to Chroma in batches — a large single batch can break local Ollama.
- Reindex via `POST /admin/reindex`; never hand-edit Chroma's on-disk files.

## Modification guidelines

- Reuse `rag_service` / `ingestion_service` rather than adding parallel workflows.
- Keep `api/` thin — no business logic there.
- Don't replace LangChain unless necessary; don't introduce Redis, auth frameworks, or extra services before the demo actually needs them.
- Preserve `backend_old` behavior unless a change is intentional (it's the behavioral reference, even though it's not actively maintained).

## Testing checklist (after backend changes)

- `python -c "import main"` succeeds from `backend/`
- `GET /health` returns `status: ok`
- Startup or `POST /admin/reindex` indexes sources
- `POST /chat/ask` returns answer + sources for a known topic
- Empty question → 422
- Empty index → no-verified-info fallback, `sources: []`
