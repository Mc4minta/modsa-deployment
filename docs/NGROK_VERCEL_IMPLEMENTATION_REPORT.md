# MOD-SA VM + ngrok + Vercel implementation report

## 0. Header

- Branch: `modsa-vm`.
- HEAD: `772448fd39068c3eedb51c161471caf7499a5b7b`.
- Date: 2026-11-08.
- Reference files `docs/reference/STEP2_FIXES_REPORT.md` and
  `docs/reference/DEPLOYMENT_CLOUDFLARE.md` were absent.
- No git commits, stages or pushes were made.

## 1. Summary

Implemented the Ubuntu VM topology with private backend, Nginx allowlist, and
optional ngrok tunnel profile. Added fixed-subnet real-IP trust, preflight
pass-through, rate limits, generic CORS-enabled Nginx errors, and a local
verification override. Updated backend CORS for the ngrok header and gated that
header in frontend chat/health requests. Added VM environment documentation,
backup/restore/reindex scripts, and a Vercel/ngrok runbook. Render configuration
was not edited. Frontend validation passed with 40 tests; backend validation
passed with 8 tests; Compose YAML parsed; Bash syntax passed. Docker, Nginx
binary, and ShellCheck were unavailable.

## 2. File inventory

| File | State | Reason |
|---|---|---|
| `.gitattributes` | Created | LF policy for deployment files |
| `.dockerignore` | Created | Root build-context exclusions |
| `backend/Dockerfile` | Changed | Root context, pinned Python, UID/GID, health gate |
| `docker-compose.yml` | Changed | VM backend/Nginx/tunnel stack |
| `docker-compose.local.yml` | Created | Local Nginx-only port |
| `nginx/nginx.conf` | Created | Allowlist, limits, proxy, errors, logging |
| `.env.vm.example` | Created | VM-only placeholders and timeout profiles |
| `scripts/backup.sh` | Created | Safe Chroma backup and retention |
| `scripts/restore.sh` | Created | Validated restore with move-aside rollback |
| `scripts/reindex.sh` | Created | In-container admin-key reindex |
| `docs/DEPLOYMENT.md` | Created | VM/ngrok/Vercel runbook |
| `README.md` | Changed | Runbook pointer |
| `backend/main.py` | Changed | CORS header and preflight cache |
| `backend/tests/test_cors.py` | Created | Allowed and non-listed origin tests |
| `frontend/src/services/api.ts` | Changed | Gated ngrok header on chat and health |
| `frontend/src/test/api.test.ts` | Changed | Default and enabled header tests |
| `render.yml` | Untouched | Explicitly protected by request |
| `data/` | Untouched | Explicitly protected by request |
| `docs/deployment-plan-free-tier.md` | Untouched | Explicitly protected by request |
| `docs/NGROK_VERCEL_STATUS.md` | Untouched | Previous audit preserved |
| `frontend/package.json` | Untouched | Explicitly protected by request |

## 3. Decisions implemented

- Backend is private on the Compose network; Nginx has no published port in
  the base stack, while `docker-compose.local.yml` publishes only
  `127.0.0.1:8080:80`.
- Public routes are exact `/api/health` (`GET`, `OPTIONS`) and
  `/api/chat/ask` (`POST`, `OPTIONS`). `/`, admin, docs, OpenAPI, and every
  other route return JSON 404.
- OPTIONS is proxied to FastAPI and maps to an empty rate-limit key.
- Chat limits are 30 requests/minute per IP with burst 10 nodelay and
  60 requests/minute globally with burst 20 nodelay. Health is 60/minute per
  IP with burst 20.
- Nginx trusts only `172.28.0.0/16`, uses `X-Forwarded-For`, and logs both
  the resolved client IP and original forwarding header. The ngrok forwarding
  behavior must be verified in deployment logs.
- Nginx does not add CORS to proxied responses. Its generic 404, 413, 429,
  502, 503, and 504 bodies use wildcard CORS because they contain no
  credentials and are generic.
- Proxy timeouts are 5 seconds connect and 60 seconds send/read. The frontend
  remains unchanged at 45 seconds; steady-state values target a 38-second
  worst-case formula.
- Chroma uses bind mount `./data/chroma:/app/chroma_db`; source chunks are
  baked into the image at `/app/data/chunks`.
- Image tags selected are `python:3.12.8-slim-bookworm`,
  `nginx:1.27.3-alpine`, and `ngrok/ngrok:3.18.0`. Verify all tags on Docker
  Hub before deployment.
- `VITE_NGROK_SKIP_BROWSER_WARNING=true` gates the optional request header.
  Default frontend behavior sends no such header.
- Backend runs one Uvicorn worker because synchronous startup ingestion must not
  be duplicated across workers.

## 4. App-code diffs and tests

Backend `backend/main.py` now allows `ngrok-skip-browser-warning` and sets
`max_age=7200`; all other CORS behavior remains unchanged. The new
`backend/tests/test_cors.py` verifies a configured-origin preflight accepts
`content-type,ngrok-skip-browser-warning` and that an unlisted origin is not
allowed.

Frontend `frontend/src/services/api.ts` adds
`ngrok-skip-browser-warning: 1` to chat and health only when the build-time
variable is exactly `"true"`. Tests verify both default omission and enabled
chat/health behavior.

## 5. Verification

| Check | Result | Evidence |
|---|---|---|
| Required branch | PASS | `git branch --show-current` = `modsa-vm` |
| Reference commit | PASS | `git cat-file -t ...` = `commit` |
| Frontend lint | PASS with existing warnings | `npm run check` |
| Frontend typecheck | PASS | `npm run check` |
| Frontend tests | PASS | 7 files, 40 tests |
| Frontend build | PASS | Vite production build completed |
| Backend tests | PASS | `python -m unittest discover -s tests -p "test_*.py"`; 8 tests |
| Default backend discovery | NOT RUN successfully | `python -m unittest discover` finds no tests because the existing tests directory is not a package; targeted discovery above passes |
| Compose YAML | PASS | Python `yaml.safe_load` for both Compose files |
| Bash syntax | PASS | `bash -n` for all three scripts |
| ShellCheck | NOT RUN | Not installed |
| LF check | PASS | CR count 0 for every task-created/changed file |
| Docker Compose config | NOT RUN | Docker unavailable |
| Nginx syntax | NOT RUN | Nginx and Docker unavailable |
| Runtime health/chat | NOT RUN | No containers or app were started |
| Git staging/commit/push | NOT RUN | Prohibited by request |

