"""Owner review round 2 — regression tests.

Posted-invoice correction (safe void+replace + dependency block), self-service
account settings (password/username), per-line unit + item replacement in the
redesigned Sales Invoice, many-line invoices, and the contextual ledger handler.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from zenith_business.services.exceptions import AuthorizationError, ValidationError
from zenith_business.services.purchase_documents import PurchaseLine
from zenith_business.services.sales_documents import ReturnLine, SaleLine


@pytest.fixture
def biz(admin_context):
    ctx = admin_context
    ctx.financial_years.create(name="FY26", start_date="2026-01-01", end_date="2026-12-31",
                               make_active=True)
    ctx.wh = ctx.warehouses.create(code="MAIN", name="Main", is_default=True)
    ctx.bag = ctx.units_repo.id_by_code("BAG")
    ctx.rice = ctx.items.create(item_code="RICE", name="Rice", base_unit_id=ctx.bag,
                                purchase_price="50", default_sale_price="100")
    ctx.oil = ctx.items.create(item_code="OIL", name="Oil", base_unit_id=ctx.bag,
                               purchase_price="30", default_sale_price="80")
    ctx.cust = ctx.parties.create(party_code="C1", name="Kabul Store", is_customer=True)
    ctx.sup = ctx.parties.create(party_code="S1", name="Nat", is_supplier=True)
    ctx.cash = next(f for f in ctx.funds_repo.list_funds() if f["code"] == "1000")["id"]
    ctx.purchase_documents.post_purchase(
        currency_code="AFN", warehouse_id=ctx.wh, party_id=ctx.sup, amount_paid="0",
        purchase_date="2026-06-01",
        lines=[PurchaseLine(item_id=ctx.rice, unit_id=ctx.bag, quantity="1000", unit_price="50"),
               PurchaseLine(item_id=ctx.oil, unit_id=ctx.bag, quantity="1000", unit_price="30")])
    return ctx


def _balanced(ctx) -> bool:
    rows = ctx.db.connection().execute(
        "SELECT debit, credit FROM financial_entry_lines").fetchall()
    return sum(Decimal(r[0]) for r in rows) == sum(Decimal(r[1]) for r in rows)


def _sale(ctx, item, qty, price, **kw):
    return ctx.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=ctx.wh, sale_date="2026-06-02",
        lines=[SaleLine(item_id=item, unit_id=ctx.bag, quantity=qty, unit_price=price)], **kw)


# ---- posted-invoice correction (§9) --------------------------------------

def test_correction_replaces_item_and_reconciles(biz):
    s = _sale(biz, biz.oil, "10", "80", party_id=biz.cust, amount_paid="0")  # wrong item
    assert biz.sales_documents.receivable(biz.cust) == "800.00"
    new = biz.sales_documents.correct_sale(
        sale_id=s.id, currency_code="AFN", warehouse_id=biz.wh, party_id=biz.cust,
        amount_paid="0", lines=[SaleLine(item_id=biz.rice, unit_id=biz.bag,
                                         quantity="10", unit_price="100")], reason="wrong item")
    assert biz.sales_repo.get(s.id)["status"] == "VOID"
    assert biz.sales_repo.get(new.id)["corrected_from_id"] == s.id
    assert biz.sales_documents.receivable(biz.cust) == "1000.00"
    assert biz.inventory_repo.stock_on_hand(biz.oil, biz.wh) == "1000.000"  # oil restored
    assert biz.inventory_repo.stock_on_hand(biz.rice, biz.wh) == "990.000"  # rice sold
    assert _balanced(biz)


def test_correction_blocked_when_return_exists(biz):
    s = _sale(biz, biz.rice, "10", "100", party_id=biz.cust, amount_paid="0")
    lid = biz.sales_repo.lines_for(s.id)[0]["id"]
    biz.sales_documents.post_return(sale_id=s.id, lines=[ReturnLine(sale_line_id=lid, quantity="2")])
    with pytest.raises(ValidationError):
        biz.sales_documents.correct_sale(
            sale_id=s.id, currency_code="AFN", warehouse_id=biz.wh, party_id=biz.cust,
            amount_paid="0", lines=[SaleLine(item_id=biz.rice, unit_id=biz.bag,
                                             quantity="8", unit_price="100")])
    # original stays intact and POSTED (not voided)
    assert biz.sales_repo.get(s.id)["status"] == "POSTED"


def test_correction_requires_permission(biz):
    s = _sale(biz, biz.rice, "1", "100", party_id=biz.cust, amount_paid="0")
    biz.users.create_user(username="sp", password="Str0ngPass!", full_name="S",
                          role_codes=["SALESPERSON"])
    biz.auth.logout(); biz.auth.login("sp", "Str0ngPass!")
    with pytest.raises(AuthorizationError):
        biz.sales_documents.correct_sale(
            sale_id=s.id, currency_code="AFN", warehouse_id=biz.wh, party_id=biz.cust,
            amount_paid="0", lines=[SaleLine(item_id=biz.rice, unit_id=biz.bag,
                                             quantity="1", unit_price="100")])


def test_correction_is_atomic_on_failure(biz):
    s = _sale(biz, biz.rice, "5", "100", party_id=biz.cust, amount_paid="0")
    before = biz.sales_documents.receivable(biz.cust)
    with pytest.raises(ValidationError):
        biz.sales_documents.correct_sale(  # empty lines → rejected, nothing changes
            sale_id=s.id, currency_code="AFN", warehouse_id=biz.wh, party_id=biz.cust,
            amount_paid="0", lines=[])
    assert biz.sales_repo.get(s.id)["status"] == "POSTED"
    assert biz.sales_documents.receivable(biz.cust) == before
    assert _balanced(biz)


# ---- self-service account settings (§12) ---------------------------------

_ADMIN_PW = "Str0ngPass!"  # matches the shared admin_context fixture


def test_change_own_password_requires_current(biz):
    with pytest.raises(ValidationError):
        biz.users.change_own_password(current_password="wrong", new_password="NewP@ss123")
    biz.users.change_own_password(current_password=_ADMIN_PW, new_password="NewP@ss123")
    biz.auth.logout()
    assert biz.auth.login("admin", "NewP@ss123") is not None


def test_change_own_username_dedup_and_preserves_id(biz):
    uid = biz.session.user_id
    biz.users.create_user(username="taken", password="Str0ngPass!", full_name="T",
                          role_codes=["CASHIER"])
    with pytest.raises(ValidationError):
        biz.users.change_own_username(current_password=_ADMIN_PW, new_username="taken")
    biz.users.change_own_username(current_password=_ADMIN_PW, new_username="boss")
    assert biz.session.user_id == uid  # id preserved
    biz.auth.logout()
    assert biz.auth.login("boss", _ADMIN_PW) is not None


# ---- redesigned Sales Invoice (headless UI, §5/§6) -----------------------

def test_invoice_many_lines_and_unit_and_item_edit(biz, qapp):
    from zenith_business.core.i18n import Translator
    from zenith_business.ui.documents.entry_page import DocumentEntryPage
    pg = DocumentEntryPage(biz, Translator(), mode="sale")
    assert pg._unit_combo.count() >= 1           # per-line unit selector present
    assert pg._table.minimumHeight() >= 100      # dominant, Expanding items table
    from PyQt6.QtWidgets import QSizePolicy
    assert pg._table.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Expanding
    rice_pl = {"item_id": biz.rice, "base_unit_id": biz.bag, "item_code": "RICE",
               "name": "Rice", "unit_symbol": "bag", "sale_price": "100"}
    oil_pl = {"item_id": biz.oil, "base_unit_id": biz.bag, "item_code": "OIL",
              "name": "Oil", "unit_symbol": "bag", "sale_price": "80"}
    for _ in range(11):                          # 10+ lines remain practical
        pg.add_line(rice_pl, qty="1", price="100")
    assert pg.line_count == 11
    # replace an item: edit row 0 (loads into strip), then commit oil instead
    pg._table.setCurrentCell(0, 0)
    pg._edit_selected()
    assert pg.line_count == 10
    pg.add_line(oil_pl, qty="2", price="80")
    assert pg.line_count == 11
    assert any(ln["item_id"] == biz.oil for ln in pg._lines)


def test_invoice_shows_previous_and_updated_balance(biz, qapp):
    from zenith_business.core.i18n import Translator
    from zenith_business.ui.documents.entry_page import DocumentEntryPage
    from zenith_business.ui.widgets.search_selector import SearchRow
    _sale(biz, biz.rice, "5", "100", party_id=biz.cust, amount_paid="0")  # prev receivable 500
    pg = DocumentEntryPage(biz, Translator(), mode="sale")
    pg.set_party(SearchRow(values=["C1", "Kabul Store"], payload={"party_id": biz.cust}))
    pg.add_line({"item_id": biz.rice, "base_unit_id": biz.bag, "item_code": "RICE",
                 "name": "Rice", "unit_symbol": "bag", "sale_price": "100"}, qty="3", price="100")
    pg.set_amount_paid("0")
    assert pg._prev_value.text().replace(",", "") == "500.00"
    assert pg._upd_value.text().replace(",", "") == "800.00"  # 500 + 300 new credit


def test_load_for_correction_populates_form(biz, qapp):
    from zenith_business.core.i18n import Translator
    from zenith_business.ui.documents.entry_page import DocumentEntryPage
    s = _sale(biz, biz.rice, "4", "100", party_id=biz.cust, amount_paid="0")
    pg = DocumentEntryPage(biz, Translator(), mode="sale")
    pg.load_for_correction(s.id)
    assert pg._correction_sale_id == s.id
    assert pg.line_count == 1
