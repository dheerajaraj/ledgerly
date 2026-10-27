from contextlib import contextmanager
from datetime import date, datetime

import pytest
from sqlalchemy import event

from app.database import SessionLocal, engine
from app.repository.models import Client, Expense, Invoice, InvoiceStatus, Payment, User


@pytest.fixture(autouse=True)
def _fresh_db(fresh_db):
    yield


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def count_queries():
    """Usage: `with count_queries() as queries: ...; assert len(queries) == 1`."""
    @contextmanager
    def _count():
        statements: list[str] = []

        def record(conn, cursor, statement, *args):
            statements.append(statement)

        event.listen(engine, "before_cursor_execute", record)
        try:
            yield statements
        finally:
            event.remove(engine, "before_cursor_execute", record)

    return _count


class Factory:
    """Builds rows directly in the session so repository tests don't depend on services."""

    def __init__(self, db):
        self.db = db

    def user(self, email="owner@example.com") -> User:
        user = User(email=email, name="Owner", hashed_password="x")
        self.db.add(user)
        self.db.flush()
        return user

    def client(self, user: User, name="Northwind", email="pay@northwind.example") -> Client:
        client = Client(user_id=user.id, name=name, email=email)
        self.db.add(client)
        self.db.flush()
        return client

    def invoice(self, client: Client, amount_cents=10_000, status=InvoiceStatus.DRAFT, created_at=None, **fields) -> Invoice:
        invoice = Invoice(
            user_id=client.user_id, client_id=client.id, description="Work", amount_cents=amount_cents,
            status=status, created_at=created_at or datetime(2026, 1, 1), **fields,
        )
        self.db.add(invoice)
        self.db.flush()
        return invoice

    def payment(self, invoice: Invoice, gross_cents=10_000, fee_cents=320, paid_at=datetime(2026, 10, 5)) -> Payment:
        payment = Payment(
            user_id=invoice.user_id, invoice_id=invoice.id, gross_cents=gross_cents,
            fee_cents=fee_cents, net_cents=gross_cents - fee_cents, paid_at=paid_at,
        )
        self.db.add(payment)
        self.db.flush()
        return payment

    def expense(self, user: User, on=date(2026, 10, 5), amount_cents=1_500, category="Software") -> Expense:
        expense = Expense(user_id=user.id, date=on, description="Thing", amount_cents=amount_cents, category=category)
        self.db.add(expense)
        self.db.flush()
        return expense


@pytest.fixture
def make(db):
    return Factory(db)
