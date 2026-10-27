class StripeNotConfigured(RuntimeError):
    """Stripe keys are missing or placeholders."""


class StripeRequestFailed(RuntimeError):
    """A Stripe API call failed (network, auth, or validation error)."""


class InvalidSignature(ValueError):
    """A webhook payload failed signature verification or is malformed."""
