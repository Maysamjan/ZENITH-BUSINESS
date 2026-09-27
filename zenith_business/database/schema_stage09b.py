"""Forward migration 0012 — readable COGS descriptions in the General Ledger.

The Stage 09 COGS journals were first written with ``Cost of goods sold —
movement 14``: an ``inventory_movements`` row id, which is an internal
identifier the customer has no way to look up and should never have been shown.
The service now names the DOCUMENT that caused the cost (``COGS — SALE-000009``,
``COGS Reversal — SRET-000001``), but entries already posted keep the text they
were written with, so an upgraded database would still show the old wording for
its existing history.

This migration rewrites those descriptions **in place** through the same rule the
service now uses. Nothing else changes: no amount, no date, no account, no line —
the journals themselves are untouched and every statement reports exactly what it
reported before. It is data-only and re-runnable, and it deliberately matches on
the old text so a description an operator may have edited is left alone.
"""

from __future__ import annotations

import sqlite3

from zenith_business.services.cogs_posting import SOURCE_TYPE, cogs_description

#: What the first version of the service wrote. Matched with LIKE so only those
#: rows are rewritten.
_LEGACY_PREFIX = "Cost of goods sold — movement %"


def migrate_stage09b(conn: sqlite3.Connection) -> None:
    """Migration 0012 — replace internal movement ids with document references."""
    rows = conn.execute(
        "SELECT e.id, m.reference_type,"
        "       COALESCE(s.document_no, sr.document_no) AS document_no"
        "  FROM financial_entries e"
        "  JOIN inventory_movements m ON m.id = e.source_id"
        "  LEFT JOIN sales s ON s.id = m.reference_id"
        "       AND m.reference_type IN ('SALE', 'SALE_CORRECTION', 'SALE_VOID')"
        "  LEFT JOIN sales_returns sr ON sr.id = m.reference_id"
        "       AND m.reference_type = 'SALES_RETURN'"
        " WHERE e.source_type = ? AND e.description LIKE ?",
        (SOURCE_TYPE, _LEGACY_PREFIX)).fetchall()
    if not rows:
        return
    conn.executemany(
        "UPDATE financial_entries SET description = ? WHERE id = ?",
        [(cogs_description(r[1], r[2]), r[0]) for r in rows])
