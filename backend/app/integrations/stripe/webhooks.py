"""Webhook signature verification and event parsing."""
import json
from dataclasses import dataclass

import stripe

from .errors import InvalidSignature, StripeNotConfigured


@dataclass(frozen=True)
class StripeEvent:
    id: str
    type: str
    data_object: dict


def verify_and_parse(payload: bytes, signature: str, secret: str) -> StripeEvent:
    """Verify the Stripe-Signature header and return the event as plain data.

    Raises StripeNotConfigured if no webhook secret is set, InvalidSignature otherwise.
    """
    if not secret:
        raise StripeNotConfigured("STRIPE_WEBHOOK_SECRET is not set.")
    try:
        stripe.Webhook.construct_event(payload, signature, secret)
    except (ValueError, stripe.SignatureVerificationError) as e:
        raise InvalidSignature("Invalid signature.") from e

    event = json.loads(payload)  # signature verified; work with plain dicts
    try:
        return StripeEvent(id=event["id"], type=event["type"], data_object=event["data"]["object"])
    except (KeyError, TypeError) as e:
        raise InvalidSignature("Malformed event.") from e
