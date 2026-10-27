import json

import pytest
from sqlalchemy.exc import IntegrityError

from app.repository.models import Invoice, InvoiceStatus
from app.services.exceptions import IntegrationUnavailable, InvalidWebhookSignature
from app.services.payment_service import PaymentService
from tests.helpers import FakeSession, FakeStripe, checkout_event, sign
from tests.unit.services.fakes import FakeEvents, FakeInvoices, FakePayments


@pytest.fixture
def ctx():
    invoices, payments, events = FakeInvoices(), FakePayments(), FakeEvents()
    db, stripe = FakeSession(), FakeStripe(fee_cents=4_380)
    svc = PaymentService(db, invoices, payments, events, stripe)
    invoice = invoices.add(Invoice(
        user_id=7, client_id=1, description="Website", amount_cents=150_000, currency="usd",
        status=InvoiceStatus.OPEN, stripe_checkout_session_id="cs_test_123", checkout_url="https://checkout/x",
    ))

    def deliver(payload: str):
        return svc.handle_webhook(payload.encode(), sign(payload))

    return type("Ctx", (), {"svc": svc, "db": db, "stripe": stripe, "invoice": invoice, "payments": payments,
                            "events": events, "deliver": staticmethod(deliver)})


def test_completed_checkout_marks_paid_and_records_payment(ctx):
    ack = ctx.deliver(checkout_event(ctx.invoice.id, 150_000))
    assert ack.model_dump(exclude_none=True) == {"received": True}

    assert ctx.invoice.status == "paid" and ctx.invoice.stripe_payment_intent_id == "pi_123"
    [payment] = ctx.payments.rows.values()
    assert (payment.user_id, payment.gross_cents, payment.fee_cents, payment.net_cents) == (7, 150_000, 4_380, 145_620)
    assert payment.paid_at == ctx.invoice.paid_at
    assert ctx.events.ids == {"evt_1"} and ctx.db.commits == 1


def test_duplicate_event_is_skipped(ctx):
    payload = checkout_event(ctx.invoice.id)
    ctx.deliver(payload)
    assert ctx.deliver(payload).duplicate is True
    assert len(ctx.payments.rows) == 1 and ctx.db.commits == 1


def test_racing_duplicate_rolls_back_and_reports_duplicate(ctx):
    ctx.db.fail_commit_with = IntegrityError("INSERT", {}, Exception("UNIQUE constraint failed"))
    assert ctx.deliver(checkout_event(ctx.invoice.id)).duplicate is True
    assert ctx.db.rollbacks == 1


def test_already_paid_invoice_is_not_paid_twice(ctx):
    ctx.deliver(checkout_event(ctx.invoice.id, event_id="evt_1"))
    ctx.deliver(checkout_event(ctx.invoice.id, event_id="evt_2"))
    assert len(ctx.payments.rows) == 1


def test_unpaid_session_is_ignored_but_event_recorded(ctx):
    ctx.deliver(checkout_event(ctx.invoice.id, payment_status="unpaid"))
    assert ctx.invoice.status == "open" and ctx.events.ids == {"evt_1"}


def test_missing_amount_and_payment_intent_fall_back(ctx):
    ctx.deliver(checkout_event(ctx.invoice.id, amount_total=None, payment_intent=None, currency=None))
    [payment] = ctx.payments.rows.values()
    assert (payment.gross_cents, payment.fee_cents, payment.currency) == (150_000, 0, "usd")
    assert ctx.stripe.calls_to("get_fee_cents") == []


def test_invoice_matched_by_session_id_when_metadata_is_missing_or_bad(ctx):
    ctx.deliver(checkout_event(None, event_id="evt_a"))
    assert ctx.invoice.status == "paid"


def test_metadata_takes_priority_over_session_id(ctx):
    other = ctx.svc.invoices.add(Invoice(user_id=8, client_id=2, description="x", amount_cents=10, status=InvoiceStatus.OPEN))
    ctx.deliver(checkout_event(other.id, session_id="cs_test_123"))
    assert other.status == "paid" and ctx.invoice.status == "open"


def test_unknown_invoice_is_acknowledged(ctx):
    ack = ctx.deliver(checkout_event(999, session_id="cs_nope"))
    assert ack.duplicate is None and ctx.payments.rows == {}


def test_void_invoice_payment_is_still_recorded(ctx):
    ctx.invoice.status = InvoiceStatus.VOID
    ctx.deliver(checkout_event(ctx.invoice.id))
    assert ctx.invoice.status == "paid"


def test_expired_event_expires_only_matching_open_session(ctx):
    ctx.deliver(checkout_event(ctx.invoice.id, event_type="checkout.session.expired", session_id="cs_old", event_id="evt_a"))
    assert ctx.invoice.status == "open"
    ctx.deliver(checkout_event(ctx.invoice.id, event_type="checkout.session.expired", event_id="evt_b"))
    assert (ctx.invoice.status, ctx.invoice.checkout_url) == ("expired", None)


def test_unhandled_event_types_are_recorded(ctx):
    ctx.deliver(json.dumps({"id": "evt_x", "type": "customer.created", "data": {"object": {}}}))
    assert ctx.events.ids == {"evt_x"} and ctx.db.commits == 1


def test_bad_signature_and_missing_secret(ctx):
    payload = checkout_event(ctx.invoice.id)
    with pytest.raises(InvalidWebhookSignature, match="Invalid signature."):
        ctx.svc.handle_webhook(payload.encode(), sign(payload, "whsec_wrong"))
    ctx.stripe.webhook_secret = ""
    with pytest.raises(IntegrationUnavailable, match="STRIPE_WEBHOOK_SECRET"):
        ctx.deliver(payload)
    assert ctx.invoice.status == "open" and ctx.db.commits == 0
