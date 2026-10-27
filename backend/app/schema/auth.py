from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from .common import InputModel, NormalizedEmail, OrmModel


class RegisterIn(InputModel):
    email: NormalizedEmail
    password: str = Field(min_length=8, max_length=128)
    name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] = ""


class LoginIn(InputModel):
    email: NormalizedEmail
    password: str


class UserOut(OrmModel):
    id: int
    email: str
    name: str


class CurrentUser(UserOut):
    """The signed-in user, as passed from api/deps.py to handlers."""


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
