"""Money helpers. Amounts are integer cents; these never go through float."""
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation


def format_cents(cents: int) -> str:
    """1234567 -> '$12,345.67', -150 -> '-$1.50'."""
    sign = "-" if cents < 0 else ""
    dollars, remainder = divmod(abs(cents), 100)
    return f"{sign}${dollars:,}.{remainder:02d}"


def parse_amount_to_cents(raw: str) -> int:
    """Parse a bank-export amount like '$1,042.00', '-18.50' or '(12.34)' into positive cents.

    Bank exports often show spending as negative or in parentheses, so the sign is dropped.
    Raises ValueError for anything that isn't a finite number.
    """
    cleaned = raw.replace("$", "").replace(",", "").strip()
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = cleaned[1:-1]
    try:
        amount = Decimal(cleaned)
    except InvalidOperation:
        raise ValueError(f"Unrecognized amount {raw!r}") from None
    if not amount.is_finite():
        raise ValueError(f"Unrecognized amount {raw!r}")
    return int((abs(amount) * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))
