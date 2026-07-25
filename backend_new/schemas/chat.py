from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=1)


class AskResponse(BaseModel):
    answer: str
    sources: list[dict[str, object]]
    confidence: str  # "high" | "medium" | "low"