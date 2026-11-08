# MOD-SA ngrok + Vercel readiness audit

## 0. Header

- Branch: `modsa-vm` (CONFIRMED; `git branch --show-current`).
- `git rev-parse HEAD`: `772449fd39068c3eedb51c161471caf7499a5b7b`.
- Audit date: 2026-11-08.
- Working tree before this report: clean. `origin/modsa-vm...HEAD` is `1 0`.
- Read-only audit; no git commits, stages or pushes were made.

## 1. Executive summary

The checked-out branch is the required branch and has no pre-existing changes. The
frontend is Vite/React and its API client can consume an absolute ngrok `/api`
base URL without rejecting it. The backend has FastAPI CORS middleware, but the
default CORS value is local-only and the allowed header list does not include
`ngrok-skip-browser-warning`. The target Nginx/ngrok VM topology is not present:
there is only one backend service in Compose, no Nginx configuration, no ngrok
service, no VM runbook, and no backup/reindex scripts. The current Docker image
does not match the deployment-plan paths it claims to use. There are no
automated Nginx or Compose checks because Docker and Nginx are unavailable.
There is one blocker for the stated architecture: the VM edge/tunnel layer and
its routing/preflight configuration must be supplied. The remaining major
deployment blockers are production environment values, correct image/data paths,
and a runbook for first boot and steady state.

## 2. Findings

### 1. Repository and working-tree state

**Answer — CONFIRMED.** The current branch is `modsa-vm`; HEAD is
`772448fd39068c3eedb51c161471caf7499a5b7b`; the last 15 commits were read.
`git status --short` and `git diff --stat` were empty before this report.
`origin/modsa-vm` exists locally and is even with HEAD (`0 0`). After this
report is created, the only expected change is this file.

`docs/STEP2_REPORT.md`, `docs/STEP2_FIXES_REPORT.md`, `docs/STEP3_REPORT.md`,
`docs/DEPLOYMENT.md`, `.gitattributes`, `docker-compose.local.yml`,
`nginx/nginx.conf`, `nginx/Dockerfile`, `vercel.json`, `scripts/backup.sh`,
`scripts/restore.sh`, and `scripts/reindex.sh` are all absent (filesystem
check). Only `scripts/create_modsa_structure.py` and `scripts/test_rag.py` are
tracked scripts, both mode `100644`, not executable. The deployment files that
exist contain CR characters: `.env.example` 33, `backend/.env.example` 52,
`backend/Dockerfile` 28, `docker-compose.yml` 25, `frontend/.env.example` 1,
`scripts/create_modsa_structure.py` 94, and `scripts/test_rag.py` 111. No
`.gitattributes` or `.dockerignore` exists.

**Step 3 status:** (a) not applied; (b) not present; (c) not present; (d) not
present; (e) not applicable because the runbook is absent.

### 2. Backend readiness for a cross-origin caller

**CORS — CONFIRMED.** `backend/main.py:45-53` adds:

```python
CORSMiddleware,
allow_origins=settings.resolved_cors_origins,
allow_credentials=False,
allow_methods=["GET", "POST"],
allow_headers=["Content-Type", "X-Admin-Key"],
```

`backend/config.py:67-70,80-81` parses `CORS_ORIGINS` as a comma-separated
list, strips surrounding whitespace, drops empty entries, and does not normalize
trailing slashes or support a regex. With exactly
`CORS_ORIGINS=https://example.vercel.app`, a JSON POST preflight using
`Content-Type` should succeed through FastAPI. A preflight requesting
`ngrok-skip-browser-warning` will not be allowed by the backend because it is
not in `allow_headers`.

**Error-path CORS — INFERRED.** The middleware is installed on the FastAPI
application before routers (`backend/main.py:44-59`), so normal responses and
FastAPI validation/HTTP errors should be wrapped with CORS headers when the
Origin is allowed. A handler-level 500 from `backend/api/chat.py:13-20` is
therefore also expected to carry them. An infrastructure error generated before
the request reaches FastAPI cannot carry backend CORS headers; the absent Nginx
layer must be designed for that case.

