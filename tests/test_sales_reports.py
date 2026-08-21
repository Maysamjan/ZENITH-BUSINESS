"""Stage 05 final — Sales Reporting engine + correction audit enrichment.

These tests pin the *reporting truth* over authoritative POSTED documents:

* partial payments split into paid vs credit (not classified whole),
* later receipts (debt collection) are NOT sales revenue,
* a corrected invoice counts exactly once (the VOID original is excluded),
* Gross / Returns stay distinguishable and Net = Gross − Returns,
* registered and walk-in sales both appear (walk-in shown by its snapshot name),
* period presets and daily / monthly breakdowns roll up correctly.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from zenith_business.services.purchase_documents import PurchaseLine
from zenith_business.services.sales_documents import ReturnLine, SaleLine
from zenith_business.services.sales_reports import preset_range


@pytest.fixture
def biz(admin_context):
    ctx = admin_context
    ctx.financial_years.create(name="FY26", start_date="2026-01-01",
                               end_date="2026-12-31", make_active=True)
    ctx.wh = ctx.warehouses.create(code="MAIN", name="Main", is_default=True)
    ctx.wh2 = ctx.warehouses.create(code="SHOW", name="Showroom")
    ctx.bag = ctx.units_repo.id_by_code("BAG")
    ctx.rice = ctx.items.create(item_code="RICE", name="Rice", base_unit_id=ctx.bag,
                                purchase_price="50", default_sale_price="100")
    ctx.sugar = ctx.items.create(item_code="SUGAR", name="Sugar", base_unit_id=ctx.bag,
                                 purchase_price="40", default_sale_price="80")
    ctx.cust = ctx.parties.create(party_code="C1", name="Ahmad Store", is_customer=True)
    ctx.sup = ctx.parties.create(party_code="S1", name="Supplier", is_supplier=True)
    ctx.cash = next(f for f in ctx.funds_repo.list_funds() if f["code"] == "1000")["id"]
    # stock both warehouses
    ctx.purchase_documents.post_purchase(
        currency_code="AFN", warehouse_id=ctx.wh, party_id=ctx.sup, amount_paid="0",
        purchase_date="2026-06-01",
        lines=[PurchaseLine(item_id=ctx.rice, unit_id=ctx.bag, quantity="500", unit_price="50"),
               PurchaseLine(item_id=ctx.sugar, unit_id=ctx.bag, quantity="500", unit_price="40")])
    return ctx


def _seed_period(biz):
    """A realistic June mix; returns the ids used by assertions."""
    D = "2026-06-10"
    ids = {}
    ids["cash"] = biz.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=biz.wh, party_id=biz.cust, amount_paid="1000",
        sale_date=D,
        lines=[SaleLine(item_id=biz.rice, unit_id=biz.bag, quantity="10", unit_price="100")])
    ids["credit"] = biz.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=biz.wh, party_id=biz.cust, amount_paid="0",
        sale_date=D,
        lines=[SaleLine(item_id=biz.rice, unit_id=biz.bag, quantity="5", unit_price="100")])
    ids["partial"] = biz.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=biz.wh, party_id=biz.cust, amount_paid="300",
        sale_date=D,
        lines=[SaleLine(item_id=biz.sugar, unit_id=biz.bag, quantity="10", unit_price="80")])
    ids["walk"] = biz.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=biz.wh, party_id=None, amount_paid="400",
        sale_date=D, walkin_name="Walk-in Guest", walkin_phone="0700000000",
        lines=[SaleLine(item_id=biz.rice, unit_id=biz.bag, quantity="4", unit_price="100")])
    ids["orig"] = biz.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=biz.wh, party_id=biz.cust, amount_paid="800",
        sale_date=D,
        lines=[SaleLine(item_id=biz.rice, unit_id=biz.bag, quantity="8", unit_price="100")])
    ids["corr"] = biz.sales_documents.correct_sale(
        sale_id=ids["orig"].id, currency_code="AFN", warehouse_id=biz.wh, party_id=biz.cust,
        amount_paid="300", sale_date=D,
        lines=[SaleLine(item_id=biz.rice, unit_id=biz.bag, quantity="3", unit_price="100")],
        reason="Customer took fewer bags")
    # later receipt (debt collection) — must NOT be counted as sales
    biz.receipts.post_receipt(party_id=biz.cust, account_id=biz.cash, amount="200",
                              currency_code="AFN", payment_method="CASH",
                              receipt_date="2026-06-11")
    # partial return against the cash sale (3 of 10 rice = 300), dated later
    sl = biz.sales_repo.lines_for(ids["cash"].id)[0]["id"]
    biz.sales_documents.post_return(sale_id=ids["cash"].id, return_date="2026-06-12",
                                    lines=[ReturnLine(sale_line_id=sl, quantity="3")])
    return ids


# ---- summary reconciliation ---------------------------------------------

def test_summary_reconciles_gross_paid_credit_returns_net(biz):
    _seed_period(biz)
    s = biz.sales_reports.summary(date_from="2026-06-01", date_to="2026-06-30")
    # Gross = 1000+500+800+400+300(corrected replacement) = 3000 (VOID 800 excluded)
    assert s["gross"] == "3000.00"
    assert s["paid"] == "2000.00"      # 1000+0+300+400+300
    assert s["credit"] == "1000.00"    # 0+500+500+0+0
    assert s["returns"] == "300.00"    # one partial return, dated in period
    assert s["net"] == "2700.00"       # gross − returns
    assert s["invoices"] == 5          # POSTED only; VOID original not counted


def test_gross_equals_paid_plus_credit(biz):
    _seed_period(biz)
    s = biz.sales_reports.summary(date_from="2026-06-01", date_to="2026-06-30")
    assert Decimal(s["gross"]) == Decimal(s["paid"]) + Decimal(s["credit"])


def test_corrected_invoice_counted_once(biz):
    """The VOID original must never inflate Gross; only the replacement counts."""
    ids = _seed_period(biz)
    s = biz.sales_reports.summary(date_from="2026-06-01", date_to="2026-06-30")
    # If the void were double-counted, Gross would be 3000+800 = 3800.
    assert s["gross"] == "3000.00"
    txns = biz.sales_reports.transactions(
        date_from="2026-06-01", date_to="2026-06-30", walkin_label="Walk-in")
    docs = [t["document_no"] for t in txns]
    assert ids["orig"].document_no not in docs      # VOID excluded
    assert ids["corr"].document_no in docs          # replacement present


def test_later_receipt_is_not_sales(biz):
    """Collecting debt after the sale must not raise Gross or Paid."""
    _seed_period(biz)
    s = biz.sales_reports.summary(date_from="2026-06-01", date_to="2026-06-30")
    # 200 receipt on 2026-06-11 is inside the range but must be invisible here.
    assert s["gross"] == "3000.00"
    assert s["paid"] == "2000.00"


def test_partial_payment_split_not_whole(biz):
    _seed_period(biz)
    txns = biz.sales_reports.transactions(
        date_from="2026-06-01", date_to="2026-06-30", walkin_label="Walk-in",
        payment_status="partial")
    assert len(txns) == 1
    row = txns[0]
    assert row["paid"] == "300.00" and row["credit"] == "500.00"


def test_paid_and_credit_filters(biz):
    _seed_period(biz)
    paid = biz.sales_reports.transactions(
        date_from="2026-06-01", date_to="2026-06-30", walkin_label="W",
        payment_status="paid")
    credit = biz.sales_reports.transactions(
        date_from="2026-06-01", date_to="2026-06-30", walkin_label="W",
        payment_status="credit")
    # fully paid: cash, walk, corrected replacement = 3
    assert len(paid) == 3
    # pure credit (nothing paid): the credit-only sale = 1
    assert len(credit) == 1


# ---- returns kept distinguishable ---------------------------------------

def test_returns_distinct_from_gross_and_net(biz):
    ids = _seed_period(biz)
    txns = biz.sales_reports.transactions(
        date_from="2026-06-01", date_to="2026-06-30", walkin_label="W")
    row = next(t for t in txns if t["document_no"] == ids["cash"].document_no)
    assert row["gross"] == "1000.00"
    assert row["returned"] == "300.00"
    assert row["net"] == "700.00"


# ---- walk-in visibility --------------------------------------------------

def test_walkin_and_registered_both_appear_walkin_named(biz):
    _seed_period(biz)
    txns = biz.sales_reports.transactions(
        date_from="2026-06-01", date_to="2026-06-30", walkin_label="Walk-in Customer")
    walk = [t for t in txns if t["walkin"]]
    reg = [t for t in txns if not t["walkin"]]
    assert len(walk) == 1 and walk[0]["party"] == "Walk-in Guest"
    assert len(reg) == 4


def test_kind_filter_registered_vs_walkin(biz):
    _seed_period(biz)
    reg = biz.sales_reports.transactions(
        date_from="2026-06-01", date_to="2026-06-30", walkin_label="W", kind="registered")
    walk = biz.sales_reports.transactions(
        date_from="2026-06-01", date_to="2026-06-30", walkin_label="W", kind="walkin")
    assert all(not t["walkin"] for t in reg) and len(reg) == 4
    assert all(t["walkin"] for t in walk) and len(walk) == 1


# ---- warehouse / customer filters ---------------------------------------

def test_warehouse_filter(biz):
    _seed_period(biz)
    # everything was posted in wh; wh2 has no sales
    s2 = biz.sales_reports.summary(date_from="2026-06-01", date_to="2026-06-30",
                                   warehouse_id=biz.wh2)
    assert s2["gross"] == "0.00" and s2["invoices"] == 0
    s1 = biz.sales_reports.summary(date_from="2026-06-01", date_to="2026-06-30",
                                   warehouse_id=biz.wh)
    assert s1["gross"] == "3000.00"


def test_customer_filter_excludes_walkin(biz):
    _seed_period(biz)
    s = biz.sales_reports.summary(date_from="2026-06-01", date_to="2026-06-30",
                                  party_id=biz.cust)
    # registered customer only: cash 1000 + credit 500 + partial 800 + corrected 300 = 2600
    assert s["gross"] == "2600.00"


# ---- date boundaries -----------------------------------------------------

def test_date_boundaries_inclusive(biz):
    _seed_period(biz)
    # sales are all on 2026-06-10; a window ending 2026-06-09 sees none
    before = biz.sales_reports.summary(date_from="2026-06-01", date_to="2026-06-09")
    assert before["gross"] == "0.00"
    # a single-day window on the sale date sees the sales but not the 06-12 return
    day = biz.sales_reports.summary(date_from="2026-06-10", date_to="2026-06-10")
    assert day["gross"] == "3000.00" and day["returns"] == "0.00"
    # the return day alone: no gross, 300 returns, net negative
    rday = biz.sales_reports.summary(date_from="2026-06-12", date_to="2026-06-12")
    assert rday["gross"] == "0.00" and rday["returns"] == "300.00"
    assert rday["net"] == "-300.00"


# ---- breakdowns ----------------------------------------------------------

def test_daily_breakdown(biz):
    _seed_period(biz)
    days = biz.sales_reports.daily_breakdown(date_from="2026-06-01", date_to="2026-06-30")
    by = {d["period"]: d for d in days}
    assert by["2026-06-10"]["gross"] == "3000.00"
    assert by["2026-06-10"]["returns"] == "0.00"
    assert by["2026-06-12"]["returns"] == "300.00"
    assert by["2026-06-12"]["net"] == "-300.00"


def test_monthly_breakdown(biz):
    _seed_period(biz)
    months = biz.sales_reports.monthly_breakdown(year=2026)
    assert len(months) == 12
    june = next(m for m in months if m["month"] == 6)
    assert june["gross"] == "3000.00" and june["returns"] == "300.00"
    assert june["net"] == "2700.00"
    # every other month is empty
    assert all(m["gross"] == "0.00" for m in months if m["month"] != 6)


def test_yearly_total_matches_month_sum(biz):
    _seed_period(biz)
    year = biz.sales_reports.summary(date_from="2026-01-01", date_to="2026-12-31")
    months = biz.sales_reports.monthly_breakdown(year=2026)
    assert Decimal(year["gross"]) == sum(Decimal(m["gross"]) for m in months)
    assert Decimal(year["net"]) == sum(Decimal(m["net"]) for m in months)


# ---- presets -------------------------------------------------------------

def test_preset_ranges():
    assert preset_range("today", "2026-06-15") == ("2026-06-15", "2026-06-15")
    # 2026-06-15 is a Monday → week starts same day
    assert preset_range("week", "2026-06-15") == ("2026-06-15", "2026-06-15")
    # 2026-06-17 is a Wednesday → week starts Monday 2026-06-15
    assert preset_range("week", "2026-06-17") == ("2026-06-15", "2026-06-17")
    assert preset_range("month", "2026-06-17") == ("2026-06-01", "2026-06-17")
    assert preset_range("year", "2026-06-17") == ("2026-01-01", "2026-06-17")


# ---- authorization -------------------------------------------------------

def test_reporting_requires_permission(biz):
    from zenith_business.services.exceptions import (
        AuthenticationError, AuthorizationError)
    biz.session.clear()
    # No signed-in user → the sales.view guard denies access.
    with pytest.raises((AuthenticationError, AuthorizationError)):
        biz.sales_reports.summary(date_from="2026-06-01", date_to="2026-06-30")


# ---- correction audit enrichment (P3) -----------------------------------

def test_correction_audit_records_human_readable_changes(biz):
    s = biz.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=biz.wh, party_id=biz.cust, amount_paid="0",
        sale_date="2026-06-10",
        lines=[SaleLine(item_id=biz.rice, unit_id=biz.bag, quantity="5", unit_price="100"),
               SaleLine(item_id=biz.sugar, unit_id=biz.bag, quantity="2", unit_price="80")])
    biz.sales_documents.correct_sale(
        sale_id=s.id, currency_code="AFN", warehouse_id=biz.wh, party_id=biz.cust,
        amount_paid="0", sale_date="2026-06-10",
        lines=[SaleLine(item_id=biz.rice, unit_id=biz.bag, quantity="3", unit_price="100")],
        reason="fix order")
    rows = biz.db.connection().execute(
        "SELECT action, details FROM audit_log WHERE action = 'sales.correct'"
        " ORDER BY id DESC").fetchall()
    assert rows, "correction audit row missing"
    details = rows[0][1]
    # human-readable line diff: Rice reduced, Sugar removed, old→new totals, reason
    assert "Rice" in details and "Sugar" in details
    assert "5" in details and "3" in details       # rice qty change
    assert "removed" in details.lower()            # sugar removed
    assert "reason=fix order" in details
    assert "old_total" in details and "new_total" in details
