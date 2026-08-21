"""Stage 05 final — UI: Sales Return lookup fix (P1) + Sales Report screen (P6-UI).

Headless (offscreen) tests driving the REAL service-backed screens:

* the Sales Return page must locate a persisted invoice by its exact number AND
  by a unique partial number the operator types, reject a nonexistent one, and
  flag an ambiguous partial — the P1 lookup defect,
* the Sales Report screen runs against authoritative POSTED documents, shows the
  Gross/Paid/Credit/Returns/Net tiles, switches Transactions/Daily/Monthly, honors
  the filters, and hands a correct payload to the (customer-identity) print.
"""

from __future__ import annotations

import pytest

from zenith_business.core.i18n import LANG_DARI, LANG_ENGLISH, Translator
from zenith_business.services.purchase_documents import PurchaseLine
from zenith_business.services.sales_documents import ReturnLine, SaleLine


@pytest.fixture
def biz(admin_context):
    ctx = admin_context
    ctx.financial_years.create(name="FY26", start_date="2026-01-01", end_date="2026-12-31",
                               make_active=True)
    ctx.wh = ctx.warehouses.create(code="MAIN", name="Main", is_default=True)
    ctx.bag = ctx.units_repo.id_by_code("BAG")
    ctx.item = ctx.items.create(item_code="RICE", name="Rice", base_unit_id=ctx.bag,
                                purchase_price="50", default_sale_price="100")
    ctx.cust = ctx.parties.create(party_code="C1", name="Ahmad Store", is_customer=True)
    ctx.sup = ctx.parties.create(party_code="S1", name="Sup", is_supplier=True)
    ctx.purchase_documents.post_purchase(
        currency_code="AFN", warehouse_id=ctx.wh, party_id=ctx.sup, amount_paid="0",
        purchase_date="2026-06-01",
        lines=[PurchaseLine(item_id=ctx.item, unit_id=ctx.bag, quantity="200", unit_price="50")])
    return ctx


def _en() -> Translator:
    return Translator(LANG_ENGLISH)


def _sale(biz, qty="10", paid="0", date="2026-06-10"):
    return biz.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=biz.wh, party_id=biz.cust, amount_paid=paid,
        sale_date=date,
        lines=[SaleLine(item_id=biz.item, unit_id=biz.bag, quantity=qty, unit_price="100")])


# ---- P1: Sales Return lookup --------------------------------------------

def test_return_lookup_by_exact_number(qapp, biz):
    sale = _sale(biz)
    from zenith_business.ui.documents.return_page import ReturnEntryPage
    page = ReturnEntryPage(biz, _en(), mode="sales_return")
    page._src_edit.setText(sale.document_no)   # e.g. SALE-000001
    page._load_source()
    assert page._source_id == sale.id
    assert page._table.rowCount() == 1
    assert not page._error.isVisibleTo(page)


def test_return_lookup_by_partial_number(qapp, biz):
    """The real defect: typing '1' or '000001' must load the one matching invoice."""
    sale = _sale(biz)
    from zenith_business.ui.documents.return_page import ReturnEntryPage
    page = ReturnEntryPage(biz, _en(), mode="sales_return")
    page._src_edit.setText("000001")
    page._load_source()
    assert page._source_id == sale.id
    assert not page._error.isVisibleTo(page)


def test_return_lookup_nonexistent_rejected(qapp, biz):
    _sale(biz)
    from zenith_business.ui.documents.return_page import ReturnEntryPage
    page = ReturnEntryPage(biz, _en(), mode="sales_return")
    page._src_edit.setText("SALE-999999")
    page._load_source()
    assert page._source_id is None
    assert page._error.isVisibleTo(page)
    assert page._table.rowCount() == 0


def test_return_lookup_ambiguous_flagged(qapp, biz):
    """Two invoices whose numbers both contain the fragment → ask for the full no."""
    _sale(biz)                          # SALE-000001
    for _ in range(9):
        _sale(biz)                      # up to SALE-000010
    from zenith_business.ui.documents.return_page import ReturnEntryPage
    page = ReturnEntryPage(biz, _en(), mode="sales_return")
    page._src_edit.setText("1")         # matches 000001 and 000010 (both contain '1')
    page._load_source()
    assert page._source_id is None
    assert page._error.isVisibleTo(page)
    assert page._error.text() == Translator(LANG_ENGLISH).gettext("s4.msg_source_ambiguous")


