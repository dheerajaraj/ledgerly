"""Expense categorization: Claude first, keyword rules as the fallback."""
import json
import logging
import re

from ..integrations.anthropic import ClaudeClient, ClaudeUnavailable
from ..repository.models import CategorySource
from ..schema.expense import CATEGORIES

log = logging.getLogger(__name__)

_KEYWORDS = {
    "Software": ["figma", "notion", "github", "adobe", "slack", "aws", "vercel", "saas", "subscription", "google workspace", "openai", "anthropic", "zoom", "dropbox", "jetbrains"],
    "Hardware": ["laptop", "monitor", "keyboard", "mouse", "macbook", "ipad", "headphones", "webcam", "ssd"],
    "Office": ["coworking", "wework", "desk", "chair", "stationery", "printer", "paper"],
    "Travel": ["flight", "airline", "hotel", "airbnb", "uber", "grab", "taxi", "train", "mrt", "parking", "fuel"],
    "Meals": ["lunch", "dinner", "coffee", "starbucks", "restaurant", "cafe", "breakfast", "food"],
    "Marketing": ["ads", "advert", "linkedin premium", "facebook ads", "google ads", "domain", "branding", "promo"],
    "Professional services": ["accountant", "lawyer", "legal", "consultant", "bookkeeping", "contractor"],
    "Utilities": ["internet", "phone", "mobile plan", "electricity", "broadband", "singtel", "starhub"],
    "Taxes & fees": ["tax", "stripe fee", "bank fee", "gst", "license", "registration"],
    "Education": ["course", "udemy", "book", "conference", "workshop", "coursera"],
}

CATEGORIZE_SYSTEM = f"""You categorize business expenses for a freelancer.
Allowed categories: {", ".join(CATEGORIES)}.
Respond with ONLY a JSON array, one object per input line, in the same order:
[{{"index": 0, "category": "<one allowed category>"}}]
No prose, no markdown fences. Use "Other" if nothing fits."""


def rule_based_category(description: str) -> str:
    text = description.lower()
    for category, words in _KEYWORDS.items():
        if any(w in text for w in words):
            return category
    return "Other"


def _parse_json(text: str):
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    return json.loads(cleaned)


class CategorizationService:
    def __init__(self, claude: ClaudeClient):
        self.claude = claude

    def categorize(self, descriptions: list[str]) -> list[tuple[str, CategorySource]]:
        """Return (category, source) for each description, in order."""
        if not descriptions:
            return []
        fallback = [(rule_based_category(d), CategorySource.RULE) for d in descriptions]
        if not self.claude.enabled:
            return fallback
        try:
            reply = self.claude.create_message(
                model=self.claude.fast_model,
                max_tokens=1000,
                system=CATEGORIZE_SYSTEM,
                messages=[{"role": "user", "content": "\n".join(f"{i}. {d}" for i, d in enumerate(descriptions))}],
            )
            items = _parse_json(reply.text)
            result = list(fallback)
            for item in items:
                i, category = int(item["index"]), item["category"]
                if 0 <= i < len(result) and category in CATEGORIES:
                    result[i] = (category, CategorySource.AI)
            return result
        except (ClaudeUnavailable, ValueError, KeyError, TypeError) as e:
            log.warning("Claude categorization failed, using keyword rules: %s", e)
            return fallback
