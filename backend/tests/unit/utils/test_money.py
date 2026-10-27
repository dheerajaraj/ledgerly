import pytest

from app.utils.money import format_cents, parse_amount_to_cents


@pytest.mark.parametrize(
    "cents, expected",
    [
        (0, "$0.00"),
        (5, "$0.05"),
        (150, "$1.50"),
        (1234567, "$12,345.67"),
        (-150, "-$1.50"),
        (-1, "-$0.01"),
        (100_000_000_00, "$100,000,000.00"),
    ],
)
def test_format_cents(cents, expected):
    assert format_cents(cents) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("42", 4200),
        ("42.00", 4200),
        ("$1,042.00", 104200),
        ("-18.50", 1850),
        ("(12.34)", 1234),
        ("  $7.5 ", 750),
        ("0.01", 1),
    ],
)
def test_parse_amount_to_cents(raw, expected):
    assert parse_amount_to_cents(raw) == expected


def test_parse_amount_is_exact_where_float_rounding_drifts():
    # round(float("0.285") * 100) == 28 and round(float("1.005") * 100) == 100 because of
    # binary float error; Decimal parsing gives the expected half-up results.
    assert parse_amount_to_cents("0.285") == 29
    assert parse_amount_to_cents("1.005") == 101
    assert parse_amount_to_cents("19999999.99") == 1999999999


@pytest.mark.parametrize("raw", ["", "x", "1.2.3", "$", "nan", "inf", "-Infinity"])
def test_parse_amount_rejects_non_numbers(raw):
    with pytest.raises(ValueError):
        parse_amount_to_cents(raw)
