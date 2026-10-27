import hashlib
import hmac
import json
import time
from types import SimpleNamespace as NS

import pytest
import stripe

from app.config import Settings
from app.integrations.stripe import (
    CheckoutSession,
    InvalidSignature,
    StripeClient,
    StripeNotConfigured,
    StripeRequestFailed,
)
from app.integrations.stripe.client import _default_sdk

WEBHOOK_SECRET = "whsec_test_secret"


def settings(**overrides) -> Settings:
    values = {"stripe_secret_key": "sk_test_dummy", "stripe_webhook_secret": WEBHOOK_SECRET, **overrides}
    return Settings(_env_file=None, **values)


class FakeSdk:
    """Records calls to the parts of stripe.StripeClient.v1 that we use."""

    def __init__(self, fail_with: Exception | None = None, intent=None):
        self.calls: list[tuple] = []
        self.fail_with = fail_with

        def call(name, result):
            def _call(*args, **kwargs):
                self.calls.append((name, args, kwargs))
                if self.fail_with:
                    raise self.fail_with
                return result
            return _call

        self.v1 = NS(
            customers=NS(create=call("customers.create", NS(id="cus_123"))),
            checkout=NS(sessions=NS(
                create=call("sessions.create", NS(id="cs_123", url="https://checkout.stripe.com/c/pay/cs_123")),
                expire=call("sessions.expire", None),
            )),
            payment_intents=NS(retrieve=call("payment_intents.retrieve", intent)),
        )


def client_with(sdk: FakeSdk, **overrides) -> StripeClient:
    return StripeClient(settings(**overrides), sdk_factory=lambda key: sdk)


def test_default_sdk_builds_real_client_with_timeout_and_retries():
    sdk = _default_sdk("sk_test_dummy")
    assert isinstance(sdk, stripe.StripeClient)


def test_calls_raise_not_configured_without_valid_key():
    client = client_with(FakeSdk(), stripe_secret_key="sk_placeholder")
    assert not client.enabled
    with pytest.raises(StripeNotConfigured):
        client.create_customer(name="A", email="a@example.com", metadata={})
    with pytest.raises(StripeNotConfigured):
        client.expire_checkout_session("cs_1")


def test_create_checkout_session_sends_line_item_and_returns_plain_data():
    sdk = FakeSdk()
    session = client_with(sdk).create_checkout_session(
        customer_id="cus_123", amount_cents=150_000, currency="usd", description="Website",
        metadata={"ledgerly_invoice_id": "7"}, success_url="https://app/ok", cancel_url="https://app/no",
    )
    assert session == CheckoutSession(id="cs_123", url="https://checkout.stripe.com/c/pay/cs_123")
    _, _, kwargs = sdk.calls[0]
    params = kwargs["params"]
    assert params["line_items"][0]["price_data"] == {
        "currency": "usd", "unit_amount": 150_000, "product_data": {"name": "Website"},
    }
    assert params["metadata"] == params["payment_intent_data"]["metadata"] == {"ledgerly_invoice_id": "7"}


def test_create_customer_returns_id():
    assert client_with(FakeSdk()).create_customer(name="A", email="a@example.com", metadata={}) == "cus_123"


def test_stripe_errors_become_request_failed():
    client = client_with(FakeSdk(fail_with=stripe.APIConnectionError("network down")))
    with pytest.raises(StripeRequestFailed, match="network down"):
        client.create_customer(name="A", email="a@example.com", metadata={})


def test_expire_ignores_stripe_errors():
    client_with(FakeSdk(fail_with=stripe.InvalidRequestError("already expired", param=None))).expire_checkout_session("cs_1")


def test_get_fee_cents_reads_balance_transaction():
    intent = NS(latest_charge=NS(balance_transaction=NS(fee=4380)))
    sdk = FakeSdk(intent=intent)
    assert client_with(sdk).get_fee_cents("pi_1") == 4380
    assert sdk.calls[0][2]["params"] == {"expand": ["latest_charge.balance_transaction"]}


@pytest.mark.parametrize(
    "sdk, overrides",
    [
        (FakeSdk(intent=NS(latest_charge=None)), {}),
        (FakeSdk(intent=NS(latest_charge=NS(balance_transaction=None))), {}),
        (FakeSdk(fail_with=RuntimeError("boom")), {}),
        (FakeSdk(), {"stripe_secret_key": ""}),
    ],
)
def test_get_fee_cents_never_raises(sdk, overrides):
    assert client_with(sdk, **overrides).get_fee_cents("pi_1") == 0


def sign(payload: str, secret: str = WEBHOOK_SECRET) -> str:
    ts = int(time.time())
    sig = hmac.new(secret.encode(), f"{ts}.{payload}".encode(), hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


def test_parse_webhook_returns_event():
    payload = json.dumps({"id": "evt_1", "type": "checkout.session.completed", "data": {"object": {"id": "cs_1"}}})
    event = client_with(FakeSdk()).parse_webhook(payload.encode(), sign(payload))
    assert (event.id, event.type, event.data_object) == ("evt_1", "checkout.session.completed", {"id": "cs_1"})


def test_parse_webhook_rejects_bad_signature_and_malformed_event():
    client = client_with(FakeSdk())
    payload = json.dumps({"id": "evt_1", "type": "x", "data": {"object": {}}})
    with pytest.raises(InvalidSignature):
        client.parse_webhook(payload.encode(), sign(payload, "whsec_wrong"))
    with pytest.raises(InvalidSignature):
        client.parse_webhook(payload.encode(), "garbage")
    malformed = json.dumps({"id": "evt_1", "type": "x"})
    with pytest.raises(InvalidSignature):
        client.parse_webhook(malformed.encode(), sign(malformed))


def test_parse_webhook_requires_secret():
    with pytest.raises(StripeNotConfigured):
        client_with(FakeSdk(), stripe_webhook_secret="").parse_webhook(b"{}", "t=1,v1=x")
