"""Stage 06 — inventory & stock management.

Stock is a signed movement ledger and nothing else: every figure the app shows
is the sum of ``inventory_movements``. These tests pin that contract end to end —
the stock effects of every document type, the opening/current split, adjustments,
transfers, low stock, movement history, the sale-time validation, and the owner's
full mandatory workflow reconciled across every screen that reports a number.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from zenith_business.services.exceptions import (
    InsufficientStockError,
    ValidationError,
)
from zenith_business.services.purchase_documents import PurchaseLine, PurchaseReturnLine
from zenith_business.services.sales_documents import ReturnLine, SaleLine


@pytest.fixture
def biz(admin_context):
    ctx = admin_context
    ctx.financial_years.create(name="FY26", start_date="2026-01-01", end_date="2026-12-31",
                               make_active=True)
    ctx.main = ctx.warehouses.create(code="MAIN", name="Main Store", is_default=True)
    ctx.wh2 = ctx.warehouses.create(code="WH2", name="Warehouse 2")
    ctx.bag = ctx.units_repo.id_by_code("BAG")
    ctx.rice = ctx.items.create(item_code="RICE", name="Rice", base_unit_id=ctx.bag,
                                purchase_price="50", default_sale_price="100",
                                reorder_level="20")
    ctx.sugar = ctx.items.create(item_code="SUGAR", name="Sugar", base_unit_id=ctx.bag,
                                 purchase_price="40", default_sale_price="80",
                                 reorder_level="50")
    ctx.cust = ctx.parties.create(party_code="C1", name="Ahmad Store", is_customer=True)
    ctx.sup = ctx.parties.create(party_code="S1", name="Supplier", is_supplier=True)
    return ctx


def _opening(biz, item, qty, wh=None, note=None, date="2026-05-01"):
    """Opening stock, dated BEFORE the trading documents as a real business would."""
    return biz.inventory.record_opening(
        item_id=item, warehouse_id=wh or biz.main, quantity_on_hand=qty, notes=note,
        movement_date=date)


def _purchase(biz, qty, item=None, wh=None):
    return biz.purchase_documents.post_purchase(
        currency_code="AFN", warehouse_id=wh or biz.main, party_id=biz.sup, amount_paid="0",
        purchase_date="2026-06-01",
        lines=[PurchaseLine(item_id=item or biz.rice, unit_id=biz.bag,
                            quantity=qty, unit_price="50")])


def _sale(biz, qty, item=None, wh=None, date="2026-06-02"):
    return biz.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=wh or biz.main, party_id=biz.cust,
        amount_paid="0", sale_date=date,
        lines=[SaleLine(item_id=item or biz.rice, unit_id=biz.bag,
                        quantity=qty, unit_price="100")])


def _cur(biz, item=None, wh=None):
    return biz.inventory.on_hand(item or biz.rice, wh)


# ---- 3. stock effects of every document type -----------------------------

def test_every_document_type_moves_stock_correctly(biz):
    """The owner's stated ladder: 100 → 120 → 115 → 116 → 114."""
    _opening(biz, biz.rice, "100")
    assert _cur(biz) == "100.000"
    _purchase(biz, "20")
    assert _cur(biz) == "120.000"
    sale = _sale(biz, "5")
    assert _cur(biz) == "115.000"
    sl = biz.sales_repo.lines_for(sale.id)[0]["id"]
    biz.sales_documents.post_return(sale_id=sale.id, return_date="2026-06-03",
                                    lines=[ReturnLine(sale_line_id=sl, quantity="1")])
    assert _cur(biz) == "116.000"
    purchase = biz.purchase_documents.list()[0]
    pl = biz.purchases_repo.lines_for(purchase["id"])[0]["id"]
    biz.purchase_documents.post_return(
        purchase_id=purchase["id"], return_date="2026-06-04",
        lines=[PurchaseReturnLine(purchase_line_id=pl, quantity="2")])
    assert _cur(biz) == "114.000"


