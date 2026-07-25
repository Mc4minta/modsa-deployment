from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.admin import router as admin_router
from api.chat import router as chat_router
from api.health import router as health_router
from config import get_settings
from services.ingestion_service import ingest_sources


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    try:
        app.state.ingestion = ingest_sources(settings)
        logger.info("Startup ingestion: %s", app.state.ingestion)
    except Exception:
        logger.exception("Startup ingestion failed")
        app.state.ingestion = {
            "status": "error",
            "reason": "startup ingestion failed",
        }
    yield


app = FastAPI(
    title="MOD-SA RAG API",
    description="KMUTT Student Affairs RAG chatbot",
    version="0.1.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.resolved_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Admin-Key"],
)

app.include_router(chat_router)
app.include_router(health_router)
app.include_router(admin_router)
