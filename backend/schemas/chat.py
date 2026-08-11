import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


MAX_QUESTION_LENGTH = 1500

_SECRET_PATTERNS = (
    r"\b(?:password|passwd|pwd)\s*[:=]\s*\S+",
    r"\b(?:api[ _-]?key|access[ _-]?token|client[ _-]?secret|secret|token)\s*[:=]\s*\S+",
    r"\b(?:sk-[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9_]{20,}|AIza[0-9A-Za-z_-]{20,}|AKIA[0-9A-Z]{16})\b",
    r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b",
    r"-----BEGIN [A-Z ]+ PRIVATE KEY-----",
    r"\bprivate[ _-]?key\s*[:=]\s*\S+",
)

_THAI_SENSITIVE_TERMS = (
    "เลขบัตรประชาชน",
    "เลขประจำตัวประชาชน",
    "หมายเลขบัตรประชาชน",
    "บัตรประชาชน",
    "รหัสผ่าน",
    "คีย์ API",
)


def _contains_sensitive_input(question: str) -> bool:
    if any(re.search(pattern, question, flags=re.IGNORECASE) for pattern in _SECRET_PATTERNS):
        return True
    if any(term.casefold() in question.casefold() for term in _THAI_SENSITIVE_TERMS):
        return True
    if re.search(r"คีย์\s*API", question, flags=re.IGNORECASE):
        return True

    digits = re.sub(r"[\s-]", "", question)
    return len(digits) == 13 and digits.isdigit() and bool(re.search(r"(?:\d[\s-]*){13}", question))


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=MAX_QUESTION_LENGTH)

    @field_validator("question", mode="before")
    @classmethod
    def normalize_question(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("question must not be empty")
        return value

    @field_validator("question")
    @classmethod
    def reject_sensitive_input(cls, value: str) -> str:
        if _contains_sensitive_input(value):
            raise ValueError("question contains sensitive information; remove it and try again")
        return value


class AskResponse(BaseModel):
    answer: str
    sources: list[dict[str, object]]
