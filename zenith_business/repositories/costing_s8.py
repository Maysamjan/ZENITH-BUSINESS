"""Stage 08 valuation reads — quantity and value from the one costed ledger.

Every figure here is the ``Decimal`` sum of ``inventory_movements`` (§24): the
signed quantity column for how much, the signed ``total_cost`` column for how
much it is worth. Nothing is stored and nothing is cached, so a valuation report,
the Inventory screen and the stock a sale is checked against cannot disagree —
they are three readings of the same rows.

Average cost is always ``value / quantity`` at the level being asked about, never
a stored per-item field: the average of an item across two warehouses is the
company average, not the average of two averages.
"""

from __future__ import annotations

from decimal import Decimal

from zenith_business.core.money import D, money, money_to_db, qty_to_db
from zenith_business.repositories.base import BaseRepository
from zenith_business.services.costing import average_cost

#: Everything on the SALES side of the ledger, by the document that caused it.
#:
#: Selected by reference_type, not movement_type, and that distinction matters: a
#: sale correction and a void take their stock back with an ADJUSTMENT movement,
#: and those movements undo a charge that a SALE already made to COGS. Filtering
#: on movement_type alone counts the original sale AND its replacement, so a
#: corrected invoice reports its goods as sold twice.
_COGS_REFERENCES = ("SALE", "SALES_RETURN", "SALE_CORRECTION", "SALE_VOID")


