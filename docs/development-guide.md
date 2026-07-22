# MOD-SA Development Guide

## Local Development

```bash
cd backend_new
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit models / keys
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Default base URL: `http://127.0.0.1:8000`

### Smoke checks

```bash
curl http://127.0.0.1:8000/health

curl -X POST http://127.0.0.1:8000/chat/ask \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"ทุนการศึกษามีอะไรบ้าง\"}"

curl -X POST http://127.0.0.1:8000/admin/reindex
# If ADMIN_API_KEY is set:
curl -X POST http://127.0.0.1:8000/admin/reindex \
  -H "X-Admin-Key: your-key"
```

---

# Environment Configuration

Copy from `backend_new/.env.example` (or repo root `.env.example`).

```env
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=qwen3:30b-a3b

EMBEDDING_BASE_URL=http://localhost:11434/v1
EMBEDDING_API_KEY=ollama
EMBEDDING_MODEL=bge-m3:latest

CHROMA_DIR=chroma_db
CHROMA_COLLECTION=modsa_kmutt
RAG_SOURCE_PATHS=../backend_old/chunks
CHUNK_SIZE=1000
CHUNK_OVERLAP=150
RETRIEVAL_K=4

APP_HOST=127.0.0.1
APP_PORT=8000
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
# ADMIN_API_KEY=change-me
```

Notes:

* Local default sources point at prepared JSON under `backend_old/chunks`.
* Ollama embeddings are used automatically when embedding URL host is localhost/`127.0.0.1` and port `11434`.
* Large index runs embed in batches; first startup may take minutes.

---

# Docker

From repo root (needs Docker + `.env`):

```bash
cp .env.example .env
docker compose up --build
```

Compose mounts `backend_old/chunks` → `/app/storage/chunks` and persists Chroma in volume `chroma_data`. Host Ollama is reached via `host.docker.internal`.

---

# Adding New Knowledge Data

```
Raw Documents
      |
      v
Chunk preparation (external data pipeline)
      |
      v
backend_old/chunks   (or path in RAG_SOURCE_PATHS)
      |
      v
POST /admin/reindex   (or restart API for lifespan ingest)
```

Do not manually edit Chroma files under `CHROMA_DIR`.

Supported inputs: `.json` (MOD-SA chunk schema), `.pdf`, `.txt`, `.md`.

---

# Adding New API Endpoint

1. Route: `api/example.py` (thin — validate + call service)
2. Schema: `schemas/example.py` if needed
3. Logic: `services/example_service.py`
4. Register router in `main.py`

Keep LLM / Chroma / loaders out of `api/`.

---

# API Reference (current)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness + last ingestion status |
| POST | `/chat/ask` | RAG answer `{answer, sources}` |
| POST | `/admin/reindex` | Force reindex (`X-Admin-Key` if configured) |

---

# Debugging Checklist

## No / weak answer

1. `GET /health` — is `ingestion.status` `indexed`?
2. Is `RAG_SOURCE_PATHS` pointing at real chunk files?
3. Does Chroma exist under `CHROMA_DIR`?
4. Is embedding model reachable (Ollama / API)?
5. Does retrieval return docs for the question?

## Wrong answer

1. Chunk quality / metadata
2. `RETRIEVAL_K`
3. Prompt constraints in `prompts/rag_prompt.py`

## Slow response

1. Startup/reindex embedding batch size (714+ chunks)
2. LLM latency
3. Avoid rebuilding index when sources unchanged (manifest skip)

## App starts but ingest fails

* Lifespan catches ingest errors; `/health` shows `ingestion.status: error`.
* Fix embedding/LLM connectivity, then `POST /admin/reindex`.

---

# Deployment Checklist

Before demo:

* `.env` filled; models pulled (e.g. `ollama pull bge-m3`)
* `GET /health` ok with indexed sources
* Sample Thai/English questions return sources
* CORS origins include the frontend URL

Before production:

* Set `ADMIN_API_KEY`
* Persist `CHROMA_DIR` (compose volume or bind mount)
* Confirm secrets not committed
* Review logging; no debug-only paths
