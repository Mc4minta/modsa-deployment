# MOD-SA Deployment Guide

Target: `frontend/` (Vite + React) on **Vercel**, `backend/` (FastAPI) on **Render**. Rationale in [deployment-audit.md](deployment-audit.md) §3-4.

---

## 1. Backend on Render

### 1.1 Create the service via render.yaml (Blueprint)

Repo root now has [`render.yaml`](../render.yaml) — a Blueprint spec. It sets the Docker build context to the repo root (`dockerContext: .`, `dockerfilePath: ./backend/Dockerfile`) so `datasets/chunks` gets baked into the image alongside `backend/` at build time — no manual copy step, no drift.

`backend/Dockerfile` was adjusted to match: `COPY backend/requirements.txt .`, `COPY backend/ .`, `COPY datasets/chunks ./datasets/chunks` (previously `COPY . .` assumed a `backend/`-scoped context).

1. Push repo to GitHub (Render deploys from a git repo).
2. Render dashboard → New → Blueprint → connect repo → Render detects `render.yaml` at root and proposes the `modsa-backend` service.
3. Apply. Render provisions the service and health check exactly as declared in `render.yaml` — plan `free`, `healthCheckPath: /health`.
4. Fill in the `sync: false` secrets Render prompts for (§1.3) — these are intentionally not committed to the repo.

No need to manually set Root Directory / Environment / Plan in the dashboard — the Blueprint owns all of that. If you ever edit `render.yaml`, push and re-sync the Blueprint in the dashboard to apply changes.

### 1.2 No persistent disk (free plan constraint)

Render's free plan doesn't support persistent disks, so `render.yaml` has no `disk` block — filesystem is ephemeral, wiped on every deploy and restart.

This is fine here: `datasets/chunks` (git-tracked, baked into the image at build) is the real source of truth, not Chroma's on-disk index. `backend/main.py`'s `lifespan` hook already runs `ingest_sources` at startup, rebuilding Chroma from `datasets/chunks` into a fresh in-container path every boot — corpus is tiny (29 docs, ~1.5MB), so this rebuild is fast.

**Tradeoffs of free plan vs. paid Starter:**
- Cold starts: free plan spins down after ~15min idle, 30-60s wake-up delay on the next request. Acceptable for a low-traffic demo, not for a live-expectation chatbot.
- Every restart/redeploy re-runs full ingestion (cheap at this corpus size, but real embedding-API cost each time if traffic causes frequent restarts).
- No horizontal reliability — single ephemeral instance, no disk-based state carried between restarts (by design here, not a gap).

If cold starts or reindex-on-every-restart become a problem, switch `plan: free` → `plan: starter` in `render.yaml` and re-add a `disk` block (see git history / [deployment-audit.md](deployment-audit.md) §3.1 for the paid-tier version of this config) — one-line change, re-sync Blueprint.

### 1.3 Environment variables

Most vars are already declared with values in `render.yaml` (§1.1) — Render sets them automatically on Blueprint apply. The ones marked `sync: false` are secrets Render will prompt you to fill in manually during Blueprint setup (never committed to git):

```
LLM_API_KEY=<your-ollama-cloud-key>
EMBEDDING_API_KEY=<your-hf-access-token>
CORS_ORIGINS=https://<your-vercel-project>.vercel.app
ADMIN_API_KEY=<generate a strong random key>
```

Everything else (`CHROMA_DIR`, `CHROMA_COLLECTION`, `RAG_SOURCE_PATHS`, `CHUNK_SIZE`, `CHUNK_OVERLAP`, `RETRIEVAL_K`, `LLM_BASE_URL`, `LLM_MODEL`, `LLM_TIMEOUT`, `LLM_MAX_RETRIES`, `EMBEDDING_PROVIDER`, `EMBEDDING_BASE_URL`, `EMBEDDING_MODEL`, `EMBEDDING_TIMEOUT`, `EMBEDDING_MAX_RETRIES`) is pinned directly in `render.yaml` — edit there, not in the dashboard, so the repo stays the source of truth (see [config.py](../backend/config.py) for what each controls).

