from datetime import date as Date, datetime
from typing import Annotated

from pydantic import Field, StringConstraints

from .common import InputModel, OrmModel

STRIPE_MAX_AMOUNT_CENTS = 99_999_999  # $999,999.99


class InvoiceCreate(InputModel):
    client_id: int
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    amount_cents: int = Field(gt=0, le=STRIPE_MAX_AMOUNT_CENTS)
    due_date: Date | None = None


class PaymentOut(OrmModel):
    gross_cents: int
    fee_cents: int
    net_cents: int
    paid_at: datetime


class InvoiceOut(OrmModel):
    id: int
    client_id: int
    client_name: str
    description: str
    amount_cents: int
    currency: str
    status: str
    due_date: Date | None
    checkout_url: str | None
    paid_at: datetime | None
    created_at: datetime
    payment: PaymentOut | None = None