**Startup — CONFIRMED.** `backend/main.py:22-35` calls `ingest_sources` inside
the synchronous lifespan before `yield`. Exceptions are non-fatal: they are
logged as `Startup ingestion failed` with a traceback and state becomes
`{"status": "error", "reason": "startup ingestion failed"}`. Successful startup
logs `Startup ingestion: %s` with the result. `backend/api/health.py:6-10`
always returns `{"status": "ok", "ingestion": <state or null>}`; it does not
change HTTP status when ingestion failed.

**Environment — CONFIRMED.** `backend/config.py:18-70` reads:

| Variable | Default |
|---|---|
| `LLM_BASE_URL` | `https://api.openai.com/v1` |
| `LLM_API_KEY` or `OPENAI_API_KEY` | unset, placeholder resolved later |
| `LLM_MODEL` | `gpt-4o-mini` |
| `LLM_TIMEOUT` / `LLM_MAX_RETRIES` | `30.0` / `2` |
| `EMBEDDING_PROVIDER` | `ollama` |
| `EMBEDDING_BASE_URL` | `https://api.openai.com/v1` |
| `EMBEDDING_API_KEY` or `OPENAI_API_KEY` | unset, placeholder/resolved LLM key |
| `EMBEDDING_MODEL` | `text-embedding-3-small` |
| `EMBEDDING_TIMEOUT` / `EMBEDDING_MAX_RETRIES` | `30.0` / `2` |
| `CHROMA_DIR` / `CHROMA_COLLECTION` | `chroma_db` / `modsa_kmutt` |
| `RAG_SOURCE_PATHS` | `chunks` |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` / `RETRIEVAL_K` | `1000` / `150` / `4` |
| `RETRIEVAL_MIN_RELEVANCE` | `0.35` |
| `APP_HOST` / `APP_PORT` | `127.0.0.1` / `8000` |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` |
| `ADMIN_API_KEY` | unset |

The VM must explicitly set `CORS_ORIGINS`, `ADMIN_API_KEY`, all external
`LLM_*` and `EMBEDDING_*` values, and `CHROMA_*` paths/collection. The target
gateway values are not in the repository and must be supplied by the operator.

### 3. Nginx readiness for ngrok + cross-origin

**CONFIRMED ABSENCE.** No `nginx/` directory, `nginx/nginx.conf`, or
`nginx/Dockerfile` exists. Consequently there is no current handling for
`OPTIONS /api/chat/ask` or `/api/health`, no Nginx CORS headers, no generated
429/502/504/404/403/413 behavior, no real-IP configuration, no route allowlist,
rate limits, body limit, proxy timeouts, or log format. Browser behavior through
this missing layer is UNKNOWN until an edge configuration is supplied.

The frontend is not built by the current Dockerfile: `backend/Dockerfile:1-28`
is a single Python image and copies `backend/` plus `data/chunks`. Therefore
there is no frontend stage to remove, and Vercel does not require one. The
frontend should remain a separate Vercel project with root directory
`frontend`.

Nginx syntax validation is NOT RUN: `nginx` and `docker` are unavailable.

### 4. Compose and images

**CONFIRMED.** `docker-compose.yml:1-25` defines only `backend`, built from
`./backend/Dockerfile` with context `./backend`, publishes
`${APP_PORT:-8000}:8000`, loads root `.env`, overrides `CHROMA_DIR` to
`/app/chroma_db`, `RAG_SOURCE_PATHS` to `/app/storage/chunks`,
`APP_HOST=0.0.0.0`, and defaults LLM/embedding URLs to
`host.docker.internal`. It mounts named volume `chroma_data` at
`/app/chroma_db` and read-only `./data/chunks` at `/app/storage/chunks`,
adds `host.docker.internal:host-gateway`, and uses `restart: unless-stopped`.
There are no healthchecks, `depends_on`, networks, resource limits, logging
options, profiles, or local override.