class CostingReadRepository(BaseRepository):
    """Valuation, COGS and gross-profit reads over the costed movement ledger."""

    # ---- valuation --------------------------------------------------------

    def valuation_by_item(self, *, warehouse_id: int | None = None,
                          as_of: str | None = None) -> list[dict]:
        """Per item: quantity held, average cost and value. Zero rows are dropped.

        An item that has moved but nets to nothing carries no value and would
        only pad the report, so it is left out — unless it still holds a value
        without quantity, which is a genuine problem the owner should see.
        """
        where, params = self._slice(warehouse_id, as_of)
        rows = self._all(
            "SELECT m.item_id, i.item_code, i.name AS item_name, i.alternate_name,"
            " u.code AS unit_code, m.quantity, m.total_cost"
            " FROM inventory_movements m"
            " JOIN items i ON i.id = m.item_id"
            " LEFT JOIN units u ON u.id = i.base_unit_id"
            f" WHERE {where}", params)
        return self._fold(rows, ("item_id", "item_code", "item_name",
                                 "alternate_name", "unit_code"))

    def valuation_by_warehouse(self, *, as_of: str | None = None) -> list[dict]:
        """Per warehouse: quantity, value and the average across its items."""
        where, params = self._slice(None, as_of)
        rows = self._all(
            "SELECT m.warehouse_id, w.code AS warehouse_code, w.name AS warehouse_name,"
            " m.quantity, m.total_cost"
            " FROM inventory_movements m"
            " JOIN warehouses w ON w.id = m.warehouse_id"
            f" WHERE {where}", params)
        return self._fold(rows, ("warehouse_id", "warehouse_code", "warehouse_name"))

    def valuation_by_item_and_warehouse(self, *, as_of: str | None = None) -> list[dict]:
        """Per item per warehouse — the level the average is actually kept at."""
        where, params = self._slice(None, as_of)
        rows = self._all(
            "SELECT m.item_id, m.warehouse_id, i.item_code, i.name AS item_name,"
            " i.alternate_name, w.name AS warehouse_name, m.quantity, m.total_cost"
            " FROM inventory_movements m"
            " JOIN items i ON i.id = m.item_id"
            " JOIN warehouses w ON w.id = m.warehouse_id"
            f" WHERE {where}", params)
        return self._fold(rows, ("item_id", "warehouse_id", "item_code", "item_name",
                                 "alternate_name", "warehouse_name"))

    def company_total(self, *, as_of: str | None = None) -> dict:
        """What the company's stock is worth, in one row."""
        where, params = self._slice(None, as_of)
        rows = self._all(
            f"SELECT quantity, total_cost FROM inventory_movements WHERE {where}", params)
        qty = sum((D(r["quantity"]) for r in rows), D(0))
        value = sum((D(r["total_cost"]) for r in rows if r["total_cost"] is not None), D(0))
        return {"quantity": qty_to_db(qty), "value": money_to_db(value),
                "average_cost": str(average_cost(value, qty))}

    # ---- cost of goods sold ----------------------------------------------

    def cogs_by_item(self, *, date_from: str | None = None, date_to: str | None = None,
                     warehouse_id: int | None = None) -> list[dict]:
        """Per item: quantity sold and what those goods cost, net of returns."""
        where, params = self._cogs_slice(date_from, date_to, warehouse_id)
        rows = self._all(
            "SELECT m.item_id, i.item_code, i.name AS item_name, i.alternate_name,"
            " m.quantity, m.total_cost FROM inventory_movements m"
            " JOIN items i ON i.id = m.item_id"
            f" WHERE {where}", params)
        folded: dict = {}
        for r in rows:
            key = r["item_id"]
            entry = folded.setdefault(key, {
                "item_id": r["item_id"], "item_code": r["item_code"],
                "item_name": r["item_name"], "alternate_name": r["alternate_name"],
                "_qty": D(0), "_cost": D(0)})
            # Sales are negative movements; report them as positive quantities
            # sold and positive cost, so a return subtracts from both.
            entry["_qty"] -= D(r["quantity"])
            entry["_cost"] -= D(r["total_cost"] or 0)
        out = []
        for entry in folded.values():
            qty, cost = entry.pop("_qty"), entry.pop("_cost")
            if qty == 0 and cost == 0:
                continue
            entry["quantity_sold"] = qty_to_db(qty)
            entry["cogs"] = money_to_db(cost)
            entry["average_cost"] = str(average_cost(cost, qty))
            out.append(entry)
        return sorted(out, key=lambda r: r["item_code"] or "")

    def cogs_total(self, *, date_from: str | None = None, date_to: str | None = None,
                   warehouse_id: int | None = None) -> str:
        """Total cost of goods sold for the period, net of sales returns."""
        where, params = self._cogs_slice(date_from, date_to, warehouse_id)
        rows = self._all(
            f"SELECT m.total_cost FROM inventory_movements m WHERE {where}", params)
        return money_to_db(-sum((D(r["total_cost"]) for r in rows
                                if r["total_cost"] is not None), D(0)))

    def cogs_for_sale(self, sale_id: int) -> str:
        """The cost of the goods that left on ONE invoice, net of its returns."""
        rows = self._all(
            "SELECT total_cost FROM inventory_movements"
            " WHERE (reference_type = 'SALE' AND reference_id = ?)"
            "    OR (reference_type IN ('SALE_VOID','SALE_CORRECTION') AND reference_id = ?)"
            "    OR (reference_type = 'SALES_RETURN' AND reference_id IN"
            "        (SELECT id FROM sales_returns WHERE sale_id = ? AND status = 'POSTED'))",
            (sale_id, sale_id, sale_id))
        return money_to_db(-sum((D(r["total_cost"]) for r in rows
                                 if r["total_cost"] is not None), D(0)))

    # ---- shared slicing ---------------------------------------------------

    @staticmethod
    def _slice(warehouse_id: int | None, as_of: str | None) -> tuple[str, list]:
        where = ["1=1"]
        params: list = []
        if warehouse_id is not None:
            where.append("m.warehouse_id = ?"); params.append(warehouse_id)
        if as_of:
            where.append("m.movement_date <= ?"); params.append(as_of)
        return " AND ".join(where), params

    @staticmethod
    def _cogs_slice(date_from: str | None, date_to: str | None,
                    warehouse_id: int | None) -> tuple[str, list]:
        marks = ",".join("?" * len(_COGS_REFERENCES))
        where = [f"m.reference_type IN ({marks})"]
        params: list = list(_COGS_REFERENCES)
        if date_from:
            where.append("m.movement_date >= ?"); params.append(date_from)
        if date_to:
            where.append("m.movement_date <= ?"); params.append(date_to)
        if warehouse_id is not None:
            where.append("m.warehouse_id = ?"); params.append(warehouse_id)
        return " AND ".join(where), params

    @staticmethod
    def _fold(rows: list[dict], keys: tuple[str, ...]) -> list[dict]:
        """Sum quantity and value per group, then derive the average from both."""
        folded: dict = {}
        for r in rows:
            key = tuple(r[k] for k in keys)
            entry = folded.setdefault(key, {k: r[k] for k in keys})
            entry["_qty"] = entry.get("_qty", D(0)) + D(r["quantity"])
            entry["_value"] = entry.get("_value", D(0)) + D(r["total_cost"] or 0)
        out = []
        for entry in folded.values():
            qty: Decimal = entry.pop("_qty")
            value: Decimal = entry.pop("_value")
            if qty == 0 and money(value) == 0:
                continue
            entry["quantity"] = qty_to_db(qty)
            entry["value"] = money_to_db(value)
            entry["average_cost"] = str(average_cost(value, qty))
            out.append(entry)
        return sorted(out, key=lambda r: str(r.get("item_code") or
                                             r.get("warehouse_code") or ""))
