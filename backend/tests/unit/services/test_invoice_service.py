from datetime import date

import pytest

from app.config import Settings
from app.integrations.stripe import StripeRequestFailed
from app.repository.models import Client, InvoiceStatus
from app.schema.invoice import InvoiceCreate
from app.services.exceptions import IntegrationFailed, IntegrationUnavailable, InvalidStatusTransition, NotFoundError
from app.services.invoice_service import InvoiceService
from tests.helpers import FakeSession, FakeStripe
from tests.unit.services.fakes import FakeClients, FakeInvoices

USER, OTHER = 1, 2


@pytest.fixture
def ctx():
    clients = FakeClients()
    client = clients.add(Client(user_id=USER, name="Northwind", email="pay@northwind.example"))
    db, stripe = FakeSession(), FakeStripe()
    settings = Settings(_env_file=None, frontend_url="https://app.example", default_currency="sgd")
    svc = InvoiceService(db, FakeInvoices(clients), clients, stripe, settings)

    def new_invoice(**fields):
        return svc.create(USER, InvoiceCreate(client_id=client.id, description="Website", amount_cents=150_000, **fields))

    return type("Ctx", (), {"svc": svc, "db": db, "stripe": stripe, "client": client, "new_invoice": staticmethod(new_invoice)})


def test_create_uses_default_currency_and_commits(ctx):
    out = ctx.new_invoice(due_date=date(2026, 12, 1))
    assert (out.status, out.currency, out.client_name, out.due_date) == ("draft", "sgd", "Northwind", date(2026, 12, 1))
    assert ctx.db.commits == 1


def test_create_rejects_other_users_client(ctx):
    with pytest.raises(NotFoundError, match="Client not found."):
        ctx.svc.create(OTHER, InvoiceCreate(client_id=ctx.client.id, description="x", amount_cents=1))


def test_get_hides_other_users_invoice(ctx):
    inv = ctx.new_invoice()
    with pytest.raises(NotFoundError, match="Invoice not found."):
        ctx.svc.get(OTHER, inv.id)


def test_payment_link_opens_invoice_with_checkout_details(ctx):
    inv = ctx.new_invoice()
    out = ctx.svc.create_payment_link(USER, inv.id)

    assert (out.status, out.checkout_url) == ("open", "https://checkout.stripe.com/c/pay/cs_test_123")
    [customer] = ctx.stripe.calls_to("create_customer")
    assert customer["metadata"] == {"ledgerly_client_id": str(ctx.client.id), "ledgerly_user_id": str(USER)}
    [checkout] = ctx.stripe.calls_to("create_checkout_session")
    assert checkout == {
        "customer_id": "cus_test_1", "amount_cents": 150_000, "currency": "sgd", "description": "Website",
        "metadata": {"ledgerly_invoice_id": str(inv.id), "ledgerly_user_id": str(USER)},
        "success_url": f"https://app.example/pay/success?invoice={inv.id}",
        "cancel_url": f"https://app.example/pay/cancelled?invoice={inv.id}",
    }
    assert ctx.client.stripe_customer_id == "cus_test_1"


def test_payment_link_reuses_existing_customer(ctx):
    ctx.client.stripe_customer_id = "cus_existing"
    ctx.svc.create_payment_link(USER, ctx.new_invoice().id)
    assert ctx.stripe.calls_to("create_customer") == []
    assert ctx.stripe.calls_to("create_checkout_session")[0]["customer_id"] == "cus_existing"


def test_open_invoice_with_link_is_returned_without_calling_stripe(ctx):
    inv = ctx.new_invoice()
    ctx.svc.create_payment_link(USER, inv.id)
    calls_before = len(ctx.stripe.calls)
    assert ctx.svc.create_payment_link(USER, inv.id).status == "open"
    assert len(ctx.stripe.calls) == calls_before


def test_checkout_failure_keeps_customer_and_leaves_invoice_draft(ctx):
    inv = ctx.new_invoice()
    commits_after_create = ctx.db.commits
    ctx.stripe.fail_checkout = StripeRequestFailed("rate limited")

    with pytest.raises(IntegrationFailed, match="Stripe couldn't create the payment link: rate limited"):
        ctx.svc.create_payment_link(USER, inv.id)

    assert ctx.client.stripe_customer_id == "cus_test_1"
    assert ctx.db.commits == commits_after_create + 1  # only the customer ID was committed
    assert ctx.svc.get(USER, inv.id).status == "draft"


def test_payment_link_without_stripe_is_unavailable(ctx):
    ctx.stripe.enabled = False
    with pytest.raises(IntegrationUnavailable, match="STRIPE_SECRET_KEY"):
        ctx.svc.create_payment_link(USER, ctx.new_invoice().id)


@pytest.mark.parametrize("status", [InvoiceStatus.PAID, InvoiceStatus.VOID])
def test_payment_link_refused_for_closed_invoices(ctx, status):
    inv = ctx.new_invoice()
    ctx.svc.invoices.rows[inv.id].status = status
    with pytest.raises(InvalidStatusTransition):
        ctx.svc.create_payment_link(USER, inv.id)
    assert ctx.stripe.calls == []


def test_void_open_invoice_expires_session(ctx):
    inv = ctx.new_invoice()
    ctx.svc.create_payment_link(USER, inv.id)
    out = ctx.svc.void(USER, inv.id)
    assert (out.status, out.checkout_url) == ("void", None)
    assert ctx.stripe.calls_to("expire_checkout_session") == [{"session_id": "cs_test_123"}]


def test_void_open_invoice_without_stripe_still_voids(ctx):
    inv = ctx.new_invoice()
    ctx.svc.create_payment_link(USER, inv.id)
    ctx.stripe.enabled = False
    assert ctx.svc.void(USER, inv.id).status == "void"


def test_void_paid_invoice_is_refused(ctx):
    inv = ctx.new_invoice()
    ctx.svc.invoices.rows[inv.id].status = InvoiceStatus.PAID
    with pytest.raises(InvalidStatusTransition, match="Paid invoices can't be voided"):
        ctx.svc.void(USER, inv.id)
