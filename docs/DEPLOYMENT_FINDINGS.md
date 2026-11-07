# MOD-SA Deployment Inspection Report

- **Branch Inspected**: `modsa-vm`
- **Commit Hash Inspected**: `3c01ed5e03823ca5a3a6e81a34fd1937450ac4e6`
- **Inspection Date**: 2026-11-07
- **Inspection Mode**: Read-only inspection; no application files changed.

---

## 1. Summary

- **Stack**: React 19 + TypeScript + Vite 8 frontend; FastAPI + LangChain + ChromaDB backend running on Python 3.12.
- **Chroma Mode**: Embedded `PersistentClient` reading and persisting directly to local disk (`chroma_db/`).
- **Streaming**: None. Both frontend and backend communicate strictly via synchronous request/response JSON (`POST /chat/ask`).
- **Embedding Setup**: Switched via `EMBEDDING_PROVIDER` (`ollama`, `huggingface`, or `openai`); defaults to `ollama` (`bge-m3:latest`), production configured for Hugging Face (`BAAI/bge-m3`).
- **Top Deployment Risks**:
  1. `docker-compose.yml` specifies `context: ./backend`, which conflicts with `backend/Dockerfile` expecting repo root `.` (`COPY backend/ .`, `COPY data/chunks ./data/chunks`).
  2. Dependencies in `backend/requirements.txt` are not pinned with exact versions (`==`), posing build reproducibility risks.
  3. No frontend Dockerfile or Nginx configuration currently exists in the repository.
  4. Backend exposes Swagger docs (`/docs`, `/redoc`, `/openapi.json`) and leaks raw exception strings in 500 error responses (`detail=str(exc)`).

---

## 2. Findings

### A. Repository layout

#### 1. Top-level structure and workspace configuration
- **Answer**: The repository is a single multi-project repository housing both frontend and backend under one Git tree. The backend lives in `backend/`, the frontend lives in `frontend/`, knowledge and pipeline data live in `data/`, documentation in `docs/`, and administrative scripts in `scripts/`. It is **not** configured as a monorepo workspace: there is no root `package.json`, the root `package-lock.json` is an empty stub (`"packages": {}`), and there is no `pnpm-workspace.yaml` or Lerna configuration. Frontend dependencies are isolated in `frontend/package.json`, and backend dependencies in `backend/requirements.txt`.
- **Evidence**: `package-lock.json:1-6`, `frontend/package.json:1-36`, `backend/requirements.txt:1-14`.
- **Confidence**: Confirmed in code.

#### 2. Differences between `modsa-vm` and other branches
- **Answer**:
  - `git branch -a` shows local branches (`dev`, `main`, `modsa-vm`, `v3`, `v4`) and corresponding remote branches on `origin`.
  - Diff against `dev` (`git diff dev..modsa-vm`): Exactly 1 file changed, 1 insertion:
    ```python
    # backend/core/embeddings.py:29
    check_embedding_ctx_length=False,
    ```
    This single line disables context length pre-checks in `OpenAIEmbeddings`.
  - Diff against `main` (`git diff --stat main..modsa-vm`): 190 files changed (29,669 insertions, 3,393 deletions). This reflects commit `3a2987e` ("V4 (#5)"), which updated chunk JSONs in `data/chunks/`, updated raw files in `data/raw/`, processed markdown in `data/processed/`, updated `data/sources.json`, and added evaluation sets in `data/evaluation/`.
  - Recent Git log on `modsa-vm`:
    - `3c01ed5 fix: bug for llm callingi` (disables `check_embedding_ctx_length`)
    - `3a2987e V4 (#5)` (data chunk updates)
    - `9a3401a Merge pull request #3 from Mc4minta/refactor/frontend`
    - `e51fa25 refactor(frontend): migrate to TypeScript`
  - VM-specific deployment changes: `modsa-vm` does **not** contain any VM-specific deployment changes (no Nginx configuration, no systemd units, no Cloudflare tunnel configuration, and no updated compose files).
- **Evidence**: `git log -n 5 modsa-vm`, `git diff dev..modsa-vm`, `backend/core/embeddings.py:29`.
- **Confidence**: Confirmed in code.

#### 3. Existing deployment files
- **Answer**:
  - `backend/Dockerfile` (`backend/Dockerfile:1-28`): Python 3.12-slim base, installs curl and build-essential, copies `backend/requirements.txt`, copies `backend/` and `data/chunks/`, creates unprivileged user `appuser`, exposes port 8000, runs container health check on `http://localhost:${PORT:-8000}/health`, and runs `uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}`.
  - `backend/.dockerignore` (`backend/.dockerignore:1-7`): Ignores `.venv`, `__pycache__`, `*.pyc`, `.env`, `chroma_db`, `.pytest_cache`, `*.log`.
  - `docker-compose.yml` (`docker-compose.yml:1-26`): Defines `backend` service with `context: ./backend`, ports `"${APP_PORT:-8000}:8000"`, volume mounts `chroma_data:/app/chroma_db` and `./data/chunks:/app/storage/chunks:ro`, and `extra_hosts` for `host.docker.internal`.
  - `render.yml` (`render.yml:1-47`): Render blueprint declaring `modsa-backend` web service, runtime `docker`, `dockerfilePath: ./backend/Dockerfile`, `dockerContext: .`, plan `free`, and `healthCheckPath: /health`.
  - Files not present: `vercel.json` (absent), `Procfile` (absent), `nginx*` (absent), `.github/workflows/*` (absent). No Cloudflare tunnel binaries or configuration files exist in the repository (Cloudflare is only referenced in documentation: `docs/deployment-plan-free-tier.md:112-132`).
