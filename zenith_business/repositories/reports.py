"""Read-only reporting repository (Sales Reporting).

All figures come from the SAME authoritative tables that post the documents —
there is no separate reporting truth. Only ``POSTED`` sales/returns are counted,
so a VOID original left behind by a correction is never double-counted, and
later receipts (debt collection) are NOT sales and never appear here.

Money columns are stored as decimal TEXT; callers sum them with ``Decimal`` for
exactness rather than relying on SQLite float coercion.
"""

from __future__ import annotations

from zenith_business.repositories.base import BaseRepository


class SalesReportRepository(BaseRepository):
    """Authoritative rows for the Sales Reporting service."""

    def posted_sales(self, date_from: str, date_to: str, *,
                     warehouse_id: int | None = None,
                     party_id: int | None = None) -> list[dict]:
        """POSTED sales in [date_from, date_to] (inclusive), newest first.

        Each row carries the money split already stored on the sale:
        ``grand_total`` (gross), ``amount_paid`` (paid at sale) and
        ``remaining_amount`` (credit created by the sale). The displayed party is
        the registered name or, for a walk-in, the entered ``walkin_name``.
        """
        where = ["s.status = 'POSTED'", "s.sale_date >= ?", "s.sale_date <= ?"]
        params: list = [date_from, date_to]
        if warehouse_id is not None:
            where.append("s.warehouse_id = ?"); params.append(warehouse_id)
        if party_id is not None:
            where.append("s.party_id = ?"); params.append(party_id)
        return self._all(
            "SELECT s.id, s.document_no, s.sale_date, s.grand_total, s.amount_paid,"
            " s.remaining_amount, s.party_id, s.warehouse_id,"
            " p.name AS party_name, s.walkin_name AS walkin_name,"
            " w.name AS warehouse_name FROM sales s"
            " LEFT JOIN parties p ON p.id = s.party_id"
            " LEFT JOIN warehouses w ON w.id = s.warehouse_id"
            f" WHERE {' AND '.join(where)}"
            " ORDER BY s.sale_date DESC, s.id DESC",
            tuple(params))

    def posted_returns(self, date_from: str, date_to: str, *,
                       warehouse_id: int | None = None,
                       party_id: int | None = None) -> list[dict]:
        """POSTED sales returns in [date_from, date_to] (inclusive)."""
        where = ["sr.status = 'POSTED'", "sr.return_date >= ?", "sr.return_date <= ?"]
        params: list = [date_from, date_to]
        if warehouse_id is not None:
            where.append("sr.warehouse_id = ?"); params.append(warehouse_id)
        if party_id is not None:
            where.append("sr.party_id = ?"); params.append(party_id)
        return self._all(
            "SELECT sr.id, sr.document_no, sr.return_date, sr.grand_total, sr.sale_id,"
            " sr.party_id, sr.warehouse_id FROM sales_returns sr"
            f" WHERE {' AND '.join(where)}"
            " ORDER BY sr.return_date DESC, sr.id DESC",
            tuple(params))

    def all_posted_returns_for_sales(self, sale_ids: list[int]) -> list[dict]:
        """Every POSTED return against the given sales, any date (for per-invoice
        "returned" totals in the transaction detail)."""
        if not sale_ids:
            return []
        marks = ",".join("?" * len(sale_ids))
        return self._all(
            f"SELECT sale_id, grand_total FROM sales_returns"
            f" WHERE status = 'POSTED' AND sale_id IN ({marks})",
            tuple(sale_ids))