The Compose build context also conflicts with the image: Compose uses
`context: ./backend`, while `backend/Dockerfile:10-13` refers to
`backend/requirements.txt`, `backend/`, and root-level `data/chunks`, paths
that require the repository root as build context. Even after correcting the
context, the image copies chunks to `/app/data/chunks` while Compose mounts
them at `/app/storage/chunks` and points ingestion at the latter. This needs
reconciliation before VM deployment.

There is no ngrok reference in tracked deployment files. A future ngrok service
would need `NGROK_AUTHTOKEN` and a static domain supplied through protected
environment configuration, the same Compose network as Nginx, and an upstream
to Nginx's published/internal port. No such service was added in this
read-only audit.

Cloudflare-specific material is limited to the Render-oriented documentation:
`docs/deployment-plan-free-tier.md:116-133` describes a Cloudflare Tunnel and
`cloudflared`; those linked guide files are absent. No Cloudflare service or
config is present in Compose. The plan itself is for Render, not the requested
Ubuntu VM.

Image tags are only `python:3.12-slim` in `backend/Dockerfile:1`; there is no
Node image and no pinned Nginx/ngrok image.

### 5. Frontend and Vercel readiness

**Vercel settings — INFERRED/CONFIRMED.** `frontend/package.json:1-38` and
`frontend/vite.config.ts:1-15` identify a Vite React TypeScript app. Build is
`npm run build`, output is Vite's default `dist`, and the root directory must
be `frontend` because the package and Vite config are there. The lockfile is
`frontend/package-lock.json`. No `engines`, `.nvmrc`, `.node-version`, or
`vercel.json` is present. No client router is present in the inspected source,
so no SPA rewrite is required for the current app.

**API URL — CONFIRMED.** `frontend/src/services/api.ts:9-11,194-205,248-260`
strips trailing slashes from `VITE_API_URL` and appends `/chat/ask` and
`/health`. Both `https://x.ngrok-free.dev/api` and the trailing-slash form
produce the requested `/api/chat/ask` and `/api/health` paths. The only URL
safety check (`api.ts:88-97`) applies to returned source URLs, not the API
base URL; it accepts HTTP/HTTPS and does not reject ngrok.

The only request header is `Content-Type: application/json`
(`api.ts:202-206`), which causes a preflight. The client does not send
`ngrok-skip-browser-warning`. It has a 45-second default chat timeout
(`api.ts:12,165-188`), parses JSON when advertised and otherwise wraps text as
`detail` (`api.ts:220-240`), maps 429 to a typed rate-limit error and 500/502
to server errors (`api.ts:55-84`). However, `useChatController.ts:322-323`
only displays a special message for validation errors; all network, timeout,
non-JSON, 429, 502, and 500 errors fall back to the localized generic
`errorMessage` supplied by the app (`i18n/locales.ts:45,145`).

No hardcoded Render, Cloudflare, or production localhost URL was found in
frontend source. `frontend/.env.example:1` documents only
`http://localhost:8000`, not the required absolute ngrok `/api` format. No
committed `.env.production` was found. The only plain HTTP frontend default is
the development fallback in `api.ts:10`; production with a Vercel
`VITE_API_URL` is HTTPS. `frontend/index.html:1-17` has no CSP meta tag or
restrictive API-origin policy.

Frontend checks were RUN with existing `node_modules`: lint PASS with five
existing Fast Refresh warnings, typecheck PASS, 38 tests PASS, and production
build PASS.

### 6. Secrets, env and docs

**CONFIRMED.** Root `.env.example:1-33` contains LLM, embedding, Chroma/RAG,
API host/port, CORS, admin key, and OCR variables. It has no
`NGROK_AUTHTOKEN`, ngrok domain, or Vercel origin. `backend/.env.example:1-52`
does document timeout/retry variables but still uses local CORS and Ollama
defaults. `.env` and `chroma_db/` are ignored by `.gitignore:1-9`; no tracked
`.env` was found. This was not an exhaustive secret scan; no values are copied
into this report.

