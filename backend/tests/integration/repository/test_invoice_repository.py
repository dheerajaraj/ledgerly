from datetime import datetime

from app.repository.invoice_repository import InvoiceRepository
from app.repository.models import InvoiceStatus


def test_get_for_user_hides_other_users_invoices(db, make):
    owner, other = make.user("a@example.com"), make.user("b@example.com")
    invoice = make.invoice(make.client(owner))
    repo = InvoiceRepository(db)

    assert repo.get_for_user(owner.id, invoice.id).id == invoice.id
    assert repo.get_for_user(other.id, invoice.id) is None
    assert repo.get_for_user(owner.id, 99_999) is None


def test_list_for_user_filters_orders_and_limits(db, make):
    owner, other = make.user("a@example.com"), make.user("b@example.com")
    client = make.client(owner)
    oldest = make.invoice(client, status=InvoiceStatus.PAID, created_at=datetime(2026, 1, 1))
    middle = make.invoice(client, status=InvoiceStatus.OPEN, created_at=datetime(2026, 2, 1))
    newest = make.invoice(client, status=InvoiceStatus.PAID, created_at=datetime(2026, 3, 1))
    make.invoice(make.client(other))
    repo = InvoiceRepository(db)

    assert [i.id for i in repo.list_for_user(owner.id)] == [newest.id, middle.id, oldest.id]
    assert [i.id for i in repo.list_for_user(owner.id, status="paid")] == [newest.id, oldest.id]
    assert [i.id for i in repo.list_for_user(owner.id, limit=1)] == [newest.id]


def test_list_for_user_loads_client_and_payment_in_one_query(db, make, count_queries):
    """Regression: the Q&A list_invoices tool used to lazy-load each invoice's client (N+1)."""
    owner = make.user()
    for n in range(5):
        make.invoice(make.client(owner, name=f"Client {n}"))
    owner_id = owner.id
    db.expire_all()

    with count_queries() as queries:
        invoices = InvoiceRepository(db).list_for_user(owner_id, limit=50)
        names = {i.client.name for i in invoices}
        payments = [i.payment for i in invoices]

    assert len(queries) == 1
    assert len(names) == 5 and payments == [None] * 5


def test_list_open_returns_only_open_invoices_for_user(db, make):
    owner, other = make.user("a@example.com"), make.user("b@example.com")
    client = make.client(owner)
    open_invoice = make.invoice(client, status=InvoiceStatus.OPEN)
    make.invoice(client, status=InvoiceStatus.DRAFT)
    make.invoice(make.client(other), status=InvoiceStatus.OPEN)

    assert [i.id for i in InvoiceRepository(db).list_open(owner.id)] == [open_invoice.id]


def test_webhook_lookups_are_unscoped(db, make):
    invoice = make.invoice(make.client(make.user()), stripe_checkout_session_id="cs_test_1")
    repo = InvoiceRepository(db)

    assert repo.get_by_id_unscoped(invoice.id).id == invoice.id
    assert repo.get_by_checkout_session_id("cs_test_1").id == invoice.id
    assert repo.get_by_checkout_session_id("cs_missing") is None


def test_add_flushes_but_does_not_commit(db, make):
    client = make.client(make.user())
    db.commit()
    from app.repository.models import Invoice

    invoice = InvoiceRepository(db).add(Invoice(user_id=client.user_id, client_id=client.id, description="x", amount_cents=1))
    assert invoice.id is not None
    db.rollback()
    assert InvoiceRepository(db).get_for_user(client.user_id, invoice.id) is None
