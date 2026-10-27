import json
from datetime import date

import pytest

from app.integrations.anthropic import ClaudeUnavailable
from app.repository.models import Client, Invoice, InvoiceStatus
from app.services.insights_service import InsightsService, fallback_summary
from tests.helpers import FakeClaude, text_reply, tool_reply
from tests.unit.services.fakes import FakeInvoices

USER = 1


def summary_block(**overrides):
    base = {"gross_income_cents": 600_000, "stripe_fees_cents": 17_520, "expenses_cents": 50_000,
            "profit_cents": 532_480, "payments_count": 4, "net_income_cents": 582_480}
    return {**base, **overrides}


REPORT = {
    "month": "2026-10",
    "this_month": summary_block(),
    "last_month": summary_block(expenses_cents=40_000),
    "income_by_client": [{"client": "Northwind", "gross_cents": 450_000, "payments": 3, "share": 0.75}],
    "expense_category_changes": [],
    "outstanding": {"open_count": 1, "open_cents": 180_000, "overdue_count": 1, "overdue_cents": 180_000},
}


class FakeAnalytics:
    def __init__(self):
        self.calls = []

    def month_report(self, user_id, month):
        self.calls.append(("month_report", user_id, month))
        return {**REPORT, "month": month}

    def period_summary(self, user_id, start, end):
        self.calls.append(("period_summary", user_id, start, end))
        return {"profit_cents": 123}

    def income_by_client(self, user_id, start, end):
        return [{"client": "Northwind"}]

    def expenses_by_category(self, user_id, start, end):
        return [{"category": "Meals"}]


def service(claude, invoices=None):
    return InsightsService(FakeAnalytics(), invoices or FakeInvoices(), claude, today=lambda: date(2026, 10, 27))


def test_fallback_summary_text():
    assert fallback_summary(REPORT) == (
        "In October 2026 you received $6,000.00 from 4 payment(s) ($175.20 in Stripe fees) and spent $500.00, "
        "leaving a profit of $5,324.80. Spending was 25% higher than last month. "
        "Northwind accounted for 75% of income. 1 invoice(s) totalling $1,800.00 are overdue."
    )


def test_fallback_summary_skips_empty_sections():
    quiet = {**REPORT, "last_month": summary_block(expenses_cents=0), "income_by_client": [],
             "outstanding": {"open_count": 0, "open_cents": 0, "overdue_count": 0, "overdue_cents": 0}}
    assert fallback_summary(quiet) == (
        "In October 2026 you received $6,000.00 from 4 payment(s) ($175.20 in Stripe fees) and spent $500.00, "
        "leaving a profit of $5,324.80."
    )


def test_summary_uses_claude_with_precomputed_report():
    claude = FakeClaude([text_reply("Great month.")])
    out = service(claude).monthly_summary(USER, None)
    assert (out.month, out.summary, out.generated_by) == ("2026-10", "Great month.", "claude")
    assert json.loads(claude.requests[0]["messages"][0]["content"])["this_month"]["profit_cents"] == 532_480


@pytest.mark.parametrize("claude", [FakeClaude(enabled=False), FakeClaude([ClaudeUnavailable("down")])])
def test_summary_falls_back(claude):
    out = service(claude).monthly_summary(USER, "2026-10")
    assert out.generated_by == "fallback" and out.summary.startswith("In October 2026")


def test_ask_runs_tools_and_sends_results_back():
    claude = FakeClaude([
        tool_reply(("get_period_summary", {"start": "2026-01-01", "end": "2027-01-01"}), ("get_income_by_client", {"start": "2026-01-01", "end": "2027-01-01"})),
        text_reply("You made $1.23."),
    ])
    svc = service(claude)
    out = svc.ask(USER, "How much?")
    assert (out.answer, out.tools_used, out.generated_by) == ("You made $1.23.", ["get_period_summary", "get_income_by_client"], "claude")

    second = claude.requests[1]["messages"]
    assert second[0] == {"role": "user", "content": "How much?"}
    assert second[1]["role"] == "assistant"
    assert [block["id"] for block in second[1]["content"]] == ["tu_1", "tu_2"]
    assert second[2]["role"] == "user"
    assert [r["tool_use_id"] for r in second[2]["content"]] == ["tu_1", "tu_2"]
    assert json.loads(second[2]["content"][0]["content"]) == {"profit_cents": 123}
    assert svc.analytics.calls[0] == ("period_summary", USER, date(2026, 1, 1), date(2027, 1, 1))
    assert "Today is 2026-10-27" in claude.requests[0]["system"]


def test_ask_reports_tool_errors_to_claude():
    claude = FakeClaude([tool_reply(("get_period_summary", {"start": "nope", "end": "2027-01-01"}), ("drop_tables", {})), text_reply("Sorry.")])
    service(claude).ask(USER, "?")
    results = claude.requests[1]["messages"][-1]["content"]
    assert all(r["is_error"] for r in results)
    assert results[1]["content"] == "Unknown tool drop_tables"


def test_ask_list_invoices_tool_is_scoped_and_shaped():
    invoices = FakeInvoices()
    mine = invoices.add(Invoice(user_id=USER, client_id=1, description="Site", amount_cents=500, status=InvoiceStatus.OPEN, due_date=date(2026, 11, 1)))
    mine.client = Client(name="Northwind")
    other = invoices.add(Invoice(user_id=2, client_id=2, description="Theirs", amount_cents=1, status=InvoiceStatus.OPEN))
    other.client = Client(name="Other")

    rows = service(FakeClaude(), invoices).run_tool(USER, "list_invoices", {"status": "open"})
    assert rows == [{"id": mine.id, "client": "Northwind", "description": "Site", "amount_cents": 500, "status": "open", "due_date": "2026-11-01"}]


def test_ask_stops_after_max_steps():
    claude = FakeClaude([tool_reply(("get_period_summary", {"start": "2026-01-01", "end": "2026-02-01"}))] * 3)
    out = service(claude).ask(USER, "?", max_steps=3)
    assert out.answer == "That question needed too many steps. Try asking something more specific."
    assert len(claude.requests) == 3


def test_ask_fallbacks():
    assert service(FakeClaude(enabled=False)).ask(USER, "?").generated_by == "fallback"
    failed = service(FakeClaude([ClaudeUnavailable("down")])).ask(USER, "?")
    assert (failed.generated_by, failed.answer) == ("fallback", "Claude isn't reachable right now. Try again in a moment.")
    empty = service(FakeClaude([text_reply("")])).ask(USER, "?")
    assert empty.answer == "I couldn't find an answer to that."