There is no `docs/DEPLOYMENT.md`. The reusable deployment plan is
`docs/deployment-plan-free-tier.md`: Render setup is `:20-76`, health and API
verification is `:78-98`, HF embedding setup is `:101-114`, Cloudflare
alternative is `:116-133`, Vercel setup is `:136-145`, and CORS wiring is
`:147-151`. These sections assume Render, not the VM/nginx/ngrok topology, and
the plan's Docker copy-path assertions conflict with the current Dockerfile.
There is no first-boot versus steady-state value set or migration/backup
runbook.

Latency is not fully bounded by the repository: the frontend is 45 seconds
(`frontend/src/services/api.ts:12`), LLM and embedding timeout defaults are
30 seconds with two retries (`backend/config.py:31-50`), and there are no
Nginx proxy timeouts. The resulting worst case can exceed 45 seconds depending
on client-library retry semantics, so the frontend timeout is the only known
binding client limit. ngrok's free endpoint behavior does not add a measured
repository-configured timeout.

### 7. Scripts

`scripts/create_modsa_structure.py:1-69` creates a legacy directory/file
scaffold and has no Cloudflare logic. `scripts/test_rag.py:1-85` is a legacy
unit test script importing `app.config`, `app.rag`, and `app.ingest`; the
current backend uses top-level `config`, `services`, and `pipeline`, so this
script is not a valid current-backend check (CONFIRMED by imports). Neither
script is executable (`100644`). `bash -n` was NOT RUN because the scripts are
Python and Bash is not required. No backup, restore, or reindex script exists.

## 3. Verification table

| Check | Result | Evidence/reason |
|---|---|---|
| Required branch | PASS | `git branch --show-current` returned `modsa-vm` |
| HEAD and working tree | PASS | HEAD recorded above; status/diff stat were empty before report |
| Remote comparison | PASS | `git rev-list --left-right --count origin/modsa-vm...HEAD` = `0 0` |
| Frontend lint | PASS with warnings | `npm run check`; five Fast Refresh warnings |
| Frontend typecheck | PASS | `npm run check` |
| Frontend tests | PASS | 7 files, 38 tests |
| Frontend production build | PASS | `vite build` completed |
| Backend unit tests | PASS | `pytest -q` found no pytest command and fallback unittest ran 6 tests |
| Backend import | NOT RUN | `python -c "import main"` hung over 120 seconds without output and was stopped |
| Nginx syntax | NOT RUN | `nginx` unavailable; Docker unavailable |
| Compose config | NOT RUN | Docker unavailable |
| Runtime health/chat/preflight | NOT RUN | No app/container was started per audit rules |
| Bash syntax | NOT RUN | No Bash scripts are present |

## 4. Gap table