## 6. Deviations, unfinished items, and recommended changes

### Deviations and unfinished items

- Docker Hub tag existence and ngrok command syntax were not contacted or
  verified from this Windows environment; the runbook explicitly requires
  operator verification.
- Nginx config could not be tested with `nginx -t`.
- Docker Compose health, startup ingestion, tunnel, and real-IP behavior could
  not be exercised.
- The backend test import triggers heavyweight embedding dependencies and takes
  several seconds, but all 8 tests pass.
- Script executable bits remain uncommitted mode `100644`; the report cannot
  stage changes. The pre-commit commands below set them.

### Recommended changes (not made)

- Consider raising or making configurable the frontend 45-second timeout after
  measuring real gateway latency.
- Consider mapping 429, timeout, and network errors to user-friendly localized
  messages instead of the current generic fallback.
- Pin Python dependency versions or commit an operator-generated lock file.
- Run ShellCheck and Nginx/Compose checks on the Ubuntu VM before exposure.
- Reconsider global/per-IP rate numbers after observing campus NAT traffic.

## 7. Open questions

1. What exact ngrok static domain, Vercel production origin, and stable preview
   origin should replace the placeholders?
2. Are the selected image tags available and approved in the VM registry policy?
3. Does the assigned ngrok agent version accept the selected `http --url`
   syntax?
4. What external gateway URL, model names, and secret rotation process are
   approved?
5. Are the expected source counts exactly 71 files and 1,233 chunks on the VM?
6. Should the university later use a named tunnel and university domain?

## 8. Fresh Ubuntu 24.04 commands and Vercel steps

```bash
git clone <repository-url>
cd modsa-deployment
git checkout modsa-vm
cp .env.vm.example .env
chmod 600 .env
mkdir -p data/chroma
sudo chown 10001:10001 data/chroma
sudo chmod 750 data/chroma
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build backend nginx
curl -fsS http://127.0.0.1:8080/nginx-health
curl -i http://127.0.0.1:8080/api/health
docker compose logs backend nginx
# after first-boot health gate and steady-state env edits:
docker compose up -d
docker compose --profile tunnel up -d
curl -i https://<assigned-static-dev-domain>/api/health
bash scripts/backup.sh
bash scripts/reindex.sh
sudo bash scripts/restore.sh backups/chroma-<timestamp>.tar.gz
```

In Vercel, import the repository, set Root Directory to `frontend`, select the
Vite preset, use `npm run build`, use `dist`, choose a Vite-supported Node
version, set `VITE_API_URL=https://<assigned-static-dev-domain>/api` and
`VITE_NGROK_SKIP_BROWSER_WARNING=true` for Production and Preview, then
redeploy. Set backend `CORS_ORIGINS` to exact origins without trailing slashes
and run `docker compose up -d`.

## 9. Pre-commit checklist

- [ ] `git ls-files --eol`
- [ ] Review `git status --short` and `git diff --stat`
- [ ] `git add --renormalize .` (operator action; not run by this task)
- [ ] `git update-index --chmod=+x scripts/*.sh` (operator action)
- [ ] Do not add `docs/reference/`
- [ ] Verify placeholders are replaced only in the untracked/private `.env`
- [ ] Run Docker Compose config and Nginx syntax checks on Ubuntu

## Appendix A

The following appendix is generated from the exact current working-tree
contents. The report file itself is excluded because including a file inside
itself would not be finite. Every other created or changed file is included
verbatim below.

### `.gitattributes`

`````
*.sh text eol=lf
Dockerfile* text eol=lf
*.yml text eol=lf
*.conf text eol=lf
.env*.example text eol=lf
*.md text eol=lf
*.dockerignore text eol=lf
`````

### `.dockerignore`

`````
.git
**/node_modules
frontend
**/.env
**/.env.*
!.env.example
!.env.vm.example
chroma_db
data/chroma
backups
logs
docs
data/raw
data/processed
data/evaluation
data/*.zip
**/__pycache__
**/.pytest_cache
**/.mypy_cache
**/.ruff_cache
**/.venv
**/venv
*.py[cod]
`````

### `backend/Dockerfile`

`````
FROM python:3.12.8-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY data/chunks ./data/chunks

RUN groupadd --gid 10001 appuser \
    && useradd --uid 10001 --gid 10001 --create-home appuser \
    && mkdir -p /app/chroma_db \
    && chown -R 10001:10001 /app
USER 10001:10001

EXPOSE 8000

# Startup ingestion is synchronous; one worker avoids duplicate Chroma work.
HEALTHCHECK --interval=30s --timeout=5s --start-period=600s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
`````

### `docker-compose.yml`

`````
services:
  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
    env_file:
      - .env
    environment:
      CHROMA_DIR: /app/chroma_db
      RAG_SOURCE_PATHS: /app/data/chunks
      APP_HOST: 0.0.0.0
    volumes:
      - ./data/chroma:/app/chroma_db
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      start_period: 600s
      retries: 3
    mem_limit: 2g
    cpus: 2.0
    restart: unless-stopped
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "5"
    networks:
      - modsa

  nginx:
    image: nginx:1.27.3-alpine
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      backend:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "wget -q -O - http://127.0.0.1/nginx-health >/dev/null"]
      interval: 30s
      timeout: 5s
      retries: 3
    mem_limit: 128m
    cpus: 0.5
    restart: unless-stopped
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "5"
    networks:
      - modsa

  ngrok:
    image: ngrok/ngrok:3.18.0
    profiles: ["tunnel"]
    command: ["http", "--url=https://${NGROK_DOMAIN:-}", "nginx:80"]
    environment:
      NGROK_AUTHTOKEN: ${NGROK_AUTHTOKEN:-}
    depends_on:
      nginx:
        condition: service_healthy
    restart: unless-stopped
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "5"
    networks:
      - modsa

networks:
  modsa:
    name: modsa
    ipam:
      config:
        - subnet: 172.28.0.0/16
`````