def test_return_lookup_partial_return_completes(qapp, biz):
    sale = _sale(biz, qty="10")
    from zenith_business.ui.documents.return_page import ReturnEntryPage
    page = ReturnEntryPage(biz, _en(), mode="sales_return")
    page._src_edit.setText("1"); page._load_source()   # unique → SALE-000001
    assert page._source_id == sale.id
    page.set_return_qty(0, "4")
    page._post(print_after=False)
    assert page.last_saved_id is not None
    assert biz.inventory.on_hand(biz.item, biz.wh) == "194.000"


# ---- P6-UI: Sales Report screen -----------------------------------------

def _report_page(biz, lang=LANG_ENGLISH):
    from zenith_business.ui.documents.sales_report_page import SalesReportPage
    return SalesReportPage(biz, Translator(lang), on_close=lambda: None,
                           on_print=lambda payload: None)


def _run_june(page):
    page._apply_preset("custom", run=False)
    page._from_edit.setText("2026-06-01")
    page._to_edit.setText("2026-06-30")
    page.run()


def test_report_summary_tiles(qapp, biz):
    _sale(biz, qty="10", paid="300")             # gross 1000, paid 300, credit 700
    biz.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=biz.wh, party_id=None, amount_paid="400",
        sale_date="2026-06-10", walkin_name="Guest",
        lines=[SaleLine(item_id=biz.item, unit_id=biz.bag, quantity="4", unit_price="100")])
    page = _report_page(biz)
    _run_june(page)
    assert page._g_val.text() == "1,400.00"
    assert page._p_val.text() == "700.00"
    assert page._c_val.text() == "700.00"
    assert page._r_val.text() == "0.00"
    assert page._n_val.text() == "1,400.00"
    assert page._table.rowCount() == 2           # both invoices in Transactions view


def test_report_returns_reduce_net(qapp, biz):
    sale = _sale(biz, qty="10", paid="1000")
    sl = biz.sales_repo.lines_for(sale.id)[0]["id"]
    biz.sales_documents.post_return(sale_id=sale.id, return_date="2026-06-12",
                                    lines=[ReturnLine(sale_line_id=sl, quantity="3")])
    page = _report_page(biz)
    _run_june(page)
    assert page._g_val.text() == "1,000.00"
    assert page._r_val.text() == "300.00"
    assert page._n_val.text() == "700.00"


def test_report_view_switch(qapp, biz):
    _sale(biz, qty="5", paid="500")
    page = _report_page(biz)
    _run_june(page)
    page._set_view("daily")
    assert page._table.columnCount() == 7        # breakdown columns
    page._set_view("monthly")
    assert page._table.rowCount() == 1           # only June has activity
    page._set_view("detail")
    assert page._table.columnCount() == 9        # detail columns


def test_report_walkin_filter(qapp, biz):
    _sale(biz, qty="5", paid="500")              # registered
    biz.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=biz.wh, party_id=None, amount_paid="200",
        sale_date="2026-06-10", walkin_name="Guest",
        lines=[SaleLine(item_id=biz.item, unit_id=biz.bag, quantity="2", unit_price="100")])
    page = _report_page(biz)
    # select walk-in kind
    i = page._kind_combo.findData("walkin")
    page._kind_combo.setCurrentIndex(i)
    _run_june(page)
    assert page._table.rowCount() == 1           # only the walk-in sale


def test_report_print_payload(qapp, biz):
    captured = {}
    _sale(biz, qty="5", paid="500")
    from zenith_business.ui.documents.sales_report_page import SalesReportPage
    page = SalesReportPage(biz, _en(), on_close=lambda: None,
                           on_print=lambda payload: captured.update(payload))
    _run_june(page)
    page._print()
    assert captured.get("summary", {}).get("gross") == "500.00"
    assert len(captured.get("detail", [])) == 1
    # printable uses the customer's business identity, not the developer identity
    from zenith_business.ui.documents.print_builder import build_sales_report_print
    data = build_sales_report_print(biz, captured)
    assert "Zenith Soft" not in (data.company.name or "")


