# MOD-SA Deployment Plan — ngrok Static Domain (No Owned Domain Needed)

Run `backend/` locally (your machine), expose via ngrok's free static domain. Avoid Render cold-starts and Cloudflare Tunnel's requirement for a domain you own. Frontend still on Vercel (free).

Tradeoff vs [deployment-plan-free-tier.md](deployment-plan-free-tier.md): zero cost, no domain purchase, no Render cold-start — but backend uptime now depends on your machine + ngrok tunnel staying up.

---

## 1. Prerequisites

- ngrok account (free) — [ngrok.com](https://ngrok.com) sign up.
- ngrok static domain reserved on your account (Dashboard → **Domains** → free tier gives 1 static `.ngrok-free.app` domain).
- Local machine can run `backend/` continuously (or as long as demo needs).
- Ollama running locally for both LLM and embeddings (no cloud API keys needed, unlike §free-tier plan).

---

## 2. Run backend locally

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:

```
LLM_BASE_URL=http://127.0.0.1:11434/v1
LLM_MODEL=<your local model>
EMBEDDING_PROVIDER=ollama
EMBEDDING_BASE_URL=http://127.0.0.1:11434
EMBEDDING_MODEL=bge-m3
CHROMA_DIR=./chroma_db
CHROMA_COLLECTION=modsa_kmutt
RAG_SOURCE_PATHS=../datasets/chunks
CORS_ORIGINS=<your Vercel URL from §4>
ADMIN_API_KEY=<generate a random string>
```

Start it:

```bash
uvicorn main:app --host 127.0.0.1 --port 8000
```

Confirm locally first: `curl http://127.0.0.1:8000/health` → `status: ok`.

---

## 3. Expose backend via ngrok static domain

1. Install ngrok, authenticate:
   ```bash
   ngrok config add-authtoken <your-authtoken>
   ```
2. Start tunnel bound to your reserved static domain:
   ```bash
   ngrok http --domain=<your-static-domain>.ngrok-free.app 8000
   ```
3. Backend now reachable at `https://<your-static-domain>.ngrok-free.app` — HTTPS included, domain stays same across restarts (unlike random free ngrok URLs).
4. Verify from outside:
   ```bash
   curl https://<your-static-domain>.ngrok-free.app/health
   ```

Keep this terminal running for as long as the demo needs backend reachable. Closing it drops the tunnel.

---

## 4. Deploy frontend to Vercel

Same as [deployment-plan-free-tier.md §5](deployment-plan-free-tier.md), except:

- `VITE_API_URL` = `https://<your-static-domain>.ngrok-free.app`

---

## 5. Wire CORS

1. In backend `.env`, set `CORS_ORIGINS=https://your-project.vercel.app`, restart uvicorn.
2. Open live Vercel URL, ask a question, confirm no CORS error in browser console.

---

## 6. Known limitations

- Backend only reachable while your machine + ngrok process both stay running — no auto-restart unless you set that up yourself (e.g. a startup script or Task Scheduler entry).
- ngrok free plan: 1 static domain, limited concurrent connections/bandwidth — fine for demo, not production traffic.
- No HF token or Ollama Cloud key needed at all — everything runs local, so no cloud LLM/embedding cost or key management.

---

## 7. Final checklist

- [ ] Ollama running locally, LLM + embedding models pulled
- [ ] Backend `.env` configured, `uvicorn` running on `127.0.0.1:8000`
- [ ] `/health` returns `status: ok` locally
- [ ] ngrok static domain reserved, tunnel running, `/health` reachable externally
- [ ] Vercel project deployed, `VITE_API_URL` pointed at ngrok static domain
- [ ] `CORS_ORIGINS` set to live Vercel URL, backend restarted
- [ ] End-to-end test from live Vercel site works, no console errors