### `docker-compose.local.yml`

`````
services:
  nginx:
    ports:
      - "127.0.0.1:8080:80"
`````

### `nginx/nginx.conf`

`````
user nginx;
worker_processes auto;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
}

http {
    # Rate policy: chat per-IP 30r/m burst 10 nodelay; global 60r/m burst 20;
    # health per-IP 60r/m burst 20. OPTIONS maps to an empty key and is free.
    limit_req_zone $chat_client_key zone=chat_per_ip:10m rate=30r/m;
    limit_req_zone $chat_global_key zone=chat_global:10m rate=60r/m;
    limit_req_zone $health_client_key zone=health_per_ip:10m rate=60r/m;

    map $request_method $chat_client_key {
        default $binary_remote_addr;
        OPTIONS "";
    }
    map $request_method $chat_global_key {
        default "all-chat";
        OPTIONS "";
    }
    map $request_method $health_client_key {
        default $binary_remote_addr;
        OPTIONS "";
    }

    log_format modsa '$remote_addr forwarded=$http_x_forwarded_for '
                     '$request_time upstream=$upstream_response_time '
                     '$status "$request"';
    access_log /var/log/nginx/access.log modsa;
    error_log /var/log/nginx/error.log warn;

    server {
        listen 80;
        server_tokens off;
        client_max_body_size 16k;
        proxy_connect_timeout 5s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        proxy_intercept_errors on;

        # ngrok forwards the browser IP in X-Forwarded-For; verify this in
        # access logs after deployment. Only the fixed Compose subnet is trusted.
        set_real_ip_from 172.28.0.0/16;
        real_ip_header X-Forwarded-For;
        real_ip_recursive on;

        add_header X-Content-Type-Options nosniff always;

        location = /nginx-health {
            default_type text/plain;
            return 200 "ok\n";
        }

        location = /api/health {
            if ($request_method !~ ^(GET|OPTIONS)$) { return 404; }
            limit_req zone=health_per_ip burst=20 nodelay;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_pass http://backend:8000/health;
        }

        location = /api/chat/ask {
            if ($request_method !~ ^(POST|OPTIONS)$) { return 404; }
            limit_req zone=chat_per_ip burst=10 nodelay;
            limit_req zone=chat_global burst=20 nodelay;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_pass http://backend:8000/chat/ask;
        }

        error_page 404 = @json_404;
        error_page 413 = @json_413;
        error_page 429 = @json_429;
        error_page 502 = @json_502;
        error_page 503 = @json_503;
        error_page 504 = @json_504;

        # These generic, credential-free error bodies may use wildcard CORS.
        location @json_404 {
            default_type application/json;
            add_header Access-Control-Allow-Origin "*" always;
            return 404 '{"detail":"Not found"}';
        }
        location @json_413 {
            default_type application/json;
            add_header Access-Control-Allow-Origin "*" always;
            return 413 '{"detail":"Request body too large"}';
        }
        location @json_429 {
            default_type application/json;
            add_header Access-Control-Allow-Origin "*" always;
            return 429 '{"detail":"Too many requests"}';
        }
        location @json_502 {
            default_type application/json;
            add_header Access-Control-Allow-Origin "*" always;
            return 502 '{"detail":"Bad gateway"}';
        }
        location @json_503 {
            default_type application/json;
            add_header Access-Control-Allow-Origin "*" always;
            return 503 '{"detail":"Service unavailable"}';
        }
        location @json_504 {
            default_type application/json;
            add_header Access-Control-Allow-Origin "*" always;
            return 504 '{"detail":"Gateway timeout"}';
        }
    }
}
`````

### `.env.vm.example`

`````
# VM stack environment. Copy to .env, then chmod 600 .env.
# Never paste real keys, tokens, or domains into chat or commit them.

# --- External OpenAI-compatible gateway ---
LLM_BASE_URL="https://<gateway-host>/v1"
LLM_API_KEY="<gateway-api-key>"
LLM_MODEL="<gateway-chat-model>"
LLM_TIMEOUT="30"
LLM_MAX_RETRIES="0"

# --- Embeddings ---
# Only EMBEDDING_PROVIDER=openai uses EMBEDDING_BASE_URL/API_KEY/TIMEOUT/RETRIES
# in backend/core/embeddings.py.
EMBEDDING_PROVIDER="openai"
EMBEDDING_BASE_URL="https://<gateway-host>/v1"
EMBEDDING_API_KEY="<gateway-api-key>"
EMBEDDING_MODEL="<gateway-embedding-model>"

# FIRST BOOT / INDEXING: use tolerant values while approximately 1,233 chunks
# are embedded in batches of 32. Switch to the steady-state values below after
# the first successful health gate.
EMBEDDING_TIMEOUT="60"
EMBEDDING_MAX_RETRIES="3"

# STEADY STATE: keep the worst-case single-request budget below 45 seconds.
# Formula: EMBEDDING_TIMEOUT x (EMBEDDING_MAX_RETRIES+1) +
#          LLM_TIMEOUT x (LLM_MAX_RETRIES+1)
# The chat path performs one query embedding and one LLM call.
# | profile      | embedding | embedding retries | LLM | LLM retries | formula |
# | first boot   | 60s       | 3                 | 30s | 0           | 270s    |
# | steady state | 8s        | 0                 | 30s | 0           | 38s     |
# EMBEDDING_TIMEOUT="8"
# EMBEDDING_MAX_RETRIES="0"

# --- Chroma and source data ---
CHROMA_DIR="/app/chroma_db"
CHROMA_COLLECTION="modsa_kmutt"
RAG_SOURCE_PATHS="/app/data/chunks"
CHUNK_SIZE="1000"
CHUNK_OVERLAP="150"
RETRIEVAL_K="4"
RETRIEVAL_MIN_RELEVANCE="0.35"

# --- API/admin ---
APP_HOST="0.0.0.0"
APP_PORT="8000"
# Exact browser origins, comma-separated; no trailing slash; no regex support.
CORS_ORIGINS="https://<project>.vercel.app,https://<stable-preview-alias>"
# Generate separately in a shell; Compose does not evaluate $(...) in .env.
# ADMIN_API_KEY="$(openssl rand -hex 32)"
ADMIN_API_KEY="<generate-with-openssl-rand-hex-32>"

# --- Tunnel ---
# Assigned from the ngrok dashboard Domains page.
NGROK_AUTHTOKEN="<ngrok-authtoken>"
NGROK_DOMAIN="<assigned-static-dev-domain>"
`````

