import logging
import time

from fastapi import APIRouter, HTTPException

from schemas.chat import AskRequest, AskResponse
from config import get_settings
from services.rag_service import answer_question


router = APIRouter(prefix="/chat")
logger = logging.getLogger(__name__)


@router.post("/ask", response_model=AskResponse)
def ask(request: AskRequest):
    started_at = time.perf_counter()
    try:
        result = answer_question(
            get_settings(),
            request.question
        )
    except Exception as exc:
        logger.exception("Chat request failed")
        logger.info(
            "Chat request outcome=error elapsed=%.3fs exception=%s",
            time.perf_counter() - started_at,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        ) from exc
    logger.info(
        "Chat request outcome=ok elapsed=%.3fs answer_length=%d source_count=%d",
        time.perf_counter() - started_at,
        len(result["answer"]),
        len(result["sources"]),
    )
    return result