def test_a_corrected_sale_never_deducts_twice(biz):
    """Correcting 10 → 4 must land on one net deduction of 4, not 14."""
    _opening(biz, biz.rice, "100")
    sale = _sale(biz, "10")
    assert _cur(biz) == "90.000"
    biz.sales_documents.correct_sale(
        sale_id=sale.id, currency_code="AFN", warehouse_id=biz.main, party_id=biz.cust,
        amount_paid="0", sale_date="2026-06-02",
        lines=[SaleLine(item_id=biz.rice, unit_id=biz.bag, quantity="4", unit_price="100")])
    assert _cur(biz) == "96.000"          # 100 − 4, never 100 − 10 − 4
    # the ledger tells the whole story: out 10, back 10, out 4
    kinds = [(m["movement_type"], m["quantity"])
             for m in biz.inventory.movement_history(item_id=biz.rice)]
    assert ("SALE", "-10.000") in kinds
    assert ("ADJUSTMENT_IN", "10.000") in kinds
    assert ("SALE", "-4.000") in kinds


# ---- 2. opening vs current stay separate ---------------------------------

def test_opening_stock_never_moves_with_trading(biz):
    _opening(biz, biz.rice, "100")
    _purchase(biz, "20")
    _sale(biz, "5")
    assert biz.inventory.opening(biz.rice) == "100.000"    # unchanged
    assert _cur(biz) == "115.000"


def test_stock_overview_separates_opening_and_current(biz):
    _opening(biz, biz.rice, "100")
    _sale(biz, "5")
    row = next(r for r in biz.inventory.stock_overview() if r["item_id"] == biz.rice)
    assert row["opening"] == "100.000"
    assert row["current"] == "95.000"
    assert row["unit"] and row["warehouses"] == "Main Store"
    assert row["minimum"] == "20.000"


def test_opening_vs_current_report_shows_the_difference(biz):
    _opening(biz, biz.rice, "100")
    _purchase(biz, "20")
    _sale(biz, "5")
    row = next(r for r in biz.inventory_reports.opening_vs_current()
               if r["item_id"] == biz.rice)
    assert row["opening"] == "100.000"
    assert row["current"] == "115.000"
    assert row["difference"] == "15.000"


# ---- 5. stock adjustment --------------------------------------------------

def test_adjustment_in_and_out_move_stock(biz):
    _opening(biz, biz.rice, "100")
    biz.inventory.adjust(item_id=biz.rice, warehouse_id=biz.main, delta="3",
                         reason="Stock count")
    assert _cur(biz) == "103.000"
    biz.inventory.adjust(item_id=biz.rice, warehouse_id=biz.main, delta="-5",
                         reason="Damaged")
    assert _cur(biz) == "98.000"


def test_adjustment_requires_a_reason(biz):
    _opening(biz, biz.rice, "100")
    for bad in ("", "   ", None):
        with pytest.raises(ValidationError):
            biz.inventory.adjust(item_id=biz.rice, warehouse_id=biz.main,
                                 delta="1", reason=bad)
    assert _cur(biz) == "100.000"          # nothing slipped through


def test_adjustment_reason_is_stored_on_the_movement(biz):
    _opening(biz, biz.rice, "100")
    biz.inventory.adjust(item_id=biz.rice, warehouse_id=biz.main, delta="3",
                         reason="Recount after audit")
    latest = biz.inventory.movement_history(item_id=biz.rice)[0]
    assert latest["movement_type"] == "ADJUSTMENT_IN"
    assert latest["notes"] == "Recount after audit"
    assert latest["user_name"]                 # attributed to a real user


def test_adjustment_cannot_remove_more_than_is_there(biz):
    _opening(biz, biz.rice, "10")
    with pytest.raises(InsufficientStockError):
        biz.inventory.adjust(item_id=biz.rice, warehouse_id=biz.main, delta="-11",
                             reason="Too much")
    assert _cur(biz) == "10.000"


def test_adjustment_is_audited(biz):
    _opening(biz, biz.rice, "100")
    biz.inventory.adjust(item_id=biz.rice, warehouse_id=biz.main, delta="3",
                         reason="Stock count")
    row = biz.db.connection().execute(
        "SELECT details FROM audit_log WHERE action = 'inventory.adjust'"
        " ORDER BY id DESC").fetchone()
    assert row is not None and "Stock count" in row[0]


# ---- 6. warehouse transfer ------------------------------------------------

def test_transfer_moves_stock_and_preserves_the_company_total(biz):
    _opening(biz, biz.rice, "100")
    before_total = _cur(biz)
    biz.inventory.transfer(item_id=biz.rice, from_warehouse_id=biz.main,
                           to_warehouse_id=biz.wh2, quantity_moved="10",
                           notes="Restock branch")
    assert _cur(biz, wh=biz.main) == "90.000"
    assert _cur(biz, wh=biz.wh2) == "10.000"
    assert _cur(biz) == before_total          # company total untouched