### `scripts/backup.sh`

`````
#!/usr/bin/env bash
set -euo pipefail

# The backend is stopped briefly. Chroma is a bind mount owned by 10001:10001.
# The archive contains top-level chroma/ and is verified before retention cleanup.

if [[ ${EUID} -ne 0 ]]; then
    exec sudo -E bash "$0" "$@"
fi

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="$ROOT_DIR/data/chroma"
BACKUP_DIR="${BACKUP_DIR:-$ROOT_DIR/backups}"
KEEP="${KEEP:-7}"
WAS_RUNNING=0
ORIGINAL_USER="${SUDO_USER:-$(id -un)}"
ORIGINAL_GROUP="$(id -gn "$ORIGINAL_USER")"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
ARCHIVE="$BACKUP_DIR/chroma-$STAMP.tar.gz"

restart_backend() {
    if [[ $WAS_RUNNING -eq 1 ]]; then
        docker compose -f "$ROOT_DIR/docker-compose.yml" up -d backend >/dev/null
    fi
}
trap restart_backend EXIT

mkdir -p "$BACKUP_DIR"
if [[ -z "$(docker compose -f "$ROOT_DIR/docker-compose.yml" ps -q --status running backend)" ]]; then
    WAS_RUNNING=0
else
    WAS_RUNNING=1
fi
docker compose -f "$ROOT_DIR/docker-compose.yml" stop backend >/dev/null
tar -czf "$ARCHIVE" -C "$DATA_DIR/.." chroma
tar -tzf "$ARCHIVE" >/dev/null
chown "$ORIGINAL_USER:$ORIGINAL_GROUP" "$ARCHIVE"

mapfile -t old_archives < <(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'chroma-*.tar.gz' -printf '%T@ %p\n' | sort -rn | awk '{print $2}')
if (( ${#old_archives[@]} > KEEP )); then
    printf '%s\n' "${old_archives[@]:KEEP:}" | xargs -r rm -f --
fi
echo "Created $ARCHIVE"
`````

### `scripts/restore.sh`

`````
#!/usr/bin/env bash
set -euo pipefail

# Restores an archive containing top-level chroma/. The old directory is moved
# aside, never recursively deleted. The backend is restarted only if it ran.

if [[ ${EUID} -ne 0 ]]; then
    exec sudo -E bash "$0" "$@"
fi
if [[ $# -ne 1 ]]; then
    echo "Usage: sudo bash scripts/restore.sh backups/chroma-<timestamp>.tar.gz" >&2
    exit 2
fi

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="$ROOT_DIR/data/chroma"
ARCHIVE="$(realpath -- "$1")"
TMP_DIR="$(mktemp -d)"
WAS_RUNNING=0

cleanup() {
    rm -rf -- "$TMP_DIR"
    if [[ $WAS_RUNNING -eq 1 ]]; then
        docker compose -f "$ROOT_DIR/docker-compose.yml" up -d backend >/dev/null || true
    fi
}
trap cleanup EXIT

[[ -f "$ARCHIVE" ]] || { echo "Archive not found: $ARCHIVE" >&2; exit 1; }
tar -tzf "$ARCHIVE" | grep -Eq '^chroma(/|$)' || {
    echo "Archive must contain top-level chroma/" >&2
    exit 1
}
if [[ -n "$(docker compose -f "$ROOT_DIR/docker-compose.yml" ps -q --status running backend)" ]]; then
    WAS_RUNNING=1
fi
docker compose -f "$ROOT_DIR/docker-compose.yml" stop backend >/dev/null
tar -xzf "$ARCHIVE" -C "$TMP_DIR"
mkdir -p "$ROOT_DIR/data"
if [[ -d "$DATA_DIR" ]]; then
    mv -- "$DATA_DIR" "$ROOT_DIR/data/chroma.bak.$(date -u +%Y%m%dT%H%M%SZ)"
fi
mv -- "$TMP_DIR/chroma" "$DATA_DIR"
chown -R 10001:10001 "$DATA_DIR"
chmod 750 "$DATA_DIR"
echo "Restored $ARCHIVE; previous data was moved aside."
`````

### `scripts/reindex.sh`

`````
#!/usr/bin/env bash
set -euo pipefail

# POST /admin/reindex deletes the Chroma collection before re-embedding. Chat
# and health remain reachable during the operation, but retrieval is empty
# first, then partial, if indexing fails; the manifest is saved only on success.
# The key is expanded inside the container and is never a command-line argument.

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if ! RESPONSE="$(
    docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T backend \
        sh -c 'curl --fail-with-body --silent --show-error --max-time 900 \
          -X POST http://127.0.0.1:8000/admin/reindex \
          -H "X-Admin-Key: ${ADMIN_API_KEY}"'
)"; then
    echo "Reindex failed; inspect backend logs and /health." >&2
    exit 1
fi
printf '%s\n' "$RESPONSE"
`````

### `docs/DEPLOYMENT.md`

