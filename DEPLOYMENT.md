# MOD-SA deployment runbook: on-prem host, single Nginx site

This runbook deploys the FastAPI backend, embedded ChromaDB and the built
frontend with Docker Compose on the on-prem host. One Nginx container serves the
React build at `/` and proxies `/api/*` to the backend, so the browser sees one
site: `https://modsa.project.cpe.kmutt.ac.th/`.

```text
Browser ─► https://modsa.project.cpe.kmutt.ac.th/
             ▼   (TODO(owner): where TLS terminates, how traffic reaches nginx)
        nginx:80   (static frontend, /api allowlist, rate limits)
             ▼
        backend:8000   (FastAPI + bind-mounted Chroma)
             ▼ outbound HTTPS
        CPE AI Gateway (LLM + embeddings)
```

Tick the boxes as you go. Never paste `LLM_API_KEY`, `EMBEDDING_API_KEY` or
`ADMIN_API_KEY` into chat, Git, tickets or screenshots.

## 1. Prerequisites and approval gate

- [ ] Written approval from KMUTT for: hosting a public service on this VM,
  the documents being served, and use of the gateway key by a public
  application. Do not share the public URL before this.
- [ ] Ubuntu 24.04 host with sudo, outbound HTTPS to Docker Hub, GitHub, the
  npm registry (the Nginx image build runs `npm ci`) and the gateway.
- [ ] Git and OpenSSL installed.

## 2. Install Docker and Compose

The stack needs Docker Engine **and the Compose v2 plugin** (`docker compose`,
with a space).

- [ ] Check what you have: `docker --version` and `docker compose version`.
- [ ] If Docker came from Ubuntu's `docker.io` package and `docker compose`
  fails with `unknown shorthand flag: 'f' in -f` or `unknown command: docker
  compose`, install the plugin: `sudo apt-get update && sudo apt-get install -y docker-compose-v2`
  (optionally `docker-buildx`).
- [ ] Alternatively, install Docker's official packages (`docker-ce`,
  `docker-ce-cli`, `containerd.io`, `docker-buildx-plugin`,
  `docker-compose-plugin`) following Docker's current Ubuntu instructions.
  Remove conflicting `docker.io` packages first.
- [ ] If `docker` reports `permission denied` on `/var/run/docker.sock`, either
  prefix commands with `sudo`, or add yourself to the `docker` group
  (`sudo usermod -aG docker $USER`, then `newgrp docker` or log in again).
  Docker group membership is effectively root on the VM; confirm it is allowed.
  Use one approach consistently.

## 3. Image tags

- [ ] Keep the `nginx`, `node` and `python` tags pinned and re-check them against
  Docker Hub before production. The Nginx image is built locally
  (`nginx/Dockerfile`, tag `modsa-nginx:1.27.3-web`).

## 4. First-time setup on the VM

- [ ] `git clone -b main <repository-url> modsa-deployment && cd modsa-deployment`
- [ ] `cp .env.vm.example .env && chmod 600 .env`
- [ ] Fill in every placeholder:
  - gateway: `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, and the `EMBEDDING_*`
    values (`EMBEDDING_PROVIDER=openai`);
  - `CORS_ORIGINS`: not needed for same-origin use; keep only for other origins;
  - `ADMIN_API_KEY`: generate in the shell with `openssl rand -hex 32` and paste
    the result. Compose does not evaluate `$(...)` inside `.env`;
- [ ] Use the **FIRST BOOT / INDEXING** embedding values (tolerant: for example
  `EMBEDDING_TIMEOUT=60`, `EMBEDDING_MAX_RETRIES=3`), because the first boot
  embeds all chunks through the gateway.
- [ ] `mkdir -p data/chroma && sudo chown 10001:10001 data/chroma && sudo chmod 750 data/chroma`
  (the backend container runs as UID/GID 10001).
- [ ] `docker compose -f docker-compose.yml -f docker-compose.local.yml config > /dev/null && echo CONFIG_OK`

## 5. First boot and health gate

- [ ] Start the backend and Nginx (the first build also compiles the frontend):
  `docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build backend nginx`
  This builds the image and then **waits for the backend health check**
  (`depends_on: service_healthy`). On a first boot with an empty index it can
  take several minutes (start period 600 s). In a second terminal follow
  `docker compose logs -f backend`. If `up` reports the backend unhealthy after
  about 11 minutes, read the logs, wait, and run the same `up -d` again.
- [ ] Startup ingestion runs before the server accepts requests. Look for
  `Indexed chunks ...` lines and then `Startup ingestion: {...}`.
  `Startup ingestion failed` means the container still starts but the index is
  empty; fix `.env` (gateway URL, key, model) and reindex (section 11).
- [ ] `curl -i http://127.0.0.1:8080/nginx-health` returns 200.
- [ ] `curl -i http://127.0.0.1:8080/api/health` returns 200. **HTTP 200 alone
  is not enough**: the app also returns 200 when ingestion failed. Check the
  `ingestion` object: `status` must not be `error`, and `files` should be 71.
  On a restart with unchanged sources it reports
  `{"status":"skipped","reason":"source files unchanged","files":71}`; that
  shape carries no chunk count, so confirm the index with a real question.
