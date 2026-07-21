from fastapi import APIRouter, HTTPException

from schemas.chat import AskRequest, AskResponse
from config import get_settings
from services.rag_service import answer_question


router = APIRouter(prefix="/chat")


@router.post("/ask", response_model=AskResponse)
def ask(request: AskRequest):

    try:
        return answer_question(
            get_settings(),
            request.question
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc)
        )