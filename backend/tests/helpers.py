"""Fakes and helpers shared by unit and api tests."""
import hashlib
import hmac
import json
import time
from collections.abc import Callable

from app.integrations.anthropic import ClaudeReply, ClaudeUnavailable, ToolCall
from app.integrations.stripe import CheckoutSession, StripeNotConfigured, StripeRequestFailed
from app.integrations.stripe.webhooks import verify_and_parse

WEBHOOK_SECRET = "whsec_test_secret"


def sign(payload: str, secret: str = WEBHOOK_SECRET) -> str:
    """A real Stripe-Signature header for payload."""
    ts = int(time.time())
    sig = hmac.new(secret.encode(), f"{ts}.{payload}".encode(), hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


def checkout_event(invoice_id: int | None, amount: int = 150_000, event_id: str = "evt_1",
                   event_type: str = "checkout.session.completed", session_id: str = "cs_test_123", **session) -> str:
    """A Stripe checkout.session.* event payload as JSON."""
    metadata = {"ledgerly_invoice_id": str(invoice_id)} if invoice_id is not None else {}
    obj = {
        "id": session_id, "object": "checkout.session", "payment_status": "paid",
        "amount_total": amount, "currency": "usd", "payment_intent": "pi_123", "metadata": metadata, **session,
    }
    return json.dumps({"id": event_id, "type": event_type, "data": {"object": obj}})


class FakeStripe:
    """Same interface as integrations.stripe.StripeClient. Webhooks are verified for real."""

    def __init__(self, enabled: bool = True, fee_cents: int = 0, webhook_secret: str = WEBHOOK_SECRET):
        self.enabled = enabled
        self.fee_cents = fee_cents
        self.webhook_secret = webhook_secret
        self.calls: list[tuple[str, dict]] = []
        self.fail_checkout: Exception | None = None
        self.session_id = "cs_test_123"

    def _record(self, method: str, kwargs: dict) -> None:
        if not self.enabled:
            raise StripeNotConfigured("Add STRIPE_SECRET_KEY to backend/.env to create payment links.")
        self.calls.append((method, kwargs))

    def calls_to(self, method: str) -> list[dict]:
        return [kwargs for call, kwargs in self.calls if call == method]

    def create_customer(self, **kwargs) -> str:
        self._record("create_customer", kwargs)
        return f"cus_test_{len(self.calls_to('create_customer'))}"

    def create_checkout_session(self, **kwargs) -> CheckoutSession:
        self._record("create_checkout_session", kwargs)
        if self.fail_checkout:
            raise self.fail_checkout
        return CheckoutSession(id=self.session_id, url=f"https://checkout.stripe.com/c/pay/{self.session_id}")

    def expire_checkout_session(self, session_id: str) -> None:
        self._record("expire_checkout_session", {"session_id": session_id})

    def get_fee_cents(self, payment_intent_id: str) -> int:
        self.calls.append(("get_fee_cents", {"payment_intent_id": payment_intent_id}))
        return self.fee_cents

    def parse_webhook(self, payload: bytes, signature: str):
        return verify_and_parse(payload, signature, self.webhook_secret)


class FakeClaude:
    """Same interface as integrations.anthropic.ClaudeClient. Replies are returned in order;
    a callable reply receives the request kwargs."""

    fast_model = "fast-model"
    smart_model = "smart-model"

    def __init__(self, replies: list[ClaudeReply | Callable[[dict], ClaudeReply] | Exception] | None = None, enabled: bool = True):
        self.replies = list(replies or [])
        self.enabled = enabled
        self.requests: list[dict] = []

    def create_message(self, **request) -> ClaudeReply:
        self.requests.append(request)
        if not self.enabled:
            raise ClaudeUnavailable("ANTHROPIC_API_KEY is not set.")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply(request) if callable(reply) else reply


def text_reply(text: str) -> ClaudeReply:
    return ClaudeReply(stop_reason="end_turn", text=text, assistant_content=[{"type": "text", "text": text}])


def tool_reply(*calls: tuple[str, dict]) -> ClaudeReply:
    tool_calls = [ToolCall(id=f"tu_{n}", name=name, input=args) for n, (name, args) in enumerate(calls, start=1)]
    return ClaudeReply(
        stop_reason="tool_use",
        text="",
        tool_calls=tool_calls,
        assistant_content=[{"type": "tool_use", "id": c.id, "name": c.name, "input": c.input} for c in tool_calls],
    )


class FakeSession:
    """Stands in for a SQLAlchemy Session in unit tests: counts commits and rollbacks."""

    def __init__(self):
        self.commits = 0
        self.rollbacks = 0
        self.fail_commit_with: Exception | None = None

    def commit(self) -> None:
        if self.fail_commit_with:
            raise self.fail_commit_with
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


