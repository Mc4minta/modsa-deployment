# MOD-SA backend

KMUTT Student Affairs RAG chatbot API. FastAPI + LangChain + ChromaDB. See root [`CLAUDE.md`](../CLAUDE.md) for architecture/layering rules.

## Run locally

```bash
cd backend
python -m venv .venv && .venv/Scripts/activate   # or source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Two embedding modes, switched by `EMBEDDING_PROVIDER` in `.env` — no code change needed:

- **`EMBEDDING_PROVIDER=ollama`** (default, local dev): `ollama pull bge-m3` first, then `EMBEDDING_BASE_URL=http://localhost:11434/v1`, `EMBEDDING_MODEL=bge-m3:latest`.
- **`EMBEDDING_PROVIDER=huggingface`** (production): `EMBEDDING_API_KEY=<hf token>`, `EMBEDDING_MODEL=BAAI/bge-m3`. Requires a Hugging Face access token — startup fails fast with a clear error if missing.

## Env var reference

| Var | Purpose | Dev value | Prod value |
|---|---|---|---|
| `LLM_BASE_URL` | LLM endpoint (OpenAI-compatible) | `http://localhost:11434/v1` (local Ollama) | Ollama Cloud endpoint |
| `LLM_API_KEY` | LLM auth | `ollama` | Ollama Cloud key |
| `LLM_MODEL` | LLM model tag | `minimax-m3:cloud` | `minimax-m3:cloud` |
| `LLM_TIMEOUT` / `LLM_MAX_RETRIES` | Bound worst-case latency on a hung provider call | `30` / `2` | same |
| `EMBEDDING_PROVIDER` | `ollama` \| `huggingface` \| `openai` | `ollama` | `huggingface` |
| `EMBEDDING_BASE_URL` | Only used by `ollama`/`openai` providers | `http://localhost:11434/v1` | — (unused for `huggingface`) |
| `EMBEDDING_API_KEY` | Auth for embedding provider | `ollama` | HF access token (**required** when provider is `huggingface`) |
| `EMBEDDING_MODEL` | Embedding model id | `bge-m3:latest` (Ollama tag) | `BAAI/bge-m3` (HF repo id) |
| `EMBEDDING_TIMEOUT` / `EMBEDDING_MAX_RETRIES` | Same as LLM, for embedding calls | `30` / `2` | same |
| `CHROMA_DIR` | Chroma persistence path | `chroma_db` | Render Persistent Disk mount path |
| `CHROMA_COLLECTION` | Chroma collection name | `modsa_kmutt` | same |
| `RAG_SOURCE_PATHS` | Where `/admin/reindex` reads source docs from | `../datasets/chunks` | path baked into the deploy image |
| `CORS_ORIGINS` | Allowed frontend origins (comma-separated) | `http://localhost:5173` | Vercel production + preview domain(s) |
| `ADMIN_API_KEY` | **Required.** `/admin/reindex` returns 500 if unset, 401 without a matching `X-Admin-Key` header | any dev value | real secret |

## Deploying

**Render (backend + Chroma):**
1. New web service, build from `backend/Dockerfile`, **Starter tier or above** (never free — cold starts are unacceptable for a live chatbot).
2. Attach a Persistent Disk, mount at `CHROMA_DIR` (e.g. `/app/chroma_db`).
3. Set all env vars from the table above (production column). `RAG_SOURCE_PATHS` should point at `chunks/` baked into the image (it's git-tracked and small) or a mounted read-only path.
4. Deploy, then `POST /admin/reindex` with header `X-Admin-Key: <ADMIN_API_KEY>` to build the index from `chunks/`.
5. Verify: `GET /health` → `status: ok`; `POST /chat/ask` with a known-topic question returns an answer + sources; empty `question` → 422; empty index → no-verified-info fallback with `sources: []`.

**Vercel (frontend):** standard git-push deploy once the frontend has a real framework scaffold. Point it at the Render backend URL, then set `CORS_ORIGINS` on Render to the actual Vercel domain(s) (production + preview wildcard if preview deploys need API access).

## Recovery

`datasets/chunks/` (git-tracked) is the source of truth, not the Chroma disk. If the disk is ever lost: redeploy + `POST /admin/reindex` rebuilds the full index from `chunks/`. No custom backup/export tooling needed at this scale.
