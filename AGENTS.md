# Repository Guidelines

## Project Structure & Module Organization

`backend_new/` is the active FastAPI RAG service. Keep HTTP handling in `api/`, workflows in `services/`, provider and Chroma clients in `core/`, ingestion utilities in `pipeline/`, Pydantic contracts in `schemas/`, and prompt text in `prompts/`. Dependencies should flow `api -> services -> core/pipeline`; do not place LLM, retrieval, or ingestion logic in routes.

`backend_old/` is legacy reference code, but its `chunks/` directory is the default knowledge source. `datasets/` contains raw, processed, and evaluation material. `docs/` holds architecture and operating notes, while `frontend/1.1wolf/` preserves the Wolf UI and `frontend/1.2tongtong/` is the active React client.

## Build, Test, and Development Commands

Run local backend commands from `backend_new/`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn main:app --reload --host 127.0.0.1 --port 8000
python -c "import main"
```

The import command is a quick syntax/import smoke check. From the repository root, `docker compose up --build` builds the service, mounts prepared chunks read-only, and persists Chroma in a named volume. Verify runtime behavior with `GET /health`, `POST /chat/ask`, and, when appropriate, `POST /admin/reindex`.

For the frontend, run `npm ci` then `npm run check` from `frontend/1.2tongtong/`; this runs lint, Vitest, and the production build.

## Coding Style & Naming Conventions

Use Python 3 conventions: four-space indentation, type hints, `snake_case` functions/modules, and `PascalCase` classes and Pydantic models. Keep functions focused and configuration centralized in `backend_new/config.py`. No formatter or linter is currently configured; follow PEP 8 and preserve the surrounding import and annotation style.

## Testing Guidelines

Legacy tests remain in `scripts/test_rag.py`. Active-backend tests live in `backend_new/tests/`, use files named `test_*.py`, and run with:

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

Cover successful retrieval, source metadata, empty-index fallback, validation errors, and reindex behavior. There is no formal coverage threshold; test changed behavior and report manual API checks in the PR.

## Commit & Pull Request Guidelines

History follows Conventional Commit-style subjects such as `feat:`, `fix:`, `refactor:`, and `docs:`. Keep commits imperative and narrowly scoped. PRs should explain the change, affected layer, configuration or data impact, and verification performed; link relevant issues and include request/response samples or UI screenshots when applicable.

## Security & Configuration

Copy `.env.example`; never commit `.env`, credentials, Chroma data, or logs. Set `ADMIN_API_KEY` outside local development, preserve source metadata, and reindex through the API rather than editing Chroma files directly.
