"""Master-data repositories and purchase posting (Stage 02 §17-§23, §27-§29)."""

from __future__ import annotations

from decimal import Decimal

from zenith_business.services.purchases import PurchaseLineInput


def test_seeded_master_data(context) -> None:
    assert context.currencies_repo.base_currency()["code"] == "AFN"
    assert context.units_repo.id_by_code("PCS") is not None
    assert len(context.accounts_repo.list_all()) >= 6


def test_item_search_and_barcode(admin_context) -> None:
    unit_id = admin_context.units_repo.id_by_code("PCS")
    admin_context.items_repo.create(
        item_code="APPLE-1", name="Apple Juice", base_unit_id=unit_id, barcode="6001234")
    results = admin_context.items_repo.search("apple")
    assert any(r["item_code"] == "APPLE-1" for r in results)
    assert admin_context.items_repo.find_by_barcode("6001234")["name"] == "Apple Juice"


def test_money_fields_stored_as_text(admin_context) -> None:
    unit_id = admin_context.units_repo.id_by_code("PCS")
    item_id = admin_context.items_repo.create(
        item_code="X-1", name="X", base_unit_id=unit_id, default_sale_price="12.5")
    row = admin_context.items_repo.get(item_id)
    assert row["default_sale_price"] == "12.50"  # canonical 2-dp text


def test_post_purchase_increases_stock_and_balances(admin_context) -> None:
    unit_id = admin_context.units_repo.id_by_code("PCS")
    wh_id = admin_context.warehouses_repo.create(code="MAIN", name="Main", is_default=True)
    item_id = admin_context.items_repo.create(
        item_code="SKU-9", name="Rice", base_unit_id=unit_id)
    sup_id = admin_context.suppliers_repo.create(supplier_code="S-1", name="Supplier")

    result = admin_context.purchases.create_and_post(
        currency_code="AFN", warehouse_id=wh_id, supplier_id=sup_id, amount_paid="100.00",
        lines=[PurchaseLineInput(item_id=item_id, unit_id=unit_id, quantity="10",
                                 unit_price="50.00")])
    assert result.grand_total == "500.00"
    assert result.remaining == "400.00"
    # Purchase adds stock (positive movement).
    assert admin_context.inventory.on_hand(item_id, wh_id) == "10.000"
    # Ledger balances.
    rows = admin_context.db.connection().execute(
        "SELECT debit, credit FROM financial_entry_lines").fetchall()
    assert sum(Decimal(r[0]) for r in rows) == sum(Decimal(r[1]) for r in rows)
