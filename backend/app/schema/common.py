from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr


class InputModel(BaseModel):
    """Base for request bodies: unknown fields are rejected with 422."""
    model_config = ConfigDict(extra="forbid")


class OrmModel(BaseModel):
    """Base for responses built from ORM objects."""
    model_config = ConfigDict(from_attributes=True)


NormalizedEmail = Annotated[EmailStr, AfterValidator(str.lower)]
