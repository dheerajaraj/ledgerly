from datetime import datetime
from typing import Annotated

from pydantic import StringConstraints

from .common import InputModel, NormalizedEmail, OrmModel

ClientName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]


class ClientCreate(InputModel):
    name: ClientName
    email: NormalizedEmail


class ClientUpdate(InputModel):
    name: ClientName
    email: NormalizedEmail


class ClientOut(OrmModel):
    id: int
    name: str
    email: str
    created_at: datetime
