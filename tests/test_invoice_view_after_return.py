"""Reopening a saved sale must show its CURRENT position, not the posted one.

The owner's example: Rice 1 × 1980 + Sugar 1 × 1750 = 3730, Rice returned in
full. Reopening SALE-000001 must show Sugar alone with a Grand Total of 1750 —
Rice is no longer something the customer owes for — while the stored sale keeps
Rice 1 and the return document stays valid.

The screen derives; it never rewrites history. Saving a correction folds the
returned quantity back into the stored line, so the sold quantity and the return
survive untouched.
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
    ctx.rice = ctx.items.create(item_code="RICE", name="Rice", base_unit_id=ctx.bag,
                                purchase_price="1500", default_sale_price="1980",
                                reorder_level="5")
    ctx.sugar = ctx.items.create(item_code="SUGAR", name="Sugar", base_unit_id=ctx.bag,
                                 purchase_price="1200", default_sale_price="1750",
                                 reorder_level="5")
    ctx.cust = ctx.parties.create(party_code="C1", name="Ahmad Store", is_customer=True)
    for item in (ctx.rice, ctx.sugar):
        ctx.inventory.record_opening(item_id=item, warehouse_id=ctx.main,
                                     quantity_on_hand="10", movement_date="2026-05-01")
    return ctx


def _sell_rice_and_sugar(biz, paid="0"):
    """Rice 1 × 1980 + Sugar 1 × 1750 = 3730."""
    return biz.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=biz.main, party_id=biz.cust, amount_paid=paid,
        sale_date="2026-06-10",
        lines=[SaleLine(item_id=biz.rice, unit_id=biz.bag, quantity="1", unit_price="1980"),
               SaleLine(item_id=biz.sugar, unit_id=biz.bag, quantity="1", unit_price="1750")])


def _return_rice(biz, sale, quantity="1"):
    line = next(l for l in biz.sales_repo.lines_for(sale.id) if l["item_id"] == biz.rice)
    return biz.sales_documents.post_return(
        sale_id=sale.id, return_date="2026-06-11",
        lines=[ReturnLine(sale_line_id=line["id"], quantity=quantity)])


def _reopen(biz, sale_id, language=LANG_ENGLISH):
    from zenith_business.ui.documents.entry_page import DocumentEntryPage
    page = DocumentEntryPage(biz, Translator(language), mode="sale",
                             on_print=lambda i: None, on_close=lambda: None)
    page.load_for_correction(sale_id)
    return page


# ---- the reopened invoice shows the current position -----------------------

def test_untouched_invoice_reopens_with_every_line(biz, qapp):
    sale = _sell_rice_and_sugar(biz)
    page = _reopen(biz, sale.id)
    assert page.line_count == 2
    assert page._grand_value.text() == "3,730.00"
    assert page._returned_card.isVisibleTo(page) is False


def test_fully_returned_item_is_not_an_active_line(biz, qapp):
    sale = _sell_rice_and_sugar(biz)
    _return_rice(biz, sale)
    page = _reopen(biz, sale.id)
    names = [ln["name"] for ln in page._lines]
    assert names == ["Sugar"]
    assert "Rice" not in names


def test_reopened_grand_total_is_the_net_total(biz, qapp):
    sale = _sell_rice_and_sugar(biz)
    _return_rice(biz, sale)
    page = _reopen(biz, sale.id)
    assert page._grand_value.text() == "1,750.00"


def test_partial_return_reduces_the_active_quantity(biz, qapp):
    """Sold 4, returned 1 → the reopened line is payable for 3."""
    sale = biz.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=biz.main, party_id=biz.cust, amount_paid="0",
        sale_date="2026-06-10",
        lines=[SaleLine(item_id=biz.rice, unit_id=biz.bag, quantity="4", unit_price="1000")])
    line = biz.sales_repo.lines_for(sale.id)[0]
    biz.sales_documents.post_return(
        sale_id=sale.id, return_date="2026-06-11",
        lines=[ReturnLine(sale_line_id=line["id"], quantity="1")])
    page = _reopen(biz, sale.id)
    assert page.line_count == 1
    assert Decimal(page._lines[0]["qty"]) == Decimal("3")
    assert page._grand_value.text() == "3,000.00"


def test_returned_items_panel_lists_item_qty_amount_and_document(biz, qapp):
    sale = _sell_rice_and_sugar(biz)
    credit_note = _return_rice(biz, sale)
    page = _reopen(biz, sale.id)
    assert page._returned_card.isVisibleTo(page) is True
    assert page._ret_table.rowCount() == 1
    assert page._ret_table.item(0, 0).text() == "Rice"
    assert page._ret_table.item(0, 1).text() == "1.00"
    assert page._ret_table.item(0, 2).text() == "1,980.00"
    assert page._ret_table.item(0, 3).text() == credit_note.document_no


def test_returned_items_panel_is_titled_in_both_languages(biz, qapp):
    sale = _sell_rice_and_sugar(biz)
    _return_rice(biz, sale)
    for language, title in ((LANG_ENGLISH, "Returned Items"), (LANG_DARI, "اقلام برگشتی")):
        page = _reopen(biz, sale.id, language)
        titles = [w.text() for w in page._returned_card.findChildren(type(page._title))]
        assert title in titles
        assert page.line_count == 1
        assert page._grand_value.text() == "1,750.00"


# ---- the screen agrees with every other surface ----------------------------

def test_invoice_view_agrees_with_list_print_balance_and_reports(biz, qapp):
    from zenith_business.ui.documents.print_builder import build_sale_invoice
    sale = _sell_rice_and_sugar(biz)
    _return_rice(biz, sale)
    page = _reopen(biz, sale.id)
    row = biz.sales_documents.list()[0]
    data, _title = build_sale_invoice(biz, sale.id)
    summary = biz.sales_reports.summary(date_from="2026-01-01", date_to="2026-12-31")

    assert page._grand_value.text() == "1,750.00"      # invoice view
    assert row["net_total"] == "1750.00"               # sales list
    assert data.grand_total == 1750.0                  # printed invoice
    assert summary["net"] == "1750.00"                 # reports
    assert Decimal(biz.sales_documents.receivable(biz.cust)) == Decimal("1750")


def test_previous_balance_excludes_this_invoice_and_updated_matches_the_account(biz, qapp):
    """Previous Balance is the account balance BEFORE this invoice, never a
    dumping ground for returned goods."""
    sale = _sell_rice_and_sugar(biz)
    _return_rice(biz, sale)
    page = _reopen(biz, sale.id)
    assert page._prev_value.text() == "0.00"
    assert page._upd_value.text() == "1,750.00"        # = the customer's receivable


def test_previous_balance_carries_an_older_unpaid_invoice(biz, qapp):
    older = biz.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=biz.main, party_id=biz.cust, amount_paid="0",
        sale_date="2026-06-01",
        lines=[SaleLine(item_id=biz.sugar, unit_id=biz.bag, quantity="1", unit_price="200")])
    assert older.document_no
    sale = _sell_rice_and_sugar(biz)
    _return_rice(biz, sale)
    page = _reopen(biz, sale.id)
    assert page._prev_value.text() == "200.00"
    assert page._upd_value.text() == "1,950.00"
    assert Decimal(biz.sales_documents.receivable(biz.cust)) == Decimal("1950")


def test_reopened_paid_amount_is_what_was_actually_paid(biz, qapp):
    """A return is a credit; it does not claim back cash the customer kept."""
    sale = _sell_rice_and_sugar(biz, paid="3730")
    _return_rice(biz, sale)
    page = _reopen(biz, sale.id)
    assert page._recv_edit.text() == "3,730.00"
    assert page._rem_value.text() == "-1,980.00"       # a refund owed back
    row = biz.sales_documents.list()[0]
    assert row["net_remaining"] == "-1980.00"          # the Sales List says the same
    assert Decimal(biz.sales_documents.receivable(biz.cust)) == Decimal("-1980")


# ---- history is preserved --------------------------------------------------

def test_reopening_never_rewrites_the_stored_sale(biz, qapp):
    sale = _sell_rice_and_sugar(biz)
    _return_rice(biz, sale)
    _reopen(biz, sale.id)
    stored = {biz.items_repo.get(l["item_id"])["name"]: l["quantity"]
              for l in biz.sales_repo.lines_for(sale.id)}
    assert Decimal(stored["Rice"]) == Decimal("1")
    assert Decimal(biz.sales_repo.get(sale.id)["grand_total"]) == Decimal("3730")
    assert len(biz.sales_returns_repo.list_for_sale(sale.id)) == 1


def test_saving_from_the_net_view_keeps_the_returned_line(biz, qapp):
    """Correcting Sugar 1 → 2 must not silently drop the returned Rice."""
    sale = _sell_rice_and_sugar(biz)
    _return_rice(biz, sale)
    page = _reopen(biz, sale.id)
    page._lines[0]["qty"] = "2"
    page._render_lines()
    page._recompute_totals()
    page._post(print_after=False)

    stored = {biz.items_repo.get(l["item_id"])["name"]: l["quantity"]
              for l in biz.sales_repo.lines_for(sale.id)}
    assert Decimal(stored["Rice"]) == Decimal("1")     # history kept
    assert Decimal(stored["Sugar"]) == Decimal("2")    # the correction applied
    assert len(biz.sales_documents.list()) == 1        # still ONE invoice
    assert biz.sales_documents.list()[0]["document_no"] == sale.document_no
    assert biz.sales_documents.list()[0]["net_total"] == "3500.00"
    assert Decimal(biz.sales_documents.receivable(biz.cust)) == Decimal("3500")
    assert len(biz.sales_returns_repo.list_for_sale(sale.id)) == 1


def test_saving_an_untouched_reopened_invoice_changes_nothing(biz, qapp):
    sale = _sell_rice_and_sugar(biz)
    _return_rice(biz, sale)
    before = biz.sales_repo.get(sale.id)["grand_total"]
    page = _reopen(biz, sale.id)
    page._post(print_after=False)
    assert biz.sales_repo.get(sale.id)["grand_total"] == before
    assert biz.sales_documents.list()[0]["net_total"] == "1750.00"
    assert Decimal(biz.sales_documents.receivable(biz.cust)) == Decimal("1750")
    assert Decimal(biz.inventory.on_hand(biz.rice)) == Decimal("10")
    assert Decimal(biz.inventory.on_hand(biz.sugar)) == Decimal("9")


def test_reopening_after_a_correction_shows_the_corrected_net(biz, qapp):
    sale = _sell_rice_and_sugar(biz)
    _return_rice(biz, sale)
    page = _reopen(biz, sale.id)
    page._lines[0]["qty"] = "2"
    page._render_lines(); page._recompute_totals()
    page._post(print_after=False)

    again = _reopen(biz, sale.id)
    assert again.line_count == 1
    assert again._lines[0]["name"] == "Sugar"
    assert Decimal(again._lines[0]["qty"]) == Decimal("2")
    assert again._grand_value.text() == "3,500.00"


def test_a_new_invoice_is_unaffected_by_any_of_this(biz, qapp):
    """The returned-items machinery must not leak into a fresh invoice."""
    from zenith_business.ui.documents.entry_page import DocumentEntryPage
    sale = _sell_rice_and_sugar(biz)
    _return_rice(biz, sale)
    page = DocumentEntryPage(biz, Translator(LANG_ENGLISH), mode="sale",
                             on_print=lambda i: None, on_close=lambda: None)
    page.load_for_correction(sale.id)
    page.reset_form()
    assert page.line_count == 0
    assert page._returned_by_item == {}
    assert page._paid_override is None
    assert page._returned_card.isVisibleTo(page) is False
    assert page._prev_value.text() == "0.00"