- **Evidence**: `backend/Dockerfile:1-28`, `docker-compose.yml:1-26`, `render.yml:1-47`.
- **Confidence**: Confirmed in code.

---

### B. Frontend

#### 4. Framework and build tool
- **Answer**:
  - Framework: React 19 (`react: ^19.2.7`, lockfile resolves to `19.2.8`; `react-dom: ^19.2.7`, lockfile resolves to `19.2.8`).
  - Build Tool: Vite 8 (`vite: ^8.1.1`, lockfile resolves to `8.1.5`; `@vitejs/plugin-react: ^6.0.3`).
  - Language: TypeScript 7 (`typescript: ^7.0.2`).
  - Linter: Oxlint (`oxlint: ^1.71.0`).
  - Test Runner: Vitest (`vitest: ^4.0.9`) with JSDOM (`jsdom: ^26.1.0`).
  - Markdown rendering: `react-markdown: ^10.1.0`, `rehype-sanitize: ^6.0.0`, `remark-gfm: ^4.0.1`.
- **Evidence**: `frontend/package.json:16-35`, `frontend/package-lock.json`.
- **Confidence**: Confirmed in code.

#### 5. Build command, output directory, required Node version
- **Answer**:
  - Build command: `npm run build`, which executes `tsc -b && vite build`.
  - Output directory: `dist/` (standard Vite output directory, confirmed by `frontend/.gitignore:11`).
  - Required Node version: Not explicitly defined in `frontend/package.json` (no `engines` field), no `.nvmrc`, no `.node-version`, and no CI configuration exists. Node.js 20 LTS or Node.js 22 LTS is required for modern Vite 8 and TypeScript 7 tooling.
- **Evidence**: `frontend/package.json:8`, `frontend/.gitignore:11`.
- **Confidence**: Build command and output directory confirmed in code; required Node version inferred/not determinable from repo.

#### 6. Backend URL configuration and hardcoded occurrences
- **Answer**:
  - Environment variable: `VITE_API_URL`.
  - Where read: `frontend/src/services/api.ts:10-11`:
    ```typescript
    const configuredApiUrl = (import.meta.env.VITE_API_URL || "").replace(/\/+$/, "");
    const API_URL = configuredApiUrl || (import.meta.env.DEV ? "http://localhost:8000" : "");
    ```
  - Baked in at build time: **YES**. Vite evaluates `import.meta.env.VITE_*` statically at compile time and injects string literals into the output bundle in `dist/`. In production builds (`import.meta.env.DEV === false`), if `VITE_API_URL` is omitted or empty, `API_URL` evaluates to `""` (empty string). Calls to `${API_URL}/chat/ask` and `${API_URL}/health` resolve as relative URLs (`/chat/ask` and `/health`).
  - Complete list of hardcoded occurrences:
    1. `frontend/.env.example:1`: `VITE_API_URL=http://localhost:8000`
    2. `frontend/src/services/api.ts:11`: `"http://localhost:8000"` (dev fallback when `VITE_API_URL` is unset)
    3. `frontend/src/services/api.ts:96`: `"http://localhost"` (fallback base origin in `isSafeUrl` validator)
    4. `frontend/scripts/mock-browser-api.mjs:61-62`: `8000`, `"127.0.0.1"`, `"http://127.0.0.1:8000"` (fixture for local tests)
    5. No Render URLs exist anywhere in `frontend/` source code. Render URLs appear only in documentation (`docs/deployment-plan-free-tier.md:71,82,87,92`).
- **Evidence**: `frontend/src/services/api.ts:10-11,96`, `frontend/.env.example:1`, `docs/deployment-plan-free-tier.md:71`.
- **Confidence**: Confirmed in code.

#### 7. Client-side routing and SPA fallback requirements
- **Answer**: The application does **not** use React Router or any client-side routing library. The entire application runs as a single-view interface in `frontend/src/App.tsx`. All user navigation (chat sessions, drawer toggles, sources modal) is controlled by React component state (`activeSessionId`, `sidebarOpen`, `sourcesMessage`). There are no non-root paths in the frontend code. However, standard Nginx SPA fallback (`try_files $uri $uri/ /index.html;`) is recommended so that direct reloads or non-root URLs do not return 404 from Nginx.
- **Evidence**: `frontend/package.json:16-22`, `frontend/src/App.tsx:24-49`, `frontend/src/main.tsx:1-19`.
- **Confidence**: Confirmed in code.