- [ ] Ask a real question (section 6) and confirm a sensible Thai answer with a
  non-empty `sources` list.

## 6. Local verification checklist

Run from the VM (`B=http://127.0.0.1:8080`):

- [ ] Chat works and is timed:
  ```bash
  curl -s -w '\nHTTP %{http_code}  %{time_total}s\n' -X POST $B/api/chat/ask \
    -H 'Content-Type: application/json' -d '{"question":"มีทุนการศึกษาอะไรบ้าง"}' | head -c 2000
  ```
- [ ] Frontend: `curl -i $B/` returns 200 with `Content-Type: text/html`; the
  `/assets/*.js` and `*.css` files referenced by `index.html` return
  `text/javascript` and `text/css`; `$B/some/deep/route` returns `index.html`.
- [ ] Allowlist: each of `/api/docs`, `/api/openapi.json`, `/api/admin/reindex`
  returns a JSON **404**, and `POST /api/health` returns 404. Only unknown
  `/api/*` paths return the JSON 404; `/` serves the app. Swagger/ReDoc are
  intentionally unreachable; they exist only inside the container.
- [ ] (Only if a cross-origin client is still used; same-origin needs no CORS.)
  Preflight with an allowed origin returns `access-control-allow-origin`
  with that origin and `access-control-max-age: 7200`:
  ```bash
  curl -i -X OPTIONS $B/api/chat/ask -H 'Origin: https://<allowed-origin>' \
    -H 'Access-Control-Request-Method: POST' \
    -H 'Access-Control-Request-Headers: content-type'
  ```
  A random origin must not get `access-control-allow-origin`.
- [ ] An oversized body (over 16 KiB) returns 413 as JSON with
  `Access-Control-Allow-Origin: *`.
- [ ] Rate limit (run last; it uses the budget for about a minute). Sending `{}`
  costs nothing because the backend answers 422 before any model call:
  ```bash
  for i in $(seq 1 15); do curl -s -o /dev/null -w '%{http_code} ' -X POST $B/api/chat/ask \
    -H 'Content-Type: application/json' -d '{}'; done; echo
  ```
  Per-IP chat limit is 30 requests/minute with burst 10 (nodelay), so expect
  about 11 non-429 responses (422) and then 429s, plus a little refill while the
  loop runs. The global limit is 60/minute with burst 20.

## 7. LLM timeouts and reasoning models

Symptom: `POST /api/chat/ask` returns 500 with a body such as
`{"detail":"Request timed out."}` after about `LLM_TIMEOUT` seconds, and the
backend log shows a successful `POST .../v1/embeddings` but no
`.../chat/completions` line.

Cause on this gateway: `qwen3.8-27b` is a reasoning model. It spends tokens on
hidden reasoning before the answer, so real RAG prompts can exceed 30 s. In a
tiny test with `max_tokens: 20` it returned `content: null`.

Diagnose from inside the container (uses the container's own environment, so no
keys are printed):

```bash
docker compose exec -T backend sh -c '
echo "--- models";  curl -s -m 20 "$LLM_BASE_URL/models" -H "Authorization: Bearer $LLM_API_KEY" | head -c 1500; echo
echo "--- model: $LLM_MODEL"
call() { curl -s -m 150 -o /tmp/r.json -w "HTTP %{http_code}  %{time_total}s\n" "$LLM_BASE_URL/chat/completions" -H "Authorization: Bearer $LLM_API_KEY" -H "Content-Type: application/json" -d "$1"; head -c 700 /tmp/r.json; echo; }
Q="สรุปขั้นตอนการสมัครหอพักนักศึกษาสั้นๆ 3 ข้อ"
echo "=== thinking ON";  call "{\"model\":\"$LLM_MODEL\",\"max_tokens\":1500,\"messages\":[{\"role\":\"user\",\"content\":\"$Q\"}]}"
echo "=== thinking OFF"; call "{\"model\":\"$LLM_MODEL\",\"max_tokens\":1500,\"chat_template_kwargs\":{\"enable_thinking\":false},\"messages\":[{\"role\":\"user\",\"content\":\"$Q\"}]}"
'
```

