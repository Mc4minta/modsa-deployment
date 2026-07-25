# MOD-SA

KMUTT Student Affairs RAG chatbot.

## Structure

- `backend/`: FastAPI RAG backend (active)
- `backend_old/`: previous monolithic backend, reference only
- `datasets/chunks/`: prepared knowledge source consumed by `backend/`
- `frontend/`: Web client
- `docs/`: Architecture + development guides (`backend-structure.md`, `development-guide.md`)
- `.agents/skills/modsa-backend/`: Agent skill for backend work

## Quick Start (local)

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit keys / models as needed
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

API:

- `GET /health`
- `POST /chat/ask` — body `{"question":"..."}`
- `POST /admin/reindex` — requires header `X-Admin-Key` matching `ADMIN_API_KEY`

Default `RAG_SOURCE_PATHS` points at `../datasets/chunks`.

## Docker

From repo root (requires `.env`):

```bash
cp .env.example .env
docker compose up --build
```

Chroma persists in the `chroma_data` volume. Chunks mount from `datasets/chunks`.
