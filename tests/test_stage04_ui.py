"""Stage 04 — UI construction, keyboard-first entry, lists, returns, print.

Headless (offscreen) tests that drive the REAL service-backed document screens:
posting a sale/purchase from the entry page persists through the atomic service,
the list screens show the persisted rows, the return page reverses from an
original, and the print builders compose real :class:`InvoiceData` for the LOCKED
A4/A5 engine (with the additive per-document title).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from zenith_business.core.i18n import LANG_DARI, LANG_ENGLISH, Translator
from zenith_business.services.purchase_documents import PurchaseLine


@pytest.fixture
def biz(admin_context):
    ctx = admin_context
    ctx.financial_years.create(name="FY26", start_date="2026-01-01", end_date="2026-12-31",
                               make_active=True)
    ctx.wh = ctx.warehouses.create(code="MAIN", name="Main", is_default=True)
    ctx.bag = ctx.units_repo.id_by_code("BAG")
    ctx.item = ctx.items.create(item_code="RICE", name="Rice", base_unit_id=ctx.bag,
                                purchase_price="50", default_sale_price="100")
    ctx.cust = ctx.parties.create(party_code="C1", name="Cust", is_customer=True)
    ctx.sup = ctx.parties.create(party_code="S1", name="Sup", is_supplier=True)
    return ctx


def _stock_in(ctx, qty="100"):
    return ctx.purchase_documents.post_purchase(
        currency_code="AFN", warehouse_id=ctx.wh, party_id=ctx.sup, amount_paid="0",
        purchase_date="2026-06-01",
        lines=[PurchaseLine(item_id=ctx.item, unit_id=ctx.bag, quantity=qty, unit_price="50")])


def _en() -> Translator:
    return Translator(LANG_ENGLISH)


# ---- entry page ---------------------------------------------------------

def test_sales_entry_posts_real_sale(qapp, biz):
    _stock_in(biz)
    from zenith_business.ui.documents.entry_page import DocumentEntryPage
    page = DocumentEntryPage(biz, _en(), mode="sale")
    page.set_party(biz.customer_search.search("Cust")[0])
    page.add_line(biz.item_search.search("Rice")[0].payload, qty="10", price="120")
    assert page.line_count == 1
    page.set_amount_paid("600")
    page._post(print_after=False)
    assert page.last_saved_id is not None
    sale = biz.sales_documents.get(page.last_saved_id)
    assert sale["grand_total"] == "1200.00"
    assert sale["party_id"] == biz.cust
    assert biz.sales_documents.receivable(biz.cust) == "600.00"
    assert biz.inventory.on_hand(biz.item, biz.wh) == "90.000"
    # form reset after posting
    assert page.line_count == 0


def test_purchase_entry_posts_real_purchase(qapp, biz):
    from zenith_business.ui.documents.entry_page import DocumentEntryPage
    page = DocumentEntryPage(biz, _en(), mode="purchase")
    page.set_party(biz.supplier_search.search("Sup")[0])
    page.add_line(biz.item_search.search("Rice")[0].payload, qty="30", price="50")
    page._post(print_after=False)
    assert page.last_saved_id is not None
    assert biz.inventory.on_hand(biz.item, biz.wh) == "30.000"
    assert biz.purchase_documents.payable(biz.sup) == "1500.00"


def test_entry_rejects_bad_quantity_inline(qapp, biz):
    _stock_in(biz)
    from zenith_business.ui.documents.entry_page import DocumentEntryPage
    page = DocumentEntryPage(biz, _en(), mode="sale")
    page.add_line(biz.item_search.search("Rice")[0].payload, qty="0", price="100")
    # a zero quantity never commits a line and surfaces an inline error
    assert page.line_count == 0
    assert not page._error.isHidden()


def test_entry_grid_keeps_minimum_height(qapp, biz):
    """The line grid must keep a usable minimum height so it never collapses to
    zero rows under the fixed panels at 1366x768 (responsiveness regression)."""
    from zenith_business.ui.documents.entry_page import DocumentEntryPage
    page = DocumentEntryPage(biz, _en(), mode="sale")
    assert page._table.minimumHeight() >= 100


def test_entry_empty_post_shows_error(qapp, biz):
    from zenith_business.ui.documents.entry_page import DocumentEntryPage
    page = DocumentEntryPage(biz, _en(), mode="sale")
    page._post(print_after=False)
    assert page.last_saved_id is None
    assert not page._error.isHidden()


# ---- list page ----------------------------------------------------------

def test_sales_list_shows_posted_rows(qapp, biz):
    _stock_in(biz)
    biz.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=biz.wh, party_id=biz.cust, amount_paid="0",
        sale_date="2026-06-02",
        lines=[__import__("zenith_business.services.sales_documents", fromlist=["SaleLine"])
               .SaleLine(item_id=biz.item, unit_id=biz.bag, quantity="4", unit_price="100")])
    from zenith_business.ui.documents.list_page import DocumentListPage
    page = DocumentListPage(biz, _en(), mode="sale")
    assert page._table.rowCount() == 1


def test_purchase_list_shows_rows(qapp, biz):
    _stock_in(biz)
    from zenith_business.ui.documents.list_page import DocumentListPage
    page = DocumentListPage(biz, _en(), mode="purchase")
    assert page._table.rowCount() == 1


# ---- return page --------------------------------------------------------

def test_sales_return_from_original(qapp, biz):
    _stock_in(biz)
    from zenith_business.services.sales_documents import SaleLine
    sale = biz.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=biz.wh, party_id=biz.cust, amount_paid="0",
        sale_date="2026-06-02",
        lines=[SaleLine(item_id=biz.item, unit_id=biz.bag, quantity="10", unit_price="100")])
    from zenith_business.ui.documents.return_page import ReturnEntryPage
    page = ReturnEntryPage(biz, _en(), mode="sales_return")
    page.open_source(sale.id)
    assert page._table.rowCount() == 1
    page.set_return_qty(0, "3")
    page._post(print_after=False)
    assert page.last_saved_id is not None
    # 10 sold − 3 returned → 7 on the customer's books; stock back up by 3
    assert biz.sales_documents.receivable(biz.cust) == "700.00"
    assert biz.inventory.on_hand(biz.item, biz.wh) == "93.000"


def test_purchase_return_from_original(qapp, biz):
    _stock_in(biz, "40")
    purchase = biz.purchase_documents.list()[0]
    from zenith_business.ui.documents.return_page import ReturnEntryPage
    page = ReturnEntryPage(biz, _en(), mode="purchase_return")
    page.open_source(purchase["id"])
    page.set_return_qty(0, "10")
    page._post(print_after=False)
    assert page.last_saved_id is not None
    assert biz.inventory.on_hand(biz.item, biz.wh) == "30.000"


def test_return_no_lines_shows_error(qapp, biz):
    _stock_in(biz)
    from zenith_business.services.sales_documents import SaleLine
    sale = biz.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=biz.wh, party_id=biz.cust, amount_paid="0",
        sale_date="2026-06-02",
        lines=[SaleLine(item_id=biz.item, unit_id=biz.bag, quantity="5", unit_price="100")])
    from zenith_business.ui.documents.return_page import ReturnEntryPage
    page = ReturnEntryPage(biz, _en(), mode="sales_return")
    page.open_source(sale.id)
    page._post(print_after=False)
    assert page.last_saved_id is None
    assert not page._error.isHidden()


# ---- print builders + engine title ------------------------------------

def test_print_builders_all_kinds(qapp, biz):
    _stock_in(biz)
    from zenith_business.services.sales_documents import SaleLine
    from zenith_business.ui.documents import print_builder as pb
    sale = biz.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=biz.wh, party_id=biz.cust, amount_paid="300",
        sale_date="2026-06-02",
        lines=[SaleLine(item_id=biz.item, unit_id=biz.bag, quantity="6", unit_price="100")])
    data, title = pb.build_sale_invoice(biz, sale.id)
    assert title == "print.title"
    assert len(data.lines) == 1 and data.lines[0].name == "Rice"
    assert data.customer_name == "Cust"
    assert Decimal(str(data.grand_total)) == Decimal("600")

    purchase = biz.purchase_documents.list()[0]
    pdata, ptitle = pb.build_purchase_invoice(biz, purchase["id"])
    assert ptitle == pb.TITLE_PURCHASE and pdata.lines

    ret = biz.sales_documents.post_return(
        sale_id=sale.id,
        lines=[__import__("zenith_business.services.sales_documents", fromlist=["ReturnLine"])
               .ReturnLine(sale_line_id=biz.sales_documents.lines(sale.id)[0]["id"], quantity="2")])
    rdata, rtitle = pb.build_sales_return(biz, ret.id)
    assert rtitle == pb.TITLE_SALES_RETURN and rdata.lines


def test_print_engine_title_override(qapp):
    from zenith_business.ui.mock.demo_invoice import build_demo_invoice
    from zenith_business.ui.print.invoice_document import A4, InvoicePrintDocument
    doc = InvoicePrintDocument(build_demo_invoice(), _en(), A4,
                               title_key="s4.print.purchase_title")
    from PyQt6.QtWidgets import QLabel
    labels = [w.text() for w in doc.findChildren(QLabel)]
    assert any("PURCHASE INVOICE" in (t or "") for t in labels)


def test_print_default_title_unchanged(qapp):
    from zenith_business.ui.mock.demo_invoice import build_demo_invoice
    from zenith_business.ui.print.invoice_document import A4, InvoicePrintDocument
    doc = InvoicePrintDocument(build_demo_invoice(), _en(), A4)
    from PyQt6.QtWidgets import QLabel
    labels = [w.text() for w in doc.findChildren(QLabel)]
    assert any("SALES INVOICE" in (t or "") for t in labels)


# ---- main window integration -------------------------------------------

def test_print_screen_parity_and_all_papers_langs(qapp, biz):
    """The printed document equals the persisted transaction, in A4/A5 × EN/Dari."""
    _stock_in(biz, "1000")
    from zenith_business.services.sales_documents import SaleLine
    from zenith_business.ui.documents import print_builder as pb
    from zenith_business.ui.print.invoice_document import PAPERS, InvoicePrintDocument, paginate
    lines = [SaleLine(item_id=biz.item, unit_id=biz.bag, quantity=str(i + 1),
                      unit_price="100", discount="10") for i in range(40)]
    sale = biz.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=biz.wh, party_id=biz.cust, amount_paid="100",
        sale_date="2026-06-05", lines=lines)
    data, title_key = pb.build_sale_invoice(biz, sale.id)
    # screen↔print parity: the print total equals the persisted grand total
    assert Decimal(str(data.grand_total)) == Decimal(sale.grand_total)
    assert len(data.lines) == 40
    for lang in (LANG_ENGLISH, LANG_DARI):
        for paper in ("A4", "A5"):
            p = PAPERS[paper]
            doc = InvoicePrintDocument(data, Translator(lang), p, title_key=title_key)
            # a 40-line invoice reflows onto multiple pages
            assert len(paginate(40, p.cap, p.reserve)) >= 2
            assert doc.width() == p.w


def test_main_window_buy_sell_opens_real_sales(qapp, biz):
    from zenith_business.core.config import AppConfig
    from zenith_business.ui.documents.entry_page import DocumentEntryPage
    from zenith_business.ui.main_window import MainWindow
    win = MainWindow(AppConfig(), database=biz.db, context=biz)
    win.select_category("menu.buy_sell")
    # first Buy & Sell command opens the real sales entry page
    assert isinstance(win.content.currentWidget(), DocumentEntryPage)
    assert win.content.currentWidget()._mode == "sale"


def test_dari_rtl_construction(qapp, biz):
    from zenith_business.ui.documents.entry_page import DocumentEntryPage
    page = DocumentEntryPage(biz, Translator(LANG_DARI), mode="purchase")
    page.retranslate(Translator(LANG_DARI))
    assert page._title.text()  # Dari label present, no crash