#### 8. Frontend chat response consumption
- **Answer**: Chat responses are consumed via plain `fetch` JSON requests. The frontend sends a standard HTTP POST request to `/chat/ask` and parses the full response body using `await response.json()`. It does **not** use `EventSource`, `ReadableStream`, `getReader`, `text/event-stream`, or WebSockets. Cancellation is handled by attaching an `AbortController` signal to the fetch call (`composeAbortSignal`).
- **Evidence**: `frontend/src/services/api.ts:204-241`:
  ```typescript
  response = await fetch(`${API_URL}/chat/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question: question.trim() }),
    signal: composed.signal,
  });
  ...
  if (contentType.includes("application/json")) {
    body = await response.json();
  ...
  return normalizeChatResponse(body);
  ```
- **Confidence**: Confirmed in code.

---

### C. Backend

#### 9. Entrypoint file, app object, and start command
- **Answer**:
  - Entrypoint file: `backend/main.py`.
  - App object: `app = FastAPI(...)` (`backend/main.py:38-43`).
  - Start commands:
    - In container: `uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}` (`backend/Dockerfile:28`).
    - In local dev: `uvicorn main:app --reload --host 127.0.0.1 --port 8000` (`backend/README.md:12`).
    - In Windows launcher: `uvicorn main:app --reload --port 8000` (`run.bat:12,185`).
    - Render configuration uses Docker runtime invoking the Dockerfile `CMD` (`render.yml:4-5`).
    - No `Procfile` exists.
- **Evidence**: `backend/main.py:38-43`, `backend/Dockerfile:28`, `render.yml:4-5`.
- **Confidence**: Confirmed in code.

#### 10. Python version and dependency pinning
- **Answer**:
  - Python version: `3.12` specified in `backend/Dockerfile:1` (`FROM python:3.12-slim`). `runtime.txt`, `pyproject.toml`, and `.python-version` do not exist.
  - Dependency file: `backend/requirements.txt` (primary app) and `data/requirements.txt` (offline data prep).
  - Dependency pinning: **None** of the dependencies are pinned to an exact version (`==`). All use minimum-version constraints (`>=`) or are unconstrained:
    - `fastapi>=0.111`
    - `uvicorn[standard]>=0.30`
    - `python-dotenv>=1.0`
    - `pypdf>=4.2`
    - `pydantic-settings>=2.3`
    - `langchain>=0.2`
    - `langchain-community>=0.2`
    - `langchain-openai>=0.1`
    - `langchain-chroma>=0.1`
    - `langchain-text-splitters>=0.2`
    - `langchain-ollama>=0.1`
    - `langchain-huggingface>=0.1`
    - `chromadb>=0.5`
    - `openai` (unpinned)
  - Exact `chromadb` requirement: `chromadb>=0.5` (`backend/requirements.txt:13`).
- **Evidence**: `backend/Dockerfile:1`, `backend/requirements.txt:1-14`.
- **Confidence**: Confirmed in code.

#### 11. Complete list of API routes
- **Answer**: The application registers three endpoints. There is no global router prefix such as `/api`. Routes are mounted directly on root. (See Section 3 for the complete route table).
- **Evidence**: `backend/main.py:54-56`, `backend/api/chat.py:8-12`, `backend/api/health.py:3-7`, `backend/api/admin.py:11-26`.
- **Confidence**: Confirmed in code.

#### 12. Environment variables read by code
- **Answer**: Environment variable reading is centralized in `backend/config.py` using Pydantic Settings (`pydantic_settings.BaseSettings`) and loaded via `python-dotenv` (`load_dotenv()`). Two auxiliary variables exist outside `config.py`: `PORT` (read by shell in `backend/Dockerfile:26,28`) and `TYPHOON_OCR_API_KEY` (read via `os.getenv` in `data/pipeline/normalize.py:76`). (See Section 3 for the complete environment variable table).
- **Evidence**: `backend/config.py:18-70`, `backend/Dockerfile:26,28`, `data/pipeline/normalize.py:76`.
- **Confidence**: Confirmed in code.

#### 13. Streaming endpoints
- **Answer**: There are **zero** streaming endpoints in the application. Neither `StreamingResponse`, `EventSourceResponse`, async generators yielding chunks, nor WebSockets exist in the backend codebase. `POST /chat/ask` calls `answer_question()`, which invokes `llm.invoke()` synchronously and returns a standard dictionary.
- **Evidence**: `backend/api/chat.py:11-18`, `backend/services/rag_service.py:179-194`:
  ```python
  response = llm.invoke(
      [
          SystemMessage(content=prompt),
          HumanMessage(content=question)
      ]
  )
  return {
      "answer": response.content,
      "sources": source_summary(docs)
  }
  ```
- **Confidence**: Confirmed in code.

#### 14. CORS configuration
- **Answer**: CORS middleware is mounted in `backend/main.py:46-52`.
  - Allowed origins: Configured via `CORS_ORIGINS` environment variable (comma-separated string parsed by `Settings.resolved_cors_origins`). Default value: `["http://localhost:5173", "http://127.0.0.1:5173"]`.
  - Allowed methods: `["GET", "POST"]` (`backend/main.py:50`).
  - Allowed credentials: `False` (`backend/main.py:49`).
  - Allowed headers: `["Content-Type", "X-Admin-Key"]` (`backend/main.py:51`).
- **Evidence**: `backend/main.py:46-52`, `backend/config.py:66-69,81-82`:
  ```python
  app.add_middleware(
      CORSMiddleware,
      allow_origins=settings.resolved_cors_origins,
      allow_credentials=False,
      allow_methods=["GET", "POST"],
      allow_headers=["Content-Type", "X-Admin-Key"],
  )
  ```
- **Confidence**: Confirmed in code.

#### 15. Existing health or readiness endpoint
- **Answer**: A dedicated health check endpoint exists at `GET /health` in `backend/api/health.py:6-11`. It returns HTTP 200 with JSON payload `{"status": "ok", "ingestion": app.state.ingestion}`. It is used as the container healthcheck in `backend/Dockerfile:25-26` and configured as the health check path in `render.yml:8`.
- **Evidence**: `backend/api/health.py:6-11`, `backend/Dockerfile:25-26`, `render.yml:8`.
- **Confidence**: Confirmed in code.

#### 16. Logging approach and local disk writes
- **Answer**:
  - Logging: Standard Python `logging` module configured in `backend/main.py:16-19` with format `"%(asctime)s %(levelname)s [%(name)s] %(message)s"` at `INFO` level, outputting to stdout/stderr.
  - Disk writes: The backend writes strictly to `settings.chroma_dir` (`chroma_db/`). This directory receives ChromaDB segment files, `chroma.sqlite3`, and `source_manifest.json` (written by `backend/pipeline/manifest.py:44-47`).
  - Other disk writes: Zero file uploads, zero temporary files, zero session caches, and zero separate SQLite databases are written to disk by the backend application.
- **Evidence**: `backend/main.py:16-20`, `backend/pipeline/manifest.py:31-47`.
- **Confidence**: Confirmed in code.

---

### D. ChromaDB and data

#### 17. ChromaDB architecture and initialization
- **Answer**: ChromaDB is embedded in-process (`PersistentClient` / local `persist_directory`). It does not run as a client/server service and does not use `HttpClient`.
- **Evidence**:
  - In `backend/core/vectorstore.py:18-22`:
    ```python
    _vector_store = Chroma(
        collection_name=settings.chroma_collection,
        persist_directory=str(settings.chroma_dir),
        embedding_function=build_embeddings(settings),
    )
    ```
  - In `backend/services/ingestion_service.py:28`:
    ```python
    client = chromadb.PersistentClient(path=str(settings.chroma_dir))
    ```
- **Confidence**: Confirmed in code.

#### 18. Persistence path, collection name, and distance metric
- **Answer**:
  - Persistence path: `settings.chroma_dir` (default: `Path("chroma_db")`, configurable via `CHROMA_DIR`).
  - Collection name: `settings.chroma_collection` (default: `"modsa_kmutt"`, configurable via `CHROMA_COLLECTION`).
  - Distance metric / collection metadata: Distance metric is **not** explicitly configured in code; no `collection_metadata` or `hnsw:space` argument is passed. Chroma and LangChain Chroma default to squared Euclidean distance (`"l2"`).
- **Evidence**: `backend/config.py:53-54`, `backend/core/vectorstore.py:18-22`.
- **Confidence**: Confirmed in code.

#### 19. Committed Chroma data, source documents, and Git LFS
- **Answer**:
  - Committed Chroma databases: None. `chroma_db/` is excluded in root `.gitignore:9` and `backend/.dockerignore:5`. No `.sqlite3` or index files are committed to Git.
  - Committed source document sets:
    - `data/chunks/`: 253 JSON chunk files across 7 subdirectories (`academic_calendar`, `academic_rules`, `dormitory`, `fees`, `others`, `registration`, `scholarship`). Total size: ~2.31 MB.
    - `data/raw/`: 28 raw documents (.pdf, .docx, .txt). Total size: ~1.84 MB.
    - `data/processed/`: 28 cleaned Markdown files. Total size: ~1.84 MB.
    - `data/evaluation/`: 2 evaluation sets (`eval.json`, `eval_311026.json`). Total size: ~1.23 MB.
    - `data/chunks_081026.zip` (~354 KB), `data/data_081026.zip` (~690 KB), `data/sources.json` (~23.6 KB).
    - Total data footprint committed in `data/`: ~8.7 MB.
  - Git LFS: **Not used**. There is no `.gitattributes` file in the repository, and files are stored as plain Git blobs.
- **Evidence**: `git ls-files data/`, `.gitignore:9`, `backend/.dockerignore:5`.
- **Confidence**: Confirmed in code.

#### 20. Ingestion and indexing pipeline
- **Answer**:
  - Ingestion implementation: `backend/services/ingestion_service.py:ingest_sources(settings, force=False)`.
  - How executed:
    1. Automatically on startup during FastAPI `lifespan` (`backend/main.py:27`).
    2. On demand via `POST /admin/reindex` (`backend/api/admin.py:31`).
  - Inputs read: Files discovered by `discover_source_files` from paths in `settings.source_paths` (`RAG_SOURCE_PATHS`, default `"chunks"`). Supported file extensions: `.json`, `.pdf`, `.txt`, `.md`.
  - Chunking behavior:
    - Pre-chunked JSON: Loaded by `load_json_documents` (`backend/pipeline/loaders.py:32-71`). Preserves chunk structure and metadata (`title`, `department`, `source_url`, `page`, `chunk_id`), flagging `_prechunked=True` to bypass splitting.
    - Non-JSON files: Split by `RecursiveCharacterTextSplitter` with `chunk_size=settings.chunk_size` (default 1000), `chunk_overlap=settings.chunk_overlap` (default 150), separators `["\n\n", "\n", " ", ""]` (`backend/pipeline/chunking.py:10-14`).
  - Embedding function: Process singleton `build_embeddings(settings)` (`backend/core/embeddings.py:9-30`).
  - Batching: Indexed into Chroma in batches of 32 chunks (`batch_size = 32`) to prevent network or provider timeouts (`backend/services/ingestion_service.py:83-91`).
  - Manifest optimization: SHA-256 fingerprint generated for all source files and saved in `source_manifest.json` inside `settings.chroma_dir`. On startup, if `previous_manifest == current_manifest` and Chroma collection has documents, indexing is skipped (`backend/services/ingestion_service.py:44-56`).
- **Evidence**: `backend/services/ingestion_service.py:39-100`, `backend/pipeline/loaders.py:17-104`, `backend/pipeline/chunking.py:9-20`.
- **Confidence**: Confirmed in code.

#### 21. Dependence on persistent filesystem on Render today
- **Answer**: On Render today, the blueprint in `render.yml:7` specifies `plan: free`. Render Free tier does not support persistent disks. Consequently, the container runs on an ephemeral disk. The application functions by baking `data/chunks/` into the Docker image (`COPY data/chunks ./data/chunks` in `backend/Dockerfile:16`). On every cold start, `lifespan` detects an empty Chroma collection and builds the index into the container's ephemeral filesystem. On a persistent filesystem (e.g. Ubuntu VM disk volume), `source_manifest.json` matches across restarts, allowing the backend to skip re-indexing and boot in milliseconds without re-embedding.
- **Evidence**: `render.yml:7`, `backend/Dockerfile:16`, `docs/deployment-plan-free-tier.md:73`, `backend/services/ingestion_service.py:44-56`.
- **Confidence**: Confirmed in code.

---

### E. Embeddings and LLM

#### 22. External embedding endpoint call details
- **Answer**:
  - File / Function: `backend/core/embeddings.py`, `build_embeddings(settings: Settings) -> Embeddings`.
  - Providers supported:
    1. `ollama`: Uses `langchain_ollama.OllamaEmbeddings`.
       - URL: `settings.resolved_embedding_base_url` (`EMBEDDING_BASE_URL`, stripped to scheme + host + port by `config.py:103-106`).
       - Model: `settings.embedding_model` (`EMBEDDING_MODEL`).
       - HTTP client: `httpx` (internal to Ollama client).
    2. `huggingface`: Uses `langchain_huggingface.HuggingFaceEndpointEmbeddings`.
       - Token: `settings.resolved_embedding_api_key` (`EMBEDDING_API_KEY` or `OPENAI_API_KEY`). Required; startup raises `ValueError` if missing (`config.py:90-94`).
       - Model: `settings.embedding_model` (`EMBEDDING_MODEL`, e.g. `"BAAI/bge-m3"`).
       - HTTP client: `requests` / `huggingface_hub` HTTP client.
    3. `openai`: Uses `langchain_openai.OpenAIEmbeddings`.
       - URL: `settings.embedding_base_url` (`EMBEDDING_BASE_URL`).
       - Key: `settings.resolved_embedding_api_key` (`EMBEDDING_API_KEY`, `LLM_API_KEY`, or `"sk-local-placeholder"`).
       - Model: `settings.embedding_model` (`EMBEDDING_MODEL`).
       - Timeout: `settings.embedding_timeout` (`EMBEDDING_TIMEOUT`, default 30.0s).
       - Max retries: `settings.embedding_max_retries` (`EMBEDDING_MAX_RETRIES`, default 2).
       - Extra flag: `check_embedding_ctx_length=False` (`backend/core/embeddings.py:29`).
       - HTTP client: `httpx` (internal to OpenAI client).
- **Evidence**: `backend/core/embeddings.py:9-30`, `backend/config.py:34-51,89-106`.
- **Confidence**: Confirmed in code.

#### 23. Embedding model name, dimension, and query-time consistency
- **Answer**:
  - Model name: Configurable via `EMBEDDING_MODEL`. Code default is `"text-embedding-3-small"` (`backend/config.py:47`). Deployment templates configure `"bge-m3:latest"` for Ollama (`backend/.env.example:26`) and `"BAAI/bge-m3"` for Hugging Face (`render.yml:39`, `backend/.env.example:32`).
  - Dimension: Not explicitly stated in code. (`BAAI/bge-m3` produces 1024-dimensional vectors; `text-embedding-3-small` produces 1536). Chroma automatically configures index dimension from the first batch added.
  - Query-time vs. ingestion model: **Identical**. Both ingestion (`ingestion_service.py:81`) and query retrieval (`rag_service.py:46`) call `get_vector_store(settings)` (`backend/core/vectorstore.py:10-24`), which binds the exact same `build_embeddings(settings)` instance.
- **Evidence**: `backend/core/vectorstore.py:18-22`, `backend/services/ingestion_service.py:81`, `backend/services/rag_service.py:46`.
- **Confidence**: Confirmed in code.

#### 24. Remaining Ollama code, config, docs, and env vars
- **Answer**: Ollama remains an active, fully supported option across the entire project:
  - Code: `backend/core/embeddings.py:3,11-15` (`OllamaEmbeddings`), `backend/config.py:34-36` (`Literal["ollama", ...]`), `backend/config.py:103-106` (host/port resolution), `backend/requirements.txt:11` (`langchain-ollama>=0.1`).
  - Config: `docker-compose.yml:14-17` (`LLM_BASE_URL: http://host.docker.internal:11434/v1`, `EMBEDDING_PROVIDER: ollama`), `render.yml:23` (`LLM_BASE_URL: https://ollama.com/v1`), `backend/.env.example:7,23-26` (`LLM_BASE_URL="http://localhost:11434/v1"`, `EMBEDDING_PROVIDER="ollama"`).
  - Docs: Documented extensively in `backend/README.md:17,24,28`, `README.md:8`, `CLAUDE.md:9,71`, `docs/backend-structure.md:10,32,149`, and `docs/deployment-plan-free-tier.md:10,48,99,114-130`.