Measured on this gateway for one short Thai prompt: `qwen3.8-27b` with thinking
on about 8.5 s, with thinking **off** about 5 s; `muse-glimmer-30b` about 22 s.
Single runs on a shared gateway; expect variation.

Options:

- [ ] Use `qwen3.8-27b` with thinking disabled. This needs a backend build that
  supports `LLM_ENABLE_THINKING` (and optionally `LLM_MAX_TOKENS`); both are
  unset by default so existing behavior is unchanged. If your build does not
  have them yet, merge that change first.
- [ ] While measuring, `LLM_TIMEOUT=90` is acceptable, but users will not wait
  that long: the frontend aborts at 45 s. Target a typical answer under about
  25 s.
- [ ] After editing `.env`, run `docker compose up -d`. `restart` does not
  re-read `.env`.

## 8. Timeout budget and steady-state settings

The worst-case time of one chat request is:

```text
EMBEDDING_TIMEOUT x (EMBEDDING_MAX_RETRIES + 1)  +  LLM_TIMEOUT x (LLM_MAX_RETRIES + 1)
```

It must stay below the frontend's 45 s limit. (Nginx waits up to 150 s, so the
frontend limit is the binding one.)

| Profile | Embedding | Emb. retries | LLM | LLM retries | Worst case |
|---|---|---|---|---|---|
| First boot / indexing | 60 s | 3 | 30 s | 0 | 270 s (acceptable only while indexing) |
| Steady state (example) | 8 s | 0 | 30 s | 0 | 38 s |

- [ ] After the first successful health gate, switch `.env` to steady-state
  values and run `docker compose up -d`. The unchanged source manifest means the
  index is not rebuilt.
- [ ] Measure about 10 real questions and fill in the table; adjust the values
  or the model if the slowest answers approach 45 s:
  ```bash
  for i in $(seq 1 10); do curl -sS -o /dev/null -w '%{http_code} %{time_total}\n' \
    $B/api/chat/ask -H 'Content-Type: application/json' -d '{"question":"..."}'; done
  ```

| Request | HTTP | Seconds | Notes |
|---|---:|---:|---|
| 1 | | | |
| 2 | | | |
| 3 | | | |
| 4 | | | |
| 5 | | | |

## 9. Public access and client IP

- [ ] TODO(owner): record how `https://modsa.project.cpe.kmutt.ac.th/` reaches
  the Nginx container (published port, reverse proxy, load balancer) and where
  TLS terminates. `docker-compose.yml` publishes no port for Nginx.
- [ ] TODO(owner): `nginx/nginx.conf` currently trusts `X-Forwarded-For` from
  `172.28.0.0/16` (the Compose network). Set `set_real_ip_from` to the real
  front proxy address. Test from outside:
  `curl -s -o /dev/null https://modsa.project.cpe.kmutt.ac.th/api/health -H 'X-Forwarded-For: 1.2.3.4'`
  then `docker compose logs nginx --tail 5`: the first field must be the
  caller's real address, not `1.2.3.4` (spoofable) and not one shared proxy
  address (all users share one rate-limit bucket).
- [ ] If you recreate the backend container later, run
  `docker compose restart nginx` (Nginx resolves `backend` only at start).

## 10. Legacy fallback: ngrok + Vercel

No longer the main path. The `ngrok` service is kept in `docker-compose.yml`
under profile `tunnel` (`docker compose --profile tunnel up -d`, needs
`NGROK_AUTHTOKEN` and `NGROK_DOMAIN` in `.env`). A Vercel-hosted frontend would
need `VITE_API_URL=https://<NGROK_DOMAIN>/api` at build time and its origin in
`CORS_ORIGINS`. The frontend no longer sends the ngrok browser-warning header,
so ngrok's interstitial page may break browser calls on that path.

## 11. Operations

- Logs: `docker compose logs -f backend`, `docker compose logs nginx --tail 50`.
- Update: `git pull`, then `docker compose up -d --build nginx` (frontend or
  Nginx changes) or `docker compose up -d --build` (everything). Then
  `docker compose restart nginx` if the backend was recreated.
- Rollback: `git checkout <previous-commit>`, then
  `docker compose up -d --build nginx` (rebuilds the frontend from that commit).
- Config changes: edit `.env`, then `docker compose up -d`. Never rely on
  `restart` for env changes.
