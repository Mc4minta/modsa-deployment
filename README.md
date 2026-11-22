# MOD-SA

KMUTT Student Affairs RAG chatbot: a React chat UI backed by a FastAPI service
(LangChain + ChromaDB) that answers questions from prepared university
documents.

## Architecture (production)

```text
Browser ──► https://modsa.project.cpe.kmutt.ac.th/
              ▼
 ┌──────────── On-prem host (Docker Compose) ─────────┐
 │  nginx: static React build  +  /api/* proxy        │
 │         (route allowlist, rate limits)              │
 │              ▼                                      │
 │          FastAPI backend ─► ChromaDB (data/chroma)  │
 └──────────────┬──────────────────────────────────────┘
                ▼ outbound HTTPS
   KMUTT CPE AI Gateway (LLM + embeddings, OpenAI-compatible)
```

The browser sees one site: Nginx serves the built frontend at `/` and proxies
only `GET /api/health` and `POST /api/chat/ask` to the backend. The backend has
no published port. Full runbook: [DEPLOYMENT.md](DEPLOYMENT.md).

TODO(owner): document where TLS terminates and how traffic reaches the Nginx
container (compose publishes no port for it in `docker-compose.yml`).

## Structure

- `backend/`: FastAPI RAG backend (active)
- `backend_old/`: previous monolithic backend, reference only
- `frontend/`: React + TypeScript + Vite web client
- `data/chunks/`: prepared knowledge source (JSON chunks, baked into the backend image)
- `data/`: other pipeline data (raw, processed, evaluation)
- `nginx/nginx.conf`: static frontend + SPA fallback, `/api` route allowlist, rate limits
- `nginx/Dockerfile`: builds the frontend and bakes it into the Nginx image
- `docker-compose.yml`: VM stack (`backend`, `nginx`; legacy `ngrok` under profile `tunnel`)
- `docker-compose.local.yml`: publishes Nginx on `127.0.0.1:8080` for local testing
- `scripts/`: `backup.sh`, `restore.sh`, `reindex.sh`
- `docs/`: deployment runbook and development guides
- `.env.example`: local-development settings (backend)
- `.env.vm.example`: VM stack settings (copy to `.env` on the VM)
- `.agents/skills/modsa-backend/`: agent skill for backend work

## Quick start (local development)

Backend:

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit keys / models as needed
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

The prepared chunks live in `data/chunks/`. If `backend/.env.example` still
points at `../datasets/chunks`, set `RAG_SOURCE_PATHS=../data/chunks` in your
`.env` (the code default is `chunks`, relative to the working directory).

Frontend:

```bash
cd frontend
npm ci
npm run dev            # uses http://localhost:8000 when VITE_API_URL is unset
```

Tests and checks:

```bash
cd backend && python -m unittest discover -s tests -p "test_*.py"
cd frontend && npm run check      # lint, typecheck, tests, build
```

## API

Backend routes (direct, local development):

| Method | Path | Notes |
|---|---|---|
| GET | `/health` | Status and last startup-ingestion result |
| POST | `/chat/ask` | Body `{"question":"..."}`; returns `answer` and `sources` |
| POST | `/admin/reindex` | Requires header `X-Admin-Key` = `ADMIN_API_KEY`; deletes and rebuilds the index |

In production, Nginx exposes only `GET /api/health` and `POST /api/chat/ask`
(plus CORS `OPTIONS` preflights). Everything else, including `/admin/*`,
`/docs`, `/redoc` and `/openapi.json`, returns a JSON 404. `/` and other
non-`/api` paths serve the frontend (`index.html` fallback).

## Deployment

The on-prem host runs Docker Compose. The Nginx image builds the frontend
(`nginx/Dockerfile`, `VITE_API_URL=/api`) and serves it next to the API proxy.

1. Prepare `.env` from [.env.vm.example](.env.vm.example).
2. Start and verify locally:
   `docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build backend nginx`
   (site and API on `http://127.0.0.1:8080`).
3. Production: `git pull` then `docker compose up -d --build nginx`.
   TODO(owner): how the public HTTPS name reaches the Nginx container.

Follow [DEPLOYMENT.md](DEPLOYMENT.md) for the details, checks and rollback.
ngrok and Vercel are a legacy fallback only; `render.yml` is kept as a fallback.

## Key configuration

| Variable | Where | Purpose |
|---|---|---|
| `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` | VM `.env` | OpenAI-compatible chat model |
| `LLM_TIMEOUT`, `LLM_MAX_RETRIES` | VM `.env` | Per-attempt timeout and retries for the LLM call |
| `EMBEDDING_PROVIDER`, `EMBEDDING_BASE_URL`, `EMBEDDING_API_KEY`, `EMBEDDING_MODEL` | VM `.env` | Embeddings (`openai` provider for the gateway) |
| `EMBEDDING_TIMEOUT`, `EMBEDDING_MAX_RETRIES` | VM `.env` | Also used while indexing; use tolerant values on first boot |
| `CORS_ORIGINS` | VM `.env` | Exact browser origins; not needed for same-origin use, only for legacy/other origins |
| `ADMIN_API_KEY` | VM `.env` | Protects `/admin/reindex` (used only inside the container) |
| `VITE_API_URL` | Docker build arg (`nginx/Dockerfile`) | Defaults to `/api` (same origin); unset in `npm run dev` = `http://localhost:8000` |
| `NGROK_AUTHTOKEN`, `NGROK_DOMAIN` | VM `.env` | Legacy tunnel only |

Never commit `.env` files or paste keys into issues or chat.

## Operations cheat sheet

```bash
docker compose ps                         # add -f docker-compose.local.yml if you used it to start
docker compose logs -f backend            # startup ingestion, errors
docker compose logs nginx --tail 50       # access log (client IPs depend on the TODO(owner) in nginx.conf)
docker compose up -d                      # applies .env changes (restart does NOT re-read .env)
docker compose restart nginx              # after the backend container is recreated
bash scripts/backup.sh                    # stops the backend briefly; archives data/chroma
bash scripts/reindex.sh                   # re-embeds all chunks (see runbook first)
```

## Known limits

- The frontend aborts a request after 45 seconds, so the backend's worst-case
  latency (embedding + LLM, including retries) must stay below that.
- Reasoning ("thinking") models on the gateway can exceed the LLM timeout.
  See the LLM section of the runbook.
- Client IP for rate limits depends on the proxy in front of Nginx; see the
  TODO(owner) in `nginx/nginx.conf`.
- Dependencies in `backend/requirements.txt` are not pinned.