- **Evidence**: `backend/core/embeddings.py:3,11-15`, `docker-compose.yml:14-17`, `backend/.env.example:7,23-26`.
- **Confidence**: Confirmed in code.

#### 25. LLM provider for answer generation
- **Answer**:
  - Library: `langchain_openai.ChatOpenAI` (`backend/core/llm.py:1,16-23`), targeting OpenAI-compatible endpoints.
  - Model name: `settings.llm_model` (`LLM_MODEL`, default `"gpt-4o-mini"`, configured as `"minimax-m3:cloud"` in `render.yml:27` and `backend/.env.example:9`).
  - API Key: `LLM_API_KEY` or `OPENAI_API_KEY` (`backend/config.py:26-29`). Falls back to placeholder `"sk-local-placeholder"` if unset (`backend/config.py:85-86`).
  - Endpoint Base URL: `LLM_BASE_URL` (`backend/config.py:25`, default `"https://api.openai.com/v1"`).
  - Timeout & retries: `LLM_TIMEOUT` (default 30.0s) and `LLM_MAX_RETRIES` (default 2) passed to `ChatOpenAI` (`backend/core/llm.py:21-22`).
  - Temperature: Hardcoded to `0` (`backend/core/llm.py:20`).
  - Token limits & cost controls: None configured in code (no `max_tokens` or per-request cost limiting).