`````
# MOD-SA VM + ngrok + Vercel deployment

This runbook deploys the FastAPI backend and embedded ChromaDB on Ubuntu 24.04.
The public path is `ngrok -> nginx -> backend`; Vercel hosts the frontend and
Nginx never serves frontend files.

```text
Vercel browser
    │ HTTPS + CORS
    ▼
ngrok static dev domain
    ▼
nginx:80  (allowlist, CORS preflight pass-through, limits)
    ▼
backend:8000  (FastAPI + bind-mounted Chroma)
```

## Prerequisites and approval gate

- [ ] Obtain KMUTT approval for the VM, public tunnel, data classification,
  external LLM/embedding gateway, and operational owners.
- [ ] Ubuntu 24.04 VM, SSH access, DNS/network egress, and a non-root operator.
- [ ] Docker Engine and Compose plugin installed from Docker's official guide.
- [ ] Git and OpenSSL installed.
- [ ] A Vercel account and the repository available to the project.
- [ ] Do not paste `LLM_API_KEY`, `EMBEDDING_API_KEY`, `ADMIN_API_KEY`, or
  `NGROK_AUTHTOKEN` into chat, Git, screenshots, or the report.

## Install Docker on Ubuntu 24.04

- [ ] Follow the official Docker Engine Ubuntu instructions for the current
  stable repository and Compose plugin.
- [ ] Confirm `docker version` and `docker compose version`.
- [ ] Add the operator to the `docker` group only if approved:
  `sudo usermod -aG docker "$USER"`; reconnect after changing groups.

## Create the ngrok account and domain

- [ ] Create/sign in to the ngrok account.
- [ ] In the dashboard open **Domains**, record the assigned free static dev
  domain as `<assigned-static-dev-domain>` and set `NGROK_DOMAIN` to that value.
- [ ] In the dashboard open **Your Authtoken**, copy it directly into the VM
  `.env`; never paste it into chat or commit it.
- [ ] Verify the chosen `ngrok/ngrok:3.18.0` image and `nginx:1.27.3-alpine`
  tag on Docker Hub before production use. The Compose command uses ngrok's
  `http --url=https://DOMAIN nginx:80` syntax; confirm it against the current
  image help output.

## First-time setup

- [ ] Clone the repository and check out `modsa-vm`.
- [ ] `cp .env.vm.example .env`
- [ ] Edit every placeholder, including the exact Vercel origins.
- [ ] Generate the admin key separately:
  `openssl rand -hex 32`; put the result in `.env` (do not use `$(...)` in
  `.env`, because Compose does not evaluate shell substitutions).
- [ ] `chmod 600 .env`
- [ ] `mkdir -p data/chroma`
- [ ] `sudo chown 10001:10001 data/chroma`
- [ ] `sudo chmod 750 data/chroma`
- [ ] Run `docker compose -f docker-compose.yml -f docker-compose.local.yml
  up -d --build backend nginx`.
- [ ] Use the FIRST BOOT / INDEXING values in `.env.vm.example`. Startup
  ingestion runs before the backend accepts requests.

## Local verification and first-boot health gate

- [ ] `curl -fsS http://127.0.0.1:8080/nginx-health`
- [ ] `curl -i http://127.0.0.1:8080/api/health`
- [ ] Check the JSON's `ingestion.status`, `files`, and `chunks`; HTTP 200 alone
  is not sufficient because the app intentionally returns 200 when ingestion
  failed. Expected prepared-data counts are 71 files and 1,233 chunks; the
  `Indexed chunks X-Y / Z` log reports chunk progress and the final health
  object reports `files` and `chunks`.
- [ ] `curl -i -X POST http://127.0.0.1:8080/api/chat/ask -H
  'Content-Type: application/json' --data '{"question":"..."}'`
- [ ] Confirm allowlist behavior:
  `curl -i http://127.0.0.1:8080/`,
  `curl -i http://127.0.0.1:8080/api/docs`,
  `curl -i -X POST http://127.0.0.1:8080/api/health`.
- [ ] Confirm preflight:
  `curl -i -X OPTIONS http://127.0.0.1:8080/api/chat/ask -H
  'Origin: https://<project>.vercel.app' -H
  'Access-Control-Request-Method: POST' -H
  'Access-Control-Request-Headers: content-type,ngrok-skip-browser-warning'`
- [ ] Test an error path, such as a request over 16 KiB, and confirm the JSON
  response includes `Access-Control-Allow-Origin: *`.
- [ ] Inspect `docker compose logs backend`; startup success is logged as
  `Startup ingestion: ...`, failure as `Startup ingestion failed`.

## Switch to steady state

- [ ] Replace the tolerant embedding values with the STEADY STATE values.
- [ ] Run `docker compose up -d` (not `restart`; restart does not re-read `.env`).
  The unchanged manifest skips re-embedding.
- [ ] Confirm `/api/health` still reports indexed data.

## Start and verify the tunnel

- [ ] `docker compose --profile tunnel up -d`
- [ ] `curl -i https://<assigned-static-dev-domain>/api/health`
- [ ] Inspect `docker compose logs nginx`; the access log includes
  `$remote_addr`, `$http_x_forwarded_for`, `$request_time`, and
  `$upstream_response_time`. The real client address must not be a
  `172.28.x.x` container address. If the backend container is recreated,
  restart Nginx because `backend:8000` is resolved at Nginx startup:
  `docker compose restart nginx`.

## Vercel setup

- [ ] Import the repository in Vercel.
- [ ] Set Root Directory to `frontend`.
- [ ] Select the Vite preset.
- [ ] Build command: `npm run build`; output directory: `dist`.
- [ ] Choose a Node version supported by the current Vite release in the Vercel
  project settings.
- [ ] Set `VITE_API_URL=https://<assigned-static-dev-domain>/api` and
  `VITE_NGROK_SKIP_BROWSER_WARNING=true` for Production and Preview.
