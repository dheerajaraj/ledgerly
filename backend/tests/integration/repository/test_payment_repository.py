from datetime import date, datetime

from app.repository.payment_repository import PaymentRepository


def test_payment_list_for_period_is_half_open_and_scoped(db, make):
    owner, other = make.user("a@example.com"), make.user("b@example.com")
    client = make.client(owner)
    inside = make.payment(make.invoice(client), paid_at=datetime(2026, 10, 1))
    make.payment(make.invoice(client), paid_at=datetime(2026, 11, 1))  # end is exclusive
    make.payment(make.invoice(client), paid_at=datetime(2026, 9, 30, 23, 59))
    make.payment(make.invoice(make.client(other)), paid_at=datetime(2026, 10, 5))
    repo = PaymentRepository(db)

    assert [p.id for p in repo.list_for_period(owner.id, date(2026, 10, 1), date(2026, 11, 1))] == [inside.id]
    assert len(repo.list_for_period(owner.id)) == 3
