# MOD-SA deployment runbook: VM backend + ngrok + Vercel frontend

This runbook deploys the FastAPI backend and embedded ChromaDB on an Ubuntu
24.04 VM with Docker Compose, publishes it through an ngrok static domain, and
serves the frontend from Vercel. Nginx never serves frontend files.

```text
Browser ─► Vercel (static React build)
             │ HTTPS + CORS, absolute URL baked in at build time
             ▼
        ngrok static domain
             ▼
        nginx:80   (route allowlist, rate limits, preflight pass-through)
             ▼
        backend:8000   (FastAPI + bind-mounted Chroma)
             ▼ outbound HTTPS
        CPE AI Gateway (LLM + embeddings)
```

Tick the boxes as you go. Never paste `LLM_API_KEY`, `EMBEDDING_API_KEY`,
`ADMIN_API_KEY` or `NGROK_AUTHTOKEN` into chat, Git, tickets or screenshots.

## 1. Prerequisites and approval gate

- [ ] Written approval from KMUTT for: hosting a public service on this VM,
  the outbound ngrok tunnel, the documents being served, and use of the
  gateway key by a public application. Do not share the public URL before this.
- [ ] Ubuntu 24.04 VM with sudo, outbound HTTPS to Docker Hub, GitHub, ngrok
  (`*.ngrok.com`, `*.ngrok-free.dev`) and the gateway.
- [ ] An ngrok account (ideally owned by a shared project address, not a
  personal one) and a Vercel account with access to the repository.
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

## 3. ngrok account, domain and image tag

- [ ] In the ngrok dashboard open **Domains** and note the free static dev
  domain assigned to the account. Use the bare domain (for example
  `something.ngrok-free.dev`): no `https://`, no path.
- [ ] In the dashboard open **Your Authtoken**. Copy it straight into the VM
  `.env`; never paste it elsewhere.
- [ ] `docker-compose.yml` pins an `ngrok/ngrok:<tag>` image. The tag `3.18.0`
  does not exist on Docker Hub and fails with `not found`. Edit the `ngrok`
  service image to a tag that exists (for example `ngrok/ngrok:latest` while
  testing; pin a verified tag afterwards) and check it with
  `docker run --rm ngrok/ngrok:<tag> --version`. ngrok may refuse very old
  agent versions, so prefer a current one.
- [ ] Keep the `nginx` and `python` tags pinned too, and re-check them against
  Docker Hub before production.

## 4. First-time setup on the VM

- [ ] `git clone -b modsa-vm <repository-url> modsa-deployment && cd modsa-deployment`
- [ ] `cp .env.vm.example .env && chmod 600 .env`
- [ ] Fill in every placeholder:
  - gateway: `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, and the `EMBEDDING_*`
    values (`EMBEDDING_PROVIDER=openai`);
  - `CORS_ORIGINS`: exact origins, comma-separated, no trailing slash (add your
    Vercel origins later, see section 10);
  - `ADMIN_API_KEY`: generate in the shell with `openssl rand -hex 32` and paste
    the result. Compose does not evaluate `$(...)` inside `.env`;
  - `NGROK_AUTHTOKEN` and `NGROK_DOMAIN` (can wait until section 8).
- [ ] Use the **FIRST BOOT / INDEXING** embedding values (tolerant: for example
  `EMBEDDING_TIMEOUT=60`, `EMBEDDING_MAX_RETRIES=3`), because the first boot
  embeds all chunks through the gateway.
- [ ] `mkdir -p data/chroma && sudo chown 10001:10001 data/chroma && sudo chmod 750 data/chroma`
  (the backend container runs as UID/GID 10001).
- [ ] `docker compose -f docker-compose.yml -f docker-compose.local.yml config > /dev/null && echo CONFIG_OK`

## 5. First boot and health gate

- [ ] Start the backend and Nginx (no tunnel yet):
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
- [ ] Allowlist: each of `/`, `/api/docs`, `/api/openapi.json`,
  `/api/admin/reindex` returns **404**, and `POST /api/health` returns 404.
  Swagger/ReDoc are intentionally unreachable; they exist only inside the
  container. `HEAD` requests also return 404 (use GET for uptime monitors).
- [ ] Preflight with an allowed origin returns `access-control-allow-origin`
  with that origin and `access-control-max-age: 7200`:
  ```bash
  curl -i -X OPTIONS $B/api/chat/ask -H 'Origin: https://<allowed-origin>' \
    -H 'Access-Control-Request-Method: POST' \
    -H 'Access-Control-Request-Headers: content-type,ngrok-skip-browser-warning'
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