def test_transfer_writes_a_linked_out_and_in_pair(biz):
    _opening(biz, biz.rice, "100")
    out_id, in_id = biz.inventory.transfer(
        item_id=biz.rice, from_warehouse_id=biz.main, to_warehouse_id=biz.wh2,
        quantity_moved="10", notes="Restock branch")
    rows = {m["id"]: m for m in biz.inventory.movement_history(item_id=biz.rice)}
    assert rows[out_id]["movement_type"] == "TRANSFER_OUT"
    assert rows[in_id]["movement_type"] == "TRANSFER_IN"
    assert rows[in_id]["reference_id"] == out_id       # the IN links to its OUT
    assert rows[out_id]["notes"] == rows[in_id]["notes"] == "Restock branch"


def test_transfer_above_available_source_stock_is_blocked(biz):
    _opening(biz, biz.rice, "10")
    with pytest.raises(InsufficientStockError):
        biz.inventory.transfer(item_id=biz.rice, from_warehouse_id=biz.main,
                               to_warehouse_id=biz.wh2, quantity_moved="11")
    assert _cur(biz, wh=biz.main) == "10.000" and _cur(biz, wh=biz.wh2) == "0.000"


def test_transfer_to_the_same_warehouse_is_blocked(biz):
    _opening(biz, biz.rice, "10")
    with pytest.raises(ValidationError):
        biz.inventory.transfer(item_id=biz.rice, from_warehouse_id=biz.main,
                               to_warehouse_id=biz.main, quantity_moved="1")


# ---- 7. sale-time stock validation ---------------------------------------

def test_sale_validates_against_current_warehouse_stock(biz):
    """Current stock 10: selling 8 and 10 is allowed, 11 is blocked."""
    _opening(biz, biz.rice, "10")
    _sale(biz, "8")
    assert _cur(biz) == "2.000"
    _purchase(biz, "8")                       # back to 10
    assert _cur(biz) == "10.000"
    _sale(biz, "10")
    assert _cur(biz) == "0.000"
    _purchase(biz, "10")
    with pytest.raises(InsufficientStockError):
        _sale(biz, "11")
    assert _cur(biz) == "10.000"              # nothing moved


def test_sale_checks_the_selected_warehouse_not_the_company_total(biz):
    _opening(biz, biz.rice, "100", wh=biz.main)
    with pytest.raises(InsufficientStockError):
        _sale(biz, "1", wh=biz.wh2)           # 100 exist, but not in WH2


def test_a_new_product_with_opening_stock_can_be_sold_immediately(biz):
    """The root cause of the old 'Not enough stock': no opening movement."""
    oil = biz.items.create(item_code="OIL", name="Oil", base_unit_id=biz.bag,
                           purchase_price="60", default_sale_price="120")
    _opening(biz, oil, "20")
    assert biz.inventory.on_hand(oil) == "20.000"
    _sale(biz, "1", item=oil)
    assert biz.inventory.on_hand(oil) == "19.000"
    assert biz.inventory.opening(oil) == "20.000"      # opening still 20


def test_opening_stock_without_a_warehouse_is_refused(biz):
    oil = biz.items.create(item_code="OIL", name="Oil", base_unit_id=biz.bag,
                           purchase_price="60", default_sale_price="120")
    with pytest.raises(ValidationError):
        biz.inventory.record_opening(item_id=oil, warehouse_id=None,
                                     quantity_on_hand="20")


# ---- 4. movement history --------------------------------------------------

def test_movement_history_carries_everything_the_operator_needs(biz):
    _opening(biz, biz.rice, "100", note="Initial count")
    sale = _sale(biz, "5")
    rows = biz.inventory.movement_history(item_id=biz.rice)
    sale_row = next(r for r in rows if r["movement_type"] == "SALE")
    assert sale_row["movement_date"] == "2026-06-02"
    assert sale_row["item_code"] == "RICE" and sale_row["item_name"] == "Rice"
    assert sale_row["warehouse_name"] == "Main Store"
    assert sale_row["document_no"] == sale.document_no      # real document number
    assert sale_row["user_name"]
    assert sale_row["qty_out"] == "5.000" and sale_row["qty_in"] == ""
    opening_row = next(r for r in rows if r["movement_type"] == "OPENING")
    assert opening_row["notes"] == "Initial count"
    assert opening_row["qty_in"] == "100.000"
    assert opening_row["unit_symbol"]        # falls back to the item's base unit


