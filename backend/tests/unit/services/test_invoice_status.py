import pytest

from app.repository.models import InvoiceStatus as S
from app.services.exceptions import InvalidStatusTransition
from app.services.invoice_status import can_transition, ensure_transition

ALLOWED = {
    (S.DRAFT, S.OPEN), (S.DRAFT, S.VOID), (S.DRAFT, S.PAID),
    (S.OPEN, S.OPEN), (S.OPEN, S.EXPIRED), (S.OPEN, S.VOID), (S.OPEN, S.PAID),
    (S.EXPIRED, S.OPEN), (S.EXPIRED, S.VOID), (S.EXPIRED, S.PAID),
    (S.VOID, S.VOID), (S.VOID, S.PAID),
}


@pytest.mark.parametrize("current", list(S))
@pytest.mark.parametrize("target", list(S))
def test_transition_matrix(current, target):
    assert can_transition(current, target) == ((current, target) in ALLOWED)


def test_paid_is_terminal():
    assert not any(can_transition(S.PAID, target) for target in S)


def test_accepts_plain_strings_from_the_database():
    assert can_transition("draft", "open")
    ensure_transition("expired", "open")


@pytest.mark.parametrize(
    "current, target, message",
    [
        (S.PAID, S.OPEN, "This invoice is already paid."),
        (S.VOID, S.OPEN, "This invoice was voided. Create a new invoice instead."),
        (S.PAID, S.VOID, "Paid invoices can't be voided. Issue a refund in Stripe instead."),
        (S.DRAFT, S.EXPIRED, "An invoice can't go from draft to expired."),
    ],
)
def test_forbidden_transitions_explain_why(current, target, message):
    with pytest.raises(InvalidStatusTransition) as exc:
        ensure_transition(current, target)
    assert exc.value.message == message
