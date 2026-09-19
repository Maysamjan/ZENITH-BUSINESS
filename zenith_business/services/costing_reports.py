"""Stage 08 — inventory valuation, COGS and gross profit.

Three reads over one costed ledger:

* **Inventory Valuation** — quantity, average cost and value, per item, per
  warehouse, and the company total.
* **Cost of Goods Sold**  — what the goods that left on sales actually cost,
  net of sales returns.
* **Gross Profit**        — ``net sales − COGS``.

Net sales is **not** recomputed here. It comes from the locked Sales Reporting
engine, which already defines it as gross minus posted returns; defining it a
second time is exactly how two screens end up disagreeing. This module owns the
cost half of the answer and borrows the revenue half from the module that owns it.

Stage 08 deliberately stops here. Gross profit is a stock-and-sales figure that
the movement ledger can answer on its own; a real Profit & Loss needs operating
expenses, and a balance sheet needs the whole chart of accounts. Those belong to
an accounting-reports stage, not to costing.
"""

from __future__ import annotations

from zenith_business.core.money import D, money_to_db


class CostingReportService:
    """Read-only valuation / COGS / gross-profit builders."""

    #: Report keys, in the order the screen offers them.
    KINDS = ("valuation", "cogs", "gross_profit")

    def __init__(self, repo, sales_reports, authz) -> None:
        self._repo = repo
        self._sales_reports = sales_reports
        self._authz = authz

    # ---- valuation --------------------------------------------------------

    def valuation(self, *, warehouse_id: int | None = None,
                  as_of: str | None = None) -> dict:
        """Stock value by item, by warehouse, and the company total.

        The three views are summed from the same rows, so the item rows always
        add up to the company total — there is no separate "total" figure that
        could drift away from the detail beneath it.
        """
        self._authz.require("inventory.view")
        return {
            "as_of": as_of,
            "warehouse_id": warehouse_id,
            "items": self._repo.valuation_by_item(warehouse_id=warehouse_id, as_of=as_of),
            "warehouses": self._repo.valuation_by_warehouse(as_of=as_of),
            "by_item_and_warehouse": self._repo.valuation_by_item_and_warehouse(as_of=as_of),
            "total": self._repo.company_total(as_of=as_of)
                     if warehouse_id is None else
                     self._company_total_for(warehouse_id, as_of),
        }

    def _company_total_for(self, warehouse_id: int, as_of: str | None) -> dict:
        rows = self._repo.valuation_by_item(warehouse_id=warehouse_id, as_of=as_of)
        qty = sum((D(r["quantity"]) for r in rows), D(0))
        value = sum((D(r["value"]) for r in rows), D(0))
        from zenith_business.core.money import qty_to_db
        from zenith_business.services.costing import average_cost
        return {"quantity": qty_to_db(qty), "value": money_to_db(value),
                "average_cost": str(average_cost(value, qty))}

    def item_value(self, item_id: int, *, warehouse_id: int | None = None) -> dict:
        """One item's position — what the Inventory screen shows per row."""
        self._authz.require("inventory.view")
        rows = [r for r in self._repo.valuation_by_item(warehouse_id=warehouse_id)
                if r["item_id"] == item_id]
        if not rows:
            return {"item_id": item_id, "quantity": "0.000",
                    "value": "0.00", "average_cost": "0.000000"}
        return rows[0]

    # ---- cost of goods sold ----------------------------------------------

    def cogs(self, *, date_from: str, date_to: str,
             warehouse_id: int | None = None) -> dict:
        self._authz.require("sales.view")
        items = self._repo.cogs_by_item(date_from=date_from, date_to=date_to,
                                        warehouse_id=warehouse_id)
        return {
            "date_from": date_from, "date_to": date_to,
            "warehouse_id": warehouse_id,
            "items": items,
            "total": self._repo.cogs_total(date_from=date_from, date_to=date_to,
                                           warehouse_id=warehouse_id),
        }

    def cogs_for_sale(self, sale_id: int) -> str:
        self._authz.require("sales.view")
        return self._repo.cogs_for_sale(sale_id)

    # ---- gross profit -----------------------------------------------------

    def gross_profit(self, *, date_from: str, date_to: str,
                     warehouse_id: int | None = None) -> dict:
        """Net sales − COGS, with both halves shown so the subtraction is checkable.

        Margin is reported against net sales; with no sales in the period there is
        nothing to take a percentage of, so it is left empty rather than shown
        as zero, which would read as "we made no margin" instead of "no sales".
        """
        self._authz.require("sales.view")
        sales = self._sales_reports.summary(date_from=date_from, date_to=date_to,
                                            warehouse_id=warehouse_id)
        net_sales = D(sales["net"])
        cogs = D(self._repo.cogs_total(date_from=date_from, date_to=date_to,
                                       warehouse_id=warehouse_id))
        profit = net_sales - cogs
        margin = ""
        if net_sales != 0:
            margin = str((profit / net_sales * D(100)).quantize(D("0.01")))
        return {
            "date_from": date_from, "date_to": date_to,
            "warehouse_id": warehouse_id,
            "gross_sales": sales["gross"],
            "returns": sales["returns"],
            "net_sales": money_to_db(net_sales),
            "cogs": money_to_db(cogs),
            "gross_profit": money_to_db(profit),
            "margin_percent": margin,
            "invoices": sales["invoices"],
        }