- [ ] Redeploy after changing either variable; both are build-time variables.
- [ ] Set backend `CORS_ORIGINS` to the exact production origin and stable
  branch-alias preview origin, without trailing slashes, then run
  `docker compose up -d`.
- [ ] Test a known question from the Vercel deployment.

## Switch-over and rollback

- [ ] Keep the existing Render deployment available during the cutover.
- [ ] Switch over by deploying Vercel with the ngrok `VITE_API_URL`.
- [ ] Roll back by restoring the previous `VITE_API_URL` in Vercel and
  redeploying.

## Limits, latency, and operations

ngrok's free dashboard currently reports approximately 20,000 requests and 1 GB
per month; verify current values in the Usage page. Each chat normally uses a
preflight plus POST unless the browser caches the preflight. Nginx's limits
protect the backend and LLM quota, not ngrok's monthly quota.

Measure about ten questions:

```bash
for i in $(seq 1 10); do
  curl -sS -o /dev/null -w '%{http_code} %{time_total}\n' \
    https://<assigned-static-dev-domain>/api/chat/ask \
    -H 'Content-Type: application/json' --data '{"question":"..."}'
done
```

| Request | HTTP code | Total seconds | Notes |
|---|---:|---:|---|
| 1 | | | |
| 2 | | | |
| 3 | | | |
| 4 | | | |
| 5 | | | |
| 6 | | | |
| 7 | | | |
| 8 | | | |
| 9 | | | |
| 10 | | | |

The frontend aborts after 45 seconds. Nginx waits about 60 seconds; ngrok has
no configured idle timeout here. The steady-state formula in `.env.vm.example`
must remain below 45 seconds.

## Troubleshooting

| Symptom | Check |
|---|---|
| CORS failure | Exact origin, no trailing slash, allowed request headers, and no ngrok interstitial |
| 429 | Nginx per-IP/global limits; campus NAT can share one IP |
| 413 | Request exceeds the 16 KiB Nginx body limit |
| 502/504 | Backend health, gateway latency, Nginx logs; frontend receives a readable JSON server error |
| Stale backend address | `docker compose restart nginx` after backend recreation |
| Healthy but empty index | Inspect `/api/health` ingestion fields and backend logs |
| Chroma permission denied | `sudo chown 10001:10001 data/chroma` and mode 750 |
| Backend import/startup slow | Wait through the 600-second health start period and inspect ingestion logs |

## Scripts

- [ ] `bash scripts/backup.sh` (optional `KEEP=7`)
- [ ] `sudo bash scripts/restore.sh backups/chroma-<timestamp>.tar.gz`
- [ ] `bash scripts/reindex.sh`

Backup/restore preserve the old Chroma directory and restore ownership. Reindex
uses the key already inside the backend container. During reindex the collection
is deleted before embeddings are added: health and chat remain reachable, but
retrieval is empty or partial if the operation fails.

## Post-first-boot and security

- [ ] Record `pip freeze` from the backend image into a lock file that an
  operator may commit later.
- [ ] Check `docker image ls` size; `langchain-huggingface` can pull heavy
  dependencies even when the VM uses the OpenAI provider.
- [ ] Verify pinned image tags on Docker Hub.
- [ ] Keep `.env` mode 600, rotate keys through the gateway/ngrok dashboards,
  and expose only the Nginx tunnel.
- [ ] Keep `/api/admin/*` blocked publicly; use the in-container-key script.
- [ ] Later, migrate the free dev domain to a university domain or ngrok Named
  Tunnel after approval.
`````

### `README.md`

`````
# MOD-SA

KMUTT Student Affairs RAG chatbot.

## Structure

- `backend/`: FastAPI RAG backend (active)
- `backend_old/`: previous monolithic backend, reference only
- `datasets/chunks/`: prepared knowledge source consumed by `backend/`
- `frontend/`: Web client
- `docs/`: Architecture + development guides (`backend-structure.md`, `development-guide.md`)
- `.agents/skills/modsa-backend/`: Agent skill for backend work

## Quick Start (local)

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit keys / models as needed
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

API:

- `GET /health`
- `POST /chat/ask` — body `{"question":"..."}`
- `POST /admin/reindex` — requires header `X-Admin-Key` matching `ADMIN_API_KEY`

VM/ngrok + Vercel deployment: see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

Default `RAG_SOURCE_PATHS` points at `../datasets/chunks`.

## Docker

From repo root (requires `.env`):

```bash
cp .env.example .env
docker compose up --build
```

Chroma persists in the `chroma_data` volume. Chunks mount from `datasets/chunks`.
`````

### `backend/main.py`

`````
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.admin import router as admin_router
from api.chat import router as chat_router
from api.health import router as health_router
from config import get_settings
from services.ingestion_service import ingest_sources


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    try:
        app.state.ingestion = ingest_sources(settings)
        logger.info("Startup ingestion: %s", app.state.ingestion)
    except Exception:
        logger.exception("Startup ingestion failed")
        app.state.ingestion = {
            "status": "error",
            "reason": "startup ingestion failed",
        }
    yield


app = FastAPI(
    title="MOD-SA RAG API",
    description="KMUTT Student Affairs RAG chatbot",
    version="0.1.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.resolved_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Admin-Key", "ngrok-skip-browser-warning"],
    max_age=7200,
)

app.include_router(chat_router)
app.include_router(health_router)
app.include_router(admin_router)
`````

### `backend/tests/test_cors.py`

`````
import unittest

from fastapi.testclient import TestClient

from main import app


class CorsTests(unittest.TestCase):
    def test_preflight_allows_ngrok_header_for_configured_origin(self):
        with TestClient(app) as client:
            response = client.options(
                "/chat/ask",
                headers={
                    "Origin": "http://localhost:5173",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": (
                        "content-type,ngrok-skip-browser-warning"
                    ),
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            "http://localhost:5173",
        )
        self.assertIn(
            "ngrok-skip-browser-warning",
            response.headers["access-control-allow-headers"],
        )
        self.assertEqual(response.headers["access-control-max-age"], "7200")

    def test_preflight_rejects_non_listed_origin(self):
        with TestClient(app) as client:
            response = client.options(
                "/chat/ask",
                headers={
                    "Origin": "https://not-configured.example",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "content-type",
                },
            )

        self.assertNotEqual(
            response.headers.get("access-control-allow-origin"),
            "https://not-configured.example",
        )


