"""All the money math lives here, in plain Python, so numbers are exact and testable.

Claude only ever *describes* these numbers; it never calculates them.
"""
from collections import defaultdict
from collections.abc import Callable
from datetime import date

from ..repository.expense_repository import ExpenseRepository
from ..repository.invoice_repository import InvoiceRepository
from ..repository.payment_repository import PaymentRepository
from ..schema.dashboard import DashboardOut
from ..utils.dates import month_bounds, month_key, shift_month


class AnalyticsService:
    def __init__(
        self,
        payments: PaymentRepository,
        expenses: ExpenseRepository,
        invoices: InvoiceRepository,
        today: Callable[[], date] = date.today,
    ):
        self.payments = payments
        self.expenses = expenses
        self.invoices = invoices
        self.today = today

    def period_summary(self, user_id: int, start: date, end: date) -> dict:
        payments = self.payments.list_for_period(user_id, start, end)
        expenses = self.expenses.list_for_period(user_id, start, end)
        net_income = sum(p.net_cents for p in payments)
        spent = sum(e.amount_cents for e in expenses)
        return {
            "start": start.isoformat(),
            "end_exclusive": end.isoformat(),
            "gross_income_cents": sum(p.gross_cents for p in payments),
            "stripe_fees_cents": sum(p.fee_cents for p in payments),
            "net_income_cents": net_income,
            "expenses_cents": spent,
            "profit_cents": net_income - spent,
            "payments_count": len(payments),
            "expenses_count": len(expenses),
        }

    def income_by_client(self, user_id: int, start: date | None = None, end: date | None = None) -> list[dict]:
        totals: dict[str, int] = defaultdict(int)
        counts: dict[str, int] = defaultdict(int)
        for p in self.payments.list_for_period(user_id, start, end):
            name = p.invoice.client.name
            totals[name] += p.gross_cents
            counts[name] += 1
        grand_total = sum(totals.values()) or 1
        rows = [
            {"client": c, "gross_cents": v, "payments": counts[c], "share": round(v / grand_total, 4)}
            for c, v in totals.items()
        ]
        return sorted(rows, key=lambda r: r["gross_cents"], reverse=True)

    def expenses_by_category(self, user_id: int, start: date | None = None, end: date | None = None) -> list[dict]:
        totals: dict[str, int] = defaultdict(int)
        for e in self.expenses.list_for_period(user_id, start, end):
            totals[e.category] += e.amount_cents
        return sorted(
            ({"category": c, "amount_cents": v} for c, v in totals.items()),
            key=lambda r: r["amount_cents"],
            reverse=True,
        )

    def monthly_series(self, user_id: int, end_month: str, months: int) -> list[dict]:
        first = shift_month(end_month, -(months - 1))
        start, _ = month_bounds(first)
        _, end = month_bounds(end_month)
        income: dict[str, int] = defaultdict(int)
        spend: dict[str, int] = defaultdict(int)
        for p in self.payments.list_for_period(user_id, start, end):
            income[month_key(p.paid_at)] += p.net_cents
        for e in self.expenses.list_for_period(user_id, start, end):
            spend[month_key(e.date)] += e.amount_cents
        series = []
        for i in range(months):
            m = shift_month(first, i)
            series.append({"month": m, "income_cents": income[m], "expenses_cents": spend[m], "net_cents": income[m] - spend[m]})
        return series

    def outstanding_invoices(self, user_id: int) -> dict:
        rows = self.invoices.list_open(user_id)
        today = self.today()
        overdue = [i for i in rows if i.due_date and i.due_date < today]
        return {
            "open_count": len(rows),
            "open_cents": sum(i.amount_cents for i in rows),
            "overdue_count": len(overdue),
            "overdue_cents": sum(i.amount_cents for i in overdue),
        }

    def month_report(self, user_id: int, month: str) -> dict:
        """Everything Claude needs to write a monthly summary, pre-computed."""
        start, end = month_bounds(month)
        prev_start, prev_end = month_bounds(shift_month(month, -1))
        this_cats = {r["category"]: r["amount_cents"] for r in self.expenses_by_category(user_id, start, end)}
        prev_cats = {r["category"]: r["amount_cents"] for r in self.expenses_by_category(user_id, prev_start, prev_end)}
        category_changes = []
        for cat in sorted(set(this_cats) | set(prev_cats)):
            now, before = this_cats.get(cat, 0), prev_cats.get(cat, 0)
            pct = None if before == 0 else round((now - before) / before * 100, 1)
            category_changes.append({"category": cat, "this_month_cents": now, "last_month_cents": before, "pct_change": pct})
        return {
            "month": month,
            "this_month": self.period_summary(user_id, start, end),
            "last_month": self.period_summary(user_id, prev_start, prev_end),
            "income_by_client": self.income_by_client(user_id, start, end),
            "expense_category_changes": category_changes,
            "outstanding": self.outstanding_invoices(user_id),
        }

    def current_month(self) -> str:
        return month_key(self.today())

    def dashboard(self, user_id: int, month: str | None, months: int) -> DashboardOut:
        month = month or self.current_month()
        start, end = month_bounds(month)
        return DashboardOut(
            month=month,
            summary=self.period_summary(user_id, start, end),
            series=self.monthly_series(user_id, month, months),
            expenses_by_category=self.expenses_by_category(user_id, start, end),
            income_by_client=self.income_by_client(user_id, start, end),
            outstanding=self.outstanding_invoices(user_id),
        )
