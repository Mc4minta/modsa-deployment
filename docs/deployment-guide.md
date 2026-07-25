# MOD-SA Deployment Guide

Target: `frontend/` (Vite + React) on **Vercel**, `backend/` (FastAPI) on **Render**. Rationale in [deployment-audit.md](deployment-audit.md) §3-4.

---

## 1. Backend on Render

### 1.1 Create the service via render.yaml (Blueprint)

Repo root now has [`render.yaml`](../render.yaml) — a Blueprint spec. It sets the Docker build context to the repo root (`dockerContext: .`, `dockerfilePath: ./backend/Dockerfile`) so `datasets/chunks` gets baked into the image alongside `backend/` at build time — no manual copy step, no drift.

`backend/Dockerfile` was adjusted to match: `COPY backend/requirements.txt .`, `COPY backend/ .`, `COPY datasets/chunks ./datasets/chunks` (previously `COPY . .` assumed a `backend/`-scoped context).

1. Push repo to GitHub (Render deploys from a git repo).
2. Render dashboard → New → Blueprint → connect repo → Render detects `render.yaml` at root and proposes the `modsa-backend` service.
3. Apply. Render provisions the service, disk, and health check exactly as declared in `render.yaml` — plan `starter`, disk mounted at `/app/chroma_db`, `healthCheckPath: /health`.
4. Fill in the `sync: false` secrets Render prompts for (§1.3) — these are intentionally not committed to the repo.

No need to manually set Root Directory / Environment / Plan / Disk in the dashboard — the Blueprint owns all of that. If you ever edit `render.yaml`, push and re-sync the Blueprint in the dashboard to apply changes.

### 1.2 Persistent Disk

Already declared in `render.yaml` (`disk: chroma-data`, 1GB, mounted at `/app/chroma_db`) — provisioned automatically on Blueprint apply. 1GB is plenty at current corpus scale (29 docs, ~1.5MB chunked JSON).

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

- [ ] `render.yaml` Blueprint applied on Render (starter plan, disk, health check all declared — §1.1)
- [ ] `sync: false` secrets filled in on Render: `LLM_API_KEY`, `EMBEDDING_API_KEY`, `CORS_ORIGINS`, `ADMIN_API_KEY`
- [ ] `datasets/chunks` reachable inside the container at `RAG_SOURCE_PATHS` (confirm via `/admin/reindex` — baked in at build via Dockerfile, §1.3)
- [ ] `/health` returns `status: ok`
- [ ] `/admin/reindex` succeeds against deployed `datasets/chunks`
- [ ] `/chat/ask` returns grounded answers + correct no-verified-info fallback
- [ ] `CORS_ORIGINS` on Render matches live Vercel domain
- [ ] Vercel `VITE_API_URL` points at Render backend URL, redeployed after setting
- [ ] End-to-end: open Vercel URL, ask a question, confirm answer + sources render

## 4. Recovery runbook

Chroma disk is not the backup — `datasets/chunks` (git-tracked) is. If the disk is lost or corrupted:
1. Redeploy the Render service (fresh disk auto-attached).
2. `curl -X POST .../admin/reindex -H "X-Admin-Key: ..."`.
3. Verify `/health` and a known `/chat/ask` question.

## 5. Open questions before you deploy

- Frontend has no API client code yet (scaffold only) — confirm where `VITE_API_URL` gets consumed once that's written.
- Confirm your Ollama Cloud + Hugging Face API keys/quotas are provisioned before Blueprint setup (needed to fill `sync: false` secrets).