def test_report_bad_dates_flagged(qapp, biz):
    _sale(biz, qty="5", paid="500")
    page = _report_page(biz)
    page._apply_preset("custom", run=False)
    page._from_edit.setText("not-a-date")
    page._to_edit.setText("2026-06-30")
    page.run()
    assert page._last is None                    # nothing ran


def test_report_renders_in_dari(qapp, biz):
    _sale(biz, qty="5", paid="500")
    page = _report_page(biz, lang=LANG_DARI)
    _run_june(page)
    assert page._g_val.text() == "500.00"
    page.retranslate(Translator(LANG_DARI))
    assert page._g_val.text() == "500.00"


# ---- A4-only Sales Report print (requirement change) --------------------

def test_report_preview_exposes_a4_not_a5(qapp):
    """A detailed report has nine columns; A5 is intentionally not offered."""
    from zenith_business.ui.documents.sales_report_preview import SalesReportPreviewPage
    prev = SalesReportPreviewPage(_en(), on_back=lambda: None)
    assert "A4" in prev._paper_buttons
    assert "A5" not in prev._paper_buttons        # the A5 button is removed
    assert prev._paper_key == "A4"
    # any attempt to switch to A5 (programmatic) is ignored — stays A4
    prev._set_paper("A5"); assert prev._paper_key == "A4"
    prev.set_paper("A5"); assert prev._paper_key == "A4"


def test_report_preview_renders_a4_en_and_dari(qapp, biz):
    from zenith_business.ui.documents.sales_report_preview import SalesReportPreviewPage
    from zenith_business.ui.documents.print_builder import build_sales_report_print
    _sale(biz, qty="5", paid="500")
    page = _report_page(biz)
    _run_june(page)
    data = build_sales_report_print(biz, page._last)
    for lang in (LANG_ENGLISH, LANG_DARI):
        prev = SalesReportPreviewPage(Translator(lang), on_back=lambda: None)
        prev._lang = lang
        prev.show_report(data)
        assert prev._paper_key == "A4"
        assert prev._base is not None
        # A4 portrait width — the sheet is the full A4 width, never squeezed to A5
        from zenith_business.ui.print.invoice_document import PAPERS
        assert prev._base.width() == PAPERS["A4"].w


def test_report_print_document_keeps_all_columns_and_totals(qapp, biz):
    from PyQt6.QtWidgets import QTableWidget
    from zenith_business.core.i18n import Translator
    from zenith_business.ui.documents.print_builder import build_sales_report_print
    from zenith_business.ui.print.invoice_document import PAPERS
    from zenith_business.ui.print.sales_report_document import SalesReportPrintDocument
    _sale(biz, qty="5", paid="500")
    page = _report_page(biz)
    _run_june(page)
    data = build_sales_report_print(biz, page._last)
    doc = SalesReportPrintDocument(data, Translator(LANG_ENGLISH), PAPERS["A4"])
    table = doc.findChild(QTableWidget)
    # nine columns preserved: Date, Invoice #, Customer, Type, Gross, Paid,
    # Credit, Returned, Net
    assert table.columnCount() == 9
    # one detail row + a Total row
    assert table.rowCount() == 2
    total_label = table.item(1, 0).text()
    assert total_label == Translator(LANG_ENGLISH).gettext("rep.total")
    # totals column (Net) sums correctly
    assert table.item(1, 8).text() == "500.00"
    # no document-level horizontal scrollbar on the printed sheet
    from PyQt6.QtCore import Qt
    assert table.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff


def test_a5_still_available_for_vouchers(qapp):
    """A5 must NOT be globally removed — vouchers/invoices still offer it."""
    from zenith_business.core.i18n import Translator
    from zenith_business.ui.documents.voucher_preview import VoucherPreviewPage
    from zenith_business.ui.pages.print_preview import PrintPreviewPage
    voucher = VoucherPreviewPage(Translator(LANG_ENGLISH), on_back=lambda: None)
    assert "A5" in voucher._paper_buttons and "A4" in voucher._paper_buttons
    invoice = PrintPreviewPage(Translator(LANG_ENGLISH))
    assert "A5" in invoice._paper_buttons and "A4" in invoice._paper_buttons