if __name__ == "__main__":
    unittest.main()
`````

### `frontend/src/services/api.ts`

`````
/**
 * API client for the backend chat contract.
 *
 * The caller owns request identity and cancellation. This module deliberately
 * does not keep a module-global AbortController, so one request cannot clear
 * or abort another request by accident.
 */
import type { AskQuestionResponse, Source } from "../types";

const configuredApiUrl = (import.meta.env.VITE_API_URL || "").replace(/\/+$/, "");
const API_URL = configuredApiUrl || (import.meta.env.DEV ? "http://localhost:8000" : "");
const DEFAULT_TIMEOUT_MS = 45_000;
const MAX_ANSWER_LENGTH = 100_000;
const NGROK_SKIP_BROWSER_WARNING = import.meta.env.VITE_NGROK_SKIP_BROWSER_WARNING === "true";

export type ApiErrorCode =
  | "UNKNOWN"
  | "VALIDATION"
  | "AUTH"
  | "RATE_LIMIT"
  | "HTTP"
  | "SERVER"
  | "TIMEOUT"
  | "ABORT"
  | "NETWORK"
  | "MALFORMED";

export interface ApiErrorOptions {
  code?: ApiErrorCode;
  status?: number | null;
  details?: unknown;
  cause?: unknown;
}

export class ApiError extends Error {
  code: ApiErrorCode;
  status: number | null;
  details: unknown;

