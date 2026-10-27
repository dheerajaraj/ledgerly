from pydantic import BaseModel, Field

from .common import InputModel


class AskIn(InputModel):
    question: str = Field(min_length=3, max_length=500)


class AskOut(BaseModel):
    answer: str
    tools_used: list[str]
    generated_by: str


class SummaryOut(BaseModel):
    month: str
    summary: str
    generated_by: str
