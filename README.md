# MOD-SA

KMUTT Student Affairs RAG chatbot.

## Structure

- `backend/`: FastAPI RAG backend (active)
- `data/chunks/`: prepared knowledge source consumed by `backend/`
- `frontend/`: Web client
- `docs/`: Architecture + development guides (`backend-structure.md`, `development-guide.md`)
- `.agents/skills/modsa-backend/`: Agent skill for backend work

## Graph build

สร้างกราฟจากเอกสารใหม่: [Phase12 expansion CLI](graph/EXPANSION.md) — รับfile/directoryใต้data/chunks ใช้schemaเดิม มีงบAPIแบบexplicit/cacheและโหลดNeo4jแบบแยกnamespaceต่อรุ่นเอกสาร ยังไม่เปิดใช้ในAPI

สำหรับเครื่องใหม่: [ติดตั้งและสร้างกราฟ](graph/QUICKSTART.md) ใช้ `python graph/run.py build`; สร้างexportเดิมได้โดยไม่ใช้API key และมีComposeแยกสำหรับNeo4j

ชุดสร้างกราฟแยกอยู่ [graph/](graph/README.md): `build/` สำหรับคำสั่ง, `data/` สำหรับ schema/input/export, `tests/` สำหรับทดสอบ. อ่าน chunks เดิมใน `data/chunks/` และไม่เปลี่ยน `/chat/ask` ซึ่งยังใช้ Vector RAG

งานทดลอง schema/โมเดล/คำตอบและรายงานเดิมย้ายไป `.local/graph-rag-research/` ที่ Git ignore แล้ว ไม่ใช่ dependency ของคำสั่งสร้างกราฟ

## Quick Start (local)


```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit keys / models as needed
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

API:

- `GET /health`
- `POST /chat/ask` — body `{"question":"..."}`
- `POST /admin/reindex` — requires header `X-Admin-Key` matching `ADMIN_API_KEY`

Default `RAG_SOURCE_PATHS` points at `../data/chunks`.

Windows PowerShell: use `.\.venv\Scripts\python.exe` instead of `python`/`pip` activation, e.g. `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`, and `Copy-Item .env.example .env`. For the server use `.\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000`.

`GET /health` returns 200 only when nonempty ingestion succeeded, otherwise 503/not_ready. Missing/unreadable input preserves the existing Chroma collection; it is not an instruction to clear it.

## Docker

From repo root (requires `.env`):

```bash
cp .env.example .env
docker compose up --build
```

Chroma persists in the `chroma_data` volume. Chunks mount from `data/chunks`.

Compose uses repository-root build context and separate Docker endpoint overrides `DOCKER_LLM_BASE_URL` / `DOCKER_EMBEDDING_BASE_URL` (default `http://host.docker.internal:11434/v1`). Do not point container endpoints at host-local `localhost`. `.dockerignore` excludes secrets, research archives and local environments from the build context.