It must stay below the frontend's 45 s limit. (Nginx waits up to 60 s and ngrok
free endpoints have no idle timeout, so the frontend limit is the binding one.)

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

## 9. Start and verify the tunnel

- [ ] Put `NGROK_AUTHTOKEN` and the bare `NGROK_DOMAIN` in `.env`, then run
  `docker compose --profile tunnel up -d` (ngrok waits for Nginx to be healthy).
- [ ] `docker compose logs ngrok --tail 20` shows the tunnel started. Common
  errors: invalid authtoken; domain not found (must match the dashboard exactly,
  no scheme); another session already using the free endpoint.
- [ ] `curl -i https://<NGROK_DOMAIN>/api/health` returns 200. Repeat from a
  different network, such as a phone on mobile data.
- [ ] **Real-IP spoof test** (do not skip):
  ```bash
  curl -s -o /dev/null https://<NGROK_DOMAIN>/api/health -H 'X-Forwarded-For: 1.2.3.4'
  docker compose logs nginx --tail 5
  ```
  The log format is `<client ip> forwarded=<header> <time> upstream=... <status> "<request>"`.
  The first field must be the caller's real public address. If it is `1.2.3.4`
  the per-IP limit can be bypassed: run `docker compose stop ngrok` and
  investigate before exposing the URL. If it is a `172.28.x.x` address, all
  users would share one rate-limit bucket and real-IP trust is not working.
- [ ] If you recreate the backend container later, run
  `docker compose restart nginx` (Nginx resolves `backend` only at start).

## 10. Vercel

Roll out to **Preview first**, then Production.

- [ ] Import the repository in Vercel. Root Directory `frontend`, Vite preset,
  build `npm run build`, output `dist`. Choose a Node version supported by the
  installed Vite release in the project settings.
- [ ] For the **Preview** environment only, set
  `VITE_API_URL=https://<NGROK_DOMAIN>/api` and
  `VITE_NGROK_SKIP_BROWSER_WARNING=true`. Both are build-time variables: redeploy
  after changing them.
- [ ] Deploy the `modsa-vm` branch. Use the stable branch-alias URL (it contains
  `-git-modsa-vm-`), not the per-deployment URL.
- [ ] On the VM add that exact origin to `CORS_ORIGINS` (no trailing slash,
  comma-separated list), then `docker compose up -d`.
- [ ] Check the preflight through the tunnel with the alias as `Origin`, then
  open the preview in a browser, ask a Thai question and watch DevTools →
  Network for CORS errors.
- [ ] Only after the preview answers real questions: add the same two variables
  to **Production**, add the production origin to `CORS_ORIGINS`, run
  `docker compose up -d`, and redeploy. Note that the ngrok-header change lives
  on `modsa-vm`; merge it before building Production from another branch.
- [ ] Rollback: restore the previous `VITE_API_URL` in Vercel and redeploy.
  Keep the Render deployment available until the new path is proven.

## 11. Operations

- Logs: `docker compose logs -f backend`, `docker compose logs nginx --tail 50`,
  `docker compose logs ngrok --tail 20`.
