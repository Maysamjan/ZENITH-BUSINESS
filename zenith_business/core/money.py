"""Decimal-safe money and quantity handling (Stage 02 §24).

NEVER use binary float for financial values. Money, quantities, prices, discounts
and exchange rates are handled as :class:`decimal.Decimal` in Python and stored as
canonical TEXT strings in SQLite (which has no native decimal type). This keeps
exact precision and consistent rounding across the whole application.

Storage format: a plain decimal string, e.g. ``"1234.56"`` (money, 2 places),
``"12.000"`` (quantity, 3 places), ``"73.5000"`` (exchange rate, 4 places).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, getcontext
from typing import Union

getcontext().prec = 34  # generous precision for intermediate calculations

Number = Union[int, str, Decimal, float]

MONEY_PLACES = Decimal("0.01")
QTY_PLACES = Decimal("0.001")
RATE_PLACES = Decimal("0.0001")
ZERO = Decimal("0.00")


def D(value: Number | None) -> Decimal:
    """Coerce a value to Decimal safely. ``None`` becomes 0.

    Floats are routed through ``str`` to avoid binary-float artifacts.
    """
    if value is None:
        return Decimal(0)
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    try:
        return Decimal(str(value).replace(",", "").strip() or "0")
    except (InvalidOperation, ValueError):
        return Decimal(0)


def parse_decimal(value: Number | None) -> Decimal:
    """Strictly parse a caller-supplied numeric value; raise on malformed input.

    Unlike :func:`D` (which is lenient — garbage becomes 0 — for safe *display*
    formatting), this is the parser for the *write* path: a value like ``"12x3"``
    or ``None`` must be rejected, never silently turned into 0 and posted. Service
    validators use this so malformed numbers can never corrupt a document (§24).
    """
    if value is None:
        raise ValueError("A numeric value is required.")
    if isinstance(value, bool):  # guard: bool is an int subclass
        raise ValueError(f"Invalid numeric value: {value!r}")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    text = str(value).replace(",", "").strip()
    if text == "":
        raise ValueError("A numeric value is required.")
    try:
        return Decimal(text)
    except InvalidOperation:
        raise ValueError(f"Invalid numeric value: {value!r}") from None


def money(value: Number | None) -> Decimal:
    """Quantize to money precision (2 places, half-up)."""
    return D(value).quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)


def quantity(value: Number | None) -> Decimal:
    return D(value).quantize(QTY_PLACES, rounding=ROUND_HALF_UP)


def rate(value: Number | None) -> Decimal:
    return D(value).quantize(RATE_PLACES, rounding=ROUND_HALF_UP)


# ---- DB (de)serialization ----------------------------------------------

def money_to_db(value: Number | None) -> str:
    return str(money(value))


def money_from_db(text: str | None) -> Decimal:
    return money(text)


def qty_to_db(value: Number | None) -> str:
    return str(quantity(value))


def qty_from_db(text: str | None) -> Decimal:
    return quantity(text)


def rate_to_db(value: Number | None) -> str:
    return str(rate(value))


def rate_from_db(text: str | None) -> Decimal:
    return rate(text)


def format_money(value: Number | None) -> str:
    """Human display with thousands separators, e.g. ``73,450.00``."""
    return f"{money(value):,.2f}"
