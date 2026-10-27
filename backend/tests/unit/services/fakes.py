"""In-memory repositories with the same methods as app/repository, for service unit tests."""
from datetime import date, datetime
from itertools import count

from app.repository.models import Client, Expense, Invoice, InvoiceStatus, Payment, User


class _Store:
    def __init__(self):
        self.rows: dict[int, object] = {}
        self._ids = count(1)

    def _add(self, row):
        if getattr(row, "id", None) is None:
            row.id = next(self._ids)
        self.rows[row.id] = row
        return row


class FakeUsers(_Store):
    def get(self, user_id):
        return self.rows.get(user_id)

    def get_by_email(self, email):
        return next((u for u in self.rows.values() if u.email == email), None)

    def add(self, user: User):
        return self._add(user)


class FakeClients(_Store):
    def get_for_user(self, user_id, client_id):
        client = self.rows.get(client_id)
        return client if client and client.user_id == user_id else None

    def list_for_user(self, user_id):
        return sorted((c for c in self.rows.values() if c.user_id == user_id), key=lambda c: c.name)

    def add(self, client: Client):
        return self._add(client)


class FakeInvoices(_Store):
    def __init__(self, clients: FakeClients | None = None):
        super().__init__()
        self.clients = clients

    def add(self, invoice: Invoice):
        invoice.status = invoice.status or InvoiceStatus.DRAFT
        invoice.created_at = invoice.created_at or datetime(2026, 10, 1)
        if self.clients and invoice.client is None:
            invoice.client = self.clients.rows[invoice.client_id]
        return self._add(invoice)

    def get_for_user(self, user_id, invoice_id):
        invoice = self.rows.get(invoice_id)
        return invoice if invoice and invoice.user_id == user_id else None

    def list_for_user(self, user_id, status=None, limit=None):
        rows = [i for i in self.rows.values() if i.user_id == user_id and (not status or i.status == status)]
        rows.sort(key=lambda i: i.created_at, reverse=True)
        return rows[:limit] if limit is not None else rows

    def list_open(self, user_id):
        return [i for i in self.rows.values() if i.user_id == user_id and i.status == InvoiceStatus.OPEN]

    def get_by_id_unscoped(self, invoice_id):
        return self.rows.get(invoice_id)

    def get_by_checkout_session_id(self, session_id):
        return next((i for i in self.rows.values() if i.stripe_checkout_session_id == session_id), None)


class FakePayments(_Store):
    def add(self, payment: Payment):
        return self._add(payment)

    def list_for_period(self, user_id, start=None, end=None):
        def in_period(p):
            paid_on = p.paid_at.date()
            return (start is None or paid_on >= start) and (end is None or paid_on < end)

        return [p for p in self.rows.values() if p.user_id == user_id and in_period(p)]


class FakeExpenses(_Store):
    def add(self, expense: Expense):
        return self._add(expense)

    def add_all(self, expenses):
        return [self._add(e) for e in expenses]

    def get_for_user(self, user_id, expense_id):
        expense = self.rows.get(expense_id)
        return expense if expense and expense.user_id == user_id else None

    def delete(self, expense):
        del self.rows[expense.id]

    def list_for_period(self, user_id, start: date | None = None, end: date | None = None):
        return [
            e for e in self.rows.values()
            if e.user_id == user_id and (start is None or e.date >= start) and (end is None or e.date < end)
        ]

    def list_for_user(self, user_id, start=None, end=None):
        return sorted(self.list_for_period(user_id, start, end), key=lambda e: (e.date, e.id), reverse=True)


class FakeEvents:
    def __init__(self):
        self.ids: set[str] = set()

    def exists(self, event_id):
        return event_id in self.ids

    def add(self, event_id, event_type):
        self.ids.add(event_id)
