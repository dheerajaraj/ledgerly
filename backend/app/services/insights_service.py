"""Claude-powered monthly summary and Q&A, each with a non-AI fallback.

Claude never does math: the summary describes a precomputed report, and Q&A answers by calling
tools that map to AnalyticsService functions.
"""
import json
import logging
from collections.abc import Callable
from datetime import date

from ..integrations.anthropic import ClaudeClient, ClaudeUnavailable
from ..repository.invoice_repository import InvoiceRepository
from ..schema.insights import AskOut, SummaryOut
from ..utils.dates import month_key, month_label
from ..utils.money import format_cents
from .analytics import AnalyticsService

log = logging.getLogger(__name__)

CLAUDE, FALLBACK = "claude", "fallback"
MAX_ASK_STEPS = 6

SUMMARY_SYSTEM = """You write a short monthly money summary for a freelancer's dashboard.
You are given pre-computed figures in JSON (amounts are in cents; convert to dollars).
Rules:
- Use ONLY the numbers provided. Never compute new totals beyond simple comparisons already implied.
- 3 to 5 sentences of plain prose. No headings, no bullet points, no emojis.
- Mention income, expenses, profit, the biggest client's share if notable, notable category changes,
  and any overdue invoices.
- Describe what happened; do not give tax, investment, or legal advice."""

DATE_RANGE = {
    "start": {"type": "string", "description": "Inclusive start date, YYYY-MM-DD"},
    "end": {"type": "string", "description": "Exclusive end date, YYYY-MM-DD"},
}

TOOLS = [
    {
        "name": "get_period_summary",
        "description": "Totals for a date range: gross income, Stripe fees, net income, expenses, profit.",
        "input_schema": {"type": "object", "properties": DATE_RANGE, "required": ["start", "end"]},
    },
    {
        "name": "get_income_by_client",
        "description": "Income per client for a date range, sorted highest first, with share of total.",
        "input_schema": {"type": "object", "properties": DATE_RANGE, "required": ["start", "end"]},
    },
    {
        "name": "get_expenses_by_category",
        "description": "Expense totals per category for a date range, sorted highest first.",
        "input_schema": {"type": "object", "properties": DATE_RANGE, "required": ["start", "end"]},
    },
    {
        "name": "list_invoices",
        "description": "List invoices, optionally filtered by status (draft, open, paid, expired, void).",
        "input_schema": {
            "type": "object",
            "properties": {"status": {"type": "string", "enum": ["draft", "open", "paid", "expired", "void"]}},
        },
    },
]


def fallback_summary(report: dict) -> str:
    this_month, last_month = report["this_month"], report["last_month"]
    parts = [
        f"In {month_label(report['month'])} you received {format_cents(this_month['gross_income_cents'])} "
        f"from {this_month['payments_count']} payment(s) "
        f"({format_cents(this_month['stripe_fees_cents'])} in Stripe fees) and spent {format_cents(this_month['expenses_cents'])}, "
        f"leaving a profit of {format_cents(this_month['profit_cents'])}."
    ]
    if last_month["expenses_cents"]:
        change = (this_month["expenses_cents"] - last_month["expenses_cents"]) / last_month["expenses_cents"] * 100
        parts.append(f"Spending was {abs(change):.0f}% {'higher' if change >= 0 else 'lower'} than last month.")
    if report["income_by_client"]:
        top = report["income_by_client"][0]
        parts.append(f"{top['client']} accounted for {top['share'] * 100:.0f}% of income.")
    outstanding = report["outstanding"]
    if outstanding["overdue_count"]:
        parts.append(f"{outstanding['overdue_count']} invoice(s) totalling {format_cents(outstanding['overdue_cents'])} are overdue.")
    return " ".join(parts)


