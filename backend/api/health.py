from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
def health(request: Request):
    return {
        "status": "ok",
        "ingestion": getattr(request.app.state, "ingestion", None),
    }
