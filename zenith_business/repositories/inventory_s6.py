"""Stage 06 inventory read models — movement history and stock positions.

Stock has exactly one source of truth: the ``inventory_movements`` ledger. Nothing
here stores a stock figure; every number below is the signed sum of movements,
computed with ``Decimal`` in Python rather than a SQL float aggregate (§24), so
the Inventory screen, the reports and the Sales stock check can never disagree.

The history query resolves each movement's source document number by joining the
document tables on ``reference_type``/``reference_id``, so the operator reads
"SALE-000002" instead of a bare row id.
"""

from __future__ import annotations

from zenith_business.core.money import D, qty_to_db
from zenith_business.repositories.base import BaseRepository

# Movement type -> the table its reference_id points at. Purely for display.
_DOC_JOINS = (
    " LEFT JOIN sales s ON m.reference_type IN ('SALE','SALE_CORRECTION')"
    " AND s.id = m.reference_id"
    " LEFT JOIN purchases pu ON m.reference_type = 'PURCHASE' AND pu.id = m.reference_id"
    " LEFT JOIN sales_returns sr ON m.reference_type = 'SALES_RETURN'"
    " AND sr.id = m.reference_id"
    " LEFT JOIN purchase_returns pr ON m.reference_type = 'PURCHASE_RETURN'"
    " AND pr.id = m.reference_id"
)
_DOC_NO = ("COALESCE(s.document_no, pu.document_no, sr.document_no, pr.document_no, '')")


class InventoryReadRepository(BaseRepository):
    """Movement history and derived stock positions."""

    # ---- movement history -------------------------------------------------

    def movements(self, *, item_id: int | None = None, warehouse_id: int | None = None,
                  movement_type: str | None = None, date_from: str | None = None,
                  date_to: str | None = None, limit: int = 500) -> list[dict]:
        """Auditable movement rows, newest first, with everything the operator needs.

        Each row carries the date, item, warehouse, movement type, signed quantity,
        the source document number, who recorded it and the note/reason.
        """
        where = ["1=1"]
        params: list = []
        if item_id is not None:
            where.append("m.item_id = ?"); params.append(item_id)
        if warehouse_id is not None:
            where.append("m.warehouse_id = ?"); params.append(warehouse_id)
        if movement_type:
            where.append("m.movement_type = ?"); params.append(movement_type)
        if date_from:
            where.append("m.movement_date >= ?"); params.append(date_from)
        if date_to:
            where.append("m.movement_date <= ?"); params.append(date_to)
        params.append(limit)
        return self._all(
            "SELECT m.id, m.movement_date, m.movement_type, m.quantity, m.notes,"
            " m.reference_type, m.reference_id,"
            f" {_DOC_NO} AS document_no,"
            " i.item_code AS item_code, i.name AS item_name,"
            " w.name AS warehouse_name,"
            # Stock-only movements (opening, adjustment, transfer) carry no unit of
            # their own, so fall back to the item's base unit for display.
            " COALESCE(un.symbol, un.name_en, bu.symbol, bu.name_en, '') AS unit_symbol,"
            " u.full_name AS user_name"
            " FROM inventory_movements m"
            " LEFT JOIN items i ON i.id = m.item_id"
            " LEFT JOIN warehouses w ON w.id = m.warehouse_id"
            " LEFT JOIN units un ON un.id = m.unit_id"
            " LEFT JOIN units bu ON bu.id = i.base_unit_id"
            " LEFT JOIN users u ON u.id = m.created_by"
            f"{_DOC_JOINS}"
            f" WHERE {' AND '.join(where)}"
            " ORDER BY m.movement_date DESC, m.id DESC LIMIT ?",
            tuple(params))

    # ---- stock positions --------------------------------------------------

    def _sum_rows(self, rows: list[dict], key: str = "item_id") -> dict:
        totals: dict = {}
        for r in rows:
            totals[r[key]] = D(totals.get(r[key], D(0))) + D(r["quantity"])
        return totals

    def stock_by_item(self, *, warehouse_id: int | None = None,
                      opening_only: bool = False) -> dict[int, str]:
        """``item_id -> quantity``. ``opening_only`` restricts to OPENING movements."""
        where = ["1=1"]
        params: list = []
        if warehouse_id is not None:
            where.append("warehouse_id = ?"); params.append(warehouse_id)
        if opening_only:
            where.append("movement_type = 'OPENING'")
        rows = self._all(
            f"SELECT item_id, quantity FROM inventory_movements"
            f" WHERE {' AND '.join(where)}", tuple(params))
        return {k: qty_to_db(v) for k, v in self._sum_rows(rows).items()}

    def stock_by_item_and_warehouse(self) -> list[dict]:
        """One row per (item, warehouse) that has ever moved, with its quantity."""
        rows = self._all(
            "SELECT m.item_id, m.warehouse_id, m.quantity,"
            " i.item_code, i.name AS item_name, i.reorder_level,"
            " w.name AS warehouse_name, un.symbol AS unit_symbol"
            " FROM inventory_movements m"
            " LEFT JOIN items i ON i.id = m.item_id"
            " LEFT JOIN warehouses w ON w.id = m.warehouse_id"
            " LEFT JOIN units un ON un.id = i.base_unit_id")
        buckets: dict[tuple, dict] = {}
        for r in rows:
            key = (r["item_id"], r["warehouse_id"])
            b = buckets.setdefault(key, {
                "item_id": r["item_id"], "warehouse_id": r["warehouse_id"],
                "item_code": r["item_code"], "item_name": r["item_name"],
                "warehouse_name": r["warehouse_name"], "unit_symbol": r["unit_symbol"],
                "reorder_level": r["reorder_level"], "_qty": D(0)})
            b["_qty"] += D(r["quantity"])
        out = []
        for b in buckets.values():
            qty = b.pop("_qty")
            out.append({**b, "quantity": qty_to_db(qty)})
        out.sort(key=lambda r: ((r["item_code"] or ""), (r["warehouse_name"] or "")))
        return out

    def warehouse_names_by_item(self) -> dict[int, list[str]]:
        """``item_id -> warehouse names currently holding a non-zero quantity``."""
        out: dict[int, list[str]] = {}
        for row in self.stock_by_item_and_warehouse():
            if D(row["quantity"]) != 0 and row["warehouse_name"]:
                out.setdefault(row["item_id"], []).append(row["warehouse_name"])
        return out

    def items_with_levels(self) -> list[dict]:
        """Active items with their unit and reorder level (the low-stock inputs)."""
        return self._all(
            "SELECT i.id, i.item_code, i.name, i.reorder_level, i.track_inventory,"
            " i.is_active, un.symbol AS unit_symbol, un.name_en AS unit_name"
            " FROM items i LEFT JOIN units un ON un.id = i.base_unit_id"
            " ORDER BY i.item_code")
