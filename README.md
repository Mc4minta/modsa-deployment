# MOD-SA

KMUTT Student Affairs RAG chatbot: a React chat UI backed by a FastAPI service
(LangChain + ChromaDB) that answers questions from prepared university
documents.

## Architecture (production)

```text
Browser ──► Vercel (React/Vite static build)
              │  HTTPS; absolute API URL baked in at build time (VITE_API_URL)
              ▼
          ngrok static domain
              ▼
 ┌──────────── Ubuntu VM (Docker Compose) ────────────┐
 │  ngrok ─► nginx (route allowlist, rate limits)      │
 │              ▼                                      │
 │          FastAPI backend ─► ChromaDB (data/chroma)  │
 └──────────────┬──────────────────────────────────────┘
                ▼ outbound HTTPS
   KMUTT CPE AI Gateway (LLM + embeddings, OpenAI-compatible)
```

Only Nginx is reachable through the tunnel, and it forwards just two routes.
The backend has no published port. Full runbook: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Structure

- `backend/`: FastAPI RAG backend (active)
- `backend_old/`: previous monolithic backend, reference only
- `frontend/`: React + TypeScript + Vite web client
- `data/chunks/`: prepared knowledge source (JSON chunks, baked into the backend image)
- `data/`: other pipeline data (raw, processed, evaluation)
- `nginx/nginx.conf`: public route allowlist, rate limits, CORS for Nginx-generated errors
- `docker-compose.yml`: VM stack (`backend`, `nginx`, `ngrok` under profile `tunnel`)
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
`/docs`, `/redoc` and `/openapi.json`, returns a JSON 404.

## Deployment

The backend runs on an Ubuntu VM with Docker Compose; the frontend is built and
hosted by Vercel and calls the backend through an ngrok static domain.

1. Prepare the VM and `.env` from [.env.vm.example](.env.vm.example).
2. Start and verify locally:
   `docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build backend nginx`
3. Start the tunnel: `docker compose --profile tunnel up -d`
4. In Vercel (Root Directory `frontend`), set `VITE_API_URL=https://<ngrok-domain>/api`
   and `VITE_NGROK_SKIP_BROWSER_WARNING=true`, then redeploy.
5. Add the Vercel origin to `CORS_ORIGINS` on the VM and run `docker compose up -d`.

Follow [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for the details, checks and
troubleshooting. The Render configuration (`render.yml`) is kept as a fallback.

## Key configuration

| Variable | Where | Purpose |
|---|---|---|
| `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` | VM `.env` | OpenAI-compatible chat model |
| `LLM_TIMEOUT`, `LLM_MAX_RETRIES` | VM `.env` | Per-attempt timeout and retries for the LLM call |
| `EMBEDDING_PROVIDER`, `EMBEDDING_BASE_URL`, `EMBEDDING_API_KEY`, `EMBEDDING_MODEL` | VM `.env` | Embeddings (`openai` provider for the gateway) |
| `EMBEDDING_TIMEOUT`, `EMBEDDING_MAX_RETRIES` | VM `.env` | Also used while indexing; use tolerant values on first boot |
| `CORS_ORIGINS` | VM `.env` | Exact browser origins, comma-separated, no trailing slash |
| `ADMIN_API_KEY` | VM `.env` | Protects `/admin/reindex` (used only inside the container) |
| `NGROK_AUTHTOKEN`, `NGROK_DOMAIN` | VM `.env` | Tunnel credentials; the domain has no `https://` |
| `VITE_API_URL` | Vercel (build time) | Absolute backend URL ending in `/api` |
| `VITE_NGROK_SKIP_BROWSER_WARNING` | Vercel (build time) | `true` adds the ngrok header that skips its browser warning page |

Never commit `.env` files or paste keys into issues or chat.

## Operations cheat sheet

```bash
docker compose ps                         # add -f docker-compose.local.yml if you used it to start
docker compose logs -f backend            # startup ingestion, errors
docker compose logs nginx --tail 50       # access log with real client IPs
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
- ngrok's free plan has monthly request and bandwidth caps and one
  automatically assigned domain; check the ngrok dashboard Usage page.
- Dependencies in `backend/requirements.txt` are not pinned.