# MOD-SA Deployment Readiness Audit & Production Architecture Plan

**Date:** 2026-07-25
**Scope:** Audit of `backend_old` (the only backend currently present in the working tree), design of a new production `backend/`, deployment-platform research, and a prioritized roadmap.

**Important situational note before anything else:** `backend_new/` — the "active" backend per `CLAUDE.md` — was **deleted from `main`** in commit `5b3723f` ("docs: add old folder for reference and delete all backend for resetting"). It only survives in git history at commit `f91b6b8` and on branches `origin/wolf` / `origin/lnwmon`. `CLAUDE.md`, `docs/backend-structure.md`, and `.agents/skills/modsa-backend/SKILL.md` are now stale — they describe a backend that isn't on disk. This audit therefore:

- Audits `backend_old` in full (Phase 1), since it's what actually exists.
- Recommends recovering `backend_new` from `f91b6b8` as the base for the new `backend/` (Phase 2), because it already has the clean layered architecture `CLAUDE.md` describes — a fresh rewrite would just re-derive it at higher cost. This was confirmed with the project owner before writing this plan.

---

## Phase 1 — Audit of `backend_old`

Correction to the assumed layout: there is **no `backend_old/app/` directory**. The FastAPI application lives at `backend_old/modsa_rag/` (`api.py`, `config.py`, `ingest.py`, `rag.py`). All line references below point there.

### 1.1 Project Structure

| # | Severity | Finding | Why it matters | Fix |
|---|----------|---------|-----------------|-----|
| S1 | High | No `Dockerfile`, `render.yaml`, CI config, or any deployment manifest anywhere in `backend_old/` (confirmed by recursive search). | Zero automated/repeatable path to production; every deploy would be manual and undocumented. | New `backend/` ships a Dockerfile + deploy config from day one (Phase 2/4). |
| S2 | Medium | `.gitignore:12-14` comments out ignoring `data/raw/`, `data/processed/`, and `chunks/`, contradicting `README.md` and `data/pipeline/README.md`, which both describe these as local-only artifacts. All three are currently git-tracked (confirmed via `git ls-files`). | Repo bloat from binary/large data churn on every content update; unclear source-of-truth story for reviewers. | Decide explicitly: either keep `chunks/` tracked as the intentional "knowledge base source of truth" (recommended — see §3.5) and drop `data/raw/`+`data/processed/` tracking, or untrack all three and ship them via a release artifact / object storage. |
| S3 | Low | `mermaid.js` (Node.js module) sits at the repo root of an all-Python backend; not imported by any Python code, purely a standalone diagram generator. | Confusing for anyone scanning the tree expecting a pure-Python project; no `package.json` to explain it. | Move to `docs/diagrams/` or delete — zero functional impact either way. |
| S4 | Low | `LICENSE` (Apache 2.0) still has the unfilled template line `Copyright [yyyy] [name of copyright owner]`. | Legally ambiguous ownership statement if this ever ships publicly. | Fill in real copyright holder/year or drop the file if not intended for public release yet. |
| S5 | Medium | `data/` (ingestion/chunking pipeline) and `modsa_rag/` (serving app) are two independently-versioned Python projects glued together only by the `chunks/` directory convention, each with its own `requirements.txt`, no shared package, no shared config. | Easy to run stale pipeline output against new app code or vice versa with no version check. | Not urgent to unify for an MVP; document the coupling explicitly (a `manifest`/version stamp already partially does this via `source_manifest.json` — see §1.4). |

### 1.2 FastAPI Architecture