| ID | Area | File(s) | Current state | Needed for ngrok+Vercel | Severity | Notes |
|---|---|---|---|---|---|---|
| G1 | ngrok service | `docker-compose.yml` | No ngrok service/reference | Add a protected-token ngrok service on the VM network with static domain | BLOCKER | Domain/token are operator inputs |
| G2 | Nginx edge | `nginx/*` absent | No reverse proxy or allowlist | Add Nginx upstream, routes, limits, timeouts, and error policy | BLOCKER | Required by target architecture |
| G3 | Preflight | `backend/main.py`, Nginx absent | FastAPI handles CORS; no edge handling | Ensure OPTIONS reaches/gets correctly answered by edge and backend | BLOCKER | `ngrok-skip-browser-warning` decision required |
| G4 | CORS origin | `.env.example`, `backend/config.py` | Local comma-list default; no regex | Set exact Vercel production/preview/custom origins; document parsing | BLOCKER | No trailing-slash normalization |
| G5 | Error CORS | Nginx absent | Backend errors likely have CORS; edge errors unknown | Add CORS headers or JSON handling for edge-generated errors | SHOULD | Prevent opaque browser failures |
| G6 | Compose/image paths | `docker-compose.yml`, `backend/Dockerfile` | Build context and source paths mismatch | Use a compatible root build context and align mount/`RAG_SOURCE_PATHS` | BLOCKER | Current Compose build can fail before indexing |
| G7 | Frontend Vercel config | `frontend/package.json`, `.env.example` | No Vercel config; local API example only | Root `frontend`, Vite, `npm run build`, `dist`, absolute HTTPS `/api` value | SHOULD | Set Production and Preview variables |
| G8 | Runbook | `docs/deployment-plan-free-tier.md` | Render runbook; no VM runbook | Rewrite for Ubuntu, Docker Compose, ngrok, Nginx, health, backup, rollback | BLOCKER | Existing plan is not target topology |
| G9 | Env example | `.env.example`, `backend/.env.example` | No ngrok/Vercel variables; local defaults | Document token/domain/origins and first-boot/steady-state values | SHOULD | Never include actual secrets |
| G10 | Rate limits | `nginx/*` absent | No rate limiting | Choose per-IP/global limits accounting for campus NAT | SHOULD | Numbers cannot be audited yet |
| G11 | Real client IP | `nginx/*` absent | No trusted forwarding policy | Explicitly handle ngrok `X-Forwarded-For` and trusted proxy scope | SHOULD | Do not assume CF headers |
| G12 | Persistence/ops | `scripts/*` | No backup/restore/reindex scripts; scripts non-executable | Add non-root-safe backup/restore and in-container-key reindex procedures | SHOULD | Restore must preserve old data |
| G13 | Runtime validation | Docker/Nginx unavailable | Compose/Nginx checks not run | Run `docker compose config`, `nginx -t`, preflight and error smoke tests on VM | SHOULD | Required before exposure |
| G14 | Timeout budget | `backend/config.py`, frontend API | 30s backend defaults, 45s browser timeout, no edge timeout | Define retry/timeout budget that fits 45s or increase client timeout intentionally | SHOULD | First-boot embedding may need separate values |

## 5. Already fine / reusable

- Required branch and clean baseline were confirmed.
- Frontend Vite build, typecheck, tests, and lint complete successfully.
- Absolute HTTPS API bases with or without a trailing slash are supported.
- FastAPI already permits `GET`, `POST`, `Content-Type`, and `X-Admin-Key` for
  configured origins.
- Startup ingestion reports state through `/health`, and admin reindex is
  protected when `ADMIN_API_KEY` is configured (`backend/api/admin.py:13-30`).
- Chroma is persisted in the Compose named volume and source chunks are mounted
  read-only (`docker-compose.yml:15-20`).

## 6. Open questions

1. What ngrok static domain and account/token will the VM use?
2. Which Vercel production, preview, and custom-domain origins should be
   allowed?
3. Should the frontend send `ngrok-skip-browser-warning`, or should the edge
   be configured so it is unnecessary?
4. What exact Nginx route allowlist, rate limits, trusted proxy ranges, and
   error JSON/CORS policy are required?
5. Which external OpenAI-compatible gateway URLs, models, and operator-managed
   secret names are intended?
6. Should first boot use tolerant embedding retries/timeouts, and what are the
   steady-state values?
7. Is the current `data/chunks` source path authoritative, or should the image
   use `datasets/chunks` as the older deployment plan states?

## 7. Not inspected

- No external ngrok, Vercel, gateway, VM, DNS, or account settings were
  contacted or inspected.
- No containers, images, application server, Nginx, or browser were started.
- No secret values were printed or exhaustively scanned.
- Absent files listed in the findings were not fabricated or inferred.

## 8. Appendix A

### `docker-compose.yml`

