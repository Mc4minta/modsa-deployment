# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

MOD-SA: KMUTT Student Affairs RAG chatbot.

- `backend/` — **active** backend. FastAPI + LangChain + ChromaDB, OpenAI-compatible LLM/embeddings (Ollama supported locally).
- `frontend/` — active React + TypeScript + Vite client with Vitest tests. See `frontend/README.md`.
- `data/` — raw/processed/chunks/evaluation data; `data/chunks/` is the source of truth.
- `graph/` — frozen GraphRAG pilot build/check/load; start at `graph/QUICKSTART.md`. `/chat/ask` remains Vector-only. No automatic schema discovery/full-corpus graph build.
- `.agents/skills/modsa-backend/SKILL.md` and `docs/backend-structure.md` — backend rules/reference; `docs/architecture.md` gives the overview and `graph/QUICKSTART.md` is the graph handoff entrypoint.

## Commands

For new-document graphs use `python graph/run.py expand --input data/chunks/<file-or-folder> --check`, then follow `graph/EXPANSION.md`. No pilot IDs/QAs required. `--extract` needs an explicitly approved document scope/API budget; `--load` is an explicit staging database write. Do not equate this with production approval or automatic update/delete.

Automated checks exist: from root run `PYTHONPATH=backend python3 -m unittest discover -s backend/tests`, and similarly `-s graph/tests`. Graph-only users need only graph requirements for `python graph/run.py check`; runtime integration tests additionally need backend dependencies. Frontend: `cd frontend && npm ci && npm run check`.

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
| POST | `/admin/reindex` | required matching `X-Admin-Key` | ingest result dict |

Startup lifespan in `main.py` runs `ingest_sources` (skips rebuild if source manifest fingerprint unchanged, unless `force=True`).

## Config

Centralized in `backend/config.py` via `pydantic-settings`, read from `.env`. Key vars: `LLM_*`, `EMBEDDING_*`, `CHROMA_DIR`, `CHROMA_COLLECTION`, `RAG_SOURCE_PATHS`, `CHUNK_SIZE`, `CHUNK_OVERLAP`, `RETRIEVAL_K`, `CORS_ORIGINS`. `ADMIN_API_KEY` is required for reindex. Choose `EMBEDDING_PROVIDER` explicitly; Docker URLs use separate `DOCKER_LLM_BASE_URL`/`DOCKER_EMBEDDING_BASE_URL` overrides.

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
- Preserve the existing Vector API unless explicitly asked to enable Hybrid. Do not recreate nonexistent legacy backend folders.

## Testing checklist (after backend changes)

- `python -c "import main"` succeeds from `backend/`
- `GET /health` returns 200/ok after nonempty ingestion, 503/not_ready otherwise
- Startup or `POST /admin/reindex` indexes sources
- `POST /chat/ask` returns answer + sources for a known topic
- Empty question → 422
- Empty index → no-verified-info fallback, `sources: []`
