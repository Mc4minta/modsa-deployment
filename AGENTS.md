# Repository Guidelines

## Project Structure & Module Organization

`backend/` contains the FastAPI RAG service: HTTP validation in `api/`, workflows in `services/`, clients in `core/`, ingestion in `pipeline/`, prompts in `prompts/`, and Pydantic contracts in `schemas/`. Dependencies flow `api -> services -> core/pipeline`; keep routes thin. `frontend/src/` holds React components, API services, i18n, utilities, and assets. Knowledge preparation lives under `data/`: source documents in `raw/`, normalized Markdown in `processed/`, retrieval JSON in `chunks/`, and review sets in `evaluation/`. Graph build code/data/tests live in `graph/`; start at `graph/QUICKSTART.md`. The ignored `.local/graph-rag-research/` archive is not a dependency. See `docs/` and component READMEs for details.

## Build, Test, and Development Commands

- Graph pilot replay: `python graph/run.py check` / `build`; new documents: `python graph/run.py expand --input data/chunks/<file-or-folder> --check`. Read `graph/EXPANSION.md` before `--extract` (explicit API budget) or `--load` (database writes). Neither enables Hybrid in the API or approves policy.

- `cd backend; python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt` prepares the API environment.
- In `backend/`, run `Copy-Item ..\.env.example .env` once, then `uvicorn main:app --reload --port 8000`.
- `cd frontend; npm ci; npm run dev` installs locked dependencies and starts Vite.
- `npm run lint` runs Oxlint; `npm run build` creates the production bundle.
- `docker compose up --build` starts the backend with persistent Chroma storage. `run.bat` starts both services on Windows once `backend/.env` exists.
- Run `python -m data.pipeline.triage` or `python -m data.pipeline.chunk` from the root.

## Coding Style & Naming Conventions

Use four spaces, type hints, `snake_case` functions/modules, and `PascalCase` classes in Python. Centralize settings in `backend/config.py`; keep LLM and vector-store clients out of routes. Frontend code uses two spaces, double quotes, semicolons, `PascalCase.tsx` components, and `camelCase` helpers. Preserve source metadata and grounded-answer fallbacks.

## Testing Guidelines

Run backend tests with `PYTHONPATH=backend python3 -m unittest discover -s backend/tests` and graph tests with the same command using `-s graph/tests` (from root, with backend dependencies). The frontend has `npm run check`. There is no coverage threshold. For backend work, run `python -c "import main"` from `backend/`, check `GET /health` (200 only after successful nonempty ingestion; 503 otherwise), exercise `POST /chat/ask`, and confirm an empty question returns 422. Frontend changes must pass lint and build, then be checked at desktop and mobile widths. Name backend tests `backend/tests/test_*.py`, graph tests `graph/tests/test_*.py`, and frontend tests `*.test.ts` or `*.test.tsx`.

## Commit & Pull Request Guidelines

History uses short Conventional Commit-style subjects such as `fix: unmatched path` and `refactor: update chunks`. Use `type: imperative summary` and keep commits focused. Pull requests should explain intent and risk, list validation, link issues, document config changes, and include UI screenshots or API request/response samples where relevant.

## Security & Configuration

Copy `.env.example`; never commit secrets, Chroma files, or logs. Protect `/admin/reindex` with `ADMIN_API_KEY`, review `CORS_ORIGINS`, and rebuild indexes through the endpoint.
