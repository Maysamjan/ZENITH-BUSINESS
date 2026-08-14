"""Document numbering (Stage 02 §32)."""

from __future__ import annotations

import pytest


def test_sequential_unique_numbers(context) -> None:
    a = context.numbering.allocate("SALE")
    b = context.numbering.allocate("SALE")
    assert a == "SALE-000001"
    assert b == "SALE-000002"
    assert a != b


def test_peek_does_not_consume(context) -> None:
    peek1 = context.numbering.peek("PUR")
    peek2 = context.numbering.peek("PUR")
    assert peek1 == peek2 == "PUR-000001"
    allocated = context.numbering.allocate("PUR")
    assert allocated == "PUR-000001"


def test_unknown_sequence_raises(context) -> None:
    with pytest.raises(KeyError):
        context.numbering.allocate("NOPE")


def test_rollback_reclaims_number(context) -> None:
    """A number allocated inside a transaction that rolls back is reclaimed."""
    before = context.numbering.peek("REC")
    try:
        with context.db.transaction():
            context.sequences_repo.allocate("REC")
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert context.numbering.peek("REC") == before
