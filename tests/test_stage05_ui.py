"""Stage 05 — money-movement UI: entry pages, lists, voucher print (headless)."""

from __future__ import annotations

import pytest

from zenith_business.core.i18n import LANG_DARI, LANG_ENGLISH, Translator
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
    ctx.purchase_documents.post_purchase(
        currency_code="AFN", warehouse_id=ctx.wh, party_id=ctx.sup, amount_paid="0",
        purchase_date="2026-06-01",
        lines=[PurchaseLine(item_id=ctx.item, unit_id=ctx.bag, quantity="100", unit_price="50")])
    ctx.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=ctx.wh, party_id=ctx.cust, amount_paid="0",
        sale_date="2026-06-02",
        lines=[SaleLine(item_id=ctx.item, unit_id=ctx.bag, quantity="10", unit_price="100")])
    return ctx


def _en():
    return Translator(LANG_ENGLISH)


def test_receipt_entry_posts_and_reduces_receivable(qapp, biz):
    from zenith_business.ui.documents.money_page import MoneyEntryPage
    page = MoneyEntryPage(biz, _en(), mode="receipt")
    page.set_party(biz.customer_search.search("Kabul")[0])
    page.set_amount("400")
    page._post(print_after=False)
    assert page.last_saved_id is not None
    assert biz.receipts.receivable(biz.cust) == "600.00"


def test_payment_entry_posts_and_reduces_payable(qapp, biz):
    from zenith_business.ui.documents.money_page import MoneyEntryPage
    page = MoneyEntryPage(biz, _en(), mode="payment")
    page.set_party(biz.supplier_search.search("National")[0])
    page.set_amount("2000")
    page._post(print_after=False)
    assert page.last_saved_id is not None
    assert biz.payments.payable(biz.sup) == "3000.00"


def test_expense_entry_posts(qapp, biz):
    from zenith_business.ui.documents.money_page import MoneyEntryPage
    page = MoneyEntryPage(biz, _en(), mode="expense")
    page._payee_edit.setText("Landlord")
    page.set_amount("1500")
    page._post(print_after=False)
    assert page.last_saved_id is not None
    e = biz.expenses.get(page.last_saved_id)
    assert e["amount"] == "1500.00"


def test_entry_empty_amount_shows_error(qapp, biz):
    from zenith_business.ui.documents.money_page import MoneyEntryPage
    page = MoneyEntryPage(biz, _en(), mode="receipt")
    page.set_party(biz.customer_search.search("Kabul")[0])
    page.set_amount("0")
    page._post(print_after=False)
    assert page.last_saved_id is None
    assert not page._error.isHidden()


def test_lists_show_rows(qapp, biz):
    from zenith_business.ui.documents.money_list_page import MoneyListPage
    from zenith_business.ui.documents.money_page import MoneyEntryPage
    rp = MoneyEntryPage(biz, _en(), mode="receipt")
    rp.set_party(biz.customer_search.search("Kabul")[0]); rp.set_amount("100")
    rp._post(print_after=False)
    lst = MoneyListPage(biz, _en(), mode="receipt")
    assert lst._table.rowCount() == 1


def test_voucher_builders_and_render(qapp, biz):
    from zenith_business.ui.documents import voucher_builder as vb
    from zenith_business.ui.documents.money_page import MoneyEntryPage
    from zenith_business.ui.print.invoice_document import PAPERS
    from zenith_business.ui.print.voucher_document import VoucherData, VoucherPrintDocument
    rp = MoneyEntryPage(biz, _en(), mode="receipt")
    rp.set_party(biz.customer_search.search("Kabul")[0]); rp.set_amount("400")
    rp._post(print_after=False)
    data = vb.build_receipt_voucher(biz, _en(), rp.last_saved_id)
    assert isinstance(data, VoucherData)
    assert data.party_name == "Kabul Store"
    assert data.amount == 400.0
    for lang in (LANG_ENGLISH, LANG_DARI):
        for paper in ("A4", "A5"):
            doc = VoucherPrintDocument(data, Translator(lang), PAPERS[paper])
            assert doc.width() == PAPERS[paper].w


def test_mainwindow_receipts_nav_opens_receipt_entry(qapp, biz):
    from zenith_business.core.config import AppConfig
    from zenith_business.ui.documents.money_page import MoneyEntryPage
    from zenith_business.ui.main_window import MainWindow
    win = MainWindow(AppConfig(), database=biz.db, context=biz)
    win.select_category("menu.receipts_payments")
    assert isinstance(win.content.currentWidget(), MoneyEntryPage)
    assert win.content.currentWidget()._mode == "receipt"


def test_dari_rtl_construction(qapp, biz):
    from zenith_business.ui.documents.money_page import MoneyEntryPage
    for mode in ("receipt", "payment", "expense"):
        page = MoneyEntryPage(biz, Translator(LANG_DARI), mode=mode)
        page.retranslate(Translator(LANG_DARI))
        assert page._title.text()
