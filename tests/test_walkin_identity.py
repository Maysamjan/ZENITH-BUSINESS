"""BUG 2 regression: a walk-in customer's entered name must appear in the Sales
List (persisted on sales.walkin_name, not held only in UI memory), while
registered customers keep their real name. No accounting/ledger relationship is
created for walk-in customers.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from zenith_business.core.i18n import Translator
from zenith_business.database.connection import Database
from zenith_business.services.context import open_application_context
from zenith_business.services.sales_documents import SaleLine


def _seed(ctx):
    ctx.financial_years.create(name="FY26", start_date="2026-01-01",
                               end_date="2026-12-31", make_active=True)
    wh = ctx.warehouses.create(code="MAIN", name="Main", is_default=True)
    bag = ctx.units_repo.id_by_code("BAG")
    rice = ctx.items.create(item_code="RICE", name="Rice", base_unit_id=bag,
                            purchase_price="50", default_sale_price="100")
    ctx.inventory.record_opening(item_id=rice, warehouse_id=wh, quantity_on_hand="100")
    cust = ctx.parties.create(party_code="C1", name="Kabul General Store", is_customer=True)
    # registered credit sale
    ctx.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=wh, party_id=cust, amount_paid="0",
        sale_date="2026-08-20",
        lines=[SaleLine(item_id=rice, unit_id=bag, quantity="5", unit_price="100")])
    # walk-in sale (paid in full — existing rule), name Ahmad Khan
    ctx.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=wh, party_id=None, amount_paid="300",
        sale_date="2026-08-20",
        lines=[SaleLine(item_id=rice, unit_id=bag, quantity="3", unit_price="100")],
        walkin_name="Ahmad Khan", walkin_phone="0700000000", walkin_address="Kabul")
    return wh, bag, rice, cust


def _list_names(ctx, qapp):
    from zenith_business.ui.documents.list_page import DocumentListPage
    lst = DocumentListPage(ctx, Translator(), mode="sale", on_print=lambda i: None)
    lst.reload()
    return [r.get("party_name") for r in lst._rows]


def test_sales_list_shows_walkin_and_registered_names(admin_context, qapp):
    _seed(admin_context)
    names = _list_names(admin_context, qapp)
    assert "Ahmad Khan" in names            # walk-in name shown (was blank before)
    assert "Kabul General Store" in names   # registered name unchanged


def test_walkin_name_is_not_a_registered_party(admin_context, qapp):
    _seed(admin_context)
    # walk-in must NOT create a customer master record
    parties = admin_context.parties.list()
    assert not any(p["name"] == "Ahmad Khan" for p in parties)


def test_sales_list_walkin_name_persists_after_restart(tmp_path, qapp):
    dbp = Path(tmp_path) / "z.db"
    db = Database(str(dbp))
    ctx = open_application_context(db, backups_dir=tmp_path / "b")
    ctx.setup.create_administrator(username="admin", password="Str0ngPass!",
                                   full_name="O", company_name="Co")
    ctx.auth.login("admin", "Str0ngPass!")
    _seed(ctx)
    assert "Ahmad Khan" in _list_names(ctx, qapp)
    db.close()
    # reopen the on-disk database (simulates an application restart)
    db2 = Database(str(dbp))
    ctx2 = open_application_context(db2, backups_dir=tmp_path / "b")
    ctx2.auth.login("admin", "Str0ngPass!")
    names = _list_names(ctx2, qapp)
    assert "Ahmad Khan" in names             # persisted in the DB, not UI memory
    assert "Kabul General Store" in names
    db2.close()


def test_sales_list_walkin_fallback_when_no_name(admin_context, qapp):
    ctx = admin_context
    ctx.financial_years.create(name="FY26", start_date="2026-01-01",
                               end_date="2026-12-31", make_active=True)
    wh = ctx.warehouses.create(code="MAIN", name="Main", is_default=True)
    bag = ctx.units_repo.id_by_code("BAG")
    rice = ctx.items.create(item_code="RICE", name="Rice", base_unit_id=bag,
                            purchase_price="50", default_sale_price="100")
    ctx.inventory.record_opening(item_id=rice, warehouse_id=wh, quantity_on_hand="100")
    ctx.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=wh, party_id=None, amount_paid="100",
        sale_date="2026-08-20",
        lines=[SaleLine(item_id=rice, unit_id=bag, quantity="1", unit_price="100")])
    names = _list_names(ctx, qapp)
    # no name entered -> localized "Walk-in Customer" fallback, never blank/None
    assert names[0] == Translator().gettext("s4.walkin")