- Update: `git pull`, then `docker compose up -d --build` (add
  `--profile tunnel` if the tunnel should be (re)created). Then
  `docker compose restart nginx` if the backend was recreated.
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
- ngrok usage: watch the dashboard Usage page. Nginx limits protect the backend
  and the gateway quota, not ngrok's monthly request cap (each chat is a
  preflight plus a POST unless the browser caches the preflight for 2 hours).
- Quick Tunnel-style restarts are not an issue here: the ngrok domain is static.

## 12. Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| `unknown shorthand flag: 'f' in -f` / `unknown command: docker compose` | Compose v2 plugin missing. Install `docker-compose-v2` (section 2). |
| `permission denied ... /var/run/docker.sock` | User not in the `docker` group. Use `sudo` or add the group (section 2). |
| `ngrok/ngrok:<tag>: not found` | The pinned tag does not exist. Change the image tag (section 3). |
| ngrok exits immediately | Check `docker compose logs ngrok`: bad authtoken, wrong `NGROK_DOMAIN` (bare domain only), or endpoint already online elsewhere. |
| `{"detail":"Request timed out."}` (500) after about `LLM_TIMEOUT` s | Slow or reasoning model. See section 7. |
| Health 200 but answers are generic and `sources` is empty | Startup ingestion failed or the index was built with a different embedding model. Check logs, fix `.env`, run the reindex. |
| Browser shows a CORS error | Origin missing or has a trailing slash in `CORS_ORIGINS`; `.env` changed without `docker compose up -d`; request header not allowed; Nginx error responses are CORS-enabled, so a plain network error usually means the tunnel or backend is down. |
| 429 | Per-IP or global Nginx limit. Campus users behind one NAT share an IP. Tune the numbers at the top of `nginx/nginx.conf`. |
| 413 | Request body over 16 KiB. |
| 502 / 504 from Nginx | Backend down or slow. Nginx returns status 502 with a JSON body for both upstream failure and timeout. After recreating the backend run `docker compose restart nginx`. |
| `permission denied` / `unable to open database file` for Chroma | `sudo chown -R 10001:10001 data/chroma && sudo chmod 750 data/chroma`. |
| `up -d` seems stuck on first boot | It is waiting for the backend health check (up to about 10 minutes). Watch `docker compose logs -f backend`. |
| `/docs` returns 404 | Intentional. Nginx blocks Swagger/ReDoc/OpenAPI and `/admin`. |
| Container OOM-killed or restarting | Backend memory limit is 4 GB; check `docker stats` and the logs. |

## 13. Security summary

- Public surface: only `GET /api/health` and `POST /api/chat/ask` (plus
  `OPTIONS`) through Nginx. Everything else returns a JSON 404.
- The backend and Chroma have no published ports. `/admin/reindex` is reachable
  only from inside the container through `scripts/reindex.sh`.
- Nginx limits: per-IP chat 30 requests/minute (burst 10), global chat
  60/minute (burst 20), health 60/minute (burst 20), body limit 16 KiB, proxy
  timeouts 5 s connect / 60 s read-send. Client IPs are taken from
  `X-Forwarded-For` only when the request comes from the Compose network.
- Nginx-generated errors (404, 413, 429, 502, 503, 504) carry
  `Access-Control-Allow-Origin: *` so the browser can show a readable error; the
  backend enforces the exact allowed origins for real responses.
- Keep `.env` at mode 600, rotate keys through the gateway and ngrok dashboards,
  and keep keys out of Git, chat and screenshots.
- The app has no user accounts. If restricted documents are added later, put
  authentication in front of the API.

## 14. Later improvements

- Pin dependency versions (record `docker compose exec -T backend pip freeze`
  after a good boot and install from that lock) and pin image tags that exist on
  Docker Hub.
- Check `docker image ls`: `langchain-huggingface` may pull heavy packages even
  when the OpenAI provider is used.
- Raise or make configurable the frontend's 45 s timeout and add user-friendly
  messages for 429, timeouts and network errors.
- Move from the free ngrok dev domain to a university domain or a named tunnel
  once approved, then update `VITE_API_URL` and `CORS_ORIGINS`.