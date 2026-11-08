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
- [ ] Verify the chosen `ngrok/ngrok:latest` image and `nginx:1.27.3-alpine`
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
- [ ] This waits for the backend health check because Nginx depends on
  `service_healthy`; first boot can take up to the 600-second start period plus
  health checks.
- [ ] In a second terminal, follow progress with
  `docker compose logs -f backend`.
- [ ] If Compose reports the backend unhealthy after about 11 minutes, inspect
  the logs, wait for ingestion to finish, and re-run `docker compose up -d`.
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

## LLM timeouts and reasoning models

The chat gateway can spend the whole token budget on hidden reasoning. Symptoms
include `{"detail":"Request timed out."}` or a response with null content, an
Nginx log with `upstream=30.0x` and status 500, and a backend log showing a
successful `/embeddings` call but no chat completion. The backend now returns
the generic `{"detail":"Internal server error"}` for unexpected failures and
logs the exception server-side.

Run diagnostics inside the backend container so the container's own environment
variables and network are used:

```bash
docker compose exec backend sh -lc '
  curl -fsS "$LLM_BASE_URL/models" -H "Authorization: Bearer $LLM_API_KEY";
  time curl -fsS "$LLM_BASE_URL/chat/completions" \
    -H "Authorization: Bearer $LLM_API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"$LLM_MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"ตอบสั้น ๆ ว่า สวัสดี\"}],\"max_tokens\":20}";
  time curl -fsS "$LLM_BASE_URL/chat/completions" \
    -H "Authorization: Bearer $LLM_API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"$LLM_MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"ตอบสั้น ๆ ว่า สวัสดี\"}],\"max_tokens\":20,\"chat_template_kwargs\":{\"enable_thinking\":false}}"
'
```

Set `LLM_ENABLE_THINKING=false` for the recommended `LLM_MODEL=qwen3.8-27b`
gateway configuration. `LLM_MAX_TOKENS=800` is a reasonable starting cap;
lower values reduce latency but can truncate Thai answers. Both variables are
optional and unset values preserve the existing request behavior. After
changing `.env`, run `docker compose up -d` (not `restart`) so Compose
recreates the backend with the new environment, followed by
`docker compose restart nginx` if the backend was recreated.

### Reading the live logs

Follow backend logs without the noisy health checks:

```bash
docker compose logs -f --tail 100 backend | grep --line-buffered -v 'GET /health'
```

Each chat request logs a line like
`Chat request outcome=ok elapsed=5.012s answer_length=123 source_count=4`,
or an error line with `outcome=error`, elapsed seconds, and the exception class.
Nginx access fields are client IP, `forwarded=`, request time, `upstream=`, and
status. Status 499 means the client closed the connection first.

## Switch to steady state

- [ ] Replace the tolerant embedding values with the STEADY STATE values.
- [ ] Run `docker compose up -d` (not `restart`; restart does not re-read `.env`).
  The unchanged manifest skips re-embedding.
- [ ] Confirm `/api/health` still reports indexed data.

## Start and verify the tunnel

- [ ] `docker compose --profile tunnel up -d`
- [ ] `curl -i https://<assigned-static-dev-domain>/api/health`
- [ ] Test forwarding-header spoof resistance:
  `curl -s https://<assigned-static-dev-domain>/api/health -H
  'X-Forwarded-For: 1.2.3.4'`, then
  `docker compose logs nginx --tail 20`. The first logged field must be the
  caller's real public IP, not `1.2.3.4` and not a `172.28.x.x` address.
  The `forwarded=` column shows the original `X-Forwarded-For` value. If the
  first field is `1.2.3.4`, stop the tunnel with
  `docker compose stop ngrok` and report the issue because per-IP limits can
  be bypassed.
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
  `VITE_NGROK_SKIP_BROWSER_WARNING=true` for Preview only.
- [ ] Deploy the preview and test it at the stable branch-alias URL. Ensure
  that origin is in backend `CORS_ORIGINS`.
- [ ] Only after preview succeeds, set the same variables for Production and
  redeploy. These are build-time variables.
- [ ] Set backend `CORS_ORIGINS` to the exact production origin and stable
  branch-alias preview origin, without trailing slashes, then run
  `docker compose up -d`.
- [ ] Test a known question from the Vercel deployment.

Before production, test rate limiting through the local override:

```bash
for i in $(seq 1 15); do
  curl -s -o /dev/null -w '%{http_code} ' -X POST \
    http://127.0.0.1:8080/api/chat/ask \
    -H 'Content-Type: application/json' -d '{}'
done
```

The empty JSON body gets backend 422 responses without LLM or embedding cost.
With the 30r/m per-IP limit, burst 10, and nodelay, expect roughly 11
non-429 responses before 429s begin, plus any refill while the loop runs. The
global 60r/m/burst-20 limit is not reached by this loop. These requests count
toward the limits for about a minute afterward.

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
| 500/502/504 | Backend health, gateway latency, Nginx/backend logs; frontend receives a generic JSON server error for backend failures |
| Stale backend address | `docker compose restart nginx` after backend recreation |
| Healthy but empty index | Inspect `/api/health` ingestion fields and backend logs |
| Chroma permission denied | `sudo chown 10001:10001 data/chroma` and mode 750 |
| Backend import/startup slow | Wait through the 600-second health start period and inspect ingestion logs |
| ngrok exits or image pull fails | Check the tag on Docker Hub; run `docker run --rm ngrok/ngrok:<tag> --version`; update the Compose tag; ensure `NGROK_DOMAIN` is bare with no scheme |
| HEAD returns 404 | Only GET/OPTIONS health and POST/OPTIONS chat are allowed; configure uptime monitors to use GET |
| Nginx validation | On the VM run `docker run --rm -v "$PWD/nginx/nginx.conf:/etc/nginx/nginx.conf:ro" nginx:1.27.3-alpine nginx -t`; a warning about unresolved `backend` outside Compose is expected, so Compose config and a real `up` are authoritative |

## Scripts

- [ ] `bash scripts/backup.sh` (optional `KEEP=7`)
- [ ] `sudo bash scripts/restore.sh backups/chroma-<timestamp>.tar.gz`
- [ ] `bash scripts/reindex.sh`
- [ ] From `backend/`, run `python -m unittest discover -s tests -p "test_*.py"`.

Backup/restore preserve the old Chroma directory and restore ownership. The
reindex handler is a synchronous `def`, not `async def`, and its blocking
ingestion call runs in FastAPI's sync threadpool. Therefore health and chat can
respond while reindex runs; this is unverified at runtime. Reindex uses the
key already inside the backend container and the current `EMBEDDING_*` values.
Switch to the tolerant FIRST BOOT values and run `docker compose up -d` before
reindexing, then switch back to STEADY STATE and run `docker compose up -d`
again. During reindex the collection is deleted before embeddings are added,
so retrieval is empty first and can be partial if indexing fails.

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
