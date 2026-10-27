from app.repository.stripe_event_repository import StripeEventRepository
from tests.helpers import checkout_event


def test_webhook_marks_invoice_paid_and_records_fee(client, auth, make_invoice, stripe, post_webhook):
    inv = make_invoice(open_link=True)
    stripe.fee_cents = 4380
    payload = checkout_event(inv["id"], 150_000)
    r = post_webhook(payload)
    assert r.status_code == 200, r.text
    assert r.json() == {"received": True}

    paid = client.get(f"/api/invoices/{inv['id']}", headers=auth).json()
    assert paid["status"] == "paid"
    assert paid["payment"] == {**paid["payment"], "gross_cents": 150_000, "fee_cents": 4380, "net_cents": 145_620}

    # Stripe retries: the same event must not create a second payment
    r2 = post_webhook(payload)
    assert r2.json()["duplicate"] is True
    dash = client.get("/api/dashboard", headers=auth).json()
    assert dash["summary"]["payments_count"] == 1
    assert dash["summary"]["net_income_cents"] == 145_620


def test_webhook_rejects_bad_signature(client, auth, make_invoice, post_webhook):
    inv = make_invoice(open_link=True)
    r = post_webhook(checkout_event(inv["id"]), secret="whsec_wrong")
    assert r.status_code == 400
    assert r.json() == {"detail": "Invalid signature."}
    assert client.get(f"/api/invoices/{inv['id']}", headers=auth).json()["status"] == "open"


def test_webhook_without_secret_is_503(client, stripe, post_webhook):
    stripe.webhook_secret = ""
    r = post_webhook(checkout_event(1))
    assert r.status_code == 503
    assert r.json() == {"detail": "STRIPE_WEBHOOK_SECRET is not set."}


def test_concurrent_duplicate_delivery_is_reported_as_duplicate(client, auth, make_invoice, post_webhook, monkeypatch):
    """Regression: two deliveries passing the dedupe check together used to 500 on the second commit."""
    inv = make_invoice(open_link=True)
    payload = checkout_event(inv["id"], event_id="evt_race")
    assert post_webhook(payload).json() == {"received": True}

    # Simulate the race: the second delivery's existence check ran before the first committed.
    monkeypatch.setattr(StripeEventRepository, "exists", lambda self, event_id: False)
    r = post_webhook(checkout_event(inv["id"], event_id="evt_race", payment_intent="pi_other"))
    assert r.status_code == 200
    assert r.json() == {"received": True, "duplicate": True}
    assert client.get("/api/dashboard", headers=auth).json()["summary"]["payments_count"] == 1


def test_async_payment_succeeded_marks_paid(client, auth, make_invoice, post_webhook):
    inv = make_invoice(open_link=True)
    post_webhook(checkout_event(inv["id"], event_type="checkout.session.async_payment_succeeded"))
    assert client.get(f"/api/invoices/{inv['id']}", headers=auth).json()["status"] == "paid"


def test_unpaid_completion_waits_for_async_event(client, auth, make_invoice, post_webhook):
    inv = make_invoice(open_link=True)
    assert post_webhook(checkout_event(inv["id"], payment_status="unpaid")).status_code == 200
    assert client.get(f"/api/invoices/{inv['id']}", headers=auth).json()["status"] == "open"


def test_invoice_found_by_session_id_when_metadata_missing(client, auth, make_invoice, post_webhook):
    inv = make_invoice(open_link=True)
    post_webhook(checkout_event(None, session_id="cs_test_123"))
    assert client.get(f"/api/invoices/{inv['id']}", headers=auth).json()["status"] == "paid"


def test_unknown_invoice_and_unknown_event_types_are_acknowledged(client, post_webhook):
    assert post_webhook(checkout_event(99_999, session_id="cs_unknown")).json() == {"received": True}
    assert post_webhook(checkout_event(1, event_id="evt_2", event_type="customer.created")).json() == {"received": True}


def test_payment_for_voided_invoice_is_still_recorded(client, auth, make_invoice, post_webhook):
    inv = make_invoice(open_link=True)
    client.post(f"/api/invoices/{inv['id']}/void", headers=auth)
    post_webhook(checkout_event(inv["id"]))
    assert client.get(f"/api/invoices/{inv['id']}", headers=auth).json()["status"] == "paid"


def test_expired_event_for_stale_session_is_ignored(client, auth, make_invoice, post_webhook):
    inv = make_invoice(open_link=True)
    post_webhook(checkout_event(inv["id"], event_type="checkout.session.expired", session_id="cs_old"))
    assert client.get(f"/api/invoices/{inv['id']}", headers=auth).json()["status"] == "open"
