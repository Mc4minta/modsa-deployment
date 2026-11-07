# MOD-SA

KMUTT Student Affairs RAG chatbot.

## Structure

- `backend/`: FastAPI RAG backend (active)
- `backend_old/`: previous monolithic backend, reference only
- `data/chunks/`: prepared knowledge source consumed by `backend/`
- `frontend/`: Web client (React + Vite)
- `nginx/`: Reverse proxy, rate limiting, and static SPA serving
- `scripts/`: Operations scripts (backup, restore, reindex, freeze dependencies)
- `docs/`: Architecture, inspection findings, and deployment guides
- `.agents/skills/modsa-backend/`: Agent skill for backend work

## Quick Start (local dev)

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

## Single-VM Production Deployment

For full deployment on an Ubuntu 24.04 VM using Docker Compose, Nginx, and Cloudflare Tunnel, follow the complete runbook:

- **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)**

Quick preview with Docker Compose:

```bash
# 1. Configure environment
cp .env.example .env
nano .env

# 2. Start stack with ephemeral Cloudflare Quick Tunnel
docker compose --profile quick up -d --build

# 3. Read generated public URL
docker compose logs cloudflared
```
