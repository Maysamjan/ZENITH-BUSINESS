"""Atomic sales posting: totals, inventory ledger, double entry, rollback
(Stage 02 §25, §26, §28, §29, §34)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from zenith_business.services.exceptions import AuthorizationError, ValidationError
from zenith_business.services.sales import SaleLineInput


def _seed_item(ctx):
    unit_id = ctx.units_repo.id_by_code("PCS")
    wh_id = ctx.warehouses_repo.create(code="MAIN", name="Main", is_default=True)
    item_id = ctx.items_repo.create(
        item_code="SKU-1", name="Widget", base_unit_id=unit_id,
        purchase_price="80.00", default_sale_price="100.00")
    cust_id = ctx.customers_repo.create(customer_code="C-1", name="Ali")
    ctx.inventory.record_opening(
        item_id=item_id, warehouse_id=wh_id, quantity_on_hand="50", unit_id=unit_id)
    return unit_id, wh_id, item_id, cust_id


def test_post_sale_totals_and_inventory(admin_context) -> None:
    unit_id, wh_id, item_id, cust_id = _seed_item(admin_context)
    sale = admin_context.sales.create_and_post(
        currency_code="AFN", warehouse_id=wh_id, customer_id=cust_id, amount_paid="200.00",
        lines=[SaleLineInput(item_id=item_id, unit_id=unit_id, quantity="3",
                             unit_price="100.00", discount="10.00")])
    # 3*100 - 10 = 290 ; paid 200 -> remaining 90
    assert sale.grand_total == "290.00"
    assert sale.remaining == "90.00"
    # Inventory reduced by 3 (signed ledger): 50 - 3 = 47
    assert admin_context.inventory.on_hand(item_id, wh_id) == "47.000"


def test_post_sale_double_entry_balances(admin_context) -> None:
    unit_id, wh_id, item_id, cust_id = _seed_item(admin_context)
    admin_context.sales.create_and_post(
        currency_code="AFN", warehouse_id=wh_id, customer_id=cust_id, amount_paid="200.00",
        lines=[SaleLineInput(item_id=item_id, unit_id=unit_id, quantity="3",
                             unit_price="100.00", discount="10.00")])
    rows = admin_context.db.connection().execute(
        "SELECT debit, credit FROM financial_entry_lines").fetchall()
    debit = sum(Decimal(r[0]) for r in rows)
    credit = sum(Decimal(r[1]) for r in rows)
    assert debit == credit == Decimal("290.00")


def test_empty_sale_rejected(admin_context) -> None:
    with pytest.raises(ValidationError):
        admin_context.sales.create_and_post(currency_code="AFN", lines=[])


def test_sale_requires_permission(admin_context) -> None:
    unit_id, wh_id, item_id, cust_id = _seed_item(admin_context)
    admin_context.users.create_user(
        username="view", password="V1ewerPass", full_name="Viewer", role_codes=["VIEWER"])
    admin_context.auth.login("view", "V1ewerPass")
    with pytest.raises(AuthorizationError):
        admin_context.sales.create_and_post(
            currency_code="AFN", warehouse_id=wh_id,
            lines=[SaleLineInput(item_id=item_id, unit_id=unit_id, quantity="1",
                                 unit_price="10.00")])


def test_failed_post_rolls_back_completely(admin_context) -> None:
    """A bad line (unknown item FK) must roll back header, number and ledger."""
    unit_id, wh_id, item_id, cust_id = _seed_item(admin_context)
    before_docs = admin_context.db.connection().execute(
        "SELECT COUNT(*) FROM sales").fetchone()[0]
    next_no = admin_context.numbering.peek("SALE")
    with pytest.raises(Exception):
        admin_context.sales.create_and_post(
            currency_code="AFN", warehouse_id=wh_id,
            lines=[SaleLineInput(item_id=999999, unit_id=unit_id, quantity="1",
                                 unit_price="10.00")])
    after_docs = admin_context.db.connection().execute(
        "SELECT COUNT(*) FROM sales").fetchone()[0]
    # No sale persisted and the document number was reclaimed.
    assert after_docs == before_docs
    assert admin_context.numbering.peek("SALE") == next_no
