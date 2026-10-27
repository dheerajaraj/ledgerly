"""Thin wrapper around the Stripe SDK. Returns plain data and raises integration errors only."""
import logging
from collections.abc import Callable
from dataclasses import dataclass

import stripe

from ...config import Settings
from .errors import StripeNotConfigured, StripeRequestFailed
from .webhooks import StripeEvent, verify_and_parse

log = logging.getLogger(__name__)

TIMEOUT_SECONDS = 20
# The SDK reuses one idempotency key across its own retries, so retried creates can't duplicate.
MAX_NETWORK_RETRIES = 2


@dataclass(frozen=True)
class CheckoutSession:
    id: str
    url: str


def _default_sdk(secret_key: str) -> stripe.StripeClient:
    return stripe.StripeClient(
        secret_key,
        max_network_retries=MAX_NETWORK_RETRIES,
        http_client=stripe.new_default_http_client(timeout=TIMEOUT_SECONDS),
    )


class StripeClient:
    def __init__(self, settings: Settings, sdk_factory: Callable[[str], stripe.StripeClient] = _default_sdk):
        self.settings = settings
        self._sdk_factory = sdk_factory

    @property
    def enabled(self) -> bool:
        return self.settings.stripe_enabled

    def _sdk(self) -> stripe.StripeClient:
        if not self.enabled:
            raise StripeNotConfigured("Add STRIPE_SECRET_KEY to backend/.env to create payment links.")
        return self._sdk_factory(self.settings.stripe_secret_key)

    def create_customer(self, *, name: str, email: str, metadata: dict[str, str]) -> str:
        """Create a Stripe Customer and return its ID."""
        sdk = self._sdk()
        try:
            customer = sdk.v1.customers.create(params={"name": name, "email": email, "metadata": metadata})
        except stripe.StripeError as e:
            raise StripeRequestFailed(str(e)) from e
        return customer.id

    def create_checkout_session(
        self,
        *,
        customer_id: str,
        amount_cents: int,
        currency: str,
        description: str,
        metadata: dict[str, str],
        success_url: str,
        cancel_url: str,
    ) -> CheckoutSession:
        """Create a hosted Checkout page for a single line item."""
        sdk = self._sdk()
        params = {
            "mode": "payment",
            "customer": customer_id,
            "line_items": [
                {
                    "quantity": 1,
                    "price_data": {
                        "currency": currency,
                        "unit_amount": amount_cents,
                        "product_data": {"name": description},
                    },
                }
            ],
            "metadata": metadata,
            "payment_intent_data": {"metadata": metadata},
            "success_url": success_url,
            "cancel_url": cancel_url,
        }
        try:
            session = sdk.v1.checkout.sessions.create(params=params)
        except stripe.StripeError as e:
            raise StripeRequestFailed(str(e)) from e
        return CheckoutSession(id=session.id, url=session.url)

    def expire_checkout_session(self, session_id: str) -> None:
        """Expire a Checkout session. A session that's already completed or expired is not an error."""
        sdk = self._sdk()
        try:
            sdk.v1.checkout.sessions.expire(session_id)
        except stripe.StripeError as e:
            log.info("Could not expire session %s: %s", session_id, e)

    def get_fee_cents(self, payment_intent_id: str) -> int:
        """Look up the Stripe processing fee via the charge's balance transaction.

        Never raises. The balance transaction can lag behind the webhook; in that case (or on any
        error) this returns 0 and the payment still records correctly (gross == net).
        """
        try:
            intent = self._sdk().v1.payment_intents.retrieve(
                payment_intent_id, params={"expand": ["latest_charge.balance_transaction"]}
            )
            balance_txn = intent.latest_charge.balance_transaction if intent.latest_charge else None
            return int(balance_txn.fee) if balance_txn else 0
        except Exception as e:  # noqa: BLE001 - fee lookup must never break the webhook
            log.warning("Fee lookup failed for %s: %s", payment_intent_id, e)
            return 0

    def parse_webhook(self, payload: bytes, signature: str) -> StripeEvent:
        return verify_and_parse(payload, signature, self.settings.stripe_webhook_secret)
