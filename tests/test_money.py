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
