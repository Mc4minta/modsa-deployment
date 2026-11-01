from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/health")
def health(request: Request):
    ingestion = getattr(request.app.state, "ingestion", None)
    ready = bool(ingestion and ingestion.get("status") in {"indexed", "skipped"}
                 and ingestion.get("files", 0) > 0)
    return JSONResponse(status_code=200 if ready else 503,
                        content={"status": "ok" if ready else "not_ready", "ingestion": ingestion})
