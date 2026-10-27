from app.integrations.anthropic import ClaudeUnavailable
from tests.helpers import text_reply, tool_reply


def test_summary_fallback_without_claude(client, auth):
    r = client.post("/api/insights/summary", headers=auth)
    assert r.status_code == 200
    assert r.json()["generated_by"] == "fallback"


def test_summary_with_claude(client, auth, claude):
    claude.enabled, claude.replies = True, [text_reply("A calm month.")]
    r = client.post("/api/insights/summary?month=2026-10", headers=auth)
    assert r.json() == {"month": "2026-10", "summary": "A calm month.", "generated_by": "claude"}
    assert claude.requests[0]["model"] == "smart-model"


def test_ask_runs_tool_loop(client, auth, claude):
    """Claude asks for a tool, our code runs it, and the final text comes back."""
    def final(request):
        tool_result = request["messages"][-1]["content"][0]
        assert tool_result["type"] == "tool_result" and "profit_cents" in tool_result["content"]
        return text_reply("You made $0.00 this year.")

    claude.enabled = True
    claude.replies = [tool_reply(("get_period_summary", {"start": "2026-01-01", "end": "2027-01-01"})), final]
    r = client.post("/api/insights/ask", json={"question": "How much did I make this year?"}, headers=auth)
    assert r.status_code == 200, r.text
    assert r.json() == {"answer": "You made $0.00 this year.", "tools_used": ["get_period_summary"], "generated_by": "claude"}


def test_ask_list_invoices_tool_returns_users_invoices(client, auth, claude, make_invoice):
    inv = make_invoice()

    def final(request):
        assert f'"id": {inv["id"]}' in request["messages"][-1]["content"][0]["content"]
        return text_reply("One draft.")

    claude.enabled, claude.replies = True, [tool_reply(("list_invoices", {"status": "draft"})), final]
    assert client.post("/api/insights/ask", json={"question": "Any drafts?"}, headers=auth).json()["answer"] == "One draft."


def test_ask_fallback_without_claude(client, auth):
    r = client.post("/api/insights/ask", json={"question": "How much did I make?"}, headers=auth)
    assert r.json()["generated_by"] == "fallback"


def test_ask_when_claude_fails_returns_fallback_not_500(client, auth, claude):
    claude.enabled, claude.replies = True, [ClaudeUnavailable("overloaded")]
    r = client.post("/api/insights/ask", json={"question": "How much did I make?"}, headers=auth)
    assert r.status_code == 200 and r.json()["generated_by"] == "fallback"


def test_expense_categorized_by_claude(client, auth, claude):
    claude.enabled, claude.replies = True, [text_reply('[{"index": 0, "category": "Meals"}]')]
    r = client.post("/api/expenses", json={"date": "2026-10-01", "description": "Team offsite", "amount_cents": 900}, headers=auth)
    assert (r.json()["category"], r.json()["category_source"]) == ("Meals", "ai")