| # | Severity | Finding | Why it matters | Fix |
|---|----------|---------|-----------------|-----|
| S6 | **Critical** | No authentication/authorization anywhere. `GET /health`, `POST /ask`, and `POST /reindex` are all fully public (`api.py:37-60`). | `/reindex` triggers a full re-embed of the entire corpus (real cost against the embedding provider) — anyone on the internet can trigger it repeatedly. This is a live cost-DoS vector, not theoretical. | Require an admin key/header on `/reindex` at minimum (matches what `backend_new` already does via `ADMIN_API_KEY`, though that too is optional/off-by-default — see §1.7). Add basic rate limiting on `/ask`. |
| S7 | High | `POST /ask` synchronously re-runs `ingest_sources()` — a full filesystem walk + SHA-256 fingerprint of every source file — on **every single request** (`api.py:48-49`), before answering. | Couples answer latency and I/O/CPU cost to corpus size on every question, even though the call almost always no-ops via manifest comparison. Wasteful and a needless dependency between two unrelated concerns (answering vs. reindexing). | Only ingest at startup (`lifespan`) and via `/reindex`; `/ask` should just query the existing vector store. |
| S8 | High | Broad `except Exception` in `/ask` returns `HTTPException(500, detail=str(exc))` verbatim (`api.py:51-52`) — the only error handling in the whole app; no `@app.exception_handler` registered anywhere. | Leaks internal exception text (file paths, provider error bodies, potentially partial key info depending on the HTTP client's error formatting) straight to API clients. | Catch narrow exception types, log full detail server-side, return a generic sanitized message to the client. |
| S9 | High | No middleware at all — confirmed zero `app.add_middleware(...)` calls in the package: no `CORSMiddleware`, no request-logging, no compression, no trusted-host check. | A browser frontend calling this API cross-origin is blocked by default; there is no request-level observability. | Add `CORSMiddleware` scoped to the known frontend origin(s); add a lightweight logging middleware. |
| S10 | Medium | No API versioning — routes are unprefixed (`/health`, `/ask`, `/reindex`), version only lives in OpenAPI metadata (`version="0.1.0"`, `api.py:29-34`). | Any breaking change to `/ask`'s contract has no migration path for existing clients. | Prefix routes with `/v1` in the new backend (already namespaced better in `backend_new` as `/chat/ask`, `/admin/reindex`, `/health` — see Phase 2). |
| S11 | Medium | Dependency injection bypassed — `get_settings()` is called directly inside each route handler (`api.py:24,47,57`) instead of via FastAPI `Depends()`. It's `@lru_cache`d so functionally fine, but not idiomatic and harder to override in tests. | Makes route-level testing (e.g., injecting a fake `Settings`) awkward. | Use `Depends(get_settings)` in the new backend. |
| S12 | Low | No background tasks used — the `/ask` reindex-then-answer flow is fully synchronous inline. | Not wrong per se given current corpus size, but blocks the request thread for the full ingest check. | Combined fix with S7 (drop the per-request reindex) resolves this. |
| S13 | Low | No tests exist for the FastAPI routes at all — `tests/test_rag.py` only covers `rag.py`/`ingest.py` internals via monkeypatching, no `TestClient`/`httpx` usage anywhere. | Route-level behavior (status codes, validation errors, auth) is entirely unverified. | Add `TestClient`-based route tests in the new backend. |

### 1.3 Configuration

| # | Severity | Finding | Why it matters | Fix |
|---|----------|---------|-----------------|-----|
| S14 | High | Hardcoded fallback secret `DEFAULT_OPENAI_COMPAT_KEY = "sk-local-placeholder"` (`config.py:12`) used whenever `LLM_API_KEY`/`EMBEDDING_API_KEY` is unset (`config.py:52-57`). | App silently starts and attempts real API calls with a fake key instead of failing fast at startup — produces confusing downstream 401s instead of a clear config error, wasting debugging time in an actual deploy. | Fail startup with a clear error if no key is configured and the target isn't a detected local Ollama endpoint. |
| S15 | High | Code-level defaults point at real OpenAI (`llm_base_url` default `https://api.openai.com/v1`, `llm_model` default `gpt-4o-mini`, `embedding_model` default `text-embedding-3-small` — `config.py:22-34`) while the actual `.env`/`.env.example` configure local Ollama. | A deploy that forgets to set `LLM_BASE_URL`/`LLM_MODEL` env vars doesn't fail — it silently targets OpenAI's real API instead, either erroring confusingly (no real key) or, worse, succeeding unexpectedly and billing a different provider than intended if `OPENAI_API_KEY` happens to be set in the environment for an unrelated reason. | Make provider selection explicit and validated at startup (log which provider/model is actually active); consider erroring if defaults are used unmodified. |
| S16 | Medium | Redundant `.env` loading: `load_dotenv()` is called directly at import time (`config.py:5,10`) in addition to `pydantic_settings.BaseSettings(env_file=".env")` already loading it (`config.py:16-20`). | Harmless but redundant; a maintainer could "fix" one call site and be confused why env values still change. | Drop the manual `load_dotenv()` call; let pydantic-settings own it. |
| S17 | Medium | `RETRIEVAL_MIN_RELEVANCE` (`config.py:42`) and `app_host`/`app_port` (`config.py:44-45`) are declared, documented in `.env.example`, but **never read anywhere** in the codebase — confirmed via grep of the whole package. | Dead configuration is actively misleading: an operator reasonably assumes setting `RETRIEVAL_MIN_RELEVANCE` changes behavior; it does nothing. | Either implement relevance filtering (recommended — see §1.6/S24) or remove the setting. Remove `app_host`/`app_port` (host/port is passed to `uvicorn` on the CLI, per `README.md:84`). |
| S18 | Low | `CHUNK_SIZE`/`CHUNK_OVERLAP` env vars in `modsa_rag/config.py:39-40` are a **different, independent setting** from the hardcoded `CHUNK_SIZE=1000`/`CHUNK_MIN=200`/`CHUNK_MAX=1600` constants in `data/pipeline/chunk.py:52-54` — the pipeline's own README explicitly flags this as a point of confusion. | Two identically-named-but-unrelated knobs is a classic footgun; someone will eventually tune the wrong one. | Rename one pair (e.g., `RAW_FALLBACK_CHUNK_SIZE` for the RAG-app-side splitter, since it's a secondary path only used for un-prechunked raw files — see §1.6). |
| S19 | Low | `requirements.txt` uses only `>=` lower bounds, no upper bounds, no lockfile (`requirements.txt:1-12`); `data/requirements.txt` likewise unpinned. | A fresh `pip install` today vs. in 6 months can silently pull a breaking major version of `langchain`/`chromadb`/`fastapi`. | Pin exact versions or add a lockfile (`pip-compile`/`uv.lock`) in the new backend. |

### 1.4 Database Layer (ChromaDB)

