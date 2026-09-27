"""Stage 06 inventory reports.

Five views of the same ledger — there is no separate reporting store, so a report
can never disagree with the Inventory screen or with the stock a sale is checked
against:

* **Current Stock**      — what every stockable item holds right now.
* **Opening vs Current** — the starting figure, today's figure, and the movement
  between them, per item.
* **Stock by Warehouse** — where the stock physically is.
* **Item Movement**      — the stock card for one item: every movement with its
  source document, user and note, plus a running balance.
* **Low Stock**          — items at or below their minimum level.

Quantities are summed with ``Decimal`` (never a SQL float) by the inventory
service these reports read from.
"""

from __future__ import annotations

from zenith_business.core.money import D, qty_to_db


class InventoryReportService:
    """Read-only report builders over the authoritative movement ledger."""

    #: Report keys, in the order the screen offers them.
    KINDS = ("current", "opening_vs_current", "by_warehouse", "movement", "low_stock")

    def __init__(self, inventory, authz) -> None:
        self._inv = inventory
        self._authz = authz

    # ---- the five reports -------------------------------------------------

    def current_stock(self) -> list[dict]:
        """Every stockable item with its current quantity and low-stock state."""
        self._authz.require("inventory.view")
        return self._inv.stock_overview()

    def opening_vs_current(self) -> list[dict]:
        """Opening, current and the net movement between them, per item.

        Opening never changes; the difference is everything trading has done since.
        """
        self._authz.require("inventory.view")
        rows = []
        for r in self._inv.stock_overview():
            opening = D(r["opening"]); current = D(r["current"])
            rows.append({**r, "difference": qty_to_db(current - opening)})
        return rows

    def stock_by_warehouse(self, *, warehouse_id: int | None = None) -> list[dict]:
        """One row per (item, warehouse) holding stock."""
        self._authz.require("inventory.view")
        rows = self._inv.stock_by_warehouse()
        if warehouse_id is not None:
            rows = [r for r in rows if r["warehouse_id"] == warehouse_id]
        return [r for r in rows if D(r["quantity"]) != 0]

    def item_movement(self, *, item_id: int, warehouse_id: int | None = None,
                      date_from: str | None = None, date_to: str | None = None) -> list[dict]:
        """One item's stock card, oldest first, with a running balance.

        The balance is accumulated over the same rows the operator sees, so the
        last line always equals the item's current stock for that filter.
        """
        self._authz.require("inventory.view")
        rows = self._inv.movement_history(
            item_id=item_id, warehouse_id=warehouse_id,
            date_from=date_from, date_to=date_to, limit=1000)
        running = D(0)
        out = []
        for r in reversed(rows):          # history is newest-first; walk forwards
            running += D(r["quantity"])
            out.append({**r, "balance": qty_to_db(running)})
        return out

    def low_stock(self) -> list[dict]:
        """Items at or below their minimum level."""
        self._authz.require("inventory.view")
        return self._inv.low_stock()

    # ---- totals for the report footers -----------------------------------

    @staticmethod
    def total_quantity(rows: list[dict], key: str = "current") -> str:
        return qty_to_db(sum((D(r.get(key) or 0) for r in rows), D(0)))
