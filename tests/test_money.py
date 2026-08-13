"""Decimal-safe money handling (Stage 02 §24)."""

from __future__ import annotations

from decimal import Decimal

from zenith_business.core import money as m


def test_no_binary_float_artifacts() -> None:
    # 0.1 + 0.2 must be exactly 0.30, not 0.30000000000000004.
    total = m.money(m.D("0.1") + m.D("0.2"))
    assert str(total) == "0.30"


def test_float_input_routed_through_str() -> None:
    assert m.money(0.1) == Decimal("0.10")
    assert m.qty_to_db(1.005) in {"1.005", "1.005"}


def test_money_rounding_half_up() -> None:
    assert str(m.money("2.345")) == "2.35"
    assert str(m.money("2.344")) == "2.34"


def test_quantity_and_rate_precision() -> None:
    assert str(m.quantity("3")) == "3.000"
    assert str(m.rate("73.5")) == "73.5000"


def test_db_round_trip_is_exact() -> None:
    value = "123456789.99"
    stored = m.money_to_db(value)
    assert stored == "123456789.99"
    assert m.money_from_db(stored) == Decimal("123456789.99")


def test_none_and_garbage_are_safe() -> None:
    assert m.money(None) == Decimal("0.00")
    assert m.D("not-a-number") == Decimal(0)


def test_thousands_formatting() -> None:
    assert m.format_money("73450") == "73,450.00"


# ---- Stage 02 audit: explicit financial edge values (§6) ----------------

import pytest  # noqa: E402


@pytest.mark.parametrize("value,expected", [
    ("0", "0.00"),
    ("0.01", "0.01"),
    ("0.10", "0.10"),
    ("1.10", "1.10"),
    ("10.99", "10.99"),
    ("999999999.99", "999999999.99"),
    ("1000000000000.00", "1000000000000.00"),
])
def test_money_db_roundtrip_edge_values(value, expected) -> None:
    assert m.money_to_db(value) == expected
    assert m.money_from_db(m.money_to_db(value)) == Decimal(expected)


def test_repeated_fractional_calculations_stay_exact() -> None:
    total = m.D(0)
    for _ in range(10):
        total += m.money("0.10")
    assert m.money(total) == Decimal("1.00")  # not 0.9999999999


def test_discount_calculation_exact() -> None:
    gross = m.money(m.D("3") * m.D("100"))
    line = m.money(gross - m.money("10"))
    assert str(line) == "290.00"


def test_exchange_rate_conversion_exact() -> None:
    # 100 USD at rate 73.5 -> 7350.00 AFN, no float drift.
    afn = m.money(m.D("100") * m.rate("73.5"))
    assert str(afn) == "7350.00"
