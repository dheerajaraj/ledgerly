from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from .models import Invoice, Payment


class PaymentRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_for_period(self, user_id: int, start: date | None = None, end: date | None = None) -> list[Payment]:
        """Payments with paid_at in [start, end), with invoice and client loaded."""
        query = (
            select(Payment)
            .where(Payment.user_id == user_id)
            .options(joinedload(Payment.invoice).joinedload(Invoice.client))
        )
        if start:
            query = query.where(Payment.paid_at >= datetime.combine(start, datetime.min.time()))
        if end:
            query = query.where(Payment.paid_at < datetime.combine(end, datetime.min.time()))
        return list(self.db.scalars(query).unique())

    def add(self, payment: Payment) -> Payment:
        self.db.add(payment)
        self.db.flush()
        return payment
