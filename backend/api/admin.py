from __future__ import annotations

import secrets

from fastapi import APIRouter, Header, HTTPException, Request

from config import get_settings
from services.ingestion_service import ingest_sources


router = APIRouter(prefix="/admin")


def _require_admin(x_admin_key: str | None) -> None:
    settings = get_settings()
    if not settings.admin_api_key:
        raise HTTPException(
            status_code=500,
            detail="ADMIN_API_KEY is not configured on the server — refusing to allow reindex.",
        )
    if not x_admin_key or not secrets.compare_digest(x_admin_key, settings.admin_api_key):
        raise HTTPException(status_code=401, detail="Invalid or missing admin API key")


@router.post("/reindex")
def reindex(
    request: Request,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
):
    _require_admin(x_admin_key)
    result = ingest_sources(get_settings(), force=True)
    request.app.state.ingestion = result
    return result
