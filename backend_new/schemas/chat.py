from pydantic import BaseModel, Field, field_validator


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1500)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        question = value.strip()
        if not question:
            raise ValueError("question must not be blank")
        return question


class AskResponse(BaseModel):
    answer: str
    sources: list[dict[str, object]]
    confidence: str  # "high" | "medium" | "low"
