from datetime import date

import pytest
from pydantic import ValidationError

from app.schema.auth import LoginIn, RegisterIn
from app.schema.client import ClientCreate, ClientUpdate
from app.schema.expense import ExpenseCreate, ExpenseUpdate
from app.schema.insights import AskIn
from app.schema.invoice import InvoiceCreate
from app.schema.system import WebhookAck


def error_types(exc: ValidationError) -> set[str]:
    return {e["type"] for e in exc.errors()}


@pytest.mark.parametrize(
    "model, body",
    [
        (RegisterIn, {"email": "a@example.com", "password": "password123", "is_admin": True}),
        (LoginIn, {"email": "a@example.com", "password": "x", "remember": True}),
        (ClientCreate, {"name": "A", "email": "a@example.com", "user_id": 2}),
        (InvoiceCreate, {"client_id": 1, "description": "x", "amount_cents": 1, "status": "paid"}),
        (ExpenseCreate, {"date": "2026-10-01", "description": "x", "amount_cents": 1, "user_id": 2}),
        (ExpenseUpdate, {"category_source": "ai"}),
        (AskIn, {"question": "How much?", "model": "x"}),
    ],
)
def test_inputs_reject_unknown_fields(model, body):
    with pytest.raises(ValidationError) as exc:
        model.model_validate(body)
    assert "extra_forbidden" in error_types(exc.value)


def test_emails_are_lowercased_and_names_trimmed():
    register = RegisterIn(email="Ann@Example.COM", password="password123", name="  Ann  ")
    assert (register.email, register.name) == ("ann@example.com", "Ann")
    assert LoginIn(email="ANN@example.com", password="x").email == "ann@example.com"
    client = ClientUpdate(name="  Acme  ", email="AP@Acme.example")
    assert (client.name, client.email) == ("Acme", "ap@acme.example")


def test_whitespace_only_names_and_descriptions_are_rejected():
    with pytest.raises(ValidationError):
        ClientCreate(name="   ", email="a@example.com")
    with pytest.raises(ValidationError):
        InvoiceCreate(client_id=1, description="   ", amount_cents=1)


@pytest.mark.parametrize("amount", [0, -1, 100_000_000])
def test_invoice_amount_bounds(amount):
    with pytest.raises(ValidationError):
        InvoiceCreate(client_id=1, description="x", amount_cents=amount)


def test_invoice_amount_allows_stripe_max():
    assert InvoiceCreate(client_id=1, description=" Logo ", amount_cents=99_999_999).description == "Logo"


def test_expense_create_category_rules():
    base = {"date": date(2026, 10, 1), "description": " Figma ", "amount_cents": 1500}
    assert ExpenseCreate(**base).category is None
    assert ExpenseCreate(**base, category="").category is None
    assert ExpenseCreate(**base, category="Software").description == "Figma"
    with pytest.raises(ValidationError, match="category must be one of"):
        ExpenseCreate(**base, category="Nope")


def test_expense_update_description_has_same_limits_as_create():
    """Regression: ExpenseUpdate.description used to accept '' and strings over 255 chars."""
    with pytest.raises(ValidationError):
        ExpenseUpdate(description="")
    with pytest.raises(ValidationError):
        ExpenseUpdate(description="x" * 256)
    assert ExpenseUpdate(description="  ok  ").description == "ok"


@pytest.mark.parametrize("field", ["date", "description", "amount_cents", "category"])
def test_expense_update_rejects_explicit_null(field):
    """Regression: {"category": null} used to reach a NOT NULL column and return 500."""
    with pytest.raises(ValidationError, match=f"{field} can't be null"):
        ExpenseUpdate.model_validate({field: None})


def test_expense_update_tracks_only_sent_fields():
    update = ExpenseUpdate.model_validate({"category": "Meals"})
    assert update.model_dump(exclude_unset=True) == {"category": "Meals"}


def test_webhook_ack_omits_duplicate_unless_set():
    assert WebhookAck().model_dump(exclude_none=True) == {"received": True}
    assert WebhookAck(duplicate=True).model_dump(exclude_none=True) == {"received": True, "duplicate": True}