```yaml
services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "${APP_PORT:-8000}:8000"
    env_file:
      - .env
    environment:
      CHROMA_DIR: /app/chroma_db
      RAG_SOURCE_PATHS: /app/storage/chunks
      APP_HOST: 0.0.0.0
      # Inside Docker, host Ollama is reachable via host.docker.internal on Desktop
      LLM_BASE_URL: ${LLM_BASE_URL:-http://host.docker.internal:11434/v1}
      EMBEDDING_PROVIDER: ${EMBEDDING_PROVIDER:-ollama}
      EMBEDDING_BASE_URL: ${EMBEDDING_BASE_URL:-http://host.docker.internal:11434/v1}
    volumes:
      - chroma_data:/app/chroma_db
      - ./data/chunks:/app/storage/chunks:ro
    extra_hosts:
      - "host.docker.internal:host-gateway"
    restart: unless-stopped

volumes:
  chroma_data:
```

### `docker-compose.local.yml`

Absent.

### `nginx/nginx.conf`

Absent.

### `nginx/Dockerfile`

Absent.

### `.env.example`

```dotenv
# Copy this file to .env and fill in your values:
#   cp .env.example .env
# .env is gitignored — never commit real API keys.

# ── RAG app · Chat / LLM (OpenAI-compatible) ──────────────────────────
LLM_BASE_URL="http://localhost:11434/v1"   # Ollama local, or your provider's /v1 URL
LLM_API_KEY="ollama"                        # any non-empty value for Ollama; real key for cloud
LLM_MODEL="minimax-m3:cloud"

# ── RAG app · Embeddings ────────────────────────────────────────────────
# EMBEDDING_PROVIDER: ollama (local dev) | huggingface (production) | openai
EMBEDDING_PROVIDER="ollama"
EMBEDDING_BASE_URL="http://localhost:11434/v1"
EMBEDDING_API_KEY="ollama"
EMBEDDING_MODEL="bge-m3:latest"             # ต้อง `ollama pull bge-m3` ก่อน

# ── RAG storage & ingestion ───────────────────────────────────────────
CHROMA_DIR="chroma_db"
CHROMA_COLLECTION="modsa_kmutt"
RAG_SOURCE_PATHS="../datasets/chunks"
CHUNK_SIZE="1000"
CHUNK_OVERLAP="150"
RETRIEVAL_K="4"
# RETRIEVAL_MIN_RELEVANCE="0.35"            # optional (reserved)

# ── API server ────────────────────────────────────────────────────────
APP_HOST="127.0.0.1"
APP_PORT="8000"
CORS_ORIGINS="http://localhost:5173,http://127.0.0.1:5173"
ADMIN_API_KEY="change-me"                   # required — /admin/reindex refuses to run without it

# ── DATA pipeline · Typhoon OCR (สำหรับ PDF สแกนเท่านั้น) ──────────────
# ขอ key ที่ https://opentyphoon.ai — ถ้าไม่มี PDF สแกน ปล่อยค่า placeholder ไว้ได้
TYPHOON_OCR_API_KEY="your-typhoon-ocr-key"
```

### `.gitattributes`

Absent.

### `vercel.json`

Absent.

### Relevant backend CORS block (`backend/main.py`)

```python
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.resolved_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Admin-Key"],
)
```

### Relevant origin parsing (`backend/config.py`)

```python
cors_origins: str = Field(
    default="http://localhost:5173,http://127.0.0.1:5173",
    alias="CORS_ORIGINS",
)

@property
def resolved_cors_origins(self) -> list[str]:
    return [item.strip() for item in self.cors_origins.split(",") if item.strip()]
```

### API URL/header/error handling (`frontend/src/services/api.ts`)

```typescript
const configuredApiUrl = (import.meta.env.VITE_API_URL || "").replace(/\/+$/, "");
const API_URL = configuredApiUrl || (import.meta.env.DEV ? "http://localhost:8000" : "");
const DEFAULT_TIMEOUT_MS = 45_000;

response = await fetch(`${API_URL}/chat/ask`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ question: question.trim() }),
  signal: composed.signal,
});
```

### `frontend/vite.config.ts`

```typescript
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    clearMocks: true,
  },
})
```

END OF REPORT
