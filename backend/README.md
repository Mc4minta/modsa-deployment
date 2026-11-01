# MOD-SA backend

KMUTT Student Affairs RAG chatbot API. FastAPI + LangChain + ChromaDB. See root [`CLAUDE.md`](../CLAUDE.md) for architecture/layering rules.

## Graph integration

New-document graph building is available via [expansion CLI](../graph/EXPANSION.md), independent of pilot IDs/QAs. It writes staging namespaces only when `--load` is selected and does not change this API's Vector retrieval.

`/chat/ask` ยังเป็น Vector RAG เดิม. ชุดสร้างกราฟและ tests แยกที่ [graph/](../graph/README.md); ไม่ต้องเปิด backend/reindex เพื่อใช้คำสั่ง build/check

`services/{graph,hybrid_rag,query}_service.py` และ `schemas/retrieval.py` อยู่ใน backend ต่อไป เพราะเป็นจุดเชื่อม runtime ไม่ใช่สคริปต์ทดลอง schema. ยังไม่ได้เปิด Hybrid ใน API

### Safe reindex

Ingestion builds a uniquely named staging collection, checks the complete chunk count, then atomically publishes `source_manifest.json` as the active-collection pointer. Embedding/count/manifest failures preserve the serving index; failed staging collections are removed when possible. Retrieval reads the pointer, and requests already holding the previous collection can finish normally. The API routes and request/response formats are unchanged.

`CHROMA_COLLECTION` is the logical base name, not necessarily the active physical collection name. Source, embedding/chunk configuration and the expected count must match before startup skips ingestion. Legacy manifests are rebuilt once on the next ingestion; this may call the configured embedding provider. This change does not run that rebuild automatically during code installation/tests.

Successful old collections are intentionally retained for in-flight requests; repeated rebuilds therefore use more disk. Remove only inactive collections during maintenance after stopping readers, never the collection named by the manifest. An interrupted process may leave an unused staging collection. Use one ingestion worker per persistent store; the in-process writer lock is not a distributed lock. Do not manually delete the manifest (it selects the serving index).

## Answer LLM and extraction are separate


ตัวตอบ `/chat/ask` อ่าน `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` จาก `.env`; ไม่ใช้ `MIMO_API_KEY`. MiMo ยังเป็น provider ของสคริปต์สกัดกราฟและผลทดลองเดิม ไม่ต้องสกัดใหม่เมื่อเปลี่ยนตัวตอบ.

ค่าปัจจุบัน `http://localhost:11434/v1` + `gemma4:31b-cloud` ใช้ Ollama local เป็น gateway ไป Cloud; ค่า key `ollama` เป็น placeholder ของ local API ไม่ใช่ cloud credential. ใช้ [tag Cloud](https://ollama.com/library/gemma4:31b-cloud) ไม่ใช่ `gemma4:31b` ซึ่งเป็น weights local. ต้อง sign in ใน Ollama และบัญชีต้องมีสิทธิ์/usage credits; HTTP 402 ไม่ใช่เหตุให้ fallback หรือเปลี่ยนโมเดลอัตโนมัติ. ดู [Ollama OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility).

Embeddings อ่าน `EMBEDDING_*` แยกจากตัวตอบ; เมื่อเลือก `ollama` จะไม่โหลด Hugging Face package. หลังแก้ `.env` ให้เริ่ม process ใหม่เพราะ settings/client มี cache. ขอบเขต Phase 10 ที่เตรียมไว้ไม่มี reranker และตอนนี้ยังไม่เชื่อม graph/hybrid retrieval เข้า `/chat/ask`.

## Run locally

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # macOS/Linux; Windows: use .venv\Scripts\python.exe directly
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Two embedding modes, switched by `EMBEDDING_PROVIDER` in `.env` — no code change needed:

- **`EMBEDDING_PROVIDER=ollama`** (default, local dev): `ollama pull bge-m3` first, then `EMBEDDING_BASE_URL=http://localhost:11434/v1`, `EMBEDDING_MODEL=bge-m3:latest`.
- **`EMBEDDING_PROVIDER=huggingface`** (production): `EMBEDDING_API_KEY=<hf token>`, `EMBEDDING_MODEL=BAAI/bge-m3`. Requires a Hugging Face access token; failed ingestion is reported as unready by `/health`.

## Env var reference

| Var | Purpose | Dev value | Prod value |
|---|---|---|---|
| `LLM_BASE_URL` | LLM endpoint (OpenAI-compatible) | `http://localhost:11434/v1` (local Ollama) | Ollama Cloud endpoint |
| `LLM_API_KEY` | LLM auth | `ollama` | Ollama Cloud key |
| `LLM_MODEL` | LLM model tag | `gemma4:31b-cloud` (local gateway) | Use the tag supported by the configured endpoint |
| `LLM_TIMEOUT` / `LLM_MAX_RETRIES` | Bound worst-case latency on a hung provider call | `30` / `2` | same |
| `EMBEDDING_PROVIDER` | `ollama` \| `huggingface` \| `openai` | `ollama` | `huggingface` |
| `EMBEDDING_BASE_URL` | Only used by `ollama`/`openai` providers | `http://localhost:11434/v1` | — (unused for `huggingface`) |
| `EMBEDDING_API_KEY` | Auth for embedding provider | `ollama` | HF access token (**required** when provider is `huggingface`) |
| `EMBEDDING_MODEL` | Embedding model id | `bge-m3:latest` (Ollama tag) | `BAAI/bge-m3` (HF repo id) |
| `EMBEDDING_TIMEOUT` / `EMBEDDING_MAX_RETRIES` | Same as LLM, for embedding calls | `30` / `2` | same |
| `CHROMA_DIR` | Chroma persistence path | `chroma_db` | Render Persistent Disk mount path |
| `CHROMA_COLLECTION` | Chroma collection name | `modsa_kmutt` | same |
| `RAG_SOURCE_PATHS` | Where `/admin/reindex` reads source docs from | `../data/chunks` | path baked into the deploy image |
| `CORS_ORIGINS` | Allowed frontend origins (comma-separated) | `http://localhost:5173` | Vercel production + preview domain(s) |
| `ADMIN_API_KEY` | **Required.** `/admin/reindex` returns 500 if unset, 401 without a matching `X-Admin-Key` header | any dev value | real secret |

## Deploying

**Render (backend + Chroma):**
1. New web service, build from `backend/Dockerfile`, **Starter tier or above** (never free — cold starts are unacceptable for a live chatbot).
2. Attach a Persistent Disk, mount at `CHROMA_DIR` (e.g. `/app/chroma_db`).
3. Set all env vars from the table above (production column). `RAG_SOURCE_PATHS` should point at `chunks/` baked into the image (it's git-tracked and small) or a mounted read-only path.
4. Deploy, then `POST /admin/reindex` with header `X-Admin-Key: <ADMIN_API_KEY>` to build the index from `chunks/`.
5. Verify: `GET /health` → `status: ok`; `POST /chat/ask` with a known-topic question returns an answer + sources; empty `question` → 422; empty index → no-verified-info fallback with `sources: []`.

**Vercel (frontend):** standard git-push deploy for the existing React/Vite frontend. Point it at the Render backend URL, then set `CORS_ORIGINS` on Render to the actual Vercel domain(s) (production + preview wildcard if preview deploys need API access).

## Recovery

`data/chunks/` (git-tracked) is the source of truth, not the Chroma disk. If the disk is ever lost: redeploy + `POST /admin/reindex` rebuilds the full index from `chunks/`. No custom backup/export tooling needed at this scale.
