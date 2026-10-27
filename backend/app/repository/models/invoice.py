"""Invoices. Money is integer cents. Allowed status transitions live in services/invoice_status.py."""
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, utcnow
from .client import Client


class InvoiceStatus(StrEnum):
    DRAFT = "draft"      # created in Ledgerly, no payment link yet
    OPEN = "open"        # Stripe Checkout link created, awaiting payment
    PAID = "paid"        # confirmed by Stripe webhook
    EXPIRED = "expired"  # Checkout session expired without payment
    VOID = "void"        # cancelled by the user


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)
    description: Mapped[str] = mapped_column(String(255))
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="usd")
    status: Mapped[str] = mapped_column(String(16), default=InvoiceStatus.DRAFT, index=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    stripe_checkout_session_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    checkout_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    client: Mapped[Client] = relationship(back_populates="invoices")
    payment: Mapped["Payment | None"] = relationship(back_populates="invoice", uselist=False)  # noqa: F821