def test_movement_history_filters(biz):
    _opening(biz, biz.rice, "100")
    _opening(biz, biz.sugar, "50")
    _sale(biz, "5")
    biz.inventory.transfer(item_id=biz.rice, from_warehouse_id=biz.main,
                           to_warehouse_id=biz.wh2, quantity_moved="10")
    assert all(r["item_code"] == "RICE"
               for r in biz.inventory.movement_history(item_id=biz.rice))
    assert all(r["warehouse_name"] == "Warehouse 2"
               for r in biz.inventory.movement_history(warehouse_id=biz.wh2))
    only_sales = biz.inventory.movement_history(movement_type="SALE")
    assert only_sales and all(r["movement_type"] == "SALE" for r in only_sales)


def test_item_movement_report_running_balance_ends_at_current_stock(biz):
    _opening(biz, biz.rice, "100")
    _purchase(biz, "20")
    _sale(biz, "5")
    rows = biz.inventory_reports.item_movement(item_id=biz.rice)
    assert rows[-1]["balance"] == biz.inventory.on_hand(biz.rice)
    assert [r["movement_type"] for r in rows] == ["OPENING", "PURCHASE", "SALE"]


# ---- 8. low stock ---------------------------------------------------------

def test_low_stock_flags_items_at_or_below_the_minimum(biz):
    _opening(biz, biz.rice, "100")            # min 20 -> fine
    _opening(biz, biz.sugar, "50")            # min 50 -> at the limit, low
    low = {r["item_code"] for r in biz.inventory.low_stock()}
    assert low == {"SUGAR"}
    _sale(biz, "85")                          # rice down to 15, below its 20
    low = {r["item_code"] for r in biz.inventory.low_stock()}
    assert low == {"RICE", "SUGAR"}


def test_stock_status_labels(biz):
    from zenith_business.ui.documents.inventory_pages import stock_status_key
    assert stock_status_key("0", "20") == "inv.status_out"
    assert stock_status_key("20", "20") == "inv.status_low"
    assert stock_status_key("21", "20") == "inv.status_ok"


# ---- 9. search ------------------------------------------------------------

def test_item_lookup_works_by_code_name_and_barcode(biz):
    biz.items.update(biz.rice, name="Rice", base_unit_id=biz.bag, barcode="8901234567890",
                     purchase_price="50", default_sale_price="100",
                     reorder_level="20", track_inventory=True)
    for term in ("RICE", "ric", "Rice", "890123"):
        found = [r.payload["item_id"] for r in biz.item_search.search(term)]
        assert biz.rice in found, term


# ---- 10. reports ----------------------------------------------------------

def test_all_five_reports_agree_with_the_ledger(biz):
    _opening(biz, biz.rice, "100")
    _opening(biz, biz.sugar, "50")
    _purchase(biz, "20")
    _sale(biz, "5")
    biz.inventory.transfer(item_id=biz.rice, from_warehouse_id=biz.main,
                           to_warehouse_id=biz.wh2, quantity_moved="10")
    svc = biz.inventory_reports
    current = {r["item_code"]: r["current"] for r in svc.current_stock()}
    assert current["RICE"] == biz.inventory.on_hand(biz.rice)
    ovc = {r["item_code"]: r for r in svc.opening_vs_current()}
    assert ovc["RICE"]["opening"] == "100.000"
    by_wh = svc.stock_by_warehouse()
    total = sum(Decimal(r["quantity"]) for r in by_wh if r["item_code"] == "RICE")
    assert str(total) == str(Decimal(biz.inventory.on_hand(biz.rice)))
    assert svc.item_movement(item_id=biz.rice)[-1]["balance"] == biz.inventory.on_hand(biz.rice)
    assert {r["item_code"] for r in svc.low_stock()} == {"SUGAR"}


def test_stock_by_warehouse_filter(biz):
    _opening(biz, biz.rice, "100")
    biz.inventory.transfer(item_id=biz.rice, from_warehouse_id=biz.main,
                           to_warehouse_id=biz.wh2, quantity_moved="10")
    rows = biz.inventory_reports.stock_by_warehouse(warehouse_id=biz.wh2)
    assert len(rows) == 1 and rows[0]["quantity"] == "10.000"