class InsightsService:
    def __init__(
        self,
        analytics: AnalyticsService,
        invoices: InvoiceRepository,
        claude: ClaudeClient,
        today: Callable[[], date] = date.today,
    ):
        self.analytics = analytics
        self.invoices = invoices
        self.claude = claude
        self.today = today

    def monthly_summary(self, user_id: int, month: str | None) -> SummaryOut:
        month = month or month_key(self.today())
        report = self.analytics.month_report(user_id, month)
        if self.claude.enabled:
            try:
                reply = self.claude.create_message(
                    model=self.claude.smart_model,
                    max_tokens=600,
                    system=SUMMARY_SYSTEM,
                    messages=[{"role": "user", "content": json.dumps(report)}],
                )
                return SummaryOut(month=month, summary=reply.text, generated_by=CLAUDE)
            except ClaudeUnavailable as e:
                log.warning("Claude summary failed: %s", e)
        return SummaryOut(month=month, summary=fallback_summary(report), generated_by=FALLBACK)

    def run_tool(self, user_id: int, name: str, args: dict):
        """Execute a tool call. Claude picks the function and arguments; our code does the querying."""
        if name == "list_invoices":
            return [
                {
                    "id": i.id,
                    "client": i.client.name,
                    "description": i.description,
                    "amount_cents": i.amount_cents,
                    "status": i.status,
                    "due_date": i.due_date.isoformat() if i.due_date else None,
                }
                for i in self.invoices.list_for_user(user_id, status=args.get("status"), limit=50)
            ]
        date_range_tools = {
            "get_period_summary": self.analytics.period_summary,
            "get_income_by_client": self.analytics.income_by_client,
            "get_expenses_by_category": self.analytics.expenses_by_category,
        }
        if name not in date_range_tools:
            raise ValueError(f"Unknown tool {name}")
        start, end = date.fromisoformat(args["start"]), date.fromisoformat(args["end"])
        return date_range_tools[name](user_id, start, end)

    def ask(self, user_id: int, question: str, max_steps: int = MAX_ASK_STEPS) -> AskOut:
        if not self.claude.enabled:
            return AskOut(
                answer="Add ANTHROPIC_API_KEY to backend/.env to ask questions about your finances.",
                tools_used=[],
                generated_by=FALLBACK,
            )
        system = (
            f"You answer questions about a freelancer's own income and expenses. Today is {self.today().isoformat()}. "
            "Always use the tools to get numbers; never guess. Amounts from tools are in cents; show dollars. "
            "Answer in 1-4 plain sentences. Describe the data; don't give tax, legal, or investment advice. "
            "If the data can't answer the question, say so."
        )
        messages: list = [{"role": "user", "content": question}]
        tools_used: list[str] = []
        for _ in range(max_steps):
            try:
                reply = self.claude.create_message(
                    model=self.claude.smart_model, max_tokens=1000, system=system, tools=TOOLS, messages=messages,
                )
            except ClaudeUnavailable as e:
                log.warning("Claude Q&A failed: %s", e)
                return AskOut(
                    answer="Claude isn't reachable right now. Try again in a moment.",
                    tools_used=tools_used,
                    generated_by=FALLBACK,
                )
            if reply.stop_reason != "tool_use":
                return AskOut(answer=reply.text or "I couldn't find an answer to that.", tools_used=tools_used, generated_by=CLAUDE)

            messages.append({"role": "assistant", "content": reply.assistant_content})
            results = []
            for call in reply.tool_calls:
                tools_used.append(call.name)
                try:
                    output = self.run_tool(user_id, call.name, call.input)
                    results.append({"type": "tool_result", "tool_use_id": call.id, "content": json.dumps(output)})
                except Exception as e:  # noqa: BLE001 - report tool errors back to Claude
                    results.append({"type": "tool_result", "tool_use_id": call.id, "content": str(e), "is_error": True})
            messages.append({"role": "user", "content": results})
        return AskOut(
            answer="That question needed too many steps. Try asking something more specific.",
            tools_used=tools_used,
            generated_by=CLAUDE,
        )