- **Evidence**: `backend/core/llm.py:9-25`, `backend/config.py:25-32`.
- **Confidence**: Confirmed in code.

---

### F. Security and abuse surface

#### 26. Data modification and admin endpoints
- **Answer**:
  - `POST /admin/reindex` (`backend/api/admin.py:25-33`): Deletes the existing Chroma collection and rebuilds it from source files. Protected by header `X-Admin-Key`. Authorization is verified in `_require_admin` (`backend/api/admin.py:14-23`):
    - If `ADMIN_API_KEY` is not set in backend settings, the endpoint raises HTTP 500 and aborts.
    - If `X-Admin-Key` is missing or does not match `ADMIN_API_KEY` (compared with constant-time `secrets.compare_digest`), it raises HTTP 401.
  - File upload endpoints: None exist in the application.
  - Data deletion / update endpoints: None exist in the application (other than `/admin/reindex`).
- **Evidence**: `backend/api/admin.py:14-33`.
- **Confidence**: Confirmed in code.

#### 27. Rate limiting, request size limits, and input validation
- **Answer**:
  - Rate limiting: **None** at backend application level (no SlowAPI, Redis limiter, or in-memory limiter).
  - Request body size limit: None explicitly configured in FastAPI or Uvicorn.
  - Input validation: Implemented on `AskRequest` (`backend/schemas/chat.py:39-59`):
    - `question` length bounded: `min_length=1`, `max_length=1500` (`MAX_QUESTION_LENGTH = 1500`).
    - Strips whitespace; rejects empty string with HTTP 422.
    - Sensitive data pattern rejection (`_contains_sensitive_input` in `backend/schemas/chat.py:27-37`): Rejects passwords, API tokens (`sk-...`, `ghp_...`, JWTs), private keys, 13-digit Thai national ID numbers, and sensitive Thai keywords ("รหัสผ่าน", "เลขบัตรประชาชน"). Rejection raises ValueError -> HTTP 422.
    - Rejects unexpected extra fields (`model_config = ConfigDict(extra="forbid")`).
  - Frontend output limit: Frontend enforces `MAX_ANSWER_LENGTH = 100_000` (`frontend/src/services/api.ts:13,130-135`).
