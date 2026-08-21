"""Owner manual-test defect fixes — regression tests for all six defects.

Covers: walk-in/registered sales (#2), pre-post line editing + safe posted-sale
Void (#3), customer/supplier account ledgers (#4), responsive scroll bodies (#5),
company logo on printed documents (#6), and the refined Sales Invoice entry (#1).
Engine/service behaviour is asserted directly; UI behaviour is driven headlessly.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from zenith_business.services.exceptions import AuthorizationError, ValidationError
from zenith_business.services.purchase_documents import PurchaseLine
from zenith_business.services.sales_documents import SaleLine


@pytest.fixture
def biz(admin_context):
    ctx = admin_context
    ctx.financial_years.create(name="FY26", start_date="2026-01-01", end_date="2026-12-31",
                               make_active=True)
    ctx.wh = ctx.warehouses.create(code="MAIN", name="Main", is_default=True)
    ctx.bag = ctx.units_repo.id_by_code("BAG")
    ctx.item = ctx.items.create(item_code="RICE", name="Rice", base_unit_id=ctx.bag,
                                purchase_price="50", default_sale_price="100")
    ctx.cust = ctx.parties.create(party_code="C1", name="Kabul Store", is_customer=True,
                                  phone="070 111 2222")
    ctx.sup = ctx.parties.create(party_code="S1", name="National Foods", is_supplier=True)
    ctx.cash = next(f for f in ctx.funds_repo.list_funds() if f["code"] == "1000")["id"]
    ctx.purchase_documents.post_purchase(
        currency_code="AFN", warehouse_id=ctx.wh, party_id=ctx.sup, amount_paid="0",
        purchase_date="2026-06-01",
        lines=[PurchaseLine(item_id=ctx.item, unit_id=ctx.bag, quantity="100", unit_price="50")])
    return ctx


def _balanced(ctx) -> bool:
    rows = ctx.db.connection().execute(
        "SELECT debit, credit FROM financial_entry_lines").fetchall()
    return sum(Decimal(r[0]) for r in rows) == sum(Decimal(r[1]) for r in rows)


def _sale(ctx, qty, price, **kw):
    return ctx.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=ctx.wh, sale_date="2026-06-02",
        lines=[SaleLine(item_id=ctx.item, unit_id=ctx.bag, quantity=qty, unit_price=price)], **kw)


# ---- defect #2 — walk-in vs registered customers -------------------------

def test_walkin_cash_sale_snapshots_name_and_no_receivable(biz):
    s = _sale(biz, "2", "100", amount_paid="200", walkin_name="Ahmad Khan",
              walkin_phone="0700111222", walkin_address="Kabul")
    row = biz.sales_repo.get(s.id)
    assert row["party_id"] is None
    assert row["walkin_name"] == "Ahmad Khan"
    assert row["walkin_phone"] == "0700111222"
    assert row["remaining_amount"] == "0.00"
    assert _balanced(biz)


def test_walkin_credit_is_rejected_no_anonymous_receivable(biz):
    with pytest.raises(ValidationError):
        _sale(biz, "2", "100", amount_paid="0", walkin_name="Nobody")  # credit walk-in


def test_registered_and_walkin_are_distinguishable(biz):
    reg = _sale(biz, "1", "100", party_id=biz.cust, amount_paid="0")
    walk = _sale(biz, "1", "100", amount_paid="100", walkin_name="Passer By")
    assert biz.sales_repo.get(reg.id)["party_id"] == biz.cust
    assert biz.sales_repo.get(walk.id)["party_id"] is None
    assert biz.sales_repo.get(walk.id)["walkin_name"] == "Passer By"


def test_walkin_snapshot_prints_entered_name(biz, qapp):
    from zenith_business.ui.documents.print_builder import build_sale_invoice
    s = _sale(biz, "1", "100", amount_paid="100", walkin_name="Sara Ahmadi")
    data, _title = build_sale_invoice(biz, s.id)
    assert data.customer_name == "Sara Ahmadi"


# ---- defect #3 — safe posted-sale Void -----------------------------------

def test_void_reverses_stock_balance_and_ledger(biz):
    s = _sale(biz, "10", "100", party_id=biz.cust, amount_paid="0")
    assert biz.sales_documents.receivable(biz.cust) == "1000.00"
    assert biz.inventory_repo.stock_on_hand(biz.item, biz.wh) == "90.000"
    biz.sales_documents.void_sale(sale_id=s.id, reason="mistake")
    assert biz.sales_repo.get(s.id)["status"] == "VOID"
    assert biz.sales_documents.receivable(biz.cust) == "0.00"
    assert biz.inventory_repo.stock_on_hand(biz.item, biz.wh) == "100.000"
    assert _balanced(biz)


def test_void_twice_is_rejected(biz):
    s = _sale(biz, "1", "100", party_id=biz.cust, amount_paid="0")
    biz.sales_documents.void_sale(sale_id=s.id)
    with pytest.raises(ValidationError):
        biz.sales_documents.void_sale(sale_id=s.id)


def test_void_blocked_when_returns_exist(biz):
    s = _sale(biz, "5", "100", party_id=biz.cust, amount_paid="0")
    line_id = biz.sales_repo.lines_for(s.id)[0]["id"]
    from zenith_business.services.sales_documents import ReturnLine
    biz.sales_documents.post_return(sale_id=s.id, lines=[ReturnLine(sale_line_id=line_id, quantity="1")])
    with pytest.raises(ValidationError):
        biz.sales_documents.void_sale(sale_id=s.id)


def test_void_requires_permission(biz):
    s = _sale(biz, "1", "100", party_id=biz.cust, amount_paid="0")
    biz.users.create_user(username="sp", password="Str0ngPass!", full_name="Sales",
                          role_codes=["SALESPERSON"])
    biz.auth.logout(); biz.auth.login("sp", "Str0ngPass!")
    with pytest.raises(AuthorizationError):
        biz.sales_documents.void_sale(sale_id=s.id)


# ---- defect #4 — customer / supplier ledger ------------------------------

def test_customer_ledger_running_balance_and_totals(biz):
    _sale(biz, "10", "100", party_id=biz.cust, amount_paid="200")  # 1000 total, 200 cash
    biz.receipts.post_receipt(party_id=biz.cust, account_id=biz.cash, amount="300",
                              currency_code="AFN", payment_method="CASH", receipt_date="2026-06-03")
    led = biz.party_ledger.customer_ledger(biz.cust)
    assert led["totals"]["total_sales"] == "1000.00"
    assert led["totals"]["total_received"] == "300.00"
    assert led["totals"]["receivable"] == "500.00"  # 1000 - 200 cash - 300 receipt
    assert led["rows"][-1]["running"] == "500.00"


def test_supplier_ledger_matches_payable(biz):
    # opening purchase in fixture already created a payable of 5000 (100 * 50)
    biz.payments.post_payment(party_id=biz.sup, account_id=biz.cash, amount="2000",
                              currency_code="AFN", payment_method="CASH", payment_date="2026-06-03")
    led = biz.party_ledger.supplier_ledger(biz.sup)
    assert led["totals"]["total_purchases"] == "5000.00"
    assert led["totals"]["total_paid"] == "2000.00"
    assert led["totals"]["payable"] == "3000.00"
    assert led["rows"][-1]["running"] == "3000.00"


def test_ledger_requires_permission(biz):
    biz.users.create_user(username="v", password="Str0ngPass!", full_name="V",
                          role_codes=["SALESPERSON"])
    # SALESPERSON has parties.ledger (granted by migration 0006) → allowed
    biz.auth.logout(); biz.auth.login("v", "Str0ngPass!")
    assert "totals" in biz.party_ledger.customer_ledger(biz.cust)


def test_dual_role_party_single_identity(biz):
    both = biz.parties.create(party_code="B1", name="Dual", is_customer=True, is_supplier=True)
    _sale(biz, "1", "100", party_id=both, amount_paid="0")
    cust_led = biz.party_ledger.customer_ledger(both)
    sup_led = biz.party_ledger.supplier_ledger(both)
    assert cust_led["party"]["id"] == sup_led["party"]["id"] == both
    assert cust_led["totals"]["receivable"] == "100.00"
    assert sup_led["totals"]["payable"] == "0.00"


# ---- defect #6 — company logo on printed documents -----------------------

def test_company_info_carries_logo_and_degrades(biz, tmp_path):
    from PyQt6.QtGui import QPixmap
    from PyQt6.QtWidgets import QApplication
    from zenith_business.ui.documents.print_builder import _company_info
    _ = QApplication.instance() or QApplication([])
    logo = tmp_path / "logo.png"; QPixmap(200, 80).save(str(logo))
    biz.company.save(legal_name="Zenith", display_name="Zenith",
                     logo_path=str(logo))
    assert _company_info(biz).logo_path == str(logo)
    # a missing file degrades gracefully to no logo (letter-mark fallback)
    biz.company.save(legal_name="Zenith", display_name="Zenith",
                     logo_path=str(tmp_path / "gone.png"))
    assert _company_info(biz).logo_path == ""


def test_logo_renders_in_print_header(biz, qapp, tmp_path):
    from PyQt6.QtGui import QColor, QPixmap
    from PyQt6.QtWidgets import QLabel
    from zenith_business.core.i18n import Translator
    from zenith_business.ui.documents.print_builder import build_sale_invoice
    from zenith_business.ui.print.invoice_document import A4, InvoicePrintDocument
    logo = tmp_path / "logo.png"; pm = QPixmap(240, 80); pm.fill(QColor("#123456")); pm.save(str(logo))
    biz.company.save(legal_name="Zenith", display_name="Zenith", logo_path=str(logo))
    s = _sale(biz, "1", "100", party_id=biz.cust, amount_paid="100")
    data, _t = build_sale_invoice(biz, s.id)
    doc = InvoicePrintDocument(data, Translator(), paper=A4)
    imgs = [w for w in doc.findChildren(QLabel) if w.property("p") == "logo-img"]
    assert imgs and not imgs[0].pixmap().isNull()


# ---- defect #1/#3 — refined Sales Invoice entry (headless UI) -------------

def test_sales_entry_walkin_toggle_and_line_edit(biz, qapp):
    from zenith_business.core.i18n import Translator
    from zenith_business.ui.documents.entry_page import DocumentEntryPage, C_QTY
    pg = DocumentEntryPage(biz, Translator(), mode="sale")
    pg._set_customer_mode("walkin")
    assert pg._customer_mode == "walkin"
    pg._walkin_name.setText("Walk Buyer")
    payload = {"item_id": biz.item, "base_unit_id": biz.bag, "item_code": "RICE",
               "name": "Rice", "unit_symbol": "bag", "sale_price": "100"}
    pg.add_line(payload, qty="2", price="100")
    # inline-edit the qty cell 2 -> 5 and confirm the grand total recomputes
    pg._table.item(0, C_QTY).setText("5")
    assert pg._grand_value.text().replace(",", "") == "500.00"
    pg.set_amount_paid("500")
    pg._post(print_after=False)
    assert pg.last_saved_id is not None
    row = biz.sales_repo.get(pg.last_saved_id)
    assert row["party_id"] is None and row["walkin_name"] == "Walk Buyer"


def test_sales_entry_line_delete(biz, qapp):
    from zenith_business.core.i18n import Translator
    from zenith_business.ui.documents.entry_page import DocumentEntryPage
    pg = DocumentEntryPage(biz, Translator(), mode="sale")
    payload = {"item_id": biz.item, "base_unit_id": biz.bag, "item_code": "RICE",
               "name": "Rice", "unit_symbol": "bag", "sale_price": "100"}
    pg.add_line(payload, qty="1", price="100")
    pg.add_line(payload, qty="2", price="100")
    assert pg.line_count == 2
    pg._table.setCurrentCell(0, 0)
    pg._delete_selected()
    assert pg.line_count == 1


# ---- defect #5 — responsive: pinned action bar over a scroll body --------

def test_entry_page_actionbar_is_last_and_grid_stretches(biz, qapp):
    # The sales page keeps the action bar as the LAST root widget with the line
    # grid stretching above it, so the totals band + Save stay visible while the
    # grid absorbs any vertical squeeze on small windows.
    from PyQt6.QtWidgets import QFrame
    from zenith_business.core.i18n import Translator
    from zenith_business.ui.documents.entry_page import DocumentEntryPage
    pg = DocumentEntryPage(biz, Translator(), mode="sale")
    root = pg.layout()
    last = root.itemAt(root.count() - 1).widget()
    assert isinstance(last, QFrame) and last.property("role") == "actionbar"
    # some root item (the line-grid card) carries the stretch factor
    assert any(root.stretch(i) == 1 for i in range(root.count()))


def test_money_page_has_pinned_actionbar_over_scroll(biz, qapp):
    from PyQt6.QtWidgets import QScrollArea
    from zenith_business.core.i18n import Translator
    from zenith_business.ui.documents.money_page import MoneyEntryPage
    pg = MoneyEntryPage(biz, Translator(), mode="receipt")
    root = pg.layout()
    kinds = [type(root.itemAt(i).widget()).__name__ for i in range(root.count())
             if root.itemAt(i).widget() is not None]
    assert "QScrollArea" in kinds
    last = root.itemAt(root.count() - 1).widget()
    assert last is not None and not isinstance(last, QScrollArea)
