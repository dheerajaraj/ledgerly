from datetime import date, datetime
from types import SimpleNamespace as NS

from app.repository.models import Expense, Invoice, InvoiceStatus
from app.services.analytics import AnalyticsService
from tests.unit.services.fakes import FakeExpenses, FakeInvoices, FakePayments

USER = 1


def payment(client_name, gross, fee, paid_at, user_id=USER):
    """Payment-shaped object; a plain namespace so invoice.client can be set without a DB."""
    return NS(id=None, user_id=user_id, gross_cents=gross, fee_cents=fee, net_cents=gross - fee, paid_at=paid_at,
              invoice=NS(client=NS(name=client_name)))


def expense(category, cents, on, user_id=USER):
    return Expense(user_id=user_id, category=category, amount_cents=cents, date=on, description="x")


def service(payments=(), expenses=(), invoices=(), today=date(2026, 10, 15)):
    payment_repo, expense_repo, invoice_repo = FakePayments(), FakeExpenses(), FakeInvoices()
    for p in payments:
        payment_repo.add(p)
    for e in expenses:
        expense_repo.add(e)
    for i in invoices:
        invoice_repo.add(i)
    return AnalyticsService(payment_repo, expense_repo, invoice_repo, today=lambda: today)


def test_period_summary_totals_in_cents():
    svc = service(
        payments=[payment("A", 100_000, 3_230, datetime(2026, 10, 2)), payment("B", 50_000, 1_480, datetime(2026, 10, 9)),
                  payment("A", 99_999, 0, datetime(2026, 11, 1)), payment("A", 1, 0, datetime(2026, 10, 2), user_id=2)],
        expenses=[expense("Software", 1_500, date(2026, 10, 3)), expense("Meals", 2_000, date(2026, 9, 30))],
    )
    assert svc.period_summary(USER, date(2026, 10, 1), date(2026, 11, 1)) == {
        "start": "2026-10-01", "end_exclusive": "2026-11-01",
        "gross_income_cents": 150_000, "stripe_fees_cents": 4_710, "net_income_cents": 145_290,
        "expenses_cents": 1_500, "profit_cents": 143_790, "payments_count": 2, "expenses_count": 1,
    }


def test_income_by_client_sorted_with_share():
    svc = service(payments=[payment("Small", 25_000, 0, datetime(2026, 10, 1)),
                            payment("Big", 50_000, 0, datetime(2026, 10, 2)), payment("Big", 25_000, 0, datetime(2026, 10, 3))])
    assert svc.income_by_client(USER) == [
        {"client": "Big", "gross_cents": 75_000, "payments": 2, "share": 0.75},
        {"client": "Small", "gross_cents": 25_000, "payments": 1, "share": 0.25},
    ]
    assert service().income_by_client(USER) == []


def test_expenses_by_category_sorted_desc():
    svc = service(expenses=[expense("Meals", 500, date(2026, 10, 1)), expense("Software", 900, date(2026, 10, 1)),
                            expense("Meals", 600, date(2026, 10, 2))])
    assert svc.expenses_by_category(USER) == [
        {"category": "Meals", "amount_cents": 1_100}, {"category": "Software", "amount_cents": 900},
    ]


def test_monthly_series_includes_empty_months():
    svc = service(payments=[payment("A", 10_000, 300, datetime(2026, 8, 20))], expenses=[expense("Meals", 400, date(2026, 10, 1))])
    assert svc.monthly_series(USER, "2026-10", 3) == [
        {"month": "2026-08", "income_cents": 9_700, "expenses_cents": 0, "net_cents": 9_700},
        {"month": "2026-09", "income_cents": 0, "expenses_cents": 0, "net_cents": 0},
        {"month": "2026-10", "income_cents": 0, "expenses_cents": 400, "net_cents": -400},
    ]


def test_outstanding_counts_overdue_against_today():
    def inv(cents, due, status=InvoiceStatus.OPEN):
        return Invoice(user_id=USER, client_id=1, amount_cents=cents, status=status, due_date=due, description="x")

    svc = service(invoices=[inv(1_000, date(2026, 10, 14)), inv(2_000, date(2026, 10, 15)), inv(4_000, None),
                            inv(8_000, date(2026, 1, 1), status=InvoiceStatus.DRAFT)])
    assert svc.outstanding_invoices(USER) == {"open_count": 3, "open_cents": 7_000, "overdue_count": 1, "overdue_cents": 1_000}


def test_month_report_category_changes():
    svc = service(expenses=[expense("Software", 2_000, date(2026, 10, 1)), expense("Software", 1_000, date(2026, 9, 1)),
                            expense("Meals", 500, date(2026, 10, 2)), expense("Travel", 700, date(2026, 9, 3))])
    report = svc.month_report(USER, "2026-10")
    assert report["expense_category_changes"] == [
        {"category": "Meals", "this_month_cents": 500, "last_month_cents": 0, "pct_change": None},
        {"category": "Software", "this_month_cents": 2_000, "last_month_cents": 1_000, "pct_change": 100.0},
        {"category": "Travel", "this_month_cents": 0, "last_month_cents": 700, "pct_change": -100.0},
    ]
    assert report["last_month"]["start"] == "2026-09-01"


def test_dashboard_defaults_to_current_month():
    dashboard = service(today=date(2026, 3, 9)).dashboard(USER, None, months=2)
    assert dashboard.month == "2026-03"
    assert [p.month for p in dashboard.series] == ["2026-02", "2026-03"]
