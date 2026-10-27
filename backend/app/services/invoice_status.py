"""The invoice status machine. Every status change goes through ensure_transition.

draft → open (payment link created) → paid (webhook) or expired (webhook, can be relinked).
Any non-paid invoice can become void. Paid invoices can't change.
Only PaymentService (the Stripe webhook) moves an invoice to paid. Stripe is the source of truth,
so a payment is recorded from any non-paid status, including void.
"""
from ..repository.models import InvoiceStatus
from .exceptions import InvalidStatusTransition

S = InvoiceStatus

ALLOWED_TRANSITIONS: dict[InvoiceStatus, frozenset[InvoiceStatus]] = {
    S.DRAFT: frozenset({S.OPEN, S.VOID, S.PAID}),
    S.OPEN: frozenset({S.OPEN, S.EXPIRED, S.VOID, S.PAID}),  # open → open recreates a missing link
    S.EXPIRED: frozenset({S.OPEN, S.VOID, S.PAID}),
    S.VOID: frozenset({S.VOID, S.PAID}),
    S.PAID: frozenset(),
}

_MESSAGES = {
    (S.PAID, S.OPEN): "This invoice is already paid.",
    (S.VOID, S.OPEN): "This invoice was voided. Create a new invoice instead.",
    (S.PAID, S.VOID): "Paid invoices can't be voided. Issue a refund in Stripe instead.",
}


def can_transition(current: str, target: str) -> bool:
    return InvoiceStatus(target) in ALLOWED_TRANSITIONS[InvoiceStatus(current)]


def ensure_transition(current: str, target: str) -> None:
    if not can_transition(current, target):
        key = (InvoiceStatus(current), InvoiceStatus(target))
        raise InvalidStatusTransition(_MESSAGES.get(key, f"An invoice can't go from {current} to {target}."))
