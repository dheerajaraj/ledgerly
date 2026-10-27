from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from .models import Invoice, InvoiceStatus


class InvoiceRepository:
    def __init__(self, db: Session):
        self.db = db

    def _with_relations(self):
        return select(Invoice).options(joinedload(Invoice.client), joinedload(Invoice.payment))

    def list_for_user(self, user_id: int, status: str | None = None, limit: int | None = None) -> list[Invoice]:
        """Newest first, with client and payment loaded in the same query."""
        query = self._with_relations().where(Invoice.user_id == user_id).order_by(Invoice.created_at.desc())
        if status:
            query = query.where(Invoice.status == status)
        if limit is not None:
            query = query.limit(limit)
        return list(self.db.scalars(query).unique())

    def get_for_user(self, user_id: int, invoice_id: int) -> Invoice | None:
        query = self._with_relations().where(Invoice.id == invoice_id, Invoice.user_id == user_id)
        return self.db.scalars(query).unique().one_or_none()

    def list_open(self, user_id: int) -> list[Invoice]:
        query = select(Invoice).where(Invoice.user_id == user_id, Invoice.status == InvoiceStatus.OPEN)
        return list(self.db.scalars(query))

    # Webhook-only lookups. Stripe events aren't tied to a signed-in user, so these are the only
    # invoice queries not filtered by user_id. Don't call them from user-facing code.
    def get_by_id_unscoped(self, invoice_id: int) -> Invoice | None:
        return self.db.get(Invoice, invoice_id)

    def get_by_checkout_session_id(self, session_id: str) -> Invoice | None:
        return self.db.scalar(select(Invoice).where(Invoice.stripe_checkout_session_id == session_id))

    def add(self, invoice: Invoice) -> Invoice:
        self.db.add(invoice)
        self.db.flush()
        return invoice
