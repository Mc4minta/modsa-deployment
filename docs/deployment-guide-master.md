# MOD-SA Deployment Guide — Master (Single Source of Truth)

Supersedes as the entry point: [deployment-guide.md](deployment-guide.md), [deployment-plan-free-tier.md](deployment-plan-free-tier.md), [deployment-plan-ngrok.md](deployment-plan-ngrok.md), [cloudflare-guide.md](cloudflare-guide.md), [ollama-bgem3-cloudflare-tunnel-guide.md](ollama-bgem3-cloudflare-tunnel-guide.md). Those files stay as detailed reference/research but this doc is where you start and pick a path.

**Fixed choices, all paths:**
- Backend: `backend/` (FastAPI, Docker) on **Render**, Free instance type + **UptimeRobot** ping to fight cold starts.
- Frontend: `frontend/` (Vite + React) on **Vercel**.
- LLM: Ollama Cloud (MiniMax), same on every path.

**Variable choice — pick one path below:**

```
Backend on Render (Free) + UptimeRobot
│
├── 1. No persistent disk (default — Chroma rebuilt from datasets/chunks every boot)
│   ├── 1a. Embeddings: Hugging Face Inference API   ← simplest, recommended default
│   ├── 1b. Embeddings: local Ollama + Cloudflare Tunnel (stable hostname, needs owned domain)
│   └── 1c. Embeddings: local Ollama + ngrok static domain (no domain needed)
│
└── 2. Persistent disk (Render Starter tier, $7/mo — not actually free, see §6)
```

Everything shares §1–3 and §7–9. Only §4/§5 (embeddings) or §6 (disk) changes per path.

---

## 1. Prerequisites (all paths)

- Repo pushed to GitHub.
- Ollama Cloud account + API key (LLM, all paths use this).
- `backend/Dockerfile` builds from **repo root** (not `backend/`), copies `datasets/chunks` alongside app code:
  ```
  COPY backend/requirements.txt .
  COPY backend/ .
  COPY datasets/chunks ./datasets/chunks
  ```
  Confirm this before deploying — Docker build context in §2 depends on it.
- Pick your embedding path now (§5) — you'll need its credentials/tools ready before filling Render env vars in §2.

---

## 2. Backend on Render — common setup

