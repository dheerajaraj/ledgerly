import pytest

from app.integrations.anthropic import ClaudeUnavailable
from app.services.categorization import CategorizationService, rule_based_category
from tests.helpers import FakeClaude, text_reply


@pytest.mark.parametrize(
    "description, category",
    [("Figma subscription", "Software"), ("GRAB to airport", "Travel"), ("Lunch", "Meals"), ("Mystery", "Other")],
)
def test_rule_based_category(description, category):
    assert rule_based_category(description) == category


def test_empty_input_makes_no_call():
    claude = FakeClaude()
    assert CategorizationService(claude).categorize([]) == []
    assert claude.requests == []


def test_disabled_claude_uses_rules():
    claude = FakeClaude(enabled=False)
    assert CategorizationService(claude).categorize(["Figma", "Mystery"]) == [("Software", "rule"), ("Other", "rule")]
    assert claude.requests == []


def test_ai_categories_override_rules_and_invalid_items_fall_back():
    reply = text_reply('```json\n[{"index": 0, "category": "Marketing"}, {"index": 1, "category": "Bogus"}, {"index": 9, "category": "Meals"}]\n```')
    claude = FakeClaude([reply])
    result = CategorizationService(claude).categorize(["Figma", "Lunch", "Mystery"])
    assert result == [("Marketing", "ai"), ("Meals", "rule"), ("Other", "rule")]
    assert claude.requests[0]["model"] == "fast-model"
    assert claude.requests[0]["messages"][0]["content"] == "0. Figma\n1. Lunch\n2. Mystery"


@pytest.mark.parametrize("reply", [text_reply("not json"), text_reply('[{"category": "Meals"}]'), text_reply('{"a": 1}'), ClaudeUnavailable("down")])
def test_bad_replies_and_failures_fall_back_to_rules(reply):
    assert CategorizationService(FakeClaude([reply])).categorize(["Lunch"]) == [("Meals", "rule")]