Notes:
- `EMBEDDING_PROVIDER=huggingface` required in prod — Ollama Cloud doesn't serve `bge-m3`, only local Ollama does.
- `ADMIN_API_KEY` is required — `/admin/reindex` refuses to run without it.
- `RAG_SOURCE_PATHS=/app/datasets/chunks` now resolves correctly — `render.yaml` + the adjusted `backend/Dockerfile` bake `datasets/chunks` into the image at build time (§1.1). Content updates to `datasets/chunks` take effect on the next deploy (push triggers rebuild); no manual copy step.

### 1.4 CORS_ORIGINS gotcha

Set to your **exact** Vercel production domain, plus preview-branch wildcard if you want preview deploys to hit the same backend. Vercel doesn't proxy CORS — this must be correct on Render's side or the frontend gets blocked.

### 1.5 Deploy and verify

```bash
curl https://<your-render-service>.onrender.com/health
curl -X POST https://<your-render-service>.onrender.com/admin/reindex -H "X-Admin-Key: <ADMIN_API_KEY>"
curl -X POST https://<your-render-service>.onrender.com/chat/ask -H "Content-Type: application/json" -d '{"question":"..."}'
```

Confirm `/chat/ask` returns grounded answer + sources for a known topic, and the no-verified-info fallback for an out-of-scope question.

---

## 2. Frontend on Vercel

`frontend/` is a Vite + React scaffold (`package.json` confirmed, dev/build/preview scripts present).

1. Vercel dashboard → New Project → import repo.
2. Root Directory: `frontend`
3. Framework Preset: Vite (auto-detected from `vite.config.js`).
4. Build Command: `npm run build` (default). Output Directory: `dist` (Vite default).
5. Environment variable: `VITE_API_URL=https://<your-render-service>.onrender.com` — set for both Production and Preview environments. **Redeploy after setting** (env var changes don't apply retroactively).
6. Use `import.meta.env.VITE_API_URL` in frontend code to call the backend — confirm this matches whatever the frontend actually reads (check `frontend/src` once API integration code exists; currently the scaffold has no API client yet).

---

## 3. Post-deploy checklist

- [ ] `render.yaml` Blueprint applied on Render (free plan, health check declared — §1.1)
- [ ] `sync: false` secrets filled in on Render: `LLM_API_KEY`, `EMBEDDING_API_KEY`, `CORS_ORIGINS`, `ADMIN_API_KEY`
- [ ] `datasets/chunks` reachable inside the container at `RAG_SOURCE_PATHS` (confirm via `/health` — baked in at build via Dockerfile, auto-ingested at startup, §1.2)
- [ ] `/health` returns `status: ok` (confirms startup ingestion succeeded, since no disk persists between deploys)
- [ ] `/admin/reindex` succeeds against deployed `datasets/chunks` (still useful for forcing a rebuild without a redeploy)
- [ ] `/chat/ask` returns grounded answers + correct no-verified-info fallback
- [ ] `CORS_ORIGINS` on Render matches live Vercel domain
- [ ] Vercel `VITE_API_URL` points at Render backend URL, redeployed after setting
- [ ] End-to-end: open Vercel URL, ask a question, confirm answer + sources render

## 4. Recovery runbook

No disk to lose — free plan is stateless by design, `datasets/chunks` (git-tracked, baked into image) is the only source of truth. Every restart/redeploy already rebuilds Chroma from scratch via startup ingestion (§1.2). If `/chat/ask` ever returns the no-verified-info fallback unexpectedly:
1. Check `/health` — confirms whether startup ingestion actually succeeded.
2. If ingestion failed, check Render logs for the failure reason (bad `EMBEDDING_API_KEY`, provider timeout, etc.) — not a data-loss scenario, a config/connectivity one.
3. `curl -X POST .../admin/reindex -H "X-Admin-Key: ..."` to force a retry without a full redeploy.

## 5. Open questions before you deploy

- Frontend has no API client code yet (scaffold only) — confirm where `VITE_API_URL` gets consumed once that's written.
- Confirm your Ollama Cloud + Hugging Face API keys/quotas are provisioned before Blueprint setup (needed to fill `sync: false` secrets).
