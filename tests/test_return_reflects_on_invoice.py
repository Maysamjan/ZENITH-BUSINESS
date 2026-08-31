"""A sales return must update the ORIGINAL invoice visibly, everywhere.

The owner's acceptance example: sell Rice 5 x 100 = 500, return 1. Afterwards the
stock is up by one, there is still exactly ONE invoice carrying its original
number, and every surface that reports a figure for that invoice — the Sales
List, the invoice itself, the printed copy, the Sales Report, the customer's
receivable and the stock ledger — agrees on 400.

The sale document is never rewritten: the sold quantities and the invoiced total
stay as the historical record, and the current position is derived from the
return documents. These tests pin that contract so a future change cannot
silently go back to showing the pre-return numbers.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from zenith_business.core.i18n import LANG_DARI, LANG_ENGLISH, Translator
from zenith_business.services.sales_documents import ReturnLine, SaleLine


@pytest.fixture
def biz(admin_context):
    ctx = admin_context
    ctx.financial_years.create(name="FY26", start_date="2026-01-01", end_date="2026-12-31",
                               make_active=True)
    ctx.main = ctx.warehouses.create(code="MAIN", name="Main Store", is_default=True)
    ctx.bag = ctx.units_repo.id_by_code("BAG")
    ctx.rice = ctx.items.create(item_code="RICE", name="Rice", alternate_name="برنج",
                                base_unit_id=ctx.bag, purchase_price="60",
                                default_sale_price="100", reorder_level="5")
    ctx.cust = ctx.parties.create(party_code="C1", name="Ahmad Store", is_customer=True)
    ctx.inventory.record_opening(item_id=ctx.rice, warehouse_id=ctx.main,
                                 quantity_on_hand="10", movement_date="2026-05-01")
    return ctx


def _sell_five(biz, paid="0"):
    """Rice 5 x 100 = 500 on credit (paid=0) unless the caller settles it."""
    return biz.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=biz.main, party_id=biz.cust, amount_paid=paid,
        sale_date="2026-06-10",
        lines=[SaleLine(item_id=biz.rice, unit_id=biz.bag, quantity="5", unit_price="100")])


def _return_one(biz, sale, notes=None):
    line_id = biz.sales_repo.lines_for(sale.id)[0]["id"]
    return biz.sales_documents.post_return(
        sale_id=sale.id, return_date="2026-06-11", notes=notes,
        lines=[ReturnLine(sale_line_id=line_id, quantity="1")])


# ---- 1. stock -------------------------------------------------------------

def test_return_increases_stock_by_the_returned_quantity(biz):
    sale = _sell_five(biz)
    assert Decimal(biz.inventory.on_hand(biz.rice)) == Decimal("5")
    _return_one(biz, sale)
    assert Decimal(biz.inventory.on_hand(biz.rice)) == Decimal("6")


def test_return_adds_one_movement_and_never_re_posts_the_sale(biz):
    sale = _sell_five(biz)
    _return_one(biz, sale)
    kinds = [m["movement_type"] for m in biz.inventory.movement_history(item_id=biz.rice)]
    assert kinds.count("SALE") == 1          # the sale is not deducted twice
    assert kinds.count("SALE_RETURN") == 1


# ---- 2. same document, no duplicate ---------------------------------------

def test_return_does_not_create_a_second_invoice(biz):
    sale = _sell_five(biz)
    _return_one(biz, sale)
    rows = biz.sales_documents.list()
    assert len(rows) == 1
    assert rows[0]["document_no"] == sale.document_no
    assert rows[0]["status"] == "POSTED"


def test_sale_document_itself_is_never_rewritten(biz):
    """Sold quantity and invoiced total stay as the historical record."""
    sale = _sell_five(biz)
    _return_one(biz, sale)
    line = biz.sales_repo.lines_for(sale.id)[0]
    assert Decimal(line["quantity"]) == Decimal("5")
    assert Decimal(biz.sales_repo.get(sale.id)["grand_total"]) == Decimal("500")


# ---- 3. the Sales List shows the financially correct amounts ---------------

def test_sales_list_shows_gross_returned_net_and_remaining(biz):
    sale = _sell_five(biz)
    before = biz.sales_documents.list()[0]
    assert (before["grand_total"], before["returned_total"], before["net_total"],
            before["net_remaining"]) == ("500.00", "0.00", "500.00", "500.00")
    _return_one(biz, sale)
    after = biz.sales_documents.list()[0]
    assert after["grand_total"] == "500.00"      # still auditable
    assert after["returned_total"] == "100.00"
    assert after["net_total"] == "400.00"
    assert after["net_remaining"] == "400.00"    # what the customer still owes


def test_returning_against_a_paid_invoice_shows_a_refund_owed(biz):
    """Cash invoice fully paid, then returned: remaining goes negative (refund due)."""
    sale = _sell_five(biz, paid="500")
    _return_one(biz, sale)
    row = biz.sales_documents.list()[0]
    assert row["net_total"] == "400.00"
    assert row["amount_paid"] == "500.00"
    assert row["net_remaining"] == "-100.00"
    # ...and that is exactly the customer's ledger position.
    assert Decimal(biz.sales_documents.receivable(biz.cust)) == Decimal("-100")


def test_sales_list_columns_use_the_net_figures(biz, qapp):
    from zenith_business.ui.documents.list_page import DocumentListPage
    sale = _sell_five(biz)
    _return_one(biz, sale)
    page = DocumentListPage(biz, Translator(LANG_ENGLISH), mode="sale")
    heads = [page._table.horizontalHeaderItem(i).text()
             for i in range(page._table.columnCount())]
    row = {h: (page._table.item(0, i).text() if page._table.item(0, i) else "")
           for i, h in enumerate(heads)}
    assert row["Invoiced"] == "500.00"
    assert row["Returned"] == "100.00"
    assert row["Net Total"] == "400.00"
    assert row["Remaining"] == "400.00"


# ---- 4. the invoice clearly shows what came back --------------------------

def test_net_view_reports_sold_returned_and_net_per_line(biz):
    sale = _sell_five(biz)
    _return_one(biz, sale)
    view = biz.sales_documents.net_view(sale.id)
    line = view["lines"][0]
    assert Decimal(line["sold"]) == Decimal("5")
    assert Decimal(line["returned"]) == Decimal("1")
    assert Decimal(line["net_quantity"]) == Decimal("4")
    assert line["net_line_total"] == "400.00"
    assert view["net_total"] == "400.00"
    assert view["has_returns"] is True


def test_printed_invoice_shows_the_net_quantity(biz, qapp):
    from zenith_business.ui.documents.print_builder import build_sale_invoice
    sale = _sell_five(biz)
    _return_one(biz, sale)
    data, _title = build_sale_invoice(biz, sale.id)
    assert len(data.lines) == 1
    assert data.lines[0].qty == 4.0


def test_return_screen_shows_sold_already_returned_and_returnable(biz, qapp):
    from zenith_business.ui.documents.return_page import ReturnEntryPage
    sale = _sell_five(biz)
    _return_one(biz, sale)
    page = ReturnEntryPage(biz, Translator(LANG_ENGLISH), mode="sales_return",
                           on_close=lambda: None, on_print=lambda i: None)
    page._src_edit.setText(sale.document_no)
    page._load_source()
    line = page._lines[0]
    assert Decimal(line["sold"]) == Decimal("5")
    assert Decimal(line["returned"]) == Decimal("1")
    assert Decimal(line["returnable"]) == Decimal("4")


# ---- 5. the human-readable note -------------------------------------------

def test_service_saves_a_readable_note_when_none_is_supplied(biz):
    sale = _sell_five(biz)
    ret = _return_one(biz, sale)
    assert biz.sales_returns_repo.get(ret.id)["notes"] == "Rice — Qty 1 returned."


def test_return_screen_builds_the_note_in_the_operator_language(biz, qapp):
    from zenith_business.ui.documents.return_page import ReturnEntryPage
    sale = _sell_five(biz)

    def note_for(language):
        page = ReturnEntryPage(biz, Translator(language), mode="sales_return",
                               on_close=lambda: None, on_print=lambda i: None)
        page._src_edit.setText(sale.document_no)
        page._load_source()
        page._return_edits[0].setText("1")
        return page._return_note(page._collect_return_lines())

    assert note_for(LANG_ENGLISH) == "Rice — Qty 1 returned."
    # Dari names the item by its Dari name, not the English one.
    assert note_for(LANG_DARI) == "برنج به تعداد 1 دانه برگشت شد."


def test_note_is_visible_in_the_returns_list(biz, qapp):
    from zenith_business.ui.documents.list_page import DocumentListPage
    sale = _sell_five(biz)
    _return_one(biz, sale)
    page = DocumentListPage(biz, Translator(LANG_ENGLISH), mode="sales_return")
    heads = [page._table.horizontalHeaderItem(i).text()
             for i in range(page._table.columnCount())]
    assert "Note" in heads
    assert page._table.item(0, heads.index("Note")).text() == "Rice — Qty 1 returned."
    assert page._table.item(0, heads.index("Source Doc")).text() == sale.document_no


# ---- 6. everything reconciles ---------------------------------------------

def test_sales_report_keeps_gross_and_returns_separate_with_net_400(biz):
    sale = _sell_five(biz)
    _return_one(biz, sale)
    summary = biz.sales_reports.summary(date_from="2026-01-01", date_to="2026-12-31")
    assert summary["gross"] == "500.00"
    assert summary["returns"] == "100.00"
    assert summary["net"] == "400.00"


def test_customer_receivable_drops_by_the_returned_value(biz):
    sale = _sell_five(biz)
    assert Decimal(biz.sales_documents.receivable(biz.cust)) == Decimal("500")
    _return_one(biz, sale)
    assert Decimal(biz.sales_documents.receivable(biz.cust)) == Decimal("400")


def test_return_history_survives_and_limits_further_returns(biz):
    sale = _sell_five(biz)
    _return_one(biz, sale)
    line_id = biz.sales_repo.lines_for(sale.id)[0]["id"]
    assert len(biz.sales_returns_repo.list_for_sale(sale.id)) == 1
    assert Decimal(biz.sales_documents.returnable_quantities(sale.id)[line_id]) == Decimal("4")
