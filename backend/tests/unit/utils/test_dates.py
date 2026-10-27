from datetime import date, datetime

import pytest

from app.utils.dates import month_bounds, month_key, month_label, parse_flexible_date, shift_month


def test_month_key_accepts_date_and_datetime():
    assert month_key(date(2026, 3, 9)) == "2026-03"
    assert month_key(datetime(2026, 12, 31, 23, 59)) == "2026-12"


def test_month_bounds_is_half_open_and_wraps_year():
    assert month_bounds("2026-10") == (date(2026, 10, 1), date(2026, 11, 1))
    assert month_bounds("2026-12") == (date(2026, 12, 1), date(2027, 1, 1))


@pytest.mark.parametrize(
    "month, delta, expected",
    [("2026-10", 0, "2026-10"), ("2026-10", 3, "2027-01"), ("2026-01", -1, "2025-12"), ("2026-06", -18, "2024-12")],
)
def test_shift_month(month, delta, expected):
    assert shift_month(month, delta) == expected


def test_month_label():
    assert month_label("2026-10") == "October 2026"


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("2026-10-02", date(2026, 10, 2)),
        (" 25/10/2026 ", date(2026, 10, 25)),
        ("10/25/2026", date(2026, 10, 25)),
        ("25-10-2026", date(2026, 10, 25)),
        ("2 Oct 2026", date(2026, 10, 2)),
    ],
)
def test_parse_flexible_date(raw, expected):
    assert parse_flexible_date(raw) == expected


def test_parse_flexible_date_prefers_day_first_when_ambiguous():
    assert parse_flexible_date("03/10/2026") == date(2026, 10, 3)


@pytest.mark.parametrize("raw", ["", "bad", "2026-13-01", "31/02/2026"])
def test_parse_flexible_date_rejects_invalid(raw):
    with pytest.raises(ValueError):
        parse_flexible_date(raw)
