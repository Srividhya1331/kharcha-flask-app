import pytest

from expense_tracker.utils import (csv_safe, format_inr, is_safe_redirect, month_bounds,
                                   parse_amount_to_paise, shift_month)


@pytest.mark.parametrize("raw,paise", [("450", 45000), ("450.5", 45050), ("1,250.50", 125050), (" 0.01 ", 1)])
def test_parse_amount_valid(raw, paise):
    assert parse_amount_to_paise(raw) == paise


@pytest.mark.parametrize("raw", ["", "abc", "0", "-5", "1.999", "NaN", "Infinity", "99999999999"])
def test_parse_amount_invalid(raw):
    with pytest.raises(ValueError):
        parse_amount_to_paise(raw)


def test_no_float_drift():
    # 0.1 + 0.2 != 0.3 with floats; paise integers stay exact
    assert parse_amount_to_paise("0.10") + parse_amount_to_paise("0.20") == parse_amount_to_paise("0.30")


@pytest.mark.parametrize("paise,expected", [
    (0, "₹0.00"), (99, "₹0.99"), (100000, "₹1,000.00"),
    (12345678, "₹1,23,456.78"), (1000000000, "₹1,00,00,000.00"), (-50000, "-₹500.00"),
])
def test_format_inr(paise, expected):
    assert format_inr(paise) == expected


def test_month_helpers_cross_year_boundary():
    assert month_bounds("2025-12")[1].isoformat() == "2026-01-01"
    assert shift_month("2026-01", -1) == "2025-12"
    assert shift_month("2025-11", 3) == "2026-02"


def test_csv_safe_blocks_formulas():
    assert csv_safe("=SUM(A1:A9)").startswith("'")
    assert csv_safe("Lunch") == "Lunch"


def test_safe_redirect():
    assert is_safe_redirect("/expenses")
    assert not is_safe_redirect("//evil.com")
    assert not is_safe_redirect("https://evil.com")
    assert not is_safe_redirect(None)
