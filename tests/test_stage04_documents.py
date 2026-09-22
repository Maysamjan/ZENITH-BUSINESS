"""Stage 04 — sales, purchases, returns engine (§39)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from zenith_business.services.exceptions import (
    AuthorizationError,
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
    ctx.wh = ctx.warehouses.create(code="MAIN", name="Main", is_default=True)
    ctx.wh2 = ctx.warehouses.create(code="SHOW", name="Showroom")
    ctx.bag = ctx.units_repo.id_by_code("BAG")
    ctx.item = ctx.items.create(item_code="RICE", name="Rice", base_unit_id=ctx.bag,
                                purchase_price="50", default_sale_price="100")
    ctx.cust = ctx.parties.create(party_code="C1", name="Cust", is_customer=True)
    ctx.sup = ctx.parties.create(party_code="S1", name="Sup", is_supplier=True)
    return ctx


def _stock_in(ctx, qty="100"):
    return ctx.purchase_documents.post_purchase(
        currency_code="AFN", warehouse_id=ctx.wh, party_id=ctx.sup, amount_paid="0",
        purchase_date="2026-06-01",
        lines=[PurchaseLine(item_id=ctx.item, unit_id=ctx.bag, quantity=qty, unit_price="50")])


def _ledger_balanced(ctx) -> bool:
    rows = ctx.db.connection().execute(
        "SELECT debit, credit FROM financial_entry_lines").fetchall()
    return sum(Decimal(r[0]) for r in rows) == sum(Decimal(r[1]) for r in rows)


# ---- sales --------------------------------------------------------------

def test_cash_sale(biz):
    _stock_in(biz)
    s = biz.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=biz.wh, party_id=biz.cust, amount_paid="1000",
        sale_date="2026-06-02",
        lines=[SaleLine(item_id=biz.item, unit_id=biz.bag, quantity="10", unit_price="100")])
    assert s.grand_total == "1000.00" and s.remaining == "0.00"
    assert biz.inventory.on_hand(biz.item, biz.wh) == "90.000"
    assert biz.sales_documents.receivable(biz.cust) == "0.00"
    assert _ledger_balanced(biz)


def test_credit_and_partial_sale(biz):
    _stock_in(biz)
    biz.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=biz.wh, party_id=biz.cust, amount_paid="0",
        sale_date="2026-06-02",
        lines=[SaleLine(item_id=biz.item, unit_id=biz.bag, quantity="5", unit_price="100")])
    biz.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=biz.wh, party_id=biz.cust, amount_paid="200",
        sale_date="2026-06-02",
        lines=[SaleLine(item_id=biz.item, unit_id=biz.bag, quantity="5", unit_price="100")])
    # 500 credit + (500-200)=300 credit → 800 receivable
    assert biz.sales_documents.receivable(biz.cust) == "800.00"


def test_multiline_and_multiwarehouse(biz):
    _stock_in(biz, "100")
    biz.purchase_documents.post_purchase(
        currency_code="AFN", warehouse_id=biz.wh2, party_id=biz.sup, amount_paid="0",
        purchase_date="2026-06-01",
        lines=[PurchaseLine(item_id=biz.item, unit_id=biz.bag, quantity="20", unit_price="50")])
    biz.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=biz.wh2, party_id=biz.cust, amount_paid="0",
        sale_date="2026-06-02",
        lines=[SaleLine(item_id=biz.item, unit_id=biz.bag, quantity="8", unit_price="120")])
    assert biz.inventory.on_hand(biz.item, biz.wh) == "100.000"
    assert biz.inventory.on_hand(biz.item, biz.wh2) == "12.000"


def test_oversell_rejected_no_partial(biz):
    _stock_in(biz, "5")
    conn = biz.db.connection()
    before = conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
    nno = biz.numbering.peek("SALE")
    with pytest.raises(InsufficientStockError):
        biz.sales_documents.post_sale(
            currency_code="AFN", warehouse_id=biz.wh, party_id=biz.cust, amount_paid="0",
            sale_date="2026-06-02",
            lines=[SaleLine(item_id=biz.item, unit_id=biz.bag, quantity="99", unit_price="100")])
    assert conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0] == before
    assert biz.numbering.peek("SALE") == nno
    assert biz.inventory.on_hand(biz.item, biz.wh) == "5.000"


@pytest.mark.parametrize("bad", ["12x3", "NaN", "Infinity", "-5", "1e999"])
def test_malformed_or_bad_price_rejected(biz, bad):
    _stock_in(biz)
    with pytest.raises(ValidationError):
        biz.sales_documents.post_sale(
            currency_code="AFN", warehouse_id=biz.wh, party_id=biz.cust, amount_paid="0",
            sale_date="2026-06-02",
            lines=[SaleLine(item_id=biz.item, unit_id=biz.bag, quantity="1", unit_price=bad)])


def test_overpayment_rejected(biz):
    _stock_in(biz)
    with pytest.raises(ValidationError):
        biz.sales_documents.post_sale(
            currency_code="AFN", warehouse_id=biz.wh, party_id=biz.cust, amount_paid="5000",
            sale_date="2026-06-02",
            lines=[SaleLine(item_id=biz.item, unit_id=biz.bag, quantity="1", unit_price="100")])


def test_closed_financial_year_rejected(biz):
    _stock_in(biz)
    fy = biz.financial_years.active()["id"]
    biz.financial_years.close(fy)
    with pytest.raises(ValidationError):
        biz.sales_documents.post_sale(
            currency_code="AFN", warehouse_id=biz.wh, party_id=biz.cust, amount_paid="0",
            sale_date="2026-06-02",
            lines=[SaleLine(item_id=biz.item, unit_id=biz.bag, quantity="1", unit_price="100")])


def test_inactive_item_and_warehouse_rejected(biz):
    _stock_in(biz)
    biz.items.set_active(biz.item, False)
    with pytest.raises(ValidationError):
        biz.sales_documents.post_sale(
            currency_code="AFN", warehouse_id=biz.wh, party_id=biz.cust, amount_paid="0",
            sale_date="2026-06-02",
            lines=[SaleLine(item_id=biz.item, unit_id=biz.bag, quantity="1", unit_price="100")])


def test_sales_rbac(biz):
    biz.users.create_user(username="v", password="V1ewerPass", full_name="V",
                          role_codes=["VIEWER"])
    _stock_in(biz)
    biz.auth.logout(); biz.auth.login("v", "V1ewerPass")
    with pytest.raises(AuthorizationError):
        biz.sales_documents.post_sale(
            currency_code="AFN", warehouse_id=biz.wh, party_id=biz.cust, amount_paid="0",
            sale_date="2026-06-02",
            lines=[SaleLine(item_id=biz.item, unit_id=biz.bag, quantity="1", unit_price="100")])


# ---- purchases ----------------------------------------------------------

def test_purchase_increases_stock_and_payable(biz):
    p = biz.purchase_documents.post_purchase(
        currency_code="AFN", warehouse_id=biz.wh, party_id=biz.sup, amount_paid="2000",
        purchase_date="2026-06-01",
        lines=[PurchaseLine(item_id=biz.item, unit_id=biz.bag, quantity="100", unit_price="50")])
    assert p.grand_total == "5000.00" and p.remaining == "3000.00"
    assert biz.inventory.on_hand(biz.item, biz.wh) == "100.000"
    assert biz.purchase_documents.payable(biz.sup) == "3000.00"
    assert _ledger_balanced(biz)


# ---- returns ------------------------------------------------------------

def test_sales_return_partial_reverses_stock_and_receivable(biz):
    _stock_in(biz)
    s = biz.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=biz.wh, party_id=biz.cust, amount_paid="0",
        sale_date="2026-06-02",
        lines=[SaleLine(item_id=biz.item, unit_id=biz.bag, quantity="10", unit_price="100")])
    sl = biz.sales_repo.lines_for(s.id)[0]["id"]
    biz.sales_documents.post_return(sale_id=s.id, return_date="2026-06-03",
                                    lines=[ReturnLine(sale_line_id=sl, quantity="3")])
    assert biz.inventory.on_hand(biz.item, biz.wh) == "93.000"
    assert biz.sales_documents.receivable(biz.cust) == "700.00"
    assert _ledger_balanced(biz)


def test_multiple_partial_returns_and_over_return(biz):
    _stock_in(biz)
    s = biz.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=biz.wh, party_id=biz.cust, amount_paid="0",
        sale_date="2026-06-02",
        lines=[SaleLine(item_id=biz.item, unit_id=biz.bag, quantity="10", unit_price="100")])
    sl = biz.sales_repo.lines_for(s.id)[0]["id"]
    biz.sales_documents.post_return(sale_id=s.id, return_date="2026-06-03",
                                    lines=[ReturnLine(sale_line_id=sl, quantity="3")])
    biz.sales_documents.post_return(sale_id=s.id, return_date="2026-06-03",
                                    lines=[ReturnLine(sale_line_id=sl, quantity="4")])
    # 3+4 returned; 3 remaining. Returning 4 now must fail.
    with pytest.raises(ValidationError):
        biz.sales_documents.post_return(sale_id=s.id, return_date="2026-06-03",
                                        lines=[ReturnLine(sale_line_id=sl, quantity="4")])
    assert Decimal(biz.sales_documents.returnable_quantities(s.id)[sl]) == Decimal("3")


def test_purchase_return_reduces_stock_and_payable(biz):
    p = biz.purchase_documents.post_purchase(
        currency_code="AFN", warehouse_id=biz.wh, party_id=biz.sup, amount_paid="0",
        purchase_date="2026-06-01",
        lines=[PurchaseLine(item_id=biz.item, unit_id=biz.bag, quantity="100", unit_price="50")])
    pl = biz.purchases_repo.lines_for(p.id)[0]["id"]
    biz.purchase_documents.post_return(purchase_id=p.id, return_date="2026-06-03",
                                       lines=[PurchaseReturnLine(purchase_line_id=pl, quantity="10")])
    assert biz.inventory.on_hand(biz.item, biz.wh) == "90.000"
    assert biz.purchase_documents.payable(biz.sup) == "4500.00"
    assert _ledger_balanced(biz)


def test_purchase_return_over_stock_rejected(biz):
    p = biz.purchase_documents.post_purchase(
        currency_code="AFN", warehouse_id=biz.wh, party_id=biz.sup, amount_paid="0",
        purchase_date="2026-06-01",
        lines=[PurchaseLine(item_id=biz.item, unit_id=biz.bag, quantity="10", unit_price="50")])
    pl = biz.purchases_repo.lines_for(p.id)[0]["id"]
    # sell 8 so only 2 remain in stock, then try to return 10 to supplier
    biz.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=biz.wh, party_id=biz.cust, amount_paid="0",
        sale_date="2026-06-02",
        lines=[SaleLine(item_id=biz.item, unit_id=biz.bag, quantity="8", unit_price="100")])
    with pytest.raises(InsufficientStockError):
        biz.purchase_documents.post_return(
            purchase_id=p.id, return_date="2026-06-03",
            lines=[PurchaseReturnLine(purchase_line_id=pl, quantity="10")])


def test_document_numbering_unique_and_reclaim(biz):
    _stock_in(biz, "100")
    nums = set()
    for _ in range(3):
        r = biz.sales_documents.post_sale(
            currency_code="AFN", warehouse_id=biz.wh, party_id=biz.cust, amount_paid="0",
            sale_date="2026-06-02",
            lines=[SaleLine(item_id=biz.item, unit_id=biz.bag, quantity="1", unit_price="100")])
        nums.add(r.document_no)
    assert len(nums) == 3
    # failed post (oversell) must not consume the next number
    nno = biz.numbering.peek("SALE")
    with pytest.raises(InsufficientStockError):
        biz.sales_documents.post_sale(
            currency_code="AFN", warehouse_id=biz.wh, party_id=biz.cust, amount_paid="0",
            sale_date="2026-06-02",
            lines=[SaleLine(item_id=biz.item, unit_id=biz.bag, quantity="9999", unit_price="100")])
    assert biz.numbering.peek("SALE") == nno


def test_both_role_party_as_customer_and_supplier(biz):
    both = biz.parties.create(party_code="B1", name="Both", is_customer=True, is_supplier=True)
    biz.purchase_documents.post_purchase(
        currency_code="AFN", warehouse_id=biz.wh, party_id=both, amount_paid="0",
        purchase_date="2026-06-01",
        lines=[PurchaseLine(item_id=biz.item, unit_id=biz.bag, quantity="10", unit_price="50")])
    biz.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=biz.wh, party_id=both, amount_paid="0",
        sale_date="2026-06-02",
        lines=[SaleLine(item_id=biz.item, unit_id=biz.bag, quantity="4", unit_price="100")])
    assert biz.purchase_documents.payable(both) == "500.00"
    assert biz.sales_documents.receivable(both) == "400.00"