- Backup: `bash scripts/backup.sh` stops the backend briefly, archives
  `data/chroma` and keeps the newest archives. It re-runs itself with `sudo`.
  Copy archives off the VM; keep `.env` backed up separately and securely. The
  index can always be rebuilt from `data/chunks`, so backups mainly save
  re-embedding time and gateway quota.
- Restore: `sudo bash scripts/restore.sh backups/chroma-<timestamp>.tar.gz`
  moves the old data aside to `data/chroma.bak.<timestamp>`.
- Reindex: `bash scripts/reindex.sh` calls the admin endpoint from inside the
  container (the key never leaves it). It deletes the collection before
  re-embedding, so retrieval is empty and then partial until it finishes, and a
  failure mid-way leaves a partial index. It re-embeds with the current
  `EMBEDDING_*` values: switch to the tolerant first-boot values and run
  `docker compose up -d` first, then back to steady state afterwards.

## 12. Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| `unknown shorthand flag: 'f' in -f` / `unknown command: docker compose` | Compose v2 plugin missing. Install `docker-compose-v2` (section 2). |
| `permission denied ... /var/run/docker.sock` | User not in the `docker` group. Use `sudo` or add the group (section 2). |
| `{"detail":"Request timed out."}` (500) after about `LLM_TIMEOUT` s | Slow or reasoning model. See section 7. |
| Health 200 but answers are generic and `sources` is empty | Startup ingestion failed or the index was built with a different embedding model. Check logs, fix `.env`, run the reindex. |
| Browser shows a CORS error | Origin missing or has a trailing slash in `CORS_ORIGINS`; `.env` changed without `docker compose up -d`; request header not allowed; Nginx error responses are CORS-enabled, so a plain network error usually means the tunnel or backend is down. |
| 429 | Per-IP or global Nginx limit. Campus users behind one NAT share an IP. Tune the numbers at the top of `nginx/nginx.conf`. |
| 413 | Request body over 16 KiB. |
| 502 / 504 from Nginx | Backend down or slow. Nginx returns status 502 with a JSON body for both upstream failure and timeout. After recreating the backend run `docker compose restart nginx`. |
| `permission denied` / `unable to open database file` for Chroma | `sudo chown -R 10001:10001 data/chroma && sudo chmod 750 data/chroma`. |
| `up -d` seems stuck on first boot | It is waiting for the backend health check (up to about 10 minutes). Watch `docker compose logs -f backend`. |
| `/api/docs` returns 404 | Intentional. Nginx blocks Swagger/ReDoc/OpenAPI and `/admin`. |
| `/` serves nothing useful | Stale Nginx image without the frontend. Run `docker compose up -d --build nginx`. |
| `npm ci` fails during the build | Check outbound access to the npm registry and that `.dockerignore` does not exclude `frontend/`. |
| Container OOM-killed or restarting | Backend memory limit is 4 GB; check `docker stats` and the logs. |

## 13. Security summary

- Public surface: the static frontend, plus `GET /api/health` and
  `POST /api/chat/ask` (plus `OPTIONS`). Any other `/api/*` path returns a JSON 404.
- The backend and Chroma have no published ports. `/admin/reindex` is reachable
  only from inside the container through `scripts/reindex.sh`.
- Nginx limits: per-IP chat 30 requests/minute (burst 10), global chat
  60/minute (burst 20), health 60/minute (burst 20), body limit 16 KiB, proxy
  timeouts 10 s connect / 150 s read-send. Client IPs come from
  `X-Forwarded-For` only from the trusted range in `nginx.conf` (TODO(owner), section 9).
- Nginx-generated errors (404, 413, 429, 502, 503, 504) carry
  `Access-Control-Allow-Origin: *` so the browser can show a readable error; the
  backend enforces the exact allowed origins for real responses.
- Keep `.env` at mode 600, rotate keys through the gateway,
  and keep keys out of Git, chat and screenshots.
- The app has no user accounts. KMUTT OAuth2 login is planned and not
  implemented. If restricted documents are added later, put authentication in
  front of the API.

## 14. Later improvements

- Pin dependency versions (record `docker compose exec -T backend pip freeze`
  after a good boot and install from that lock) and pin image tags that exist on
  Docker Hub.
- Check `docker image ls`: `langchain-huggingface` may pull heavy packages even
  when the OpenAI provider is used.
- Raise or make configurable the frontend's 45 s timeout and add user-friendly
  messages for 429, timeouts and network errors.
- Add KMUTT OAuth2 login (needs an approved design first).