"""Stage 08 — the weighted-average costing engine (constitution §4.7, Spec §11).

ONE engine decides what every stock movement is worth, and it writes that worth
onto the movement itself. The movement ledger already answers "how much stock is
there"; from Stage 08 the same row also answers "what is it worth", so quantity
and value can never drift apart into two stories.

Why the cost is captured when the movement happens, and never re-derived later
--------------------------------------------------------------------------------
It is tempting to leave the ledger alone and work the cost out on demand from the
purchase that caused it. That does not survive contact with this system: a
purchase **correction** rewrites its line row in place (same id, new price), so
the price a movement was made at is genuinely gone afterwards. A cost worked out
after the fact would quietly use today's price for yesterday's receipt. So a
movement's cost is a historical fact, recorded once, exactly like its quantity —
and a later edit posts a NEW compensating movement rather than rewriting history.

The rules
---------
Cost is averaged per **(item, warehouse)**, because valuation has to be reportable
per warehouse and a transfer must not change what the company is worth.

* **Inbound at a known price** — a purchase, or opening stock. The price paid is
  the cost: ``line total / quantity``, so a line discount lowers the cost of the
  goods rather than disappearing.
* **Outbound** — a sale, a manual issue, a transfer out. Leaves at the **current
  weighted average** of that item in that warehouse. For a sale, that is COGS.
* **Reversals** — a correction or a void takes back a movement that really
  happened. It reverses at the cost the original went at, never at today's
  average, or a re-costed reversal would leak value.
* **Purchase return** — goods go back to the supplier at what was paid for them
  (found through the return's own link to the purchase line), not at the average.
* **Sale return** — goods come back at the cost they left at, so returning what
  you sold restores exactly the value the sale removed.
* **Transfer in** — costed from its paired transfer out, so the value leaving one
  warehouse is the value arriving in the other and the **company total is
  unchanged**.
* **Inbound with no price to point at** — a manual adjustment in. Uses the current
  average, which leaves the average undisturbed, falling back to the item's
  purchase price when there is no stock to average.

Money is Decimal throughout and never a SQL float aggregate (§24).
"""

from __future__ import annotations

import sqlite3
from decimal import Decimal

from zenith_business.core.money import D, money, money_to_db

#: Cost is carried to more places than money so repeated averaging does not drift;
#: the *value* written to a movement is rounded to money precision.
COST_PRECISION = Decimal("0.000001")


def average_cost(value: Decimal, quantity: Decimal) -> Decimal:
    """Weighted average unit cost, or zero when there is nothing to average."""
    if quantity == 0:
        return D(0)
    return (value / quantity).quantize(COST_PRECISION)


def line_unit_cost(line_total, quantity) -> Decimal:
    """What one unit of a document line actually cost, discount included."""
    qty = D(quantity)
    if qty == 0:
        return D(0)
    return (D(line_total) / qty).quantize(COST_PRECISION)


class MovementCoster:
    """Decides the cost of one movement, reading only the ledger and documents.

    Deliberately built on a raw connection: it is consulted from inside the
    inventory repository, which is the single point every movement passes
    through — so no posting path can create stock that nobody costed, and no
    locked Stage 05/06/07 service had to change to get costing.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # ---- ledger reads -----------------------------------------------------

    def position(self, item_id: int, warehouse_id: int,
                 before_id: int | None = None) -> tuple[Decimal, Decimal]:
        """(quantity, value) held of this item in this warehouse.

        ``before_id`` excludes the movement being costed and everything after it.
        When costing a NEW movement the row does not exist yet, so the position is
        naturally "before"; when RE-costing an existing row (the migration
        backfill) it does exist, and letting a movement into the average it is
        about to be priced from makes the average depend on itself.
        """
        sql = ("SELECT quantity, total_cost FROM inventory_movements"
               " WHERE item_id = ? AND warehouse_id = ?")
        params: list = [item_id, warehouse_id]
        if before_id is not None:
            sql += " AND id < ?"
            params.append(before_id)
        rows = self._conn.execute(sql, params).fetchall()
        qty = sum((D(r[0]) for r in rows), D(0))
        value = sum((D(r[1]) for r in rows if r[1] is not None), D(0))
        return qty, value

    def current_average(self, item_id: int, warehouse_id: int,
                        before_id: int | None = None) -> Decimal:
        qty, value = self.position(item_id, warehouse_id, before_id)
        return average_cost(value, qty)

    def _item_purchase_price(self, item_id: int) -> Decimal:
        row = self._conn.execute(
            "SELECT purchase_price FROM items WHERE id = ?", (item_id,)).fetchone()
        return D(row[0]) if row and row[0] is not None else D(0)

    def _movement_unit_cost(self, movement_id: int) -> Decimal | None:
        row = self._conn.execute(
            "SELECT unit_cost FROM inventory_movements WHERE id = ?",
            (movement_id,)).fetchone()
        return D(row[0]) if row and row[0] is not None else None

    def _movement_total_cost(self, movement_id: int) -> Decimal | None:
        row = self._conn.execute(
            "SELECT total_cost FROM inventory_movements WHERE id = ?",
            (movement_id,)).fetchone()
        return D(row[0]) if row and row[0] is not None else None

    def _cost_of_source_movement(self, *, reference_type: str, reference_line_id: int,
                                 item_id: int,
                                 before_id: int | None = None) -> Decimal | None:
        """The unit cost the ORIGINAL movement for this document line went at.

        The newest matching movement wins: a corrected bill re-receives its line,
        and the live stock is the one the latest receipt brought in. ``before_id``
        keeps a replay from reaching forward into movements that had not happened
        yet at the point being costed.
        """
        sql = ("SELECT unit_cost FROM inventory_movements"
               " WHERE reference_type = ? AND reference_line_id = ? AND item_id = ?"
               "   AND unit_cost IS NOT NULL")
        params: list = [reference_type, reference_line_id, item_id]
        if before_id is not None:
            sql += " AND id < ?"
            params.append(before_id)
        row = self._conn.execute(sql + " ORDER BY id DESC LIMIT 1", params).fetchone()
        return D(row[0]) if row else None

    # ---- the decision -----------------------------------------------------

    def unit_cost_for(self, *, item_id: int, warehouse_id: int, movement_type: str,
                      quantity: Decimal, reference_type: str | None,
                      reference_id: int | None, reference_line_id: int | None,
                      before_id: int | None = None) -> Decimal:
        """The unit cost to record against a movement about to be written."""
        inbound = quantity > 0

        # --- inbound at a price we actually paid ---------------------------
        if reference_type == "PURCHASE" and reference_line_id is not None:
            row = self._conn.execute(
                "SELECT line_total, quantity FROM purchase_lines WHERE id = ?",
                (reference_line_id,)).fetchone()
            if row is not None:
                return line_unit_cost(row[0], row[1])

        if reference_type == "OPENING":
            return self._item_purchase_price(item_id)

        # --- a reversal goes back at the cost it came at -------------------
        # A correction or a void undoes a document line that really moved stock.
        # Re-costing it at today's average would leave value behind.
        if reference_type in ("PURCHASE_CORRECTION", "PURCHASE_VOID") \
                and reference_line_id is not None:
            original = self._cost_of_source_movement(
                reference_type="PURCHASE", reference_line_id=reference_line_id,
                item_id=item_id, before_id=before_id)
            if original is not None:
                return original
        if reference_type in ("SALE_CORRECTION", "SALE_VOID") \
                and reference_line_id is not None:
            original = self._cost_of_source_movement(
                reference_type="SALE", reference_line_id=reference_line_id,
                item_id=item_id, before_id=before_id)
            if original is not None:
                return original

        # --- returns follow the document they undo -------------------------
        if reference_type == "PURCHASE_RETURN" and reference_id is not None:
            cost = self._purchase_return_cost(reference_id, item_id, before_id)
            if cost is not None:
                return cost
        if reference_type == "SALES_RETURN" and reference_id is not None:
            cost = self._sale_return_cost(reference_id, item_id, before_id)
            if cost is not None:
                return cost

        # --- a transfer in is worth exactly what left the other warehouse --
        if movement_type == "TRANSFER_IN" and reference_id is not None:
            paired = self._movement_unit_cost(reference_id)
            if paired is not None:
                return paired

        # --- everything else is valued at what we hold ---------------------
        average = self.current_average(item_id, warehouse_id, before_id)
        if average != 0:
            return average
        # Nothing on hand to average: an inbound adjustment has to start
        # somewhere, and the item's own purchase price is the best figure the
        # system has. An outbound from empty stock costs nothing by definition.
        return self._item_purchase_price(item_id) if inbound else D(0)

    def _purchase_return_cost(self, return_id: int, item_id: int,
                              before_id: int | None = None) -> Decimal | None:
        """Goods go back to the supplier at what was paid for them."""
        row = self._conn.execute(
            "SELECT purchase_line_id FROM purchase_return_lines"
            " WHERE return_id = ? AND item_id = ? ORDER BY id LIMIT 1",
            (return_id, item_id)).fetchone()
        if row is None or row[0] is None:
            return None
        return self._cost_of_source_movement(
            reference_type="PURCHASE", reference_line_id=row[0], item_id=item_id,
            before_id=before_id)

    def _sale_return_cost(self, return_id: int, item_id: int,
                          before_id: int | None = None) -> Decimal | None:
        """Goods come back at the cost the sale took them out at."""
        row = self._conn.execute(
            "SELECT sale_line_id FROM sales_return_lines"
            " WHERE return_id = ? AND item_id = ? ORDER BY id LIMIT 1",
            (return_id, item_id)).fetchone()
        if row is None or row[0] is None:
            return None
        return self._cost_of_source_movement(
            reference_type="SALE", reference_line_id=row[0], item_id=item_id,
            before_id=before_id)

    def cost_movement(self, *, item_id: int, warehouse_id: int, movement_type: str,
                      quantity, reference_type: str | None, reference_id: int | None,
                      reference_line_id: int | None,
                      before_id: int | None = None) -> tuple[str, str]:
        """``(unit_cost, total_cost)`` for a movement, ready to store.

        ``total_cost`` carries the SAME sign as the quantity, so summing the
        column over any slice of the ledger gives the value held there, and
        summing it over sales gives COGS with the sign flipped.

        ``total_cost`` is stored at **money** precision, deliberately. Keeping
        sub-cent fractions would make a report's rows stop adding up to its own
        total, because rounding a sum is not the same as summing rounded parts —
        and warehouse rows that do not add up to the company total is exactly the
        kind of unexplained difference nobody can defend. Whole cents everywhere
        mean every subtotal, at every grouping level, adds up exactly.

        ``unit_cost`` keeps the finer costing precision: it is a reference figure
        for audit, and repeated averaging at two places would visibly drift.
        """
        qty = D(quantity)
        unit = self.unit_cost_for(
            item_id=item_id, warehouse_id=warehouse_id, movement_type=movement_type,
            quantity=qty, reference_type=reference_type, reference_id=reference_id,
            reference_line_id=reference_line_id,
            before_id=before_id).quantize(COST_PRECISION)

        # A transfer must leave the company worth exactly what it was worth. So
        # the arriving side takes the EXACT value that left, rather than
        # re-multiplying a rounded unit cost and landing a cent away from it.
        if movement_type == "TRANSFER_IN" and reference_id is not None:
            paired = self._movement_total_cost(reference_id)
            if paired is not None:
                return str(unit), money_to_db(-paired)
        return str(unit), money_to_db(money(qty * unit))
