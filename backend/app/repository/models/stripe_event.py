from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, utcnow


class ProcessedStripeEvent(Base):
    """Stripe can deliver the same webhook more than once; this makes handling idempotent."""
    __tablename__ = "processed_stripe_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    type: Mapped[str] = mapped_column(String(64))
    received_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
