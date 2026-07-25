# MOD-SA Deployment Plan — Free Tier

Deploy `backend/` (FastAPI) on Render **Free** plan, `frontend/` (Vite + React) on Vercel. Zero cost, manual dashboard setup.

---

## 1. Prerequisites

- Repo pushed to GitHub.
- Ollama Cloud account + API key (LLM).
- Hugging Face account + access token (embeddings — see §4).
- `backend/Dockerfile` present in repo, expects to build from **repo root** (not `backend/`) — it copies `datasets/chunks` alongside the app code. Confirm it has these lines:
  ```
  COPY backend/requirements.txt .
  COPY backend/ .
  COPY datasets/chunks ./datasets/chunks
  ```
  If it instead says `COPY requirements.txt .` / `COPY . .`, update it to the above before deploying — the build context in §2 depends on it.

---

## 2. Deploy backend to Render (Free plan)

1. Go to [dashboard.render.com](https://dashboard.render.com), log in (or sign up — free, no card required for Free plan).
2. Click **New +** (top right) → **Web Service**.
3. Under "Connect a repository", find and click your repo. If not listed, click **Configure account**, grant Render access on GitHub, come back and select it.
4. Fill in the config form:
   - **Name**: `modsa-backend`
   - **Region**: nearest to your users (e.g. Singapore)
   - **Branch**: your deploy branch (e.g. `main`)
   - **Root Directory**: leave **blank**
   - **Runtime**: **Docker**
   - **Dockerfile Path**: `backend/Dockerfile`
   - **Docker Build Context Directory**: `.`
5. Scroll to **Instance Type** → select **Free**.
6. Scroll to **Environment Variables** → click **Add Environment Variable**, add each of these one at a time:

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

   EMBEDDING_PROVIDER=huggingface
   EMBEDDING_BASE_URL=https://api-inference.huggingface.co
   EMBEDDING_API_KEY=<your Hugging Face token — see §4>
   EMBEDDING_MODEL=BAAI/bge-m3
   EMBEDDING_TIMEOUT=30
   EMBEDDING_MAX_RETRIES=2

   CORS_ORIGINS=<leave blank for now, come back after §3>
   ADMIN_API_KEY=<generate a random string, e.g. via `openssl rand -hex 32`>
   ```

7. Scroll to **Health Check Path** → enter `/health`.
8. Click **Create Web Service**. Render builds and boots the container — first build takes a few minutes. Watch the **Logs** tab that opens automatically.
9. Once live, copy the service URL from the top of the page (`https://modsa-backend-xxxx.onrender.com`) — needed in §3 and to update `CORS_ORIGINS` afterward.

**No disk is attached** (Free plan doesn't support persistent disks). This is fine: `datasets/chunks` is git-tracked and baked into the image at build time; `backend/main.py`'s startup hook rebuilds the Chroma index from it on every boot. Tradeoff: the service spins down after ~15min idle, and the next request triggers a 30-60s cold start plus a fresh re-ingest.

---

## 3. Verify the backend

1. In the service page, left sidebar → **Logs**. Confirm you see a line from startup ingestion reporting files found under `/app/datasets/chunks` (not `0 files` or a path error).
2. Run:
   ```bash
   curl https://<your-render-service>.onrender.com/health
   ```
   Expect `status: ok`. If not, go back to Logs and find the actual error (usually a bad `EMBEDDING_API_KEY` or provider timeout).
3. Run:
   ```bash
   curl -X POST https://<your-render-service>.onrender.com/chat/ask -H "Content-Type: application/json" -d '{"question":"..."}'
   ```
   Confirm it returns a grounded answer with sources for a known topic.
4. Force a manual reindex any time without waiting for a redeploy:
   ```bash
   curl -X POST https://<your-render-service>.onrender.com/admin/reindex -H "X-Admin-Key: <ADMIN_API_KEY>"
   ```

---

## 4. Getting a Hugging Face token (for `EMBEDDING_API_KEY`)

Local dev uses Ollama for embeddings (no real key needed — Ollama Cloud doesn't serve `bge-m3`, so it can't be used in production). Production needs a real Hugging Face Inference API token instead:

1. Go to [huggingface.co](https://huggingface.co) → sign up or log in.
2. Click your profile icon (top right) → **Settings**.
3. Left sidebar → **Access Tokens**.
4. Click **Create new token** → type **Read** → name it (e.g. `modsa-embed`) → **Create token**.
5. Copy the token (`hf_...`) — shown once.
6. Paste it into Render's `EMBEDDING_API_KEY` env var (§2, step 6).

Note: the first embedding call after the model has been idle can take ~20s to warm up, or briefly return a 503 — the configured `EMBEDDING_MAX_RETRIES=2` absorbs this.

---

## 5. Deploy frontend to Vercel

1. Go to [vercel.com](https://vercel.com), log in (or sign up, free).
2. Click **Add New...** → **Project**.
3. Import your GitHub repo.
4. **Root Directory**: `frontend`.
5. Framework Preset: **Vite** (auto-detected from `vite.config.js`).
6. Build Command: `npm run build` (default). Output Directory: `dist` (default).
7. Add environment variable: `VITE_API_URL` = your Render backend URL from §2 step 9. Set it for both **Production** and **Preview**.
8. Click **Deploy**. Wait for build to finish, then copy the live Vercel URL.

---

## 6. Wire CORS between the two

1. Back on Render, service → **Environment** → edit `CORS_ORIGINS` → set to your Vercel production URL (e.g. `https://your-project.vercel.app`).
2. Save — Render redeploys automatically on env var change.
3. Open the live Vercel URL in a browser, ask a question, confirm you get an answer with no CORS error in the browser console.

---

## 7. Final checklist

- [ ] Render service created, Free plan, Docker build context `.`, Dockerfile path `backend/Dockerfile`
- [ ] All env vars set on Render (§2 step 6), including real `LLM_API_KEY`, `EMBEDDING_API_KEY`, `ADMIN_API_KEY`
- [ ] `/health` returns `status: ok`
- [ ] `/chat/ask` returns grounded answers with sources
- [ ] Vercel project deployed, `VITE_API_URL` pointed at Render URL
- [ ] `CORS_ORIGINS` on Render updated to the live Vercel URL
- [ ] End-to-end test from the live Vercel site works with no console errors
