from app.integrations.stripe import StripeRequestFailed
from tests.helpers import checkout_event


def test_create_and_get_invoice(client, auth, make_invoice):
    inv = make_invoice(amount_cents=50_000)
    assert inv["status"] == "draft" and inv["client_name"] == "Northwind" and inv["currency"] == "usd"
    assert client.get(f"/api/invoices/{inv['id']}", headers=auth).json() == inv
    assert client.get("/api/invoices/99999", headers=auth).json() == {"detail": "Invoice not found."}


def test_create_invoice_requires_own_client(client, auth):
    r = client.post("/api/invoices", json={"client_id": 99999, "description": "x", "amount_cents": 100}, headers=auth)
    assert r.status_code == 404
    assert r.json() == {"detail": "Client not found."}


def test_list_invoices_filters_by_status(client, auth, make_invoice):
    draft = make_invoice()
    opened = make_invoice(open_link=True)
    assert {i["id"] for i in client.get("/api/invoices", headers=auth).json()} == {draft["id"], opened["id"]}
    assert [i["id"] for i in client.get("/api/invoices?status=open", headers=auth).json()] == [opened["id"]]


def test_payment_link_creates_customer_and_checkout_once(client, auth, make_invoice, stripe):
    inv = make_invoice(amount_cents=150_000, open_link=True)
    assert inv["checkout_url"] == "https://checkout.stripe.com/c/pay/cs_test_123"

    [checkout] = stripe.calls_to("create_checkout_session")
    assert checkout["amount_cents"] == 150_000 and checkout["currency"] == "usd"
    assert checkout["metadata"]["ledgerly_invoice_id"] == str(inv["id"])
    assert checkout["success_url"].endswith(f"/pay/success?invoice={inv['id']}")

    # An open invoice with a link returns the existing link instead of creating another
    again = client.post(f"/api/invoices/{inv['id']}/payment-link", headers=auth)
    assert again.json()["checkout_url"] == inv["checkout_url"]
    assert len(stripe.calls_to("create_checkout_session")) == 1
    assert len(stripe.calls_to("create_customer")) == 1


def test_failed_checkout_keeps_customer_so_retry_does_not_duplicate_it(client, auth, make_invoice, stripe):
    inv = make_invoice()
    stripe.fail_checkout = StripeRequestFailed("card_declined")
    r = client.post(f"/api/invoices/{inv['id']}/payment-link", headers=auth)
    assert r.status_code == 502
    assert r.json() == {"detail": "Stripe couldn't create the payment link: card_declined"}
    assert client.get(f"/api/invoices/{inv['id']}", headers=auth).json()["status"] == "draft"

    stripe.fail_checkout = None
    assert client.post(f"/api/invoices/{inv['id']}/payment-link", headers=auth).json()["status"] == "open"
    assert len(stripe.calls_to("create_customer")) == 1
    assert stripe.calls_to("create_checkout_session")[-1]["customer_id"] == "cus_test_1"


def test_payment_link_without_stripe_is_503(client, auth, make_invoice, stripe):
    inv = make_invoice()
    stripe.enabled = False
    r = client.post(f"/api/invoices/{inv['id']}/payment-link", headers=auth)
    assert r.status_code == 503
    assert r.json() == {"detail": "Add STRIPE_SECRET_KEY to backend/.env to create payment links."}


def test_paid_invoice_cannot_be_relinked_or_voided(client, auth, make_invoice, post_webhook):
    inv = make_invoice(open_link=True)
    post_webhook(checkout_event(inv["id"]))

    link = client.post(f"/api/invoices/{inv['id']}/payment-link", headers=auth)
    assert link.status_code == 409 and link.json() == {"detail": "This invoice is already paid."}
    void = client.post(f"/api/invoices/{inv['id']}/void", headers=auth)
    assert void.status_code == 409
    assert void.json() == {"detail": "Paid invoices can't be voided. Issue a refund in Stripe instead."}


def test_void_expires_open_session_and_blocks_relink(client, auth, make_invoice, stripe):
    inv = make_invoice(open_link=True)
    voided = client.post(f"/api/invoices/{inv['id']}/void", headers=auth)
    assert voided.status_code == 200
    assert (voided.json()["status"], voided.json()["checkout_url"]) == ("void", None)
    assert stripe.calls_to("expire_checkout_session") == [{"session_id": "cs_test_123"}]

    link = client.post(f"/api/invoices/{inv['id']}/payment-link", headers=auth)
    assert link.status_code == 409
    assert link.json() == {"detail": "This invoice was voided. Create a new invoice instead."}


def test_void_draft_without_stripe(client, auth, make_invoice, stripe):
    inv = make_invoice()
    stripe.enabled = False
    assert client.post(f"/api/invoices/{inv['id']}/void", headers=auth).json()["status"] == "void"


def test_expired_invoice_can_be_relinked(client, auth, make_invoice, stripe, post_webhook):
    inv = make_invoice(open_link=True)
    post_webhook(checkout_event(inv["id"], event_type="checkout.session.expired"))
    expired = client.get(f"/api/invoices/{inv['id']}", headers=auth).json()
    assert (expired["status"], expired["checkout_url"]) == ("expired", None)

    stripe.session_id = "cs_test_456"
    relinked = client.post(f"/api/invoices/{inv['id']}/payment-link", headers=auth).json()
    assert (relinked["status"], relinked["checkout_url"]) == ("open", "https://checkout.stripe.com/c/pay/cs_test_456")
