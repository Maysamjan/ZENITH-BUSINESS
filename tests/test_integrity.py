"""SQLite integrity guarantees after real work (Stage 02 §22)."""

from __future__ import annotations

from zenith_business.services.purchases import PurchaseLineInput
from zenith_business.services.sales import SaleLineInput


def _integrity(conn) -> tuple[str, int]:
    ic = conn.execute("PRAGMA integrity_check").fetchone()[0]
    fk = conn.execute("PRAGMA foreign_key_check").fetchall()
    return ic, len(fk)


def test_integrity_ok_on_fresh_migrated_db(context) -> None:
    ic, fk = _integrity(context.db.connection())
    assert ic == "ok"
    assert fk == 0


def test_integrity_ok_after_complex_transactions(admin_context) -> None:
    unit = admin_context.units_repo.id_by_code("PCS")
    wh = admin_context.warehouses_repo.create(code="MAIN", name="Main", is_default=True)
    item = admin_context.items_repo.create(item_code="I1", name="Item", base_unit_id=unit)
    cust = admin_context.customers_repo.create(customer_code="C1", name="Cust")
    sup = admin_context.suppliers_repo.create(supplier_code="S1", name="Sup")
    admin_context.purchases.create_and_post(
        currency_code="AFN", warehouse_id=wh, supplier_id=sup, amount_paid="500",
        lines=[PurchaseLineInput(item_id=item, unit_id=unit, quantity="20", unit_price="50")])
    admin_context.sales.create_and_post(
        currency_code="AFN", warehouse_id=wh, customer_id=cust, amount_paid="300",
        lines=[SaleLineInput(item_id=item, unit_id=unit, quantity="5", unit_price="100")])
    admin_context.users.create_user(username="u2", password="Xy12345!",
                                    full_name="U2", role_codes=["CASHIER"])
    ic, fk = _integrity(admin_context.db.connection())
    assert ic == "ok"
    assert fk == 0
