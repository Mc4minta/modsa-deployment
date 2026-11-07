import logging

from fastapi import APIRouter, HTTPException

from schemas.chat import AskRequest, AskResponse
from config import get_settings
from services.rag_service import answer_question

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat")


@router.post("/ask", response_model=AskResponse)
def ask(request: AskRequest):

    try:
        return answer_question(
            get_settings(),
            request.question
        )

    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to process chat question")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )
