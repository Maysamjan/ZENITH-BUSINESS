"""Stage 02 audit hardening: financial/inventory invariants (§6, §8, §9, §29, §33).

These prove that invalid states are *rejected*, and — critically — that a rejected
operation leaves NO partial state behind (no sale row, no inventory movement, no
consumed document number).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from zenith_business.services.exceptions import (
    InsufficientStockError,
    InvalidJournalError,
    ValidationError,
)
from zenith_business.services.financial import JournalLine
from zenith_business.services.purchases import PurchaseLineInput
from zenith_business.services.sales import SaleLineInput


def _seed(ctx, opening="10"):
    unit = ctx.units_repo.id_by_code("PCS")
    wh = ctx.warehouses_repo.create(code="MAIN", name="Main", is_default=True)
    item = ctx.items_repo.create(item_code="I1", name="Item", base_unit_id=unit,
                                 default_sale_price="100")
    cust = ctx.customers_repo.create(customer_code="C1", name="Cust")
    if opening is not None:
        ctx.inventory.record_opening(item_id=item, warehouse_id=wh,
                                     quantity_on_hand=opening, unit_id=unit)
    return unit, wh, item, cust


# ---- input validation ---------------------------------------------------

def test_oversell_blocked(admin_context) -> None:
    unit, wh, item, cust = _seed(admin_context, opening="10")
    with pytest.raises(InsufficientStockError):
        admin_context.sales.create_and_post(
            currency_code="AFN", warehouse_id=wh, customer_id=cust,
            lines=[SaleLineInput(item_id=item, unit_id=unit, quantity="999",
                                 unit_price="100")])


def test_negative_price_blocked(admin_context) -> None:
    unit, wh, item, cust = _seed(admin_context)
    with pytest.raises(ValidationError):
        admin_context.sales.create_and_post(
            currency_code="AFN", warehouse_id=wh,
            lines=[SaleLineInput(item_id=item, unit_id=unit, quantity="1",
                                 unit_price="-5")])


def test_discount_exceeds_line_blocked(admin_context) -> None:
    unit, wh, item, cust = _seed(admin_context)
    with pytest.raises(ValidationError):
        admin_context.sales.create_and_post(
            currency_code="AFN", warehouse_id=wh,
            lines=[SaleLineInput(item_id=item, unit_id=unit, quantity="1",
                                 unit_price="100", discount="500")])


def test_stockable_item_requires_warehouse(admin_context) -> None:
    unit, wh, item, cust = _seed(admin_context)
    with pytest.raises(ValidationError):
        admin_context.sales.create_and_post(
            currency_code="AFN",  # no warehouse
            lines=[SaleLineInput(item_id=item, unit_id=unit, quantity="1",
                                 unit_price="100")])


def test_backorder_flag_allows_negative_when_explicit(admin_context) -> None:
    unit, wh, item, cust = _seed(admin_context, opening="2")
    res = admin_context.sales.create_and_post(
        currency_code="AFN", warehouse_id=wh, allow_backorder=True,
        lines=[SaleLineInput(item_id=item, unit_id=unit, quantity="5",
                             unit_price="100")])
    assert res.document_no.startswith("SALE-")
    assert admin_context.inventory.on_hand(item, wh) == "-3.000"


def test_non_stockable_item_needs_no_warehouse(admin_context) -> None:
    unit = admin_context.units_repo.id_by_code("PCS")
    svc = admin_context.items_repo.create(
        item_code="SVC", name="Service", base_unit_id=unit,
        default_sale_price="100", track_inventory=False)
    res = admin_context.sales.create_and_post(
        currency_code="AFN",
        lines=[SaleLineInput(item_id=svc, unit_id=unit, quantity="1", unit_price="100")])
    assert res.grand_total == "100.00"


# ---- rejected operations leave NO partial state -------------------------

def test_oversell_leaves_no_partial_state(admin_context) -> None:
    unit, wh, item, cust = _seed(admin_context, opening="10")
    conn = admin_context.db.connection()
    before_sales = conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
    before_moves = conn.execute("SELECT COUNT(*) FROM inventory_movements").fetchone()[0]
    before_journal = conn.execute("SELECT COUNT(*) FROM financial_entries").fetchone()[0]
    next_no = admin_context.numbering.peek("SALE")
    with pytest.raises(InsufficientStockError):
        admin_context.sales.create_and_post(
            currency_code="AFN", warehouse_id=wh,
            lines=[SaleLineInput(item_id=item, unit_id=unit, quantity="999",
                                 unit_price="100")])
    assert conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0] == before_sales
    assert conn.execute("SELECT COUNT(*) FROM inventory_movements").fetchone()[0] == before_moves
    assert conn.execute("SELECT COUNT(*) FROM financial_entries").fetchone()[0] == before_journal
    # Stock check happens before writing → number not even consumed.
    assert admin_context.inventory.on_hand(item, wh) == "10.000"
    assert admin_context.numbering.peek("SALE") == next_no


# ---- journal balance guard ----------------------------------------------

def test_unbalanced_journal_rejected_by_service(admin_context) -> None:
    cash = admin_context.accounts_repo.id_by_code("1000")
    sales = admin_context.accounts_repo.id_by_code("4000")
    before = admin_context.db.connection().execute(
        "SELECT COUNT(*) FROM financial_entries").fetchone()[0]
    with pytest.raises(InvalidJournalError):
        admin_context.financial.post_entry(
            source_type="MANUAL",
            lines=[JournalLine(account_id=cash, debit="100"),
                   JournalLine(account_id=sales, credit="70")])
    # Rolled back — no entry, no lines committed.
    after = admin_context.db.connection().execute(
        "SELECT COUNT(*) FROM financial_entries").fetchone()[0]
    assert after == before


def test_balanced_journal_posts(admin_context) -> None:
    cash = admin_context.accounts_repo.id_by_code("1000")
    sales = admin_context.accounts_repo.id_by_code("4000")
    entry_id = admin_context.financial.post_entry(
        source_type="MANUAL",
        lines=[JournalLine(account_id=cash, debit="100.00"),
               JournalLine(account_id=sales, credit="100.00")])
    assert admin_context.financial_repo.entry_balance(entry_id) == "0.00"


def test_sale_and_purchase_journals_balance(admin_context) -> None:
    unit, wh, item, cust = _seed(admin_context, opening="100")
    admin_context.sales.create_and_post(
        currency_code="AFN", warehouse_id=wh, customer_id=cust, amount_paid="150",
        lines=[SaleLineInput(item_id=item, unit_id=unit, quantity="3", unit_price="100")])
    sup = admin_context.suppliers_repo.create(supplier_code="S1", name="Sup")
    admin_context.purchases.create_and_post(
        currency_code="AFN", warehouse_id=wh, supplier_id=sup, amount_paid="200",
        lines=[PurchaseLineInput(item_id=item, unit_id=unit, quantity="5", unit_price="80")])
    rows = admin_context.db.connection().execute(
        "SELECT debit, credit FROM financial_entry_lines").fetchall()
    assert sum(Decimal(r[0]) for r in rows) == sum(Decimal(r[1]) for r in rows)


# ---- malformed numeric input is rejected, never coerced to zero (§11.F) ----

@pytest.mark.parametrize("bad", ["12x3", "abc", "1.2.3", "", "  ", "1e", None])
def test_malformed_price_rejected_not_zeroed(admin_context, bad) -> None:
    unit, wh, item, cust = _seed(admin_context)
    conn = admin_context.db.connection()
    before = conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
    next_no = admin_context.numbering.peek("SALE")
    with pytest.raises(ValidationError):
        admin_context.sales.create_and_post(
            currency_code="AFN", warehouse_id=wh,
            lines=[SaleLineInput(item_id=item, unit_id=unit, quantity="1", unit_price=bad)])
    assert conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0] == before
    assert admin_context.numbering.peek("SALE") == next_no


def test_malformed_amount_paid_rejected(admin_context) -> None:
    unit, wh, item, cust = _seed(admin_context)
    with pytest.raises(ValidationError):
        admin_context.sales.create_and_post(
            currency_code="AFN", warehouse_id=wh, amount_paid="lots",
            lines=[SaleLineInput(item_id=item, unit_id=unit, quantity="1", unit_price="100")])


def test_malformed_journal_amount_rejected(admin_context) -> None:
    from zenith_business.services.financial import JournalLine
    cash = admin_context.accounts_repo.id_by_code("1000")
    rev = admin_context.accounts_repo.id_by_code("4000")
    with pytest.raises(ValidationError):
        admin_context.financial.post_entry(
            source_type="MANUAL",
            lines=[JournalLine(account_id=cash, debit="ten"),
                   JournalLine(account_id=rev, credit="100")])


def test_malformed_transfer_quantity_rejected(admin_context) -> None:
    unit, wh, item, cust = _seed(admin_context, opening="10")
    wh2 = admin_context.warehouses_repo.create(code="W2", name="W2")
    with pytest.raises(ValidationError):
        admin_context.inventory.transfer(
            item_id=item, from_warehouse_id=wh, to_warehouse_id=wh2, quantity_moved="5x")