- **Evidence**: `backend/schemas/chat.py:6-59`, `frontend/src/services/api.ts:13,130-135`.
- **Confidence**: Confirmed in code.

#### 28. Public documentation and debug surfaces
- **Answer**:
  - Public documentation: FastAPI defaults are **not disabled** in `backend/main.py:38-43`. Therefore, `/docs` (Swagger UI), `/redoc` (ReDoc), and `/openapi.json` are publicly exposed.
  - Debug mode: Not enabled on FastAPI instance (`debug=False` default).
  - Exception disclosure: In `backend/api/chat.py:20-24`, generic exceptions in `ask` are caught and returned as `HTTPException(status_code=500, detail=str(exc))`. This leaks raw Python exception messages to the client.
- **Evidence**: `backend/main.py:38-43`, `backend/api/chat.py:20-24`.
- **Confidence**: Confirmed in code.

#### 29. Committed secrets and `.gitignore` coverage
- **Answer**:
  - Committed secrets: **None found**. All `.env.example` files contain placeholder strings (`"ollama"`, `"change-me"`, `"your-typhoon-ocr-key"`). No real API keys, tokens, or credentials are committed.
  - `.gitignore` coverage:
    - Root `.gitignore:1` ignores `.env`.
    - Root `.gitignore:9` ignores `chroma_db/`.
    - Root `.gitignore:12-14` has `# data/raw/`, `# chunks/`, `# data/processed/` **commented out**. Consequently, all files under `data/chunks/`, `data/raw/`, and `data/processed/` are actively tracked by Git.
    - `backend/.dockerignore:1-7` ignores `.venv`, `__pycache__`, `*.pyc`, `.env`, `chroma_db`.
    - `frontend/.gitignore:10-13` ignores `node_modules`, `dist`, `*.local`.
- **Evidence**: `.gitignore:1-16`, `backend/.dockerignore:1-7`, `frontend/.gitignore:1-24`.
- **Confidence**: Confirmed in code.

#### 30. User data handling and storage
- **Answer**:
  - Backend: Completely stateless. No database for chat messages, no logging of user questions or answers, no chat session tracking, and no file uploads.
  - Frontend: Chat history is stored entirely client-side in the user's browser `localStorage` under keys `modsa-chats` and `modsa-sidebar-open` (`frontend/src/utils/storage.ts:3-10`). Storage is constrained to a maximum of 50 chats, 100 messages per chat, 20,000 characters per message, and 500,000 total characters.
- **Evidence**: `frontend/src/utils/storage.ts:3-10,194-209`, `backend/api/chat.py:11-24`.
- **Confidence**: Confirmed in code.

---

### G. Tests and CI

#### 31. Existing tests, test commands, and CI workflows
- **Answer**:
  - Backend unit tests (`backend/tests/`):
    - `backend/tests/test_chat_schema.py`: Validates `AskRequest` trimming, length validation, sensitive pattern rejection, and rejection of extra fields.
    - `backend/tests/test_chat_prompt.py`: Validates prompt escaping (`escape_retrieved_context`).
    - Test command: `python -m unittest discover tests` (run from `backend/`).
  - Outdated script: `scripts/test_rag.py` exists but uses obsolete `from app...` imports from a legacy structure; it does not execute cleanly without modification.
  - Frontend unit tests (`frontend/src/`):
    - 6 Vitest suites covering API error handling, input guards, chat recovery, state transitions, storage persistence, and component rendering (`MessageBubble`, `SourcesPanel`).
    - Test commands: `npm run test:run` (`vitest run`), `npm run check` (runs lint, typecheck, tests, and build).
  - CI workflows: None exist (no `.github/workflows/` directory in the repository).
  - Deployment validation commands:
    - Backend: `python -c "import main"` from `backend/`; `GET /health` -> 200; `POST /chat/ask` with empty body -> 422; `POST /chat/ask` with query -> 200; `POST /admin/reindex` with `X-Admin-Key` -> 200.
    - Frontend: `npm run check` in `frontend/`.
