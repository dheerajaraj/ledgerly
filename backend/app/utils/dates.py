"""Month keys ("YYYY-MM") and lenient date parsing."""
from datetime import date, datetime

DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%d %b %Y")


def month_key(d: date | datetime) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def month_bounds(month: str) -> tuple[date, date]:
    """'2026-10' -> (2026-10-01, 2026-11-01) as a half-open range."""
    y, m = (int(x) for x in month.split("-"))
    start = date(y, m, 1)
    end = date(y + (m == 12), m % 12 + 1, 1)
    return start, end


def shift_month(month: str, delta: int) -> str:
    y, m = (int(x) for x in month.split("-"))
    idx = y * 12 + (m - 1) + delta
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


def month_label(month: str) -> str:
    """'2026-10' -> 'October 2026'."""
    y, m = (int(x) for x in month.split("-"))
    return date(y, m, 1).strftime("%B %Y")


def parse_flexible_date(raw: str, formats: tuple[str, ...] = DATE_FORMATS) -> date:
    """Parse a date in the first matching format. Raises ValueError if none match."""
    raw = raw.strip()
    for fmt in formats:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date {raw!r}")
