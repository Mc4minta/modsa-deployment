# Plan: backend_new implementation for Vercel + Render + Chroma-disk + Ollama-Cloud-MiniMax + dual bge-m3 embedding (local/HF)

## Context

Target stack decided across this conversation:
- Frontend: Vercel (React)
- Backend: FastAPI on Render
- Vector store: ChromaDB on Render Persistent Disk
- LLM: Ollama Cloud, MiniMax model (already OpenAI-compatible, `core/llm.py` needs zero code change — just correct env vars)
- Embeddings: bge-m3, but **two interchangeable backends**: local Ollama (`ollama pull bge-m3`, dev machine only — confirmed unreachable from Render without a public tunnel, which the user has ruled out as unreliable/insecure for prod) and **Hugging Face Inference API** (confirmed `bge-m3` not offered by Ollama Cloud itself). HF becomes the production embedding path; local Ollama stays the dev-only path. Switch must be a config change, not a code change.

Blocking bug found in current code: `embedding_uses_ollama` in [config.py](backend_new/config.py:88) URL-sniffs for `localhost`/`127.0.0.1`/`::1` port `11434` only. This can never select Hugging Face and would misfire for any non-localhost Ollama host. Must become an explicit provider flag.

Also carrying forward the two audit findings (`docs/deployment-audit.md`) that are load-bearing for a **public** deploy specifically (not the full hardening backlog — scoped down, see "Out of scope" below):
- S6/S37 (critical): `/admin/reindex` currently allows unauthenticated access whenever `ADMIN_API_KEY` is unset (`api/admin.py:12-17`) — real cost-DoS surface once this is on the public internet.
- S28 (critical): zero timeout/retry on LLM or embedding HTTP calls (`core/llm.py`, `core/embeddings.py`) — a hung provider call blocks a request indefinitely.
- S22 (medium, but compounds badly with HF's per-call network cost): `get_vector_store()` rebuilds a fresh Chroma + embeddings client on every single request (`core/vectorstore.py:9-13`, called from `services/rag_service.py` and `services/ingestion_service.py` with no caching).
- S9/S38: CORS is currently wildcard methods/headers with `allow_credentials=True` (`main.py:46-52`) — should narrow to the real Vercel origin(s) since they're now known.
- S14: hardcoded placeholder key fallback (`config.py:14`, `DEFAULT_OPENAI_COMPAT_KEY`) — silently masks a missing HF token or Ollama Cloud key instead of failing fast.

## Out of scope (explicitly deferred, not part of this plan)

Rate limiting, structured logging middleware, full test suite, prompt-injection delimiters, streaming responses, incremental ingestion, API versioning — these are real findings in `docs/deployment-audit.md` Phase 4.2/4.3 but not required to stand up this specific stack safely. Flag as follow-up, don't build now.

## Changes

### 1. `config.py` — explicit embedding provider switch
- Add `embedding_provider: Literal["ollama", "huggingface", "openai"] = Field(default="ollama", alias="EMBEDDING_PROVIDER")`.
- Replace `embedding_uses_ollama` URL-sniff with a direct read of `embedding_provider` (keep the property name/shape other code depends on, or update call sites — check `core/embeddings.py` is the only consumer).
- Add fail-fast validation: if `embedding_provider == "huggingface"` and no `EMBEDDING_API_KEY`/HF token present, raise a clear config error at `get_settings()` time instead of falling back to `DEFAULT_OPENAI_COMPAT_KEY` (closes S14 for this path specifically).
- Add `llm_timeout: float = Field(default=30.0, alias="LLM_TIMEOUT")`, `llm_max_retries: int = Field(default=2, alias="LLM_MAX_RETRIES")`, and equivalents for embeddings, or a shared pair — used in step 2.

### 2. `core/embeddings.py` — add Hugging Face branch, keep Ollama branch, add timeout/retry
```
build_embeddings(settings):
    if settings.embedding_provider == "ollama":
        OllamaEmbeddings(model=..., base_url=...)
    elif settings.embedding_provider == "huggingface":
        HuggingFaceEndpointEmbeddings(model=settings.embedding_model, huggingfacehub_api_token=..., ...)
    else:
        OpenAIEmbeddings(..., timeout=..., max_retries=...)
```
- `EMBEDDING_MODEL` for the HF path = `BAAI/bge-m3` (HF repo id), for Ollama path = `bge-m3` (Ollama tag) — same env var, different value per environment, which is exactly the "easy switch" requirement: dev `.env` sets `EMBEDDING_PROVIDER=ollama` + `EMBEDDING_MODEL=bge-m3`; Render env vars set `EMBEDDING_PROVIDER=huggingface` + `EMBEDDING_MODEL=BAAI/bge-m3` + `EMBEDDING_API_KEY=<hf token>`.
- New dependency: `langchain-huggingface` (pulls in `huggingface_hub`) — add to `requirements.txt`.

### 3. `core/llm.py` — point at Ollama Cloud, add timeout/retry
- No branching needed (Ollama Cloud is OpenAI-compatible, existing `ChatOpenAI` construction already works) — just add `timeout=settings.llm_timeout, max_retries=settings.llm_max_retries` to the constructor call (closes S28).
- Production env vars: `LLM_BASE_URL=<Ollama Cloud endpoint>`, `LLM_MODEL=minimax-m3:cloud` (per existing `.env.example`), `LLM_API_KEY=<Ollama Cloud key>`.

### 4. `core/vectorstore.py` + call sites — singleton caching (closes S22)
- Cache the `Chroma` instance (and therefore its embeddings client) once per process, e.g. `@lru_cache` keyed off `get_settings()` (already itself `lru_cache`d, so this composes cleanly) or a module-level singleton built in `main.py`'s `lifespan`.
- Update `services/rag_service.py` (`retrieve_documents`, `answer_question`) and `services/ingestion_service.py` to reuse the cached instance instead of calling `get_vector_store(settings)` / `build_llm(settings)` fresh per call. This matters more once embeddings go over the network to HF — avoids rebuilding an HTTP client per chat message.

### 5. `api/admin.py` — required admin key in production (closes S6/S37)
- Fail startup (or fail the route with a clear 500/misconfiguration signal) if `ADMIN_API_KEY` is unset when not running locally — simplest: require it unconditionally once deployed (document as a required Render env var), rather than adding an `ENV=local` detection layer (keeps scope small, matches "don't over-engineer" project guidance).
- Switch the `!=` comparison to `secrets.compare_digest` while touching this function.

### 6. `main.py` — narrow CORS (closes S9/S38)
- `allow_methods=["GET", "POST"]`, `allow_headers=["Content-Type", "X-Admin-Key"]` instead of `["*"]`; keep `allow_credentials` only if actually needed (likely not — no cookies/session in this API, safe to set `False`).
- `CORS_ORIGINS` set to the real Vercel production domain + preview wildcard.

### 7. `Dockerfile` — light touch
- Add non-root `USER`, add `HEALTHCHECK CMD curl -f http://localhost:8000/health || exit 1`. Skip multi-stage build (not required at this scale, keep it simple).

### 8. `.env.example` — document both embedding modes side by side
- Add commented `EMBEDDING_PROVIDER` block showing the local-dev (`ollama` + `bge-m3`) and prod (`huggingface` + `BAAI/bge-m3` + HF token) variants, plus `LLM_TIMEOUT`/`LLM_MAX_RETRIES`.

## Deployment steps (Render + Vercel)

1. Render web service, build from `backend_new/Dockerfile`, **Starter tier or above** (never free — cold starts unacceptable for live chat, per `docs/deployment-audit.md` §3.1).
2. Attach Persistent Disk, mount at `CHROMA_DIR` (e.g. `/app/chroma_db`).
3. Set env vars: `LLM_BASE_URL`, `LLM_MODEL=minimax-m3:cloud`, `LLM_API_KEY` (Ollama Cloud), `EMBEDDING_PROVIDER=huggingface`, `EMBEDDING_MODEL=BAAI/bge-m3`, `EMBEDDING_API_KEY` (HF token), `ADMIN_API_KEY` (required, real secret), `CORS_ORIGINS` (Vercel domain), `CHROMA_DIR`, `RAG_SOURCE_PATHS` (mount/copy `backend_old/chunks` into the image or a Render disk path — decide which; simplest is bake `chunks/` into the Docker image since it's git-tracked and small).
4. Deploy, then `POST /admin/reindex` with `X-Admin-Key` to build the index from `chunks/`.
5. Verify `/health`, `/chat/ask` for a known topic, empty-question 422, empty-index fallback — per `CLAUDE.md` testing checklist.
6. Deploy frontend to Vercel once it has a real framework scaffold (currently empty per `CLAUDE.md` — separate prerequisite, flag to user, not part of this backend plan), point at the Render URL, then set the real `CORS_ORIGINS` value (step 3) once the Vercel domain is known.

## Verification

- `python -c "import main"` from `backend_new/` after code changes.
- Local smoke test with `EMBEDDING_PROVIDER=ollama` (existing local Ollama + bge-m3) — confirm no regression on the dev path.
- Local smoke test with `EMBEDDING_PROVIDER=huggingface` (HF token in `.env`) — confirm `/admin/reindex` and `/chat/ask` work end-to-end against the HF Inference API.
- Confirm missing HF token now fails fast at startup with a clear error instead of silently using the placeholder key.
- Confirm `/admin/reindex` returns 401 without `X-Admin-Key` once `ADMIN_API_KEY` is set.
- After Render deploy: run the same `/health` → `/admin/reindex` → `/chat/ask` sequence against the live URL.