| # | Severity | Finding | Why it matters | Fix |
|---|----------|---------|-----------------|-----|
| S20 | High | Ingestion is **full delete-and-rebuild**, not incremental: `reset_collection()` (`ingest.py:194-200`) wipes the entire Chroma collection before `add_documents()` re-embeds everything, on *any* detected source change (`ingest.py:203-254`). | At current scale (29 files) this is cheap; it does not scale — every content edit re-embeds the whole knowledge base, wasting API calls/cost. | Fine to defer for MVP (see Phase 4 roadmap — flagged as "important," not "immediate"), but design the new backend so incremental upsert is a contained future change (it already partially is, since fingerprinting is per-file — see S21). |
| S21 | Good practice (no fix needed) | Manifest-based fingerprinting (`file_fingerprint`, `ingest.py:67-78`; SHA-256+size+mtime) with a saved `source_manifest.json`, and a self-healing rebuild path if the manifest matches but the live Chroma collection is empty (`ingest.py:106-111`) — this self-heal path is unit-tested. | This is a genuinely solid piece of the design — worth explicitly preserving in the migration, not just tolerating. | Carry forward as-is into the new backend. |
| S22 | Medium | A brand-new `Chroma` client object is instantiated on every call to `get_vector_store()` (`ingest.py:44-49`), which is called on every `/ask` and `/reindex` — no client/connection caching. | Inefficient (not incorrect, since Chroma persists to disk) — unnecessary object construction overhead per request. | Cache the vector store instance at app startup (module-level or via a DI singleton), reuse across requests. |
| S23 | High (operational) | No backup/recovery strategy exists at all — nothing writes the Chroma collection anywhere except the local `chroma_db/` directory, which is itself gitignored. | If the disk/volume is lost, the entire vector index is gone with no automated recovery path (though see the key insight in §3.5 — it's fully rebuildable from `chunks/`, which mitigates severity significantly). | Document explicitly: "Chroma is a rebuildable cache; `chunks/` is the real backup," and make `/reindex` from a known-good `chunks/` state the documented recovery procedure (see Phase 3/4). |

### 1.5 API (REST design, validation, errors, logging, performance)

| # | Severity | Finding | Why it matters | Fix |
|---|----------|---------|-----------------|-----|
| S24 | Medium | Only `AskRequest.question` validation is `min_length=1` (`api.py:14`) — no max length, no rate limiting, no input sanitization beyond that. | An arbitrarily long question could blow past LLM context limits or be used for abuse/cost amplification. | Add a reasonable `max_length` and basic per-IP rate limiting. |
| S25 | Medium | No structured/leveled logging anywhere in `backend_old` (no `logging` calls at all in `api.py`; `ingest.py` does use `logger.warning`/`logger.info` in a few places, but there's no app-wide logging configuration). | No operational visibility into request volume, errors, or latency once deployed. | Configure structured logging app-wide in the new backend (see Phase 2). |
| S26 | Low | No pagination anywhere — not applicable given the current single-answer `/ask` response shape, but worth noting for any future "list sources"/"list documents" admin endpoint. | N/A now; flagging as a design note for future endpoints only. | No action needed for MVP. |
| S27 | Low | `/health` returns `{"status": "ok", "ingestion": ...}` unconditionally — even if the last ingestion attempt failed, `/health` doesn't reflect that as a non-200/degraded status. | A monitoring probe hitting `/health` would see "ok" even if the knowledge base failed to load at startup. | Make `/health` check `app.state.ingestion` for an error state and report degraded/503 accordingly. |

### 1.6 LLM Layer

| # | Severity | Finding | Why it matters | Fix |
|---|----------|---------|-----------------|-----|
| S28 | **Critical** | No retry, timeout, or backoff configuration anywhere on LLM or embedding calls — confirmed via grep (`timeout\|retry\|max_retries\|backoff` → zero matches in `modsa_rag/`). `build_llm()` (`rag.py:35-41`) constructs a bare `ChatOpenAI(...)` with none of these params. | A hung or rate-limited provider call blocks the request indefinitely — no graceful degradation, no bounded worst-case latency. This is the single most consequential reliability gap in the codebase for a real deployment. | Add `timeout=` and `max_retries=` to both LLM and embedding client construction; consider a circuit breaker if traffic grows. |
| S29 | Medium | No streaming support — `/ask` is a single blocking `invoke()` call (`rag.py:116`) returning a plain JSON body, not `StreamingResponse`/SSE. | Every answer waits for full LLM generation before any bytes reach the client — worse perceived latency for longer answers. | Nice-to-have for MVP, not blocking; consider SSE streaming in a later iteration once auth/reliability basics are in place. |
| S30 | High | No prompt-injection mitigation — retrieved chunk content (`doc.page_content`) is interpolated directly into the `{context}` slot of the system prompt with no delimiters, sanitization, or instruction-injection defense (`rag.py:44-53`, `106-111`). | Currently lower-risk since the corpus is a fixed, curated local set (not live user-supplied content), but nothing in the code guards against a future poisoned/malicious source document overriding system instructions. | Wrap retrieved content in explicit delimiters the system prompt tells the model to treat as untrusted data, not instructions (a cheap, standard mitigation). Document this as a known residual risk if not implemented immediately. |
| S31 | Medium | LLM provider is hardcoded to `langchain_openai.ChatOpenAI` — only "OpenAI-compatible over HTTP" is swappable via config (`base_url`/`api_key`/`model`); a genuinely different provider family (e.g., native Anthropic SDK) would require code changes. Embeddings have a real (if narrow) branch: `OllamaEmbeddings` vs `OpenAIEmbeddings` based on a URL-sniffing heuristic (`config.py:59-63`) that only checks `localhost`/`127.0.0.1`/`::1` on port `11434` — a remote (non-localhost) Ollama instance wouldn't be detected. | Provider abstraction is asymmetric and the Ollama-detection heuristic is brittle for anything but local dev. | Acceptable for MVP given the stated "OpenAI-compatible or Ollama" scope; note the heuristic's blind spot if Ollama Cloud or a remote Ollama host is ever used directly (see Phase 3 — Ollama Cloud is presented as OpenAI-compatible anyway, which works fine under the existing `ChatOpenAI` path). |
| S32 | Good practice (no fix needed) | Retrieval-empty fallback is implemented and correctly short-circuits before calling the LLM at all (`answer_question`, `rag.py:97-104`), returning a localized (Thai/English) "no verified info" message with `sources: []`. This exact behavior is unit-tested. | This is exactly the RAG behavior rule `CLAUDE.md` requires — a genuinely good piece of the design. | Carry forward as-is into the new backend. |

### 1.7 RAG Pipeline

| # | Severity | Finding | Why it matters | Fix |
|---|----------|---------|-----------------|-----|
| S33 | Medium | No context-length budget — `format_context()` (`rag.py:44-53`) concatenates all `k` retrieved chunks with no character/token cap. | If `retrieval_k` or individual chunk sizes grow, this can silently exceed the LLM's context window with no truncation logic or warning. | Add a token-budget check (even a rough character-count proxy) before sending to the LLM. |
| S34 | Medium | Pre-chunked JSON (from `data/pipeline/chunk.py`) is the primary path and correctly skips re-splitting via the `_prechunked` flag (`ingest.py:114-149`, `179-191`), but a secondary `RecursiveCharacterTextSplitter` path exists for raw `.pdf`/`.txt`/`.md` dropped directly into a source path — this is a second, cruder chunking strategy that's inconsistent with the structure-aware chunker used for the primary corpus. | Two different chunking qualities depending on which path a document takes could produce inconsistent retrieval quality. | Not urgent — this path is essentially unused in the current data flow (everything currently goes through pre-chunked JSON). Document it as intentional-fallback-only. |
| S35 | Low | `similarity_search()` (not `similarity_search_with_score()`) is used (`rag.py:84-90`) — no relevance score is ever available to filter against, which is *why* `RETRIEVAL_MIN_RELEVANCE` (S17) can't currently be implemented without also changing this call. | Explains the root cause of the dead-config finding S17 — worth fixing together. | Switch to `similarity_search_with_score()` and apply `RETRIEVAL_MIN_RELEVANCE` as an actual filter, or formally drop the setting. |
| S36 | Low | No re-ranking or MMR diversity applied to retrieved chunks — plain top-k similarity only. | Acceptable at current corpus size/quality; flagging as a scalability note only. | Not needed for MVP. |

### 1.8 Security

| # | Severity | Finding | Why it matters | Fix |
|---|----------|---------|-----------------|-----|
| S37 | **Critical** | (Restates S6) No auth on any endpoint, including the cost-triggering `/reindex`. | Public, unauthenticated cost/DoS vector. | Add admin-key auth on `/reindex` at minimum before any public deployment. |
| S38 | High | (Restates S9) No CORS policy configured — either fully blocks legitimate frontend access or, if a proxy/gateway strips CORS enforcement, there's no origin allowlist decided anywhere in code. | Undefined cross-origin security posture. | Configure explicit `CORSMiddleware` with an origin allowlist in the new backend. |
| S39 | Medium | (Restates S8) Verbose error messages returned to clients. | Information disclosure. | Sanitize client-facing error responses. |
| S40 | Low | File uploads: not applicable — `backend_old`'s FastAPI app has no upload endpoint at all (ingestion reads from a local filesystem path, not from HTTP uploads). | N/A — noting explicitly since the audit brief asked about file uploads. | No action needed; if an admin-upload endpoint is added later, validate file type/size and scan before ingesting. |
| S41 | Low | Path traversal: `discover_source_files()` (`ingest.py:52-64`) walks a fixed, config-defined `source_paths` list — not user-input-driven, so no path-traversal surface currently exists via the API. | N/A for current design; flagging because the audit brief asked. | No action needed unless a future endpoint accepts user-supplied file paths. |
| S42 | High | (Restates S30) No prompt-injection defense on retrieved context. | See S30. | See S30. |
| S43 | Medium | (Restates S24) No API abuse/rate-limiting control on `/ask` (cost amplification against the LLM/embedding provider) beyond the accidental throttling effect of synchronous per-request ingestion (S7 — which is itself being removed as a fix, making this gap more exposed once S7 is fixed). | Once S7 is fixed (good), `/ask` becomes *faster* to abuse at volume unless rate limiting is added at the same time. | Bundle S7's fix with adding real rate limiting — don't fix one without the other. |

### 1.9 Production Readiness — Technical Debt Summary

- **Dead code/config**: `RETRIEVAL_MIN_RELEVANCE`, `app_host`, `app_port` (S17); orphaned `mermaid.js` (S3).
- **Duplicated/confusable logic**: `CHUNK_SIZE`/`CHUNK_OVERLAP` name collision across two subsystems (S18); redundant `.env` loading (S16).
- **Hidden coupling**: `/ask` transitively coupled to full-corpus fingerprinting cost via inline reindex (S7); two independently-versioned Python projects (`data/` and `modsa_rag/`) glued only by filesystem convention (S5).
- **Anti-patterns**: broad exception swallowing with raw message leakage (S8); hardcoded placeholder secret masking misconfiguration (S14); DI bypassed in favor of direct function calls (S11).
- **Unused files**: none clearly dead beyond what's listed above — the codebase is small and mostly all in active use.
- **Bottom line**: the RAG *logic* itself (manifest-based idempotent ingestion, empty-retrieval fallback, structure-aware chunking) is genuinely well-designed for a project this size. The **operational/production layer around it — auth, error handling, retries, logging, CORS, tests — is essentially absent.** This is a "good prototype, zero production hardening" codebase, exactly what you'd expect from a project explicitly built demo-first (confirmed by `.agents/skills/modsa-backend/SKILL.md`'s own stated philosophy: "don't introduce Redis/auth frameworks/extra services before the demo actually needs them"). None of this is sloppy — it's an intentional, reasonable MVP trade-off that now needs to be paid down before real deployment.

---

## Phase 2 — Design: Migration Plan `backend_old` → `backend/`

### 2.1 Migration base decision

**Recover `backend_new` from git (`git checkout f91b6b8 -- backend_new`, or cherry-pick from `origin/wolf`) and rename/promote it to `backend/`, then harden it.** Do not rewrite from scratch.

Reasoning: the Explore audit of `backend_new` at commit `f91b6b8` found it already implements the exact layered architecture `CLAUDE.md` documents (`api/ → services/ → core/ | pipeline/`), with no meaningful layering violations — `services/` is pure Python with no FastAPI leakage, `core/` is thin client factories, `pipeline/` is pure data-prep. Its problems are the *same category* of gaps found in `backend_old` (no auth, no retry logic, no tests, unpinned deps, plain logging) — not structural ones. Rewriting from zero would mean re-deriving a folder layout that already exists and is already correct; the actual work needed is hardening, not redesigning.

### 2.2 Recommended folder tree

```
backend/
├── main.py                    # FastAPI app assembly, lifespan, middleware registration only
├── config.py                  # Centralized Settings (pydantic-settings) — single source of truth
├── Dockerfile                 # Non-root user, HEALTHCHECK, pinned base image
├── .dockerignore
├── .env.example                # Complete, accurate, no stray/irrelevant vars
├── requirements.txt            # Pinned exact versions
├── requirements.lock           # (or uv.lock/poetry.lock) — reproducible installs
├── api/                        # Routes, request validation, HTTP status mapping ONLY
│   ├── __init__.py
│   ├── chat.py                 # POST /v1/chat/ask
│   ├── admin.py                # POST /v1/admin/reindex (auth-gated)
│   └── health.py                # GET /health (reflects real ingestion/DB state)
├── services/                    # Business workflows — no FastAPI types
│   ├── __init__.py
│   ├── rag_service.py           # ask() workflow: retrieve -> prompt -> LLM -> respond
│   └── ingestion_service.py     # ingest() workflow: discover -> chunk -> embed -> store
├── core/                        # Reusable infra clients — no business logic
│   ├── __init__.py
│   ├── llm.py                    # build_llm() with timeout/retry configured
│   ├── embeddings.py             # build_embeddings() with timeout/retry configured
│   └── vectorstore.py             # Cached Chroma client singleton
├── pipeline/                     # Data prep — no LLM/FastAPI calls
│   ├── __init__.py
│   ├── loaders.py
│   ├── chunking.py
│   └── manifest.py                # Carry forward backend_old's fingerprinting design as-is (S21)
├── prompts/
│   ├── __init__.py
│   └── rag_prompt.py               # System prompt, with untrusted-context delimiters (fix for S30)
├── schemas/
│   ├── __init__.py
│   └── chat.py                     # Pydantic request/response models, with max_length validation (fix for S24)
├── middleware/
│   ├── __init__.py
│   └── logging.py                  # Structured request logging (fix for S25)
└── tests/                          # NEW — did not exist in backend_new or backend_old
    ├── __init__.py
    ├── conftest.py                  # TestClient fixture, fake Settings override
    ├── test_health.py
    ├── test_chat.py                 # Covers empty-retrieval fallback, auth-less 200, validation 422
    ├── test_admin.py                 # Covers auth-gated 401/403 without key, 200 with key
    └── test_rag_service.py           # Carry forward backend_old's existing rag/ingest unit tests
```

**Why each folder exists** (same rationale as `docs/backend-structure.md`, reaffirmed — this is the correct shape, it just needs a `middleware/` addition and a real `tests/`):

| Folder | Purpose | Must not contain |
|---|---|---|
| `api/` | HTTP surface: routing, request validation, status-code mapping | Business logic, LLM/Chroma calls |
| `services/` | Orchestrates a full user-facing workflow (ask, ingest) | FastAPI `Request`/`Response` types |
| `core/` | Stateless, reusable clients to external systems (LLM, embeddings, vector store) | Business/orchestration logic |
| `pipeline/` | Pure data transformation (load → chunk → fingerprint) | Any network call to LLM/FastAPI |
| `prompts/` | Prompt templates as data, not logic | Retrieval logic |
| `schemas/` | Pydantic I/O contracts | Side effects |
| `middleware/` | Cross-cutting request concerns (logging, future rate-limiting) | Business logic |
| `tests/` | Executable proof the above actually works | — |

### 2.3 Concrete improvements over `backend_new`/`backend_old` (what changes, and why)

| Area | Old behavior | New behavior | Fixes |
|---|---|---|---|
| Auth | `ADMIN_API_KEY` optional, open if unset | `ADMIN_API_KEY` **required** at startup in any non-local environment (fail fast if unset outside `ENV=local`) | S6, S37 |
| Rate limiting | None | `slowapi` (or equivalent) on `/chat/ask`, e.g. 10 req/min/IP for MVP | S24, S43 |
| Error handling | Bare `except Exception` → raw message to client | Narrow exception types + `@app.exception_handler`; log full detail server-side, generic message to client | S8, S39 |
| Retry/timeout | None on LLM/embedding calls | `timeout=` + `max_retries=` on both `ChatOpenAI`/`OllamaEmbeddings` construction in `core/` | S28 |
| Logging | Plain `logging.basicConfig`, no request logging | Structured logging (JSON formatter) + request-ID middleware | S25 |
| CORS | Configured but `allow_credentials=True` + wildcard methods/headers (over-broad) in `backend_new`; entirely missing in `backend_old` | Explicit origin allowlist from `CORS_ORIGINS`, `allow_credentials=False` unless a session mechanism actually needs it, narrow `allow_methods`/`allow_headers` | S9, S38 |
| Health check | Always reports "ok" regardless of ingestion state | Reflects actual ingestion/vectorstore state, returns 503 if degraded | S27 |
| Config | Hardcoded placeholder key fallback; dead `RETRIEVAL_MIN_RELEVANCE`/`app_host`/`app_port` | Fail-fast on missing key outside local Ollama; dead settings removed or implemented (relevance filtering via `similarity_search_with_score`) | S14, S17, S35 |
| `.env.example` | Stray `TYPHOON_OCR_API_KEY`, brittle relative `RAG_SOURCE_PATHS="../backend_old/chunks"` | Only vars this backend actually reads; `RAG_SOURCE_PATHS` documented as a Docker-mount path, not a relative filesystem assumption | backend_new gap noted in audit |
| Dependencies | Unpinned `>=`, `openai` with zero constraint | Pinned exact versions + lockfile | S19 |
| Docker | Runs as root, no `HEALTHCHECK`, no multi-stage | Non-root `USER`, `HEALTHCHECK CMD curl -f localhost:8000/health`, slim final stage | backend_new gap noted in audit |
| Tests | None (`backend_new`), narrow internals-only (`backend_old`) | `TestClient`-based route tests + carried-forward RAG unit tests | S13 |
| Prompt injection | None | Delimited untrusted-context block in system prompt | S30, S42 |
| Vector store client | New `Chroma` object per call | Cached singleton, built once at startup | S22 |
| `/ask` reindex coupling | Reindexes on every request | Only ingests at startup + `/admin/reindex` | S7 |

### 2.4 Files to remove, merge, or rename relative to `backend_old`

- **Remove**: `mermaid.js` (move to `docs/diagrams/` if kept at all — not part of the app).
- **Remove**: dead settings `RETRIEVAL_MIN_RELEVANCE` (unless implemented per S35), `app_host`, `app_port`.
- **Merge**: the two independent chunking configs (`modsa_rag/config.py` CHUNK_SIZE/OVERLAP vs `data/pipeline/chunk.py` constants) should be renamed to make the split explicit rather than merged into one (they genuinely serve different pipelines) — e.g. `RAW_FALLBACK_CHUNK_SIZE` for the RAG-app-side splitter.
- **Rename**: `modsa_rag/` package → flatten into `backend/` root-level layered packages (`api/`, `services/`, etc.) — matches `backend_new`'s already-correct shape, abandons the old `modsa_rag/` monolithic-module naming.
- **Keep unchanged**: `data/` pipeline (raw → processed → chunk.py → `chunks/`) stays as-is; it's a separate, already-reasonable data-prep tool, out of scope for backend hardening. `chunks/` remains the ingestion source (`RAG_SOURCE_PATHS`), mounted read-only into the backend container per the existing `docker-compose.yml` pattern.
- **Add net-new**: `tests/`, `middleware/logging.py`, `requirements.lock`, proper multi-stage/non-root `Dockerfile`.

---

## Phase 3 — Production Deployment Research

### 3.1 Backend hosting comparison

| Platform | Simplicity | Pricing (small prod instance) | Scaling | Cold starts | Storage | Deployment experience | Verdict for MOD-SA MVP |
|---|---|---|---|---|---|---|---|
| **Render** | High — git-push deploy, managed TLS/domains, simple dashboard | Starter $7/mo, Standard $25/mo | Vertical scaling via plan tier; manual horizontal scaling on higher tiers | Free tier: 30–60s after 15min idle (unacceptable for prod); **paid tiers: none** | Persistent Disks — SSD-backed, encrypted at rest, automatic daily encrypted snapshots (but disk-restore explicitly discouraged for DB recovery — corruption risk) | Best-in-class for a small team wanting minimal ops | **Recommended** — matches user's proposal, use Starter ($7/mo) minimum, never the free tier, for the always-on backend |
| **Railway** | High — similar git-push simplicity | No free tier; per-second metering, ~$10–15/mo typical for an always-on 1GB workload | Similar vertical-first model | None on paid usage | Volumes, metered | Comparable to Render, often marginally cheaper at small scale | Solid alternative if Render's disk-restore caveat is a concern; slightly less mature docs/ecosystem |
| **Fly.io** | Medium — more powerful (global Machines/volumes model) but more concepts to learn | Pay-as-you-go, no base fee; ~$2–10/mo depending on size; volumes $0.15/GB/mo always billed | Best of the three for true multi-region/edge placement | Machines can suspend/resume fast, but tuning required — not zero-config | Volumes, billed continuously | More ops overhead, more power | Overkill for MVP; keep in mind if multi-region latency becomes a real requirement later |
| **DigitalOcean** (App Platform / Droplet+volume) | Medium-High | App Platform ~$5–12/mo basic; Droplet+volume gives full control at similar cost | Manual/vertical on App Platform; full control on a Droplet | None if always-on | Block Storage volumes, standard snapshot tooling | Good middle ground, less "batteries-included" than Render | Reasonable fallback if Render's specific constraints (disk-restore, region) become a blocker |
| **AWS / GCP / Azure** | Low for a solo/small team — most powerful, most moving parts (ECS/Fargate or Cloud Run + EBS/Persistent Disk/Managed Disk, IAM, VPC, etc.) | Highly variable; typically higher effective cost for equivalent small workload once engineering time is counted | Best-in-class, industry standard | Cloud Run/Fargate can cold-start similarly to Render's free tier unless kept warm | Enterprise-grade managed storage, full backup/versioning tooling | Steepest learning curve, most powerful when you need it | **Not recommended now** — correct target only once traffic/compliance/scale genuinely demands it; premature for an MVP demo |

### 3.2 ChromaDB deployment & limitations

**Deployment options considered:**

- **Render Persistent Disk** (user's proposal) — works, SSD-backed, encrypted, auto-snapshotted; the one hard rule is *don't rely on disk-restore for recovery* (Render's own docs warn a restore can land in a corrupted state) — use application-level backup instead.
- **Docker volume on a VPS** — full control, more ops burden (you own patching/monitoring), fine if already running a VPS for other reasons.
- **Railway/DigitalOcean volumes** — functionally equivalent to Render's disk option, similar caveats.
- **Cloud object storage (S3-compatible) as the *backup* target, not primary store** — Chroma itself needs local/attached disk to operate; object storage is the right place to periodically export collection snapshots to, not to run Chroma directly against.

**Limitations that matter (and don't, for this project):**

- ChromaDB is single-node only — no built-in HA/failover; a process crash halts queries until manual restart + index reload.
- Performance is stable to a few dozen QPS; metadata-filter+ANN combined queries degrade hard under load in some benchmarks (P99 50ms → 800ms observed at 1M vectors with a filter).
- Practical single-node ceiling is roughly 10–50M embeddings before horizontal scaling becomes necessary.
- **MOD-SA's actual corpus is 29 documents / ~1.5MB of chunked JSON.** This is not within several orders of magnitude of where ChromaDB's limits start to matter. ChromaDB is unambiguously sufficient for this project's current and medium-term scale (even 100x corpus growth stays comfortably within single-node territory).

**When to graduate to Qdrant/Weaviate/Milvus/Pinecone:** only once one of these becomes true — (a) complex metadata filtering needs correct pre-filter+ANN behavior (Qdrant's Rust core applies filters before ANN search, the technically correct order; Chroma applies them after, which can hurt recall at scale), (b) corpus grows into the multi-million-vector range, or (c) concurrent QPS regularly exceeds a few dozen. None of these apply to MOD-SA today. Document this as an explicit future trigger, not a current action item.

**Backup strategy — the key project-specific insight:** most generic ChromaDB backup advice assumes the vector store is the *only* copy of the data. That's not true here — `chunks/` is git-tracked and is the actual source of truth; the Chroma index is a fully reproducible derived artifact, rebuildable at any time via `/admin/reindex`. So the correct, cheapest backup strategy is:

1. Treat `chunks/` (in git) as the real backup — already satisfied.
2. Don't rely on Render's disk snapshot as the recovery mechanism (per Render's own warning).
3. Recovery procedure = provision a fresh disk + redeploy + trigger `/admin/reindex` from the git-tracked `chunks/`. No custom export/import tooling needed for MVP scale.

### 3.3 Frontend: Vercel evaluation

- **API communication**: frontend calls the Render backend via `NEXT_PUBLIC_API_URL`-style build-time env var; standard pattern, well-documented, low risk.
- **Environment variables**: set per-environment (Preview/Production) in Vercel's dashboard; redeploy required after changes — a common source of "I fixed it and nothing happened" confusion, worth documenting in the runbook.
- **CORS**: must be enforced on the **backend** (Render) side, not Vercel — Vercel doesn't proxy cross-origin calls by default. `CORS_ORIGINS` on Render needs the Vercel production domain **and** the Vercel preview-branch wildcard domain if preview deployments should also be able to call the API during development/QA.
- **Deployment workflow**: git-push-to-deploy, preview deployments per PR — genuinely excellent for iteration speed, no notes against it.
- **CDN/caching**: Vercel's edge CDN serves static frontend assets well; API responses from Render are not cached by Vercel (correct — RAG answers shouldn't be CDN-cached anyway).
- **Verdict**: no concerns — Vercel is a safe, low-effort choice for the frontend as proposed.

### 3.4 Verdict on the user's proposed architecture

**Vercel (frontend) + Render (FastAPI backend) + ChromaDB on Render Persistent Disk is sound for a production MVP.** Two adjustments to make it fully correct:

1. Use Render's **Starter tier ($7/mo) or above** — never the free tier — for the always-on backend, since free-tier cold starts (30-60s) are unacceptable for a live chatbot.
2. Treat Render's disk as ephemeral-but-durable-enough, not as the backup — the real backup is the git-tracked `chunks/` corpus, and recovery is "redeploy + reindex," not "restore the disk."

No need to introduce Qdrant, a separate object-storage export pipeline, or a different cloud provider for the MVP. Revisit only when the graduation triggers in §3.2 are actually hit.

---

## Phase 4 — Actionable Roadmap

### 4.1 Immediate fixes (must do before any public deployment)

1. Recover `backend_new` from git (`git checkout f91b6b8 -- backend_new`) and promote to `backend/` (Phase 2 base decision).
2. Require `ADMIN_API_KEY` (fail startup if unset outside local dev) — closes S6/S37.
3. Add rate limiting to `/chat/ask` — closes S24/S43.
4. Add `timeout=`/`max_retries=` to LLM and embedding client construction — closes S28.
5. Fix CORS: explicit origin allowlist, drop wildcard methods/headers, reconsider `allow_credentials` — closes S9/S38.
6. Replace broad `except Exception` + raw message leakage with narrow handling + sanitized client responses — closes S8/S39.
7. Remove hardcoded placeholder API key fallback; fail fast on missing credentials outside local Ollama — closes S14.
8. Pin `requirements.txt` + add a lockfile — closes S19.
9. Non-root, `HEALTHCHECK`-equipped Dockerfile.
10. Deploy on Render **Starter tier or above**, never free tier.

### 4.2 Important improvements (should do soon after launch)

1. Remove per-request reindex coupling in `/ask` — closes S7.
2. Add structured logging + request-ID middleware — closes S25.
3. Make `/health` reflect actual ingestion/vectorstore state — closes S27.
4. Add `TestClient`-based route tests + carry forward existing RAG unit tests — closes S13.
5. Remove dead config (`RETRIEVAL_MIN_RELEVANCE`, `app_host`, `app_port`) or implement relevance filtering via `similarity_search_with_score` — closes S17/S35.
6. Add prompt-injection delimiters around retrieved context — closes S30/S42.
7. Cache the Chroma vector store client as a singleton — closes S22.
8. Document and rehearse the recovery procedure (redeploy + `/admin/reindex` from `chunks/`) — operationalizes §3.2.
9. Decide and fix the `chunks/`/`data/raw/`/`data/processed/` git-tracking inconsistency — closes S2.

### 4.3 Nice-to-have improvements

1. Streaming responses (SSE) for `/ask` — closes S29.
2. Incremental (non-full-rebuild) ingestion — closes S20.
3. API versioning prefix (`/v1/...`) — closes S10.
4. Switch to `Depends()`-based settings injection — closes S11.
5. Basic metrics/monitoring integration (e.g., request count/latency histograms) once traffic justifies it.
6. Move `mermaid.js` to `docs/diagrams/`; fill in `LICENSE` copyright header.

### 4.4 Recommended production architecture (ASCII)

```
                        ┌─────────────────────┐
                        │       Users          │
                        │  (browser, mobile)   │
                        └──────────┬────────────┘
                                   │ HTTPS
                                   ▼
                        ┌─────────────────────┐
                        │       Vercel          │
                        │   (frontend, CDN)     │
                        └──────────┬────────────┘
                                   │ HTTPS (CORS-allowed origin)
                                   ▼
                 ┌─────────────────────────────────┐
                 │           Render (Starter+)        │
                 │  ┌───────────────────────────┐  │
                 │  │   FastAPI (backend/)         │  │
                 │  │  api/ -> services/ ->        │  │
                 │  │  core/ | pipeline/            │  │
                 │  │  + auth + rate limit +        │  │
                 │  │  retry/timeout + logging       │  │
                 │  └───────────┬───────────────┘  │
                 │              │                      │
                 │  ┌───────────▼───────────────┐  │
                 │  │  ChromaDB (Persistent Disk)   │  │
                 │  │  rebuildable from chunks/       │  │
                 │  └───────────────────────────┘  │
                 └──────────────┬──────────────────────┘
                                │ HTTPS (OpenAI-compatible API)
                                ▼
                 ┌─────────────────────────────────┐
                 │   LLM / Embedding Provider          │
                 │   (Ollama Cloud / OpenAI-compat)     │
                 └─────────────────────────────────┘

           Source of truth (git):  chunks/  →  reindex on deploy
```

### 4.5 Final `backend/` folder tree

See §2.2 above (reproduced in full there) — `api/`, `services/`, `core/`, `pipeline/`, `prompts/`, `schemas/`, `middleware/`, `tests/`, plus `main.py`, `config.py`, `Dockerfile`, `.dockerignore`, `.env.example`, `requirements.txt`, `requirements.lock`.

### 4.6 Deployment checklist

- [ ] `backend_new` recovered from git and promoted to `backend/`
- [ ] `ADMIN_API_KEY` set as a required Render env var (not the placeholder default)
- [ ] `CORS_ORIGINS` set to the exact Vercel production + preview domains
- [ ] `LLM_BASE_URL`/`LLM_MODEL`/`EMBEDDING_*` env vars explicitly set (never relying on OpenAI code-defaults)
- [ ] Requirements pinned + lockfile committed
- [ ] Dockerfile: non-root user, `HEALTHCHECK` present
- [ ] Render service on Starter tier or above (not free)
- [ ] Persistent Disk attached and mounted at the configured `CHROMA_DIR`
- [ ] `/admin/reindex` smoke-tested against the deployed `chunks/` corpus post-deploy
- [ ] `/health` verified to report real ingestion state
- [ ] Rate limiting verified against `/chat/ask` (manual burst test)
- [ ] Route-level tests passing in CI (or at minimum run manually pre-deploy)
- [ ] Recovery runbook written: "redeploy + `/admin/reindex`" documented somewhere durable (README or `docs/`)
- [ ] Vercel `NEXT_PUBLIC_API_URL`(or equivalent) pointed at the Render backend URL

### 4.7 Risk assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Unauthenticated `/reindex` triggers cost-DoS | High if deployed as-is | High (real API cost) | Immediate fix #2 (§4.1) |
| Hung LLM call with no timeout blocks a worker | Medium under any real traffic | Medium-High (request pile-up) | Immediate fix #4 |
| Render disk loss with no backup discipline | Low probability, but currently no rehearsed recovery | Medium (mitigated heavily by `chunks/` being the real source of truth) | Important fix #8 |
| Wrong LLM provider silently used due to unset env var | Medium (easy to forget on first deploy) | Medium (confusing failures, possible wrong billing) | Immediate fix #7 + checklist item |
| Free-tier cold starts if someone "saves cost" by downgrading | Medium (tempting cost optimization) | High (broken UX, 30-60s hangs) | Explicit checklist item, document why Starter+ is required |
| Prompt injection via a future untrusted content source | Low today (fixed curated corpus), rises if corpus sourcing changes | Medium | Important fix #6, revisit if corpus ingestion ever includes external/user-submitted content |

### 4.8 Estimated deployment difficulty per component

| Component | Difficulty | Notes |
|---|---|---|
| Recovering + hardening `backend/` | Medium (2-4 focused days) | Bulk of the work is the Immediate + Important lists above; structure already exists |
| Render backend deploy | Low | Git-push deploy, well-documented |
| ChromaDB on Render disk | Low | Attach disk, set `CHROMA_DIR`, done — no separate DB service to provision |
| Vercel frontend deploy | Low | Standard, frontend scaffold currently empty though (`frontend/` has no `package.json` yet — separate prerequisite, not part of this backend audit) |
| CORS/env wiring between Vercel and Render | Low-Medium | Easy to get wrong once (wrong origin string), quick to fix once discovered |
| Monitoring/observability | Low for MVP (structured logs only), Medium if real metrics dashboards added later | Deferred to "nice-to-have" |

### 4.9 Suggested deployment order

1. Recover and harden `backend/` locally (Immediate fixes list) — verify with `python -c "import main"`, `/health`, `/chat/ask`, `/admin/reindex` per `CLAUDE.md`'s existing testing checklist.
2. Deploy `backend/` to Render (Starter tier), attach Persistent Disk, set all env vars from the checklist.
3. Trigger `/admin/reindex` against the deployed instance, verify `/chat/ask` returns grounded answers with sources for a known topic, and verify the no-verified-info fallback for an out-of-scope question.
4. Build/deploy the frontend to Vercel once it has an actual framework scaffold (currently empty per `CLAUDE.md`), pointed at the Render backend URL.
5. Wire `CORS_ORIGINS` on Render to the live Vercel domain(s) and re-verify end-to-end from the deployed frontend.
6. Add monitoring/logging review as a standing operational habit; revisit Important/Nice-to-have lists on a regular cadence rather than treating this as one-and-done.

---

## Sources (Phase 3 research, July 2026)

- [Render vs Railway vs Fly.io: Pricing Compared (2026)](https://dev.to/pavel-hostim/render-vs-railway-vs-flyio-pricing-compared-2026-2e5p)
- [Render vs Railway vs Fly.io: Pricing Compared and When Each Wins (2026)](https://hostim.dev/blog/render-vs-railway-vs-fly-pricing/)
- [Railway vs Render vs Fly.io for Solo Developers in 2026](https://devtoolpicks.com/blog/railway-vs-render-vs-fly-io-solo-developers-2026)
- [Single-Node Chroma: Performance and Limitations — Chroma Docs](https://docs.trychroma.com/deployment/performance)
- [ChromaDB in RAG: Advantages, Limits and Alternatives — Edana](https://edana.ch/en/2026/02/08/pros-and-cons-of-chromadb-for-retrieval-augmented-generation-great-for-getting-started-but-risky/)
- [Persistent Disks – Render Docs](https://render.com/docs/disks)
- [ChromaDB Backups — Chroma Cookbook](https://cookbook.chromadb.dev/strategies/backup/)
- [Vector Database Comparison 2026: ChromaDB vs. Qdrant vs. pgvector vs. Pinecone vs. LanceDB](https://4xxi.com/articles/vector-database-comparison/)
- [Qdrant vs Chroma 2026: Best Vector DB for RAG?](https://www.kunalganglani.com/blog/qdrant-vs-chroma)
- [Platforms with a real free tier for developers in 2026 — Render](https://render.com/articles/platforms-with-a-real-free-tier-for-developers-in-2026)
- [FastAPI deployment options — Render](https://render.com/articles/fastapi-deployment-options)
- [Node.js Deployment Guide (2026): Render & Vercel](https://medium.com/@krishsurya1249/node-js-deployment-guide-2026-production-setup-environment-variables-render-vercel-6169329a7253)