1. [dashboard.render.com](https://dashboard.render.com) → log in (free, no card needed for Free instance type).
2. **New +** → **Web Service** → connect your GitHub repo (grant Render access if not listed yet).
3. Config form:
   - **Name**: `modsa-backend`
   - **Language**: **Docker** (not Python 3 — this unlocks the Dockerfile fields below)
   - **Branch**: your deploy branch (e.g. `main`)
   - **Region**: nearest your users (e.g. Singapore)
   - **Root Directory**: leave **blank**
   - **Dockerfile Path**: `backend/Dockerfile`
   - **Docker Build Context Directory**: `.`
4. **Instance Type** → **Free**.
5. **Environment Variables** — add the common set now (embedding-specific vars come from §5 depending on path):
   ```
   CHROMA_DIR=/app/chroma_db
   CHROMA_COLLECTION=modsa_kmutt
   RAG_SOURCE_PATHS=/app/datasets/chunks
   CHUNK_SIZE=1000
   CHUNK_OVERLAP=150
   RETRIEVAL_K=4

   LLM_BASE_URL=https://ollama.com/v1
   LLM_API_KEY=<your Ollama Cloud key>
   LLM_MODEL=minimax-m3:cloud
   LLM_TIMEOUT=30
   LLM_MAX_RETRIES=2

   CORS_ORIGINS=<leave blank for now, fill after §7>
   ADMIN_API_KEY=<generate a random string, e.g. openssl rand -hex 32>
   ```
6. **Health Check Path**: `/health`.
7. **Create Web Service**. First build takes a few minutes — watch **Logs** tab.
8. Once live, copy the service URL (`https://modsa-backend-xxxx.onrender.com`) — needed for §3, §5, §7.

Now go configure embeddings (§5), come back and verify (§2.1).

### 2.1 Verify backend boots and ingests

1. **Logs** tab → confirm a startup-ingestion line reporting files found under `/app/datasets/chunks` (not `0 files` / path error — if so, the Dockerfile `COPY datasets/chunks` step didn't land).
2. ```bash
   curl https://<your-render-service>.onrender.com/health
   ```
   Expect `status: ok`. Otherwise check Logs for the real error (bad embedding key, provider timeout, etc.).
3. ```bash
   curl -X POST https://<your-render-service>.onrender.com/chat/ask -H "Content-Type: application/json" -d '{"question":"..."}'
   ```
   Confirm grounded answer + sources for a known topic.
4. Force a reindex any time without redeploying:
   ```bash
   curl -X POST https://<your-render-service>.onrender.com/admin/reindex -H "X-Admin-Key: <ADMIN_API_KEY>"
   ```

---

## 3. UptimeRobot — keep the free instance warm

Render Free spins down after ~15min idle (30-60s cold start on next request). UptimeRobot pings the service on an interval so it rarely fully sleeps mid-demo. It does **not** eliminate cold starts (deploys still restart the container, still re-run ingestion), it just prevents idle-timeout sleep during normal usage windows.

1. [uptimerobot.com](https://uptimerobot.com) → sign up (free plan: 50 monitors, 5-min interval).
2. Dashboard → **Add New Monitor**.
3. Monitor Type: **HTTP(s)**.
4. Friendly Name: `modsa-backend`.
5. URL: `https://<your-render-service>.onrender.com/health`.
6. Monitoring Interval: **5 minutes** (free plan minimum — under Render free's ~15min sleep window, keeps it awake).
7. Save. Confirm first check comes back **Up**.

Notes:
- Every ping re-triggers `/health` only — no reindex cost, cheap.
- Doesn't help the very first deploy or a manual restart (still cold on those) — only prevents idle-timeout sleep between pings.
- If demo traffic is bursty and infrequent, this is what keeps the first real user request from eating a 30-60s wait.

---

## 4. No persistent disk (path 1 — default)

Render Free doesn't support persistent disks anyway, so this is the natural fit, not a compromise: `datasets/chunks` (git-tracked, baked into the image at build) is the real source of truth, not Chroma's on-disk index. `backend/main.py`'s `lifespan` hook reruns `ingest_sources` at every boot, rebuilding Chroma fresh — corpus is tiny (29 docs, ~1.5MB), rebuild is fast.

Tradeoffs:
- Every restart/redeploy re-embeds from scratch (cheap at this size; real API cost per re-embed if using a paid embedding API and restarts are frequent).
- No state carried between restarts — by design here, not a gap.

Verify no disk attached: service → **Disks** tab → should read "No disks attached". If something's there, remove it (would silently start costing once free allowance is exceeded).

Now pick an embedding path — §5a, §5b, or §5c.

---

## 5. Embedding paths (only relevant under §4 — no persistent disk)

### 5a. Hugging Face Inference API (recommended default)

Simplest — no extra infra, no home PC required.

1. [huggingface.co](https://huggingface.co) → sign up/log in.
2. Profile icon → **Settings** → **Access Tokens**.
3. **Create new token** → type **Read** → name it (e.g. `modsa-embed`) → **Create token**.
4. Copy the token (`hf_...`, shown once).
5. On Render, add:
   ```
   EMBEDDING_PROVIDER=huggingface
   EMBEDDING_BASE_URL=https://api-inference.huggingface.co
   EMBEDDING_API_KEY=<the hf_... token>
   EMBEDDING_MODEL=BAAI/bge-m3
   EMBEDDING_TIMEOUT=30
   EMBEDDING_MAX_RETRIES=2
   ```

Note: first call after model idle can take ~20s to warm up or briefly 503 — `EMBEDDING_MAX_RETRIES=2` absorbs this.

### 5b. Local Ollama + Cloudflare Tunnel (stable hostname, needs owned domain)

Trades HF dependency for a home-PC-uptime dependency — only use if your machine stays on and networked whenever Render needs it. Needs a domain you own added to Cloudflare (domain purchase ~$8-15/yr if you don't have one — see honesty-check in [ollama-bgem3-cloudflare-tunnel-guide.md](ollama-bgem3-cloudflare-tunnel-guide.md) for a no-domain quick-tunnel fallback, unstable URL).

1. **Run bge-m3 locally**:
   ```powershell
   ollama pull bge-m3
   ollama serve
   curl http://127.0.0.1:11434/api/tags
   ```
2. **Install cloudflared**:
   ```powershell
   winget install --id Cloudflare.cloudflared
   ```
3. **Login + create named tunnel**:
   ```powershell
   cloudflared tunnel login
   cloudflared tunnel create modsa-embeddings
   ```
4. **Route hostname**:
   ```powershell
   cloudflared tunnel route dns modsa-embeddings embeddings.yourdomain.com
   ```
5. **Config file** — `%USERPROFILE%\.cloudflared\config.yml`:
   ```yaml
   tunnel: modsa-embeddings
   credentials-file: C:\Users\<you>\.cloudflared\<tunnel-id>.json

   ingress:
     - hostname: embeddings.yourdomain.com
       service: http://127.0.0.1:11434
     - service: http_status:404
   ```
6. **Test manually**: `cloudflared tunnel run modsa-embeddings`, then `curl https://embeddings.yourdomain.com/api/tags` from elsewhere.
7. **Install as auto-restarting Windows service**:
   ```powershell
   cloudflared service install
   Start-Service cloudflared
   Get-Service cloudflared
   ```
   Fallback if `service install` fails: Task Scheduler, trigger "At startup", action `cloudflared.exe tunnel run modsa-embeddings`, "Run whether user is logged in or not", enable restart-on-failure.
8. On Render, add:
   ```
   EMBEDDING_PROVIDER=ollama
   EMBEDDING_BASE_URL=https://embeddings.yourdomain.com
   EMBEDDING_MODEL=bge-m3
   EMBEDDING_TIMEOUT=30
   EMBEDDING_MAX_RETRIES=2
   ```

Full detail + no-domain quick-tunnel path: [cloudflare-guide.md](cloudflare-guide.md), [ollama-bgem3-cloudflare-tunnel-guide.md](ollama-bgem3-cloudflare-tunnel-guide.md).

Keep in mind: PC on, Ollama running, tunnel service running, every time Render needs to embed. Named tunnel URL stays fixed across restarts — set Render env once.

### 5c. Local Ollama + ngrok (dev/static domain, no owned domain needed)

Note: this path is really "backend also runs locally, exposed via ngrok" per [deployment-plan-ngrok.md](deployment-plan-ngrok.md) — but the embedding-only variant below just tunnels Ollama's embedding endpoint the same way, keeping the FastAPI backend on Render.

1. ngrok account (free) → [ngrok.com](https://ngrok.com) → reserve a static domain (Dashboard → **Domains**, free tier gives 1 `.ngrok-free.app` domain).
2. Run bge-m3 locally:
   ```powershell
   ollama pull bge-m3
   ollama serve
   ```
3. Authenticate + tunnel the Ollama port:
   ```bash
   ngrok config add-authtoken <your-authtoken>
   ngrok http --domain=<your-static-domain>.ngrok-free.app 11434 --request-header-add "ngrok-skip-browser-warning: true"
   ```
4. Verify: `curl https://<your-static-domain>.ngrok-free.app/api/tags`.
5. On Render, add:
   ```
   EMBEDDING_PROVIDER=ollama
   EMBEDDING_BASE_URL=https://<your-static-domain>.ngrok-free.app
   EMBEDDING_MODEL=bge-m3
   EMBEDDING_TIMEOUT=30
   EMBEDDING_MAX_RETRIES=2
   ```

Limitations: ngrok free plan = 1 static domain, limited concurrent connections/bandwidth — fine for demo, not production traffic. No auto-restart unless you script one (Task Scheduler). Static domain means no re-updating Render on restart (unlike ngrok's random free URLs).

Full alternative (whole backend local, not just embeddings): [deployment-plan-ngrok.md](deployment-plan-ngrok.md).

---

## 6. Persistent disk (path 2 — Render Starter tier, not free)

Render's **Free** instance type does not support persistent disks at all — this path requires switching to **Starter ($7/mo) or above**. Only take this path if cold-start-free always-on behavior or avoiding re-embedding on every restart matters enough to pay for it; otherwise stay on path 1 (§4).

Differences from path 1:
1. Render service → **Settings** → **Instance Type** → **Starter** (or above).
2. Service → **Disks** tab → **Add Disk** → mount path matching `CHROMA_DIR` (e.g. `/app/chroma_db`), size per corpus needs (1GB minimum tier is plenty here).
3. Chroma index persists across restarts — `ingest_sources` at startup should skip rebuild when the source manifest fingerprint is unchanged (per `main.py` lifespan logic), so restarts get fast boots instead of full re-embeds.
4. Embedding provider choice (§5a/5b/5c) is unaffected — still pick one, independent of disk.
5. **Important — don't rely on disk-restore for recovery.** Render's disk snapshots exist but a restore can land in a corrupted state (Render's own docs warn this). `datasets/chunks` (git-tracked) stays the actual backup; if the disk is ever suspect, trigger `/admin/reindex` to rebuild from source rather than restoring a snapshot.
6. UptimeRobot (§3) becomes less critical on Starter (no free-tier idle sleep to begin with) but doesn't hurt to keep it as an uptime alert.

Cost note: this is the one deviation from "free" in the whole guide — flag it to whoever owns the bill before flipping the instance type.

---

## 7. Frontend on Vercel (all paths)

`frontend/` is a Vite + React scaffold.

1. [vercel.com](https://vercel.com) → **Add New...** → **Project** → import your repo.
2. **Root Directory**: `frontend`.
3. Framework Preset: **Vite** (auto-detected).
4. Build Command: `npm run build` (default). Output Directory: `dist` (default).
5. Environment variable: `VITE_API_URL` = your backend URL (Render URL for paths 1a/1b partial/2; ngrok static domain if using full-local-backend variant of §5c) — set for **Production** and **Preview**.
6. **Deploy**. Redeploy after changing env vars (they don't apply retroactively).
7. Confirm frontend code actually reads `import.meta.env.VITE_API_URL` once API integration exists (scaffold currently has no API client).

---

## 8. Wire CORS (all paths)

1. Back on Render (or your local `.env` if backend is local per full-ngrok variant) → set `CORS_ORIGINS` to your live Vercel URL exactly, e.g. `https://your-project.vercel.app`.
2. Save — Render redeploys automatically on env var change (or restart uvicorn locally).
3. Open the live Vercel URL, ask a question, confirm no CORS error in browser console.

---

## 9. Final checklist (all paths)

- [ ] Render service: Docker, build context `.`, Dockerfile path `backend/Dockerfile`, correct Instance Type for chosen path (Free for §4, Starter+ for §6)
- [ ] Common env vars set (§2 step 5): `LLM_API_KEY`, `ADMIN_API_KEY`, `CORS_ORIGINS`
- [ ] Embedding env vars set per chosen path (§5a/5b/5c)
- [ ] If path 2: disk attached, mounted at `CHROMA_DIR` (§6)
- [ ] UptimeRobot monitor set up and reporting **Up** (§3) — skip only if on Starter+ and don't care about the alerting
- [ ] `/health` returns `status: ok`
- [ ] `/chat/ask` returns grounded answers + correct no-verified-info fallback for out-of-scope questions
- [ ] Vercel deployed, `VITE_API_URL` pointed at backend URL, redeployed after setting
- [ ] `CORS_ORIGINS` matches live Vercel domain exactly
- [ ] End-to-end: open Vercel URL, ask a question, confirm answer + sources render, no console errors

---

## 10. Recovery runbook

- **Path 1 (no disk)**: nothing to lose — `datasets/chunks` is the only source of truth, every restart rebuilds Chroma from it. If `/chat/ask` unexpectedly returns the no-verified-info fallback: check `/health` first, then Render logs for the actual failure (bad embedding key/timeout — a config issue, not data loss), then force `POST /admin/reindex`.
- **Path 2 (disk)**: if disk looks corrupted/stale, do **not** restore from snapshot — force `POST /admin/reindex` to rebuild from `datasets/chunks` instead.
- **Embedding path 5b/5c (self-hosted)**: if `/chat/ask` times out on embedding calls specifically (not LLM), check home PC is on, Ollama running, tunnel service/ngrok process alive — this is the most fragile link in either path.

---

## 11. Related reference docs

- [deployment-audit.md](deployment-audit.md) — original platform research/rationale (Render vs Railway/Fly/DO/AWS), full paid-tier hardening roadmap.
- [bge-m3-tunnel-research-2026-07-26.md](bge-m3-tunnel-research-2026-07-26.md) — Cloudflare Tunnel vs ngrok tradeoff research behind §5b/§5c.
- [filename-length-fix-2026-07-26.md](filename-length-fix-2026-07-26.md) — past deploy failure (Thai filenames >255 bytes), byte-length check script — relevant if `datasets/chunks` gets new files.
- [development-guide.md](development-guide.md) — local dev setup, unrelated to deploy path choice.
</content>