- **Evidence**: `backend/tests/test_chat_schema.py:1-36`, `backend/tests/test_chat_prompt.py:1-16`, `frontend/package.json:6-15`.
- **Confidence**: Confirmed in code.

---

## 3. Route Table and Environment Variable Table

### API Route Table

| Method | Full Path | Router Prefix | Handler | File:Line | Auth / Protection | Request Model / Headers | Response Model | Purpose |
|---|---|---|---|---|---|---|---|---|
| `GET` | `/health` | None | `health` | `backend/api/health.py:7` | Public (None) | None | `{status: str, ingestion: Any}` | Container & deployment health check |
| `POST` | `/chat/ask` | `/chat` | `ask` | `backend/api/chat.py:12` | Public (None) | Body: `AskRequest` (`{question: str}`) | `AskResponse` (`{answer: str, sources: list}`) | RAG question answering |
| `POST` | `/admin/reindex` | `/admin` | `reindex` | `backend/api/admin.py:26` | Protected | Header: `X-Admin-Key: <ADMIN_API_KEY>` | `{status: str, files: int, ...}` | Wipes collection and rebuilds vector index |
| `GET` | `/docs` | None | FastAPI default | `backend/main.py:38` | Public (None) | None | HTML | Interactive Swagger UI |
| `GET` | `/redoc` | None | FastAPI default | `backend/main.py:38` | Public (None) | None | HTML | ReDoc documentation UI |
| `GET` | `/openapi.json` | None | FastAPI default | `backend/main.py:38` | Public (None) | None | JSON | OpenAPI schema specification |

---

### Environment Variable Table

| Variable Name | Read Where | Default Value | Purpose | Committed Secret? |
|---|---|---|---|---|
| `LLM_BASE_URL` | `backend/config.py:25` | `https://api.openai.com/v1` | Base URL for OpenAI-compatible LLM endpoint | No (placeholder in `.env.example`) |
| `LLM_API_KEY` / `OPENAI_API_KEY` | `backend/config.py:26-29` | `None` (falls back to `"sk-local-placeholder"`) | Authentication key for LLM provider | No (placeholder in `.env.example`) |
| `LLM_MODEL` | `backend/config.py:30` | `gpt-4o-mini` | Model identifier for LLM generation | No |
| `LLM_TIMEOUT` | `backend/config.py:31` | `30.0` | Timeout in seconds for LLM HTTP calls | No |
| `LLM_MAX_RETRIES` | `backend/config.py:32` | `2` | Maximum retry attempts for failed LLM calls | No |
| `EMBEDDING_PROVIDER` | `backend/config.py:34-37` | `ollama` | Provider selection: `ollama`, `huggingface`, or `openai` | No |
| `EMBEDDING_BASE_URL` | `backend/config.py:38-41` | `https://api.openai.com/v1` | Base URL for embedding endpoint | No |
| `EMBEDDING_API_KEY` / `OPENAI_API_KEY` | `backend/config.py:42-45` | `None` (falls back to LLM key or placeholder) | Auth key for embeddings (required if `huggingface`) | No (placeholder in `.env.example`) |
| `EMBEDDING_MODEL` | `backend/config.py:46-49` | `text-embedding-3-small` | Model identifier for embeddings | No |
| `EMBEDDING_TIMEOUT` | `backend/config.py:50` | `30.0` | Timeout in seconds for embedding calls | No |
| `EMBEDDING_MAX_RETRIES` | `backend/config.py:51` | `2` | Maximum retry attempts for embedding calls | No |
| `CHROMA_DIR` | `backend/config.py:53` | `chroma_db` | Filesystem path for ChromaDB persistence | No |
| `CHROMA_COLLECTION` | `backend/config.py:54` | `modsa_kmutt` | ChromaDB collection name | No |
| `RAG_SOURCE_PATHS` | `backend/config.py:55` | `chunks` | Comma-separated paths containing source documents | No |
| `CHUNK_SIZE` | `backend/config.py:56` | `1000` | Character chunk size for splitting non-JSON files | No |
| `CHUNK_OVERLAP` | `backend/config.py:57` | `150` | Overlap character count for document splitting | No |
| `RETRIEVAL_K` | `backend/config.py:58` | `4` | Number of context chunks retrieved for answer | No |
| `RETRIEVAL_MIN_RELEVANCE` | `backend/config.py:59-62` | `0.35` | Minimum relevance threshold (reserved setting) | No |
| `APP_HOST` | `backend/config.py:64` | `127.0.0.1` | Host interface for local server binding | No |
| `APP_PORT` | `backend/config.py:65` | `8000` | Port for local server binding | No |
| `CORS_ORIGINS` | `backend/config.py:66-69` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated origins allowed by CORSMiddleware | No |
| `ADMIN_API_KEY` | `backend/config.py:70` | `None` | Secret key required to authorize `/admin/reindex` | No (placeholder in `.env.example`) |
| `PORT` | `backend/Dockerfile:26,28` | `8000` (in `${PORT:-8000}`) | Port injected by container runtime | No |
| `TYPHOON_OCR_API_KEY` | `data/pipeline/normalize.py:76` | `None` | API key for offline Typhoon OCR processing | No (placeholder in `.env.example`) |
| `VITE_API_URL` | `frontend/src/services/api.ts:10` | `""` (dev fallback: `http://localhost:8000`) | Backend URL baked into frontend static bundle | No |

