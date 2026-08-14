"""Serious end-to-end integration on a REAL file database (Stage 02 §32).

Exercises the whole stack against an on-disk SQLite file (not mocks): setup →
auth → master data → purchase → sale → persistence across a simulated restart →
backup → restore → integrity checks.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from zenith_business.database.connection import Database
from zenith_business.services.context import open_application_context
from zenith_business.services.purchases import PurchaseLineInput
from zenith_business.services.sales import SaleLineInput


def _open(path: Path, backups: Path):
    db = Database(path)
    return db, open_application_context(db, backups_dir=backups)


def test_full_business_cycle_with_restart_and_restore(tmp_path: Path) -> None:
    db_path = tmp_path / "zenith.db"
    backups = tmp_path / "backups"

    # 1-4. init, migrate, first admin, authenticate
    db, ctx = _open(db_path, backups)
    ctx.setup.create_administrator(
        username="owner", password="Str0ngPass!", full_name="Owner",
        company_name="Zenith Trading Co.")
    ctx.auth.login("owner", "Str0ngPass!")

    # 5-9. master data
    unit = ctx.units_repo.id_by_code("PCS")
    wh = ctx.warehouses_repo.create(code="MAIN", name="Main", is_default=True)
    sup = ctx.suppliers_repo.create(supplier_code="S1", name="Supplier")
    cust = ctx.customers_repo.create(customer_code="C1", name="Customer")
    item = ctx.items_repo.create(item_code="SKU1", name="Widget", base_unit_id=unit,
                                 purchase_price="50", default_sale_price="100")

    # 10-12. purchase → stock up, balanced accounting
    ctx.purchases.create_and_post(
        currency_code="AFN", warehouse_id=wh, supplier_id=sup, amount_paid="500",
        lines=[PurchaseLineInput(item_id=item, unit_id=unit, quantity="20", unit_price="50")])
    assert ctx.inventory.on_hand(item, wh) == "20.000"

    # 13-16. sale → stock down, customer receivable, balanced accounting
    sale = ctx.sales.create_and_post(
        currency_code="AFN", warehouse_id=wh, customer_id=cust, amount_paid="300",
        lines=[SaleLineInput(item_id=item, unit_id=unit, quantity="5", unit_price="100")])
    assert ctx.inventory.on_hand(item, wh) == "15.000"
    assert sale.grand_total == "500.00" and sale.remaining == "200.00"

    rows = db.connection().execute(
        "SELECT debit, credit FROM financial_entry_lines").fetchall()
    assert sum(Decimal(r[0]) for r in rows) == sum(Decimal(r[1]) for r in rows)

    # 17. audit trail present
    assert len(ctx.audit.recent(100)) > 0
    ar_balance = ctx.financial_repo.account_balance(ctx.accounts_repo.id_by_code("1100"))
    sale_doc = sale.document_no
    next_sale_no = ctx.numbering.peek("SALE")

    # 18-21. logout, restart (new Database on same file), login, verify persistence
    ctx.auth.logout()
    db.close()

    db2, ctx2 = _open(db_path, backups)
    # Migrations already applied → no double-apply.
    assert ctx2.is_setup_required is False
    user = ctx2.auth.login("owner", "Str0ngPass!")
    assert user.full_name == "Owner"
    assert ctx2.inventory.on_hand(item, wh) == "15.000"
    assert ctx2.financial_repo.account_balance(ctx2.accounts_repo.id_by_code("1100")) == ar_balance
    # Document numbering survives restart (no reset).
    assert ctx2.numbering.peek("SALE") == next_sale_no
    assert ctx2.sales_repo.get_by_document_no(sale_doc) is not None

    # 22. backup
    backup_file = ctx2.backup.create_backup()
    assert ctx2.backup.validate_backup(backup_file)

    # mutate after backup (add a customer), then restore over it
    ctx2.customers_repo.create(customer_code="C2", name="Post-Backup Customer")
    assert ctx2.customers_repo.get(2) is not None  # exists before restore
    ctx2.backup.restore_backup(backup_file, db_path)  # closes db2
    db2.close()

    # 23-24. reopen restored db, verify state rolled back to backup point
    db3, ctx3 = _open(db_path, backups)
    ctx3.auth.login("owner", "Str0ngPass!")
    assert ctx3.inventory.on_hand(item, wh) == "15.000"
    # The post-backup customer is gone; the pre-backup one remains.
    assert ctx3.customers_repo.get(1) is not None
    assert ctx3.customers_repo.get(2) is None

    # 25-26. integrity checks on the restored database
    ic = db3.connection().execute("PRAGMA integrity_check").fetchone()[0]
    fk = db3.connection().execute("PRAGMA foreign_key_check").fetchall()
    assert ic == "ok"
    assert len(fk) == 0
    db3.close()
