from datetime import date as Date
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from .common import InputModel, OrmModel

CATEGORIES = [
    "Software",
    "Hardware",
    "Office",
    "Travel",
    "Meals",
    "Marketing",
    "Professional services",
    "Utilities",
    "Taxes & fees",
    "Education",
    "Other",
]

Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


def _check_category(value: str) -> str:
    if value not in CATEGORIES:
        raise ValueError(f"category must be one of {CATEGORIES}")
    return value


class ExpenseCreate(InputModel):
    date: Date
    description: Description
    amount_cents: int = Field(gt=0)
    # Leave empty to let Claude categorize it
    category: str | None = None

    @field_validator("category")
    @classmethod
    def valid_category(cls, value):
        if value in (None, ""):
            return None
        return _check_category(value)


class ExpenseUpdate(InputModel):
    """Partial update: only fields present in the request are changed."""
    date: Date | None = None
    description: Description | None = None
    amount_cents: int | None = Field(default=None, gt=0)
    category: str | None = None

    @field_validator("category")
    @classmethod
    def valid_category(cls, value):
        return value if value is None else _check_category(value)

    @model_validator(mode="after")
    def no_explicit_nulls(self):
        nulls = sorted(name for name in self.model_fields_set if getattr(self, name) is None)
        if nulls:
            raise ValueError(f"{', '.join(nulls)} can't be null")
        return self


class ExpenseOut(OrmModel):
    id: int
    date: Date
    description: str
    amount_cents: int
    category: str
    category_source: str


class CsvImportOut(BaseModel):
    imported: int
    skipped_rows: list[int]
    expenses: list[ExpenseOut]
