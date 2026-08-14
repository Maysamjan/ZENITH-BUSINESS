"""Inventory movement-ledger integrity (Stage 02 §8, §28)."""

from __future__ import annotations

import pytest

from zenith_business.services.exceptions import InsufficientStockError, ValidationError
from zenith_business.services.purchases import PurchaseLineInput
from zenith_business.services.sales import SaleLineInput


def _seed(ctx):
    unit = ctx.units_repo.id_by_code("KG")  # decimal-friendly unit
    wh1 = ctx.warehouses_repo.create(code="W1", name="Store 1", is_default=True)
    wh2 = ctx.warehouses_repo.create(code="W2", name="Store 2")
    item = ctx.items_repo.create(item_code="RICE", name="Rice", base_unit_id=unit)
    sup = ctx.suppliers_repo.create(supplier_code="S1", name="Sup")
    cust = ctx.customers_repo.create(customer_code="C1", name="Cust")
    return unit, wh1, wh2, item, sup, cust


def test_stock_is_sum_of_signed_movements(admin_context) -> None:
    unit, wh1, wh2, item, sup, cust = _seed(admin_context)
    admin_context.inventory.record_opening(item_id=item, warehouse_id=wh1,
                                            quantity_on_hand="100.5", unit_id=unit)
    admin_context.purchases.create_and_post(
        currency_code="AFN", warehouse_id=wh1, supplier_id=sup,
        lines=[PurchaseLineInput(item_id=item, unit_id=unit, quantity="10.25",
                                 unit_price="50")])
    admin_context.sales.create_and_post(
        currency_code="AFN", warehouse_id=wh1, customer_id=cust,
        lines=[SaleLineInput(item_id=item, unit_id=unit, quantity="0.75",
                             unit_price="80")])
    # 100.5 + 10.25 - 0.75 = 110.000 (decimal-exact)
    assert admin_context.inventory.on_hand(item, wh1) == "110.000"


def test_multi_warehouse_isolation_and_total(admin_context) -> None:
    unit, wh1, wh2, item, sup, cust = _seed(admin_context)
    admin_context.inventory.record_opening(item_id=item, warehouse_id=wh1,
                                            quantity_on_hand="30", unit_id=unit)
    admin_context.inventory.record_opening(item_id=item, warehouse_id=wh2,
                                            quantity_on_hand="20", unit_id=unit)
    assert admin_context.inventory.on_hand(item, wh1) == "30.000"
    assert admin_context.inventory.on_hand(item, wh2) == "20.000"
    assert admin_context.inventory.on_hand(item) == "50.000"  # all warehouses


def test_transfer_is_atomic_and_conserves_total(admin_context) -> None:
    unit, wh1, wh2, item, sup, cust = _seed(admin_context)
    admin_context.inventory.record_opening(item_id=item, warehouse_id=wh1,
                                            quantity_on_hand="40", unit_id=unit)
    admin_context.inventory.transfer(item_id=item, from_warehouse_id=wh1,
                                     to_warehouse_id=wh2, quantity_moved="15", unit_id=unit)
    assert admin_context.inventory.on_hand(item, wh1) == "25.000"
    assert admin_context.inventory.on_hand(item, wh2) == "15.000"
    assert admin_context.inventory.on_hand(item) == "40.000"  # conserved


def test_transfer_insufficient_stock_blocked(admin_context) -> None:
    unit, wh1, wh2, item, sup, cust = _seed(admin_context)
    admin_context.inventory.record_opening(item_id=item, warehouse_id=wh1,
                                            quantity_on_hand="5", unit_id=unit)
    with pytest.raises(InsufficientStockError):
        admin_context.inventory.transfer(item_id=item, from_warehouse_id=wh1,
                                         to_warehouse_id=wh2, quantity_moved="10")
    # Nothing moved.
    assert admin_context.inventory.on_hand(item, wh1) == "5.000"
    assert admin_context.inventory.on_hand(item, wh2) == "0.000"


def test_transfer_same_warehouse_rejected(admin_context) -> None:
    unit, wh1, wh2, item, sup, cust = _seed(admin_context)
    admin_context.inventory.record_opening(item_id=item, warehouse_id=wh1,
                                            quantity_on_hand="5", unit_id=unit)
    with pytest.raises(ValidationError):
        admin_context.inventory.transfer(item_id=item, from_warehouse_id=wh1,
                                         to_warehouse_id=wh1, quantity_moved="1")


def test_adjustment_updates_stock(admin_context) -> None:
    unit, wh1, wh2, item, sup, cust = _seed(admin_context)
    admin_context.inventory.record_opening(item_id=item, warehouse_id=wh1,
                                            quantity_on_hand="10", unit_id=unit)
    admin_context.inventory.adjust(item_id=item, warehouse_id=wh1, delta="-3",
                                   reason="damage")
    assert admin_context.inventory.on_hand(item, wh1) == "7.000"