  constructor(message: string, { code = "UNKNOWN", status = null, details = null, cause }: ApiErrorOptions = {}) {
    super(message, cause !== undefined ? { cause } : undefined);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

function getErrorDetail(body: unknown): string {
  if (!body) return "";
  if (typeof body === "string") return body.slice(0, 500);
  if (isPlainObject(body)) {
    if (typeof body.detail === "string") return body.detail.slice(0, 500);
    if (Array.isArray(body.detail)) return "Validation failed";
    if (typeof body.message === "string") return body.message.slice(0, 500);
  }
  return "";
}

function errorForStatus(status: number, body: unknown): ApiError {
  const detail = getErrorDetail(body);
  if (status === 400 || status === 422) {
    return new ApiError(detail || "The request was not valid.", {
      code: "VALIDATION",
      status,
      details: body,
    });
  }
  if (status === 401 || status === 403) {
    return new ApiError(detail || "The request is not authorized.", {
      code: "AUTH",
      status,
      details: body,
    });
  }
  if (status === 429) {
    return new ApiError(detail || "Too many requests. Please try again later.", {
      code: "RATE_LIMIT",
      status,
      details: body,
    });
  }
  return new ApiError(detail || `The server returned ${status}.`, {
    code: status >= 500 ? "SERVER" : "HTTP",
    status,
    details: body,
  });
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

export function isSafeUrl(value: unknown): boolean {
  if (typeof value !== "string" || !value.trim()) return false;
  try {
    const origin = typeof window !== "undefined" ? window.location.origin : "http://localhost";
    const url = new URL(value, origin);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

export function normalizeSource(source: unknown, index: number = 0): Source | null {
  if (!isPlainObject(source)) return null;

  const normalized: Source = {
    title: typeof source.title === "string" ? source.title.slice(0, 300) : "",
    source: typeof source.source === "string" ? source.source.slice(0, 500) : "",
    department:
      typeof source.department === "string" ? source.department.slice(0, 200) : "",
    page: typeof source.page === "number" || typeof source.page === "string" ? source.page : "",
    url: isSafeUrl(source.url) ? (source.url as string) : "",
    id: typeof source.id === "string" ? source.id.slice(0, 160) : `source-${index + 1}`,
  };

  return normalized.title || normalized.source || normalized.url || normalized.department
    ? normalized
    : null;
}

export function normalizeChatResponse(data: unknown): AskQuestionResponse {
  if (!isPlainObject(data) || typeof data.answer !== "string") {
    throw new ApiError("The server returned an invalid answer.", {
      code: "MALFORMED",
      details: data,
    });
  }

  if (data.answer.length > MAX_ANSWER_LENGTH) {
    throw new ApiError("The server returned an oversized answer.", {
      code: "MALFORMED",
      details: { length: data.answer.length },
    });
  }

  if (data.sources !== undefined && !Array.isArray(data.sources)) {
    throw new ApiError("The server returned invalid source data.", {
      code: "MALFORMED",
      details: data,
    });
  }

  return {
    answer: data.answer,
    sources: ((data.sources as unknown[]) || [])
      .slice(0, 100)
      .map((source, index) => normalizeSource(source, index))
      .filter((source): source is Source => source !== null),
  };
}

interface ComposedSignal {
  signal: AbortSignal;
  wasTimedOut: () => boolean;
  cleanup: () => void;
}

function composeAbortSignal(signal: AbortSignal | undefined, timeoutMs: number): ComposedSignal {
  const controller = new AbortController();
  let timedOut = false;
  let timeoutId: ReturnType<typeof setTimeout> | null = null;

  const abortFromCaller = () => controller.abort(signal?.reason);
  if (signal) {
    if (signal.aborted) abortFromCaller();
    else signal.addEventListener("abort", abortFromCaller, { once: true });
  }

  if (timeoutMs > 0) {
    timeoutId = setTimeout(() => {
      timedOut = true;
      controller.abort("timeout");
    }, timeoutMs);
  }

  return {
    signal: controller.signal,
    wasTimedOut: () => timedOut,
    cleanup: () => {
      if (timeoutId) clearTimeout(timeoutId);
      signal?.removeEventListener("abort", abortFromCaller);
    },
  };
}

export interface AskQuestionOptions {
  signal?: AbortSignal;
  timeoutMs?: number;
}

export async function askQuestion(
  question: string,
  { signal, timeoutMs = DEFAULT_TIMEOUT_MS }: AskQuestionOptions = {}
): Promise<AskQuestionResponse> {
  if (typeof question !== "string" || !question.trim()) {
    throw new ApiError("Question cannot be empty.", { code: "VALIDATION", status: 422 });
  }

  const composed = composeAbortSignal(signal, timeoutMs);
  try {
    let response: Response;
    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (NGROK_SKIP_BROWSER_WARNING) headers["ngrok-skip-browser-warning"] = "1";
      response = await fetch(`${API_URL}/chat/ask`, {
        method: "POST",
        headers,
        body: JSON.stringify({ question: question.trim() }),
        signal: composed.signal,
      });
    } catch (error) {
      if (composed.wasTimedOut()) {
        throw new ApiError("The request timed out.", { code: "TIMEOUT", cause: error });
      }
      if (composed.signal.aborted) {
        throw new ApiError("The request was cancelled.", { code: "ABORT", cause: error });
      }
      throw new ApiError("Unable to reach the server.", { code: "NETWORK", cause: error });
    }

    let body: unknown = null;
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      try {
        body = await response.json();
      } catch (error) {
        if (!response.ok) body = null;
        else {
          throw new ApiError("The server returned invalid JSON.", {
            code: "MALFORMED",
            status: response.status,
            cause: error,
          });
        }
      }
    } else {
      const text = await response.text();
      body = text ? { detail: text } : null;
    }

    if (!response.ok) throw errorForStatus(response.status, body);
    return normalizeChatResponse(body);
  } finally {
    composed.cleanup();
  }
}

/** Backward-compatible no-op. Cancellation is now owned by the chat hook. */
export function cancelRequest(): boolean {
  return false;
}

export async function checkHealth({ signal, timeoutMs = 10_000 }: AskQuestionOptions = {}): Promise<boolean> {
  const composed = composeAbortSignal(signal, timeoutMs);
  try {
    const headers: Record<string, string> = {};
    if (NGROK_SKIP_BROWSER_WARNING) headers["ngrok-skip-browser-warning"] = "1";
    const response = await fetch(`${API_URL}/health`, { headers, signal: composed.signal });
    return response.ok;
  } catch {
    return false;
  } finally {
    composed.cleanup();
  }
}

export { API_URL, DEFAULT_TIMEOUT_MS };
`````

### `frontend/src/test/api.test.ts`

`````
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  askQuestion,
  normalizeChatResponse,
  normalizeSource,
} from "../services/api";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

let fetchMock: ReturnType<typeof vi.fn>;

describe("chat API contract", () => {
  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("normalizes answers and removes unsafe or empty sources", () => {
    const result = normalizeChatResponse({
      answer: "Grounded answer",
      sources: [
        { title: "Handbook", url: "https://example.com/handbook" },
        { title: "Unsafe", url: "javascript:alert(1)" },
        null,
        {},
      ],
    });

    expect(result).toEqual({
      answer: "Grounded answer",
      sources: [
        {
          title: "Handbook",
          source: "",
          department: "",
          page: "",
          url: "https://example.com/handbook",
          id: "source-1",
        },
        {
          title: "Unsafe",
          source: "",
          department: "",
          page: "",
          url: "",
          id: "source-2",
        },
      ],
    });
    expect(normalizeSource({ title: "", source: "" })).toBeNull();
  });

  it("rejects malformed successful responses", () => {
    expect(() => normalizeChatResponse({ sources: [] })).toThrowError(ApiError);
    expect(() => normalizeChatResponse({ answer: "ok", sources: {} })).toThrowError(
      expect.objectContaining({ code: "MALFORMED" })
    );
  });

  it.each([
    [422, "VALIDATION"],
    [429, "RATE_LIMIT"],
    [500, "SERVER"],
  ])("maps HTTP %s to a typed error", async (status: number, code: string) => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: `error-${status}` }, status));

    await expect(askQuestion("question")).rejects.toMatchObject({ code, status });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/chat/ask"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ question: "question" }),
      })
    );
  });

  it("does not send the optional ngrok header by default", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ answer: "ok", sources: [] }));

    await askQuestion("question");

    const [, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(options.headers).toEqual({ "Content-Type": "application/json" });
  });

  it("sends the optional ngrok header on chat and health when enabled", async () => {
    vi.stubEnv("VITE_NGROK_SKIP_BROWSER_WARNING", "true");
    vi.resetModules();
    const api = await import("../services/api");
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ answer: "ok", sources: [] }))
      .mockResolvedValueOnce(new Response("", { status: 200 }));

    await api.askQuestion("question");
    await api.checkHealth();

    expect(fetchMock.mock.calls[0][1].headers).toEqual({
      "Content-Type": "application/json",
      "ngrok-skip-browser-warning": "1",
    });
    expect(fetchMock.mock.calls[1][1].headers).toEqual({
      "ngrok-skip-browser-warning": "1",
    });
  });

  it("maps caller cancellation to ABORT and timeout to TIMEOUT", async () => {
    fetchMock.mockImplementation((_: RequestInfo | URL, options: RequestInit & { signal: AbortSignal }) => new Promise((resolve, reject) => {
      options.signal.addEventListener("abort", () => {
        reject(Object.assign(new Error("aborted"), { name: "AbortError" }));
      });
      void resolve;
    }));

    const caller = new AbortController();
    const cancelled = askQuestion("cancel me", { signal: caller.signal, timeoutMs: 100 });
    caller.abort();
    await expect(cancelled).rejects.toMatchObject({ code: "ABORT" });

    vi.useFakeTimers();
    const timedOut = expect(
      askQuestion("time out", { timeoutMs: 5 })
    ).rejects.toMatchObject({ code: "TIMEOUT" });
    await vi.advanceTimersByTimeAsync(6);
    await timedOut;
  });
});
`````