---

## 4. Streaming Verdict

No user-facing flow or backend API endpoint in this repository depends on SSE, streaming HTTP chunked transfers, or WebSockets. Both the frontend client (`frontend/src/services/api.ts:204-241`) and the backend service (`backend/services/rag_service.py:179-194`, `backend/api/chat.py:11-18`) execute request-response cycles exclusively using standard synchronous JSON payloads over HTTP POST. While Cloudflare Quick Tunnels (`trycloudflare.com`) historically exhibit buffering and incompatibility with Server-Sent Events (SSE) and HTTP streaming (subject to re-verification against current Cloudflare documentation), this limitation has **no impact** on the MOD-SA application because SSE is not utilized anywhere in the architecture. However, for a production VM deployment, a named Cloudflare Tunnel (`cloudflared tunnel run`) bound to a custom domain remains strongly recommended over an ephemeral Quick Tunnel for DNS stability, static routing, and systemd service management.

---

## 5. Open Questions

1. **LLM Provider on the VM**: Will the production deployment continue pointing to Ollama Cloud (`https://ollama.com/v1` with `minimax-m3:cloud`), a locally hosted Ollama instance running directly on the Ubuntu VM, or another cloud provider (such as Typhoon or OpenAI)?
2. **Embedding Provider on the VM**: What embedding provider will be active on the VM? If Hugging Face Inference API (`EMBEDDING_PROVIDER=huggingface`, `BAAI/bge-m3`) is used, is a valid Hugging Face token ready? If local Ollama (`EMBEDDING_PROVIDER=ollama`) is preferred on the VM, does the VM have sufficient RAM/CPU to run `bge-m3` alongside the app?
3. **Cloudflare Tunnel Architecture**: Is the intended Cloudflare deployment a persistent Named Tunnel (`cloudflared tunnel run <tunnel-name>`) managed with a tunnel token, or an ephemeral Quick Tunnel?
4. **Node.js Target Version**: What Node.js runtime version is standardized for building the frontend container or CI pipeline (e.g. Node 20 LTS or Node 22 LTS)?
5. **Public API Docs Exposure**: Should the Swagger UI (`/docs`), ReDoc (`/redoc`), and OpenAPI schema (`/openapi.json`) remain publicly accessible on the VM, or should they be disabled in FastAPI (`docs_url=None`) or blocked at the Nginx reverse proxy level?
6. **Data Directory Git Tracking**: The repository currently tracks ~8.7 MB of data files under `data/` (`raw/`, `processed/`, `chunks/`), while `data/pipeline/README.md:18-20` asserts that these folders should be gitignored. Is `data/chunks/` intended to remain the source of truth committed to the repository for VM deployments?

---

## 6. Implications for the Planned Deployment

- **Fix Docker Build Context in Compose**: In `docker-compose.yml:4`, the context is set to `./backend`, while `backend/Dockerfile` expects the build context to be the repository root (`.`):
  ```dockerfile
  COPY backend/requirements.txt .
  COPY backend/ .
  COPY data/chunks ./data/chunks
  ```
  Attempting `docker compose build` using the existing `docker-compose.yml` fails. The new Compose file must set `context: .` and `dockerfile: backend/Dockerfile` (matching `render.yml`).
- **No Separate ChromaDB Container Needed**: Because Chroma is initialized in-process (`PersistentClient`), no external ChromaDB container, server process, or network bridge is required. The VM only needs to persist `CHROMA_DIR` (e.g. `/app/chroma_db`) via a named Docker volume or bind mount.
- **Frontend Architecture on VM**: The frontend currently lacks a Dockerfile. To serve frontend and backend from a single Ubuntu VM, a multi-stage Dockerfile or an Nginx container serving `frontend/dist/` should be introduced.
- **Eliminate CORS via Relative Routing**: If Nginx serves the frontend static assets at `/` and reverse-proxies `/chat/`, `/health`, and `/admin/` to the backend container on port 8000, the frontend can be built with `VITE_API_URL=""` (empty). This causes the frontend to make same-origin requests (`/chat/ask`), completely eliminating CORS preflight overhead and cross-origin configuration issues.
- **Lock Down `/admin/reindex`**: The reindex endpoint wipes and re-embeds the entire vector database. In production on the VM, `ADMIN_API_KEY` must be set to a high-entropy secret, and Nginx can optionally restrict access to `/admin/` (or block it from the public tunnel).
- **Sanitize Error Tracebacks**: In `backend/api/chat.py:23`, `detail=str(exc)` forwards raw internal exceptions to clients on HTTP 500 errors. An application exception handler or Nginx error page should sanitize 500 responses to prevent leaking internal library error strings.
- **Pin Backend Dependencies**: `backend/requirements.txt` contains loose minimum versions (`fastapi>=0.111`, `chromadb>=0.5`, unpinned `openai`). For reliable VM builds, dependencies should be pinned using `pip freeze` or a lockfile.

---

## 7. Not Inspected

1. **Target Ubuntu VM Host Environment**: The target VM's CPU architecture, available RAM, disk space, Docker version, and host network configuration could not be inspected as no access to the target host exists.
2. **Cloudflare Account and Domain Configuration**: Cloudflare DNS zones, Tunnel dashboard configs, and Cloudflare WAF/caching rules could not be inspected.
3. **Live API Provider Latency and Health**: External connectivity and response times to Ollama Cloud (`https://ollama.com/v1`) and Hugging Face Inference API (`https://api-inference.huggingface.co`) were not tested, as network calls to external third-party services were prohibited during this inspection.
