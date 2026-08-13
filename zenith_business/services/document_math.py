"""Shared, Decimal-safe document line math and ledger guards (Stage 02 §24, §29).

Centralizes the arithmetic + validation that sales and purchases both need, so the
rules (no negative price, no negative quantity, discount never exceeds the line
gross, and journals must balance) are defined exactly once and cannot drift apart.
"""

from __future__ import annotations

from decimal import Decimal
from typing import NamedTuple

from zenith_business.core.money import D, money, quantity
from zenith_business.repositories.documents import FinancialRepository
from zenith_business.services.exceptions import InvalidJournalError, ValidationError


class ComputedLine(NamedTuple):
    quantity: Decimal
    unit_price: Decimal
    discount: Decimal
    gross: Decimal
    line_total: Decimal


def compute_line(raw_quantity, raw_unit_price, raw_discount=0) -> ComputedLine:
    """Validate and compute one document line with exact Decimal math.

    Rules enforced (§24): quantity > 0, unit_price >= 0, discount >= 0, and the
    discount may not exceed the line's gross (a line total can never be negative).
    """
    qty = quantity(raw_quantity)
    price = money(raw_unit_price)
    disc = money(raw_discount)
    if qty <= 0:
        raise ValidationError("Line quantity must be greater than zero.",
                              user_message="Each line must have a quantity above zero.")
    if price < 0:
        raise ValidationError("Unit price cannot be negative.",
                              user_message="Unit price cannot be negative.")
    if disc < 0:
        raise ValidationError("Discount cannot be negative.",
                              user_message="Discount cannot be negative.")
    gross = money(qty * price)
    if disc > gross:
        raise ValidationError("Line discount cannot exceed the line total.",
                              user_message="A discount cannot be larger than the line amount.")
    return ComputedLine(qty, price, disc, gross, money(gross - disc))


def assert_journal_balanced(financial: FinancialRepository, entry_id: int) -> None:
    """Raise :class:`InvalidJournalError` unless the entry's debits == credits.

    Called inside the posting transaction, so an unbalanced journal rolls back
    the whole business document instead of committing corrupt accounting (§29).
    """
    if D(financial.entry_balance(entry_id)) != Decimal(0):
        raise InvalidJournalError(
            f"Journal entry {entry_id} does not balance "
            f"(net debit-credit = {financial.entry_balance(entry_id)}).")
