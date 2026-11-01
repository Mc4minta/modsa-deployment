"""Validated intent for the opt-in pilot; not an arbitrary query language."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Category = Literal["scholarship", "fees", "academic_calendar", "academic_rules", "registration", "others"]
AcademicYear = Annotated[int, Field(ge=2400, le=3000)]
AdmissionRound = Annotated[int, Field(ge=1, le=99)]


class QueryIntent(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    categories: list[Category] = Field(default_factory=list, max_length=6)
    academic_years: list[AcademicYear] = Field(default_factory=list, max_length=20)
    rounds: list[AdmissionRound] = Field(default_factory=list, max_length=20)
    ambiguities: list[str] = Field(default_factory=list, max_length=10)
