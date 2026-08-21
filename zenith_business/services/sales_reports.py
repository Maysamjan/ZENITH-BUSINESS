"""Sales Reporting service.

Definitions (authoritative, from persisted POSTED documents only):

* **Gross Sales**  = Σ grand_total of POSTED sales in the period. A VOID original
  left by a correction is excluded, so corrected invoices count exactly once.
* **Paid / Cash**  = Σ amount_paid recorded AT the time of sale.
* **Credit**       = Σ remaining_amount created by those sales ( = Gross − Paid ).
* **Returns**      = Σ grand_total of POSTED sales-returns dated in the period.
* **Net Sales**    = Gross − Returns.

A later receipt (debt collection) is NOT a sale and never appears here — this
service only reads the ``sales`` / ``sales_returns`` tables, never receipts.
Money is summed with ``Decimal`` for exactness.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from zenith_business.core.money import D, format_money, money_to_db
from zenith_business.repositories.reports import SalesReportRepository


def _iso(d: date) -> str:
    return d.isoformat()


def preset_range(preset: str, today: str) -> tuple[str, str]:
    """Resolve a period preset to inclusive [from, to] ISO dates.

    ``preset`` in {today, week, month, year}. ``today`` is an ISO date string so
    the caller controls "now" (and tests are deterministic).
    """
    t = date.fromisoformat(today)
    if preset == "today":
        return _iso(t), _iso(t)
    if preset == "week":                       # Mon..today of the current week
        start = t - timedelta(days=t.weekday())
        return _iso(start), _iso(t)
    if preset == "month":
        return _iso(t.replace(day=1)), _iso(t)
    if preset == "year":
        return _iso(t.replace(month=1, day=1)), _iso(t)
    return _iso(t), _iso(t)


class SalesReportService:
    def __init__(self, repo: SalesReportRepository, session, authz) -> None:
        self._repo = repo
        self._session = session
        self._authz = authz

    # ---- core roll-up ----------------------------------------------------

    def summary(self, *, date_from: str, date_to: str, warehouse_id: int | None = None,
                party_id: int | None = None) -> dict:
        self._authz.require("sales.view")
        sales = self._repo.posted_sales(date_from, date_to, warehouse_id=warehouse_id,
                                        party_id=party_id)
        gross = sum((D(s["grand_total"]) for s in sales), D(0))
        paid = sum((D(s["amount_paid"]) for s in sales), D(0))
        credit = sum((D(s["remaining_amount"]) for s in sales), D(0))
        returns = sum((D(r["grand_total"]) for r in self._repo.posted_returns(
            date_from, date_to, warehouse_id=warehouse_id, party_id=party_id)), D(0))
        net = gross - returns
        return {
            "date_from": date_from, "date_to": date_to,
            "invoices": len(sales),
            "gross": money_to_db(gross), "paid": money_to_db(paid),
            "credit": money_to_db(credit), "returns": money_to_db(returns),
            "net": money_to_db(net),
        }

    def transactions(self, *, date_from: str, date_to: str, walkin_label: str,
                     warehouse_id: int | None = None, party_id: int | None = None,
                     payment_status: str | None = None,
                     kind: str | None = None) -> list[dict]:
        """One row per POSTED sale in the period, with per-invoice returned/net.

        ``payment_status`` in {paid, credit, partial}; ``kind`` in
        {registered, walkin}. ``walkin_label`` is the localized fallback name.
        """
        self._authz.require("sales.view")
        sales = self._repo.posted_sales(date_from, date_to, warehouse_id=warehouse_id,
                                        party_id=party_id)
        ret_by_sale: dict[int, D] = {}
        for r in self._repo.all_posted_returns_for_sales([s["id"] for s in sales]):
            ret_by_sale[r["sale_id"]] = ret_by_sale.get(r["sale_id"], D(0)) + D(r["grand_total"])
        rows: list[dict] = []
        for s in sales:
            is_walkin = s["party_id"] is None
            if kind == "registered" and is_walkin:
                continue
            if kind == "walkin" and not is_walkin:
                continue
            paid = D(s["amount_paid"]); credit = D(s["remaining_amount"])
            if payment_status == "paid" and credit > 0:
                continue
            if payment_status == "credit" and paid > 0:
                continue
            if payment_status == "partial" and not (paid > 0 and credit > 0):
                continue
            returned = ret_by_sale.get(s["id"], D(0))
            rows.append({
                "id": s["id"], "document_no": s["document_no"], "date": s["sale_date"],
                "party": s["party_name"] or s["walkin_name"] or walkin_label,
                "walkin": is_walkin,
                "gross": s["grand_total"], "paid": s["amount_paid"],
                "credit": s["remaining_amount"],
                "returned": money_to_db(returned),
                "net": money_to_db(D(s["grand_total"]) - returned),
                "warehouse": s.get("warehouse_name") or "",
            })
        return rows

    # ---- breakdowns ------------------------------------------------------

    def daily_breakdown(self, *, date_from: str, date_to: str,
                        warehouse_id: int | None = None,
                        party_id: int | None = None) -> list[dict]:
        """Per-day gross/paid/credit/returns/net across the range (dates that had
        activity, ascending)."""
        self._authz.require("sales.view")
        sales = self._repo.posted_sales(date_from, date_to, warehouse_id=warehouse_id,
                                        party_id=party_id)
        rets = self._repo.posted_returns(date_from, date_to, warehouse_id=warehouse_id,
                                         party_id=party_id)
        days: dict[str, dict[str, D]] = {}

        def _bucket(key: str) -> dict[str, D]:
            return days.setdefault(key, {"gross": D(0), "paid": D(0),
                                         "credit": D(0), "returns": D(0)})
        for s in sales:
            b = _bucket(s["sale_date"])
            b["gross"] += D(s["grand_total"]); b["paid"] += D(s["amount_paid"])
            b["credit"] += D(s["remaining_amount"])
        for r in rets:
            _bucket(r["return_date"])["returns"] += D(r["grand_total"])
        out = []
        for key in sorted(days):
            b = days[key]
            out.append({
                "period": key,
                "gross": money_to_db(b["gross"]), "paid": money_to_db(b["paid"]),
                "credit": money_to_db(b["credit"]), "returns": money_to_db(b["returns"]),
                "net": money_to_db(b["gross"] - b["returns"]),
            })
        return out

    def monthly_breakdown(self, *, year: int, warehouse_id: int | None = None,
                          party_id: int | None = None) -> list[dict]:
        """12-month roll-up for a year (all months, ascending)."""
        self._authz.require("sales.view")
        out = []
        for month in range(1, 13):
            last = calendar.monthrange(year, month)[1]
            df = _iso(date(year, month, 1)); dt = _iso(date(year, month, last))
            s = self.summary(date_from=df, date_to=dt, warehouse_id=warehouse_id,
                             party_id=party_id)
            out.append({
                "period": f"{year}-{month:02d}", "month": month,
                "gross": s["gross"], "paid": s["paid"], "credit": s["credit"],
                "returns": s["returns"], "net": s["net"], "invoices": s["invoices"],
            })
        return out

    # ---- convenience -----------------------------------------------------

    @staticmethod
    def fmt(value) -> str:
        return format_money(value)
