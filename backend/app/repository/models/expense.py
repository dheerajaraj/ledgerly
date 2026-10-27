from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, utcnow


class CategorySource(StrEnum):
    MANUAL = "manual"  # the user chose it
    AI = "ai"          # Claude
    RULE = "rule"      # keyword fallback


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    description: Mapped[str] = mapped_column(String(255))
    amount_cents: Mapped[int] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(40), default="Other")
    category_source: Mapped[str] = mapped_column(String(10), default=CategorySource.MANUAL)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