def test_reports_require_permission(biz):
    from zenith_business.services.exceptions import AuthenticationError, AuthorizationError
    biz.session.clear()
    with pytest.raises((AuthenticationError, AuthorizationError)):
        biz.inventory_reports.current_stock()


# ---- MANDATORY WORKFLOW: reconciled across every screen ------------------

def test_mandatory_workflow_reconciles_everywhere(biz):
    """The owner's exact flow, then the SAME number checked on every surface."""
    # 1. Opening 100
    _opening(biz, biz.rice, "100", note="Initial count")
    assert _cur(biz) == "100.000"
    # 2. Purchase +20
    purchase = _purchase(biz, "20")
    assert _cur(biz) == "120.000"
    # 3. Sale 10
    sale = _sale(biz, "10")
    assert _cur(biz) == "110.000"
    # 4. Sales Return 2
    sl = biz.sales_repo.lines_for(sale.id)[0]["id"]
    biz.sales_documents.post_return(sale_id=sale.id, return_date="2026-06-03",
                                    lines=[ReturnLine(sale_line_id=sl, quantity="2")])
    assert _cur(biz) == "112.000"
    # 5. Correct the sale quantity to 5 (2 already returned; 5 >= 2 so it is allowed)
    biz.sales_documents.correct_sale(
        sale_id=sale.id, currency_code="AFN", warehouse_id=biz.main, party_id=biz.cust,
        amount_paid="0", sale_date="2026-06-02",
        lines=[SaleLine(item_id=biz.rice, unit_id=biz.bag, quantity="5", unit_price="100")],
        reason="corrected to 5")
    assert _cur(biz) == "117.000"           # gave back 10, took 5 — no double deduction
    # 6. Adjustment +3
    biz.inventory.adjust(item_id=biz.rice, warehouse_id=biz.main, delta="3",
                         reason="Stock count")
    assert _cur(biz) == "120.000"
    # 7. Transfer 10 Main -> Warehouse 2
    biz.inventory.transfer(item_id=biz.rice, from_warehouse_id=biz.main,
                           to_warehouse_id=biz.wh2, quantity_moved="10",
                           notes="Restock branch")
    assert _cur(biz, wh=biz.main) == "110.000"
    assert _cur(biz, wh=biz.wh2) == "10.000"
    assert _cur(biz) == "120.000"           # company total preserved

    # ---- the same figures on every surface that reports a number ----
    company_total, main_qty, wh2_qty = "120.000", "110.000", "10.000"

    # Inventory / stock overview
    overview = next(r for r in biz.inventory.stock_overview() if r["item_id"] == biz.rice)
    assert overview["current"] == company_total
    assert overview["opening"] == "100.000"
    assert set(overview["warehouses"].split(", ")) == {"Main Store", "Warehouse 2"}

    # Stock by warehouse
    by_wh = {r["warehouse_name"]: r["quantity"]
             for r in biz.inventory_reports.stock_by_warehouse()
             if r["item_code"] == "RICE"}
    assert by_wh == {"Main Store": main_qty, "Warehouse 2": wh2_qty}

    # Movement history: every change is on the record, and they sum to current
    history = biz.inventory.movement_history(item_id=biz.rice)
    assert sum(Decimal(m["quantity"]) for m in history) == Decimal(company_total)
    assert {m["movement_type"] for m in history} >= {
        "OPENING", "PURCHASE", "SALE", "SALE_RETURN", "ADJUSTMENT_IN", "TRANSFER_OUT",
        "TRANSFER_IN"}

    # Item movement report ends on the current figure
    assert biz.inventory_reports.item_movement(item_id=biz.rice)[-1]["balance"] == company_total

    # Sales: one invoice, corrected quantity, original number
    sales = biz.sales_documents.list()
    assert len(sales) == 1
    assert sales[0]["document_no"] == sale.document_no
    assert biz.sales_documents.lines(sale.id)[0]["quantity"] == "5.000"

    # Sales Return: history preserved and still valid against the corrected line
    assert len(biz.sales_returns_repo.list_for_sale(sale.id)) == 1
    # sold 5 − returned 2 still returnable
    assert Decimal(biz.sales_documents.returnable_quantities(sale.id)[sl]) == Decimal("3")

    # Purchase still intact
    assert biz.purchases_repo.get(purchase.id)["document_no"] == purchase.document_no

    # Current-stock report agrees with the ledger
    rep = {r["item_code"]: r["current"] for r in biz.inventory_reports.current_stock()}
    assert rep["RICE"] == company_total
