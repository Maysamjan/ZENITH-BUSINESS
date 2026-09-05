"""Stage 07 — purchases parity: a bill behaves exactly like an invoice.

Everything the sales side had to learn across three owner review rounds now holds
for purchases too. The contract these tests pin:

    Purchase List = Purchase Invoice View = Printed Purchase Invoice
                  = Purchase Return = Supplier Balance = Inventory = Stock Movement

Nothing stores its own copy of a figure: the list, the reopened bill, the print
and the supplier balance all read ``net_view`` or the movement ledger. A return
never rewrites the bill, and a correction amends the SAME document in place.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from zenith_business.core.i18n import LANG_DARI, LANG_ENGLISH, Translator
from zenith_business.services.exceptions import ValidationError
from zenith_business.services.purchase_documents import PurchaseLine, PurchaseReturnLine


@pytest.fixture
def biz(admin_context):
    ctx = admin_context
    ctx.financial_years.create(name="FY26", start_date="2026-01-01", end_date="2026-12-31",
                               make_active=True)
    ctx.main = ctx.warehouses.create(code="MAIN", name="Main Store", is_default=True)
    ctx.bag = ctx.units_repo.id_by_code("BAG")
    # A real Dari name, so the Dari screens can be checked for real.
    ctx.rice = ctx.items.create(item_code="RICE", name="Rice", alternate_name="برنج",
                                base_unit_id=ctx.bag, purchase_price="100",
                                default_sale_price="150", reorder_level="5")
    ctx.sugar = ctx.items.create(item_code="SUGAR", name="Sugar", base_unit_id=ctx.bag,
                                 purchase_price="80", default_sale_price="120",
                                 reorder_level="5")
    ctx.sup = ctx.parties.create(party_code="S1", name="Karim Supply", is_supplier=True)
    return ctx


def _buy(biz, qty="10", price="100", paid="0", item=None):
    """Rice 10 × 100 = 1000 on credit unless the caller settles it."""
    return biz.purchase_documents.post_purchase(
        currency_code="AFN", warehouse_id=biz.main, party_id=biz.sup, amount_paid=paid,
        purchase_date="2026-06-01",
        lines=[PurchaseLine(item_id=item or biz.rice, unit_id=biz.bag,
                            quantity=qty, unit_price=price)])


def _return(biz, purchase, qty="4", notes=None):
    line = biz.purchases_repo.lines_for(purchase.id)[0]
    return biz.purchase_documents.post_return(
        purchase_id=purchase.id, return_date="2026-06-02", notes=notes,
        lines=[PurchaseReturnLine(purchase_line_id=line["id"], quantity=qty)])


def _reopen(biz, purchase_id, language=LANG_ENGLISH):
    from zenith_business.ui.documents.entry_page import DocumentEntryPage
    page = DocumentEntryPage(biz, Translator(language), mode="purchase",
                             on_print=lambda i: None, on_close=lambda: None)
    page.load_purchase_for_correction(purchase_id)
    return page


# ---- 1. supplier integrity ------------------------------------------------

def test_credit_purchase_without_a_supplier_is_refused(biz):
    """An unpaid balance has to be owed to somebody — otherwise the payable posts
    with no party and no supplier ledger can ever show it."""
    with pytest.raises(ValidationError):
        biz.purchase_documents.post_purchase(
            currency_code="AFN", warehouse_id=biz.main, party_id=None, amount_paid="0",
            purchase_date="2026-06-01",
            lines=[PurchaseLine(item_id=biz.rice, unit_id=biz.bag,
                                quantity="5", unit_price="100")])


def test_partly_paid_purchase_without_a_supplier_is_refused(biz):
    with pytest.raises(ValidationError):
        biz.purchase_documents.post_purchase(
            currency_code="AFN", warehouse_id=biz.main, party_id=None, amount_paid="200",
            purchase_date="2026-06-01",
            lines=[PurchaseLine(item_id=biz.rice, unit_id=biz.bag,
                                quantity="5", unit_price="100")])


def test_cash_purchase_without_a_supplier_is_still_allowed(biz):
    """Nothing is owed, so nobody needs to be named."""
    posted = biz.purchase_documents.post_purchase(
        currency_code="AFN", warehouse_id=biz.main, party_id=None, amount_paid="500",
        purchase_date="2026-06-01",
        lines=[PurchaseLine(item_id=biz.rice, unit_id=biz.bag,
                            quantity="5", unit_price="100")])
    assert posted.remaining == "0.00"


# ---- 2. the payment model -------------------------------------------------

def test_cash_credit_and_partial_on_the_purchase_screen(biz, qapp):
    from zenith_business.ui.documents.entry_page import DocumentEntryPage
    from zenith_business.ui.widgets.search_selector import SearchRow
    page = DocumentEntryPage(biz, Translator(LANG_ENGLISH), mode="purchase",
                             on_print=lambda i: None, on_close=lambda: None)
    page.set_party(SearchRow(values=["S1", "Karim Supply"], payload={"party_id": biz.sup}))
    page.add_line({"item_id": biz.rice, "base_unit_id": biz.bag, "item_code": "RICE",
                   "name": "Rice", "unit_symbol": "bag"}, qty="10", price="100")
    assert page._grand_value.text() == "1,000.00"

    page.set_payment_type("cash")
    assert page.amount_paid == "1,000.00"
    assert page.remaining == "0.00"
    assert page._recv_edit.isReadOnly() is True     # derived, never typed

    page.set_payment_type("credit")
    assert page.amount_paid == "0.00"
    assert page.remaining == "1,000.00"

    page.set_payment_type("partial")
    assert page._recv_edit.isReadOnly() is False    # the operator types it
    page._recv_edit.setText("300")
    page._on_paid_typed()
    assert page.remaining == "700.00"


def test_partial_amount_cannot_exceed_the_total(biz, qapp):
    from zenith_business.ui.documents.entry_page import DocumentEntryPage
    page = DocumentEntryPage(biz, Translator(LANG_ENGLISH), mode="purchase",
                             on_print=lambda i: None, on_close=lambda: None)
    page.add_line({"item_id": biz.rice, "base_unit_id": biz.bag, "item_code": "RICE",
                   "name": "Rice", "unit_symbol": "bag"}, qty="10", price="100")
    page.set_payment_type("partial")
    page._recv_edit.setText("1500")
    page._on_paid_typed()
    assert page._error.isVisibleTo(page) is True
    assert page.remaining == "0.00"                 # clamped to the grand total


def test_partial_amount_cannot_be_negative(biz, qapp):
    from zenith_business.ui.documents.entry_page import DocumentEntryPage
    page = DocumentEntryPage(biz, Translator(LANG_ENGLISH), mode="purchase",
                             on_print=lambda i: None, on_close=lambda: None)
    page.add_line({"item_id": biz.rice, "base_unit_id": biz.bag, "item_code": "RICE",
                   "name": "Rice", "unit_symbol": "bag"}, qty="10", price="100")
    page.set_payment_type("partial")
    page._recv_edit.setText("-5")
    page._on_paid_typed()
    assert page._error.isVisibleTo(page) is True


def test_remaining_recalculates_when_the_bill_changes(biz, qapp):
    from zenith_business.ui.documents.entry_page import DocumentEntryPage
    page = DocumentEntryPage(biz, Translator(LANG_ENGLISH), mode="purchase",
                             on_print=lambda i: None, on_close=lambda: None)
    page.add_line({"item_id": biz.rice, "base_unit_id": biz.bag, "item_code": "RICE",
                   "name": "Rice", "unit_symbol": "bag"}, qty="10", price="100")
    page.set_payment_type("partial")
    page._recv_edit.setText("300"); page._on_paid_typed()
    assert page.remaining == "700.00"
    page._lines[0]["qty"] = "12"                    # the bill grows
    page._render_lines(); page._recompute_totals()
    assert page._grand_value.text() == "1,200.00"
    assert page.remaining == "900.00"


def test_a_sale_never_offers_partial(biz, qapp):
    """A part-paid sale is a Credit invoice plus a Receipt — not a typed amount."""
    from zenith_business.ui.documents.entry_page import DocumentEntryPage
    page = DocumentEntryPage(biz, Translator(LANG_ENGLISH), mode="sale",
                             on_print=lambda i: None, on_close=lambda: None)
    assert page._seg_partial.isVisibleTo(page) is False
    page.set_payment_type("partial")
    assert page.payment_type() == "cash"             # falls back, never partial


# ---- 3. a return reflects on the bill everywhere --------------------------

def test_return_updates_stock_list_and_supplier_balance(biz):
    purchase = _buy(biz)
    assert Decimal(biz.inventory.on_hand(biz.rice)) == Decimal("10")
    assert Decimal(biz.purchase_documents.payable(biz.sup)) == Decimal("1000")
    _return(biz, purchase, "4")
    assert Decimal(biz.inventory.on_hand(biz.rice)) == Decimal("6")
    row = biz.purchase_documents.list()[0]
    assert row["grand_total"] == "1000.00"           # still auditable
    assert row["returned_total"] == "400.00"
    assert row["net_total"] == "600.00"
    assert row["net_remaining"] == "600.00"
    assert Decimal(biz.purchase_documents.payable(biz.sup)) == Decimal("600")


def test_net_view_reports_bought_returned_and_net(biz):
    purchase = _buy(biz)
    _return(biz, purchase, "4")
    view = biz.purchase_documents.net_view(purchase.id)
    line = view["lines"][0]
    assert Decimal(line["bought"]) == Decimal("10")
    assert Decimal(line["returned"]) == Decimal("4")
    assert Decimal(line["net_quantity"]) == Decimal("6")
    assert view["net_total"] == "600.00"
    assert view["has_returns"] is True


def test_printed_bill_shows_the_net_quantity(biz, qapp):
    from zenith_business.ui.documents.print_builder import build_purchase_invoice
    purchase = _buy(biz)
    _return(biz, purchase, "4")
    data, _title = build_purchase_invoice(biz, purchase.id)
    assert data.lines[0].qty == 6.0
    assert data.grand_total == 600.0


def test_fully_returned_bill_prints_an_explanation(biz, qapp):
    from zenith_business.ui.documents.print_builder import build_purchase_invoice
    purchase = _buy(biz)
    _return(biz, purchase, "10")
    data, _title = build_purchase_invoice(biz, purchase.id)
    assert data.lines == []
    assert data.note_key == "print.fully_returned"
    row = biz.purchase_documents.list()[0]
    assert row["net_total"] == "0.00"
    assert Decimal(biz.purchase_documents.payable(biz.sup)) == Decimal("0")


def test_purchase_return_saves_a_readable_note(biz):
    purchase = _buy(biz)
    credit = _return(biz, purchase, "4")
    assert biz.purchase_returns_repo.get(credit.id)["notes"] == "Rice — Qty 4 returned."


def test_return_note_is_visible_in_the_returns_list(biz, qapp):
    from zenith_business.ui.documents.list_page import DocumentListPage
    purchase = _buy(biz)
    credit = _return(biz, purchase, "4")
    page = DocumentListPage(biz, Translator(LANG_ENGLISH), mode="purchase_return")
    heads = [page._table.horizontalHeaderItem(i).text()
             for i in range(page._table.columnCount())]
    assert page._table.item(0, heads.index("Note")).text() == "Rice — Qty 4 returned."
    assert page._table.item(0, heads.index("Source Doc")).text() == purchase.document_no
    assert credit.document_no


# ---- 4. reopening a bill shows its current state --------------------------

def test_reopened_bill_shows_the_net_position(biz, qapp):
    purchase = _buy(biz)
    _return(biz, purchase, "4")
    page = _reopen(biz, purchase.id)
    assert page.line_count == 1
    assert Decimal(page._lines[0]["qty"]) == Decimal("6")
    assert page._grand_value.text() == "600.00"
    assert page._returned_card.isVisibleTo(page) is True
    assert page._ret_table.item(0, 0).text() == "Rice"
    assert page._ret_table.item(0, 1).text() == "4.00"


def test_fully_returned_line_leaves_the_payable_grid(biz, qapp):
    purchase = biz.purchase_documents.post_purchase(
        currency_code="AFN", warehouse_id=biz.main, party_id=biz.sup, amount_paid="0",
        purchase_date="2026-06-01",
        lines=[PurchaseLine(item_id=biz.rice, unit_id=biz.bag, quantity="5", unit_price="100"),
               PurchaseLine(item_id=biz.sugar, unit_id=biz.bag, quantity="2", unit_price="80")])
    rice_line = next(l for l in biz.purchases_repo.lines_for(purchase.id)
                     if l["item_id"] == biz.rice)
    biz.purchase_documents.post_return(
        purchase_id=purchase.id, return_date="2026-06-02",
        lines=[PurchaseReturnLine(purchase_line_id=rice_line["id"], quantity="5")])
    page = _reopen(biz, purchase.id)
    assert [ln["name"] for ln in page._lines] == ["Sugar"]
    assert page._grand_value.text() == "160.00"


def test_reopened_previous_balance_excludes_this_bill(biz, qapp):
    purchase = _buy(biz)
    _return(biz, purchase, "4")
    page = _reopen(biz, purchase.id)
    assert page._prev_value.text() == "0.00"
    assert page._upd_value.text() == "600.00"        # = the supplier's payable


def test_reopened_bill_shows_the_recorded_payment_type(biz, qapp):
    for paid, expected in (("0", "credit"), ("1000", "cash"), ("300", "partial")):
        purchase = _buy(biz, paid=paid)
        page = _reopen(biz, purchase.id)
        assert page.payment_type() == expected


def test_reopening_in_dari_agrees_with_english(biz, qapp):
    purchase = _buy(biz)
    _return(biz, purchase, "4")
    for language in (LANG_ENGLISH, LANG_DARI):
        page = _reopen(biz, purchase.id, language)
        assert page.line_count == 1
        assert page._grand_value.text() == "600.00"
        assert page._returned_card.isVisibleTo(page) is True


# ---- 5. correction amends the SAME bill -----------------------------------

def test_correction_keeps_one_bill_with_its_number(biz):
    purchase = _buy(biz)
    biz.purchase_documents.correct_purchase(
        purchase_id=purchase.id, currency_code="AFN", warehouse_id=biz.main,
        party_id=biz.sup, amount_paid="0", purchase_date="2026-06-01",
        lines=[PurchaseLine(item_id=biz.rice, unit_id=biz.bag, quantity="8",
                            unit_price="100")])
    rows = biz.purchase_documents.list()
    assert len(rows) == 1
    assert rows[0]["document_no"] == purchase.document_no
    assert rows[0]["status"] == "POSTED"
    assert Decimal(biz.inventory.on_hand(biz.rice)) == Decimal("8")
    assert Decimal(biz.purchase_documents.payable(biz.sup)) == Decimal("800")


def test_correction_after_a_return_keeps_the_return(biz):
    purchase = _buy(biz)
    _return(biz, purchase, "4")
    biz.purchase_documents.correct_purchase(
        purchase_id=purchase.id, currency_code="AFN", warehouse_id=biz.main,
        party_id=biz.sup, amount_paid="0", purchase_date="2026-06-01",
        lines=[PurchaseLine(item_id=biz.rice, unit_id=biz.bag, quantity="8",
                            unit_price="100")])
    assert Decimal(biz.purchases_repo.get(purchase.id)["grand_total"]) == Decimal("800")
    assert biz.purchase_documents.list()[0]["net_total"] == "400.00"
    assert Decimal(biz.purchase_documents.payable(biz.sup)) == Decimal("400")
    assert Decimal(biz.inventory.on_hand(biz.rice)) == Decimal("4")
    assert len(biz.purchase_returns_repo.list_for_purchase(purchase.id)) == 1


def test_correction_below_the_returned_quantity_is_refused(biz):
    purchase = _buy(biz)
    _return(biz, purchase, "4")
    with pytest.raises(ValidationError):
        biz.purchase_documents.correct_purchase(
            purchase_id=purchase.id, currency_code="AFN", warehouse_id=biz.main,
            party_id=biz.sup, amount_paid="0", purchase_date="2026-06-01",
            lines=[PurchaseLine(item_id=biz.rice, unit_id=biz.bag, quantity="2",
                                unit_price="100")])


def test_correction_cannot_drop_a_returned_item(biz):
    purchase = biz.purchase_documents.post_purchase(
        currency_code="AFN", warehouse_id=biz.main, party_id=biz.sup, amount_paid="0",
        purchase_date="2026-06-01",
        lines=[PurchaseLine(item_id=biz.rice, unit_id=biz.bag, quantity="5", unit_price="100"),
               PurchaseLine(item_id=biz.sugar, unit_id=biz.bag, quantity="2", unit_price="80")])
    rice_line = next(l for l in biz.purchases_repo.lines_for(purchase.id)
                     if l["item_id"] == biz.rice)
    biz.purchase_documents.post_return(
        purchase_id=purchase.id, return_date="2026-06-02",
        lines=[PurchaseReturnLine(purchase_line_id=rice_line["id"], quantity="2")])
    with pytest.raises(ValidationError):
        biz.purchase_documents.correct_purchase(
            purchase_id=purchase.id, currency_code="AFN", warehouse_id=biz.main,
            party_id=biz.sup, amount_paid="0", purchase_date="2026-06-01",
            lines=[PurchaseLine(item_id=biz.sugar, unit_id=biz.bag, quantity="2",
                                unit_price="80")])


def test_saving_a_reopened_bill_keeps_the_returned_line(biz, qapp):
    purchase = _buy(biz)
    _return(biz, purchase, "4")
    page = _reopen(biz, purchase.id)
    page._lines[0]["qty"] = "4"                      # net 4 + 4 returned = 8 stored
    page._render_lines(); page._recompute_totals()
    page._post(print_after=False)
    assert Decimal(biz.purchases_repo.get(purchase.id)["grand_total"]) == Decimal("800")
    assert len(biz.purchase_documents.list()) == 1
    assert len(biz.purchase_returns_repo.list_for_purchase(purchase.id)) == 1
    assert biz.purchase_documents.list()[0]["net_total"] == "400.00"


def test_correction_posts_a_difference_only_journal(biz):
    """The bill is never journalled twice — only the delta moves."""
    purchase = _buy(biz)
    before = biz.db.connection().execute(
        "SELECT COUNT(*) FROM financial_entries WHERE source_type = 'PURCHASE'").fetchone()[0]
    biz.purchase_documents.correct_purchase(
        purchase_id=purchase.id, currency_code="AFN", warehouse_id=biz.main,
        party_id=biz.sup, amount_paid="0", purchase_date="2026-06-01",
        lines=[PurchaseLine(item_id=biz.rice, unit_id=biz.bag, quantity="8",
                            unit_price="100")])
    after = biz.db.connection().execute(
        "SELECT COUNT(*) FROM financial_entries WHERE source_type = 'PURCHASE'").fetchone()[0]
    assert after == before                            # no second purchase entry
    corrections = biz.db.connection().execute(
        "SELECT COUNT(*) FROM financial_entries"
        " WHERE source_type = 'PURCHASE_CORRECTION'").fetchone()[0]
    assert corrections == 1
    assert Decimal(biz.purchase_documents.payable(biz.sup)) == Decimal("800")


def test_a_no_op_correction_posts_no_journal(biz):
    purchase = _buy(biz)
    biz.purchase_documents.correct_purchase(
        purchase_id=purchase.id, currency_code="AFN", warehouse_id=biz.main,
        party_id=biz.sup, amount_paid="0", purchase_date="2026-06-01",
        lines=[PurchaseLine(item_id=biz.rice, unit_id=biz.bag, quantity="10",
                            unit_price="100")])
    corrections = biz.db.connection().execute(
        "SELECT COUNT(*) FROM financial_entries"
        " WHERE source_type = 'PURCHASE_CORRECTION'").fetchone()[0]
    assert corrections == 0


# ---- 6. void --------------------------------------------------------------

def test_void_reverses_stock_ledger_and_payable(biz):
    purchase = _buy(biz)
    biz.purchase_documents.void_purchase(purchase_id=purchase.id, reason="wrong supplier")
    assert Decimal(biz.inventory.on_hand(biz.rice)) == Decimal("0")
    assert Decimal(biz.purchase_documents.payable(biz.sup)) == Decimal("0")
    assert biz.purchases_repo.get(purchase.id)["status"] == "VOID"


def test_void_is_blocked_while_a_return_exists(biz):
    purchase = _buy(biz)
    _return(biz, purchase, "4")
    with pytest.raises(ValidationError):
        biz.purchase_documents.void_purchase(purchase_id=purchase.id)


# ---- 7. supplier payments stay a separate document ------------------------

def test_a_supplier_payment_never_touches_the_bill(biz):
    """Later payment is settlement, not a change to what was bought."""
    purchase = _buy(biz)
    cash = biz.accounts_repo.id_by_code("1000")
    biz.payments.post_payment(party_id=biz.sup, account_id=cash, amount="200",
                              currency_code="AFN", payment_date="2026-06-03")
    assert Decimal(biz.purchase_documents.payable(biz.sup)) == Decimal("800")
    row = biz.purchase_documents.list()[0]
    assert row["amount_paid"] == "0.00"               # the bill is unchanged
    assert row["net_total"] == "1000.00"
    assert row["id"] == purchase.id


# ---- 8. the whole workflow reconciles -------------------------------------

def test_mandatory_workflow_reconciles_on_every_surface(biz, qapp):
    from zenith_business.ui.documents.list_page import DocumentListPage
    from zenith_business.ui.documents.print_builder import build_purchase_invoice

    purchase = _buy(biz)                                   # 10 × 100 = 1000 credit
    _return(biz, purchase, "4")                            # net 600
    biz.purchase_documents.correct_purchase(               # bill becomes 8 × 100
        purchase_id=purchase.id, currency_code="AFN", warehouse_id=biz.main,
        party_id=biz.sup, amount_paid="0", purchase_date="2026-06-01",
        lines=[PurchaseLine(item_id=biz.rice, unit_id=biz.bag, quantity="8",
                            unit_price="100")])
    cash = biz.accounts_repo.id_by_code("1000")
    biz.payments.post_payment(party_id=biz.sup, account_id=cash, amount="200",
                              currency_code="AFN", payment_date="2026-06-03")

    row = biz.purchase_documents.list()[0]
    view = biz.purchase_documents.net_view(purchase.id)
    page = _reopen(biz, purchase.id)
    data, _title = build_purchase_invoice(biz, purchase.id)
    listing = DocumentListPage(biz, Translator(LANG_ENGLISH), mode="purchase")
    heads = [listing._table.horizontalHeaderItem(i).text()
             for i in range(listing._table.columnCount())]

    assert row["net_total"] == "400.00"                                  # list
    assert listing._table.item(0, heads.index("Net Total")).text() == "400.00"
    assert view["net_total"] == "400.00"                                 # engine
    assert page._grand_value.text() == "400.00"                          # reopened bill
    assert data.grand_total == 400.0                                     # print
    assert Decimal(biz.purchase_documents.payable(biz.sup)) == Decimal("200")  # balance
    assert Decimal(biz.inventory.on_hand(biz.rice)) == Decimal("4")      # inventory

    movements = biz.inventory.movement_history(item_id=biz.rice)         # stock movement
    assert sum(Decimal(m["quantity"]) for m in movements) == Decimal("4")
    assert len(biz.purchase_documents.list()) == 1                       # one bill
    assert len(biz.purchase_returns_repo.list_for_purchase(purchase.id)) == 1

    rows = biz.db.connection().execute(
        "SELECT debit, credit FROM financial_entry_lines").fetchall()
    assert (sum(Decimal(r["debit"]) for r in rows)
            == sum(Decimal(r["credit"]) for r in rows))


# ---- 9. control-audit fixes (owner-reported) -------------------------------

def test_line_total_always_equals_qty_times_price_minus_discount(biz, qapp):
    """A row reading 12 × 100 = 1,000 under a Grand Total of 1,200 is impossible.

    The line total is derived at render time, so no code path can leave the cell
    behind after changing the quantity, price or discount.
    """
    from zenith_business.ui.documents.entry_page import C_TOTAL, DocumentEntryPage
    page = DocumentEntryPage(biz, Translator(LANG_ENGLISH), mode="purchase",
                             on_print=lambda i: None, on_close=lambda: None)
    page.add_line({"item_id": biz.rice, "base_unit_id": biz.bag, "item_code": "RICE",
                   "name": "Rice", "unit_symbol": "bag"}, qty="10", price="100")
    assert page._table.item(0, C_TOTAL).text() == "1,000.00"
    assert page._grand_value.text() == "1,000.00"

    # Any mutation of the line, however it arrives, keeps cell and total in step.
    page._lines[0]["qty"] = "12"
    page._render_lines(); page._recompute_totals()
    assert page._table.item(0, C_TOTAL).text() == "1,200.00"
    assert page._grand_value.text() == "1,200.00"

    page._lines[0]["price"] = "50"
    page._render_lines(); page._recompute_totals()
    assert page._table.item(0, C_TOTAL).text() == "600.00"
    assert page._grand_value.text() == "600.00"

    page._lines[0]["discount"] = "100"
    page._render_lines(); page._recompute_totals()
    assert page._table.item(0, C_TOTAL).text() == "500.00"
    assert page._grand_value.text() == "500.00"


def test_typing_a_quantity_in_the_grid_updates_the_row_total(biz, qapp):
    from zenith_business.ui.documents.entry_page import C_QTY, C_TOTAL, DocumentEntryPage
    page = DocumentEntryPage(biz, Translator(LANG_ENGLISH), mode="purchase",
                             on_print=lambda i: None, on_close=lambda: None)
    page.add_line({"item_id": biz.rice, "base_unit_id": biz.bag, "item_code": "RICE",
                   "name": "Rice", "unit_symbol": "bag"}, qty="10", price="100")
    page._table.item(0, C_QTY).setText("12")
    assert page._table.item(0, C_TOTAL).text() == "1,200.00"
    assert page._grand_value.text() == "1,200.00"


def test_dari_returns_list_shows_a_dari_note_whatever_language_posted_it(biz, qapp):
    """A Dari reader must never be shown the English sentence."""
    from zenith_business.ui.documents.list_page import DocumentListPage
    from zenith_business.ui.documents.return_page import ReturnEntryPage
    purchase = _buy(biz)
    page = ReturnEntryPage(biz, Translator(LANG_ENGLISH), mode="purchase_return",
                           on_close=lambda: None, on_print=lambda i: None)
    page._src_edit.setText(purchase.document_no)
    page._load_source()
    page._return_edits[0].setText("4")
    page._post(print_after=False)                 # posted from the ENGLISH screen

    english = DocumentListPage(biz, Translator(LANG_ENGLISH), mode="purchase_return")
    dari = DocumentListPage(biz, Translator(LANG_DARI), mode="purchase_return")
    assert english._table.item(0, 4).text() == "Rice — Qty 4 returned."
    assert dari._table.item(0, 4).text() == "برنج به تعداد 4 دانه برگشت شد."


def test_the_dari_return_screen_builds_a_dari_note(biz, qapp):
    from zenith_business.ui.documents.return_page import ReturnEntryPage
    purchase = _buy(biz)
    page = ReturnEntryPage(biz, Translator(LANG_DARI), mode="purchase_return",
                           on_close=lambda: None, on_print=lambda i: None)
    page._src_edit.setText(purchase.document_no)
    page._load_source()
    page._return_edits[0].setText("4")
    assert page._return_note(page._collect_return_lines()) == \
        "برنج به تعداد 4 دانه برگشت شد."


def test_a_hand_typed_note_is_never_replaced(biz, qapp):
    """Localizing an auto-generated sentence must not overwrite the operator's words."""
    from zenith_business.ui.documents.list_page import DocumentListPage
    purchase = _buy(biz)
    _return(biz, purchase, "4", notes="Driver damaged the sacks in transit")
    for language in (LANG_ENGLISH, LANG_DARI):
        page = DocumentListPage(biz, Translator(language), mode="purchase_return")
        assert page._table.item(0, 4).text() == "Driver damaged the sacks in transit"


# ---- 10. the Suppliers screen ---------------------------------------------
#
# A supplier-shaped VIEW of the shared people — not a second supplier table, not
# a second balance. Every figure comes from the existing party ledger, the same
# read the Supplier Ledger screen uses.

def _suppliers_page(biz, language=LANG_ENGLISH):
    from zenith_business.ui.master.pages import SuppliersPage
    return SuppliersPage(biz, Translator(language))


def test_supplier_totals_add_up(biz):
    """total_purchases − total_paid must equal payable, or all three look wrong."""
    purchase = _buy(biz)                       # 1000 on credit
    _return(biz, purchase, "4")                # −400
    cash = biz.accounts_repo.id_by_code("1000")
    biz.payments.post_payment(party_id=biz.sup, account_id=cash, amount="200",
                              currency_code="AFN", payment_date="2026-06-03")
    _buy(biz, qty="5", paid="200")             # +500 billed, 200 paid on the bill
    totals = biz.party_ledger.supplier_ledger(biz.sup)["totals"]
    assert totals["total_purchases"] == "1100.00"   # net of the return
    assert totals["total_paid"] == "400.00"         # payment + paid on the bill
    assert totals["payable"] == "700.00"
    assert (Decimal(totals["total_purchases"]) - Decimal(totals["total_paid"])
            == Decimal(totals["payable"]))
    # ...and it is the same figure the purchase side reports.
    assert Decimal(biz.purchase_documents.payable(biz.sup)) == Decimal(totals["payable"])


def test_suppliers_screen_lists_only_suppliers_with_ledger_figures(biz, qapp):
    biz.parties.create(party_code="C9", name="Retail Customer", is_customer=True)
    purchase = _buy(biz)
    _return(biz, purchase, "4")
    page = _suppliers_page(biz)
    rows = {r["party_code"]: r for r in page.page._rows}
    assert set(rows) == {"S1"}                       # the customer is not listed
    assert rows["S1"]["purchases_display"] == "600.00"
    assert rows["S1"]["paid_display"] == "0.00"
    assert rows["S1"]["payable_display"] == "600.00"
    assert rows["S1"]["balance_display"] == "600.00"


def test_suppliers_screen_shows_the_required_columns(biz, qapp):
    page = _suppliers_page(biz)
    headers = [c.title for c in page.page._columns]
    assert headers == ["sup.col_code", "sup.col_name", "sup.col_business",
                       "sup.col_phone", "sup.col_balance", "sup.col_purchases",
                       "sup.col_paid", "sup.col_payable", "sup.col_status"]


def test_suppliers_screen_view_account_opens_the_supplier_ledger(biz, qapp):
    opened: dict = {}
    page = _suppliers_page(biz)
    page.set_view_account_handler(lambda pid, role: opened.update(pid=pid, role=role))
    page._view({"id": biz.sup, "is_customer": 0})
    assert opened == {"pid": biz.sup, "role": "supplier"}


def test_a_dual_role_party_shows_both_obligations(biz, qapp):
    """Netting a payable against a receivable would hide two real debts."""
    from zenith_business.services.sales_documents import SaleLine
    both = biz.parties.create(party_code="S2", name="Nasir Trading",
                              is_supplier=True, is_customer=True)
    biz.purchase_documents.post_purchase(
        currency_code="AFN", warehouse_id=biz.main, party_id=both, amount_paid="0",
        purchase_date="2026-06-01",
        lines=[PurchaseLine(item_id=biz.rice, unit_id=biz.bag, quantity="3",
                            unit_price="100")])
    biz.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=biz.main, party_id=both, amount_paid="0",
        sale_date="2026-06-02",
        lines=[SaleLine(item_id=biz.rice, unit_id=biz.bag, quantity="2",
                        unit_price="150")])
    page = _suppliers_page(biz)
    row = next(r for r in page.page._rows if r["party_code"] == "S2")
    assert "300.00" in row["balance_display"]        # payable
    assert "300.00" in row["balance_display"]        # receivable, both named
    assert row["payable_display"] == "300.00"


def test_new_supplier_uses_the_shared_person_form(biz, qapp):
    """One form, one table — the Suppliers screen only pre-ticks the role."""
    from PyQt6.QtWidgets import QCheckBox

    import zenith_business.ui.master.pages as pages
    page = _suppliers_page(biz)
    grabbed: dict = {}
    original = pages.FormDialog.exec
    pages.FormDialog.exec = lambda self: grabbed.setdefault("dlg", self) and 0
    try:
        page._new()
    finally:
        pages.FormDialog.exec = original
    boxes = {b.text(): b for b in grabbed["dlg"].findChildren(QCheckBox)}
    assert boxes["Supplier"].isChecked() is True
    assert boxes["Customer"].isChecked() is False


def test_the_persons_screen_still_defaults_to_customer(biz, qapp):
    from PyQt6.QtWidgets import QCheckBox

    import zenith_business.ui.master.pages as pages
    from zenith_business.ui.master.pages import PersonsPage
    page = PersonsPage(biz, Translator(LANG_ENGLISH))
    grabbed: dict = {}
    original = pages.FormDialog.exec
    pages.FormDialog.exec = lambda self: grabbed.setdefault("dlg", self) and 0
    try:
        page._new()
    finally:
        pages.FormDialog.exec = original
    boxes = {b.text(): b for b in grabbed["dlg"].findChildren(QCheckBox)}
    assert boxes["Customer"].isChecked() is True
    assert boxes["Supplier"].isChecked() is False


def test_suppliers_screen_reads_the_same_figures_in_dari(biz, qapp):
    purchase = _buy(biz)
    _return(biz, purchase, "4")
    english = {r["party_code"]: r for r in _suppliers_page(biz, LANG_ENGLISH).page._rows}
    dari = {r["party_code"]: r for r in _suppliers_page(biz, LANG_DARI).page._rows}
    for key in ("purchases_display", "paid_display", "payable_display",
                "balance_display"):
        assert english["S1"][key] == dari["S1"][key]


# ---- row actions must be VISIBLE, not just present ----------------------
#
# "View Account" shipped as an empty box. Two separate causes, both in shared UI
# code, so these guard every table in the app — not only Suppliers.

@pytest.fixture
def themed(qapp):
    """The real stylesheet, which is what sizes and colours a row action."""
    from zenith_business.ui.design.theme import build_stylesheet

    previous = qapp.styleSheet()
    qapp.setStyleSheet(build_stylesheet())
    yield qapp
    qapp.setStyleSheet(previous)


def _row_action_cell(page, qapp):
    from PyQt6.QtCore import QSize

    page.resize(QSize(1366, 760))
    page.show()
    qapp.processEvents()
    table = page.page._table
    cell = table.cellWidget(0, table.columnCount() - 1)
    assert cell is not None, "the action column has no widget"
    return cell


def test_a_row_action_button_fits_inside_its_table_cell(biz, themed):
    """A button taller than its cell has its label clipped away — an empty box.

    setFixedHeight() cannot hold this: Qt applies a stylesheet ``min-height`` by
    calling setMinimumHeight() on the widget, which overrides it. The height has
    to come from the stylesheet, so assert the rendered geometry, not the intent.
    """
    from PyQt6.QtWidgets import QPushButton, QToolButton

    cell = _row_action_cell(_suppliers_page(biz), themed)
    buttons = cell.findChildren(QPushButton) + cell.findChildren(QToolButton)
    assert buttons, "the row has no action control"
    for button in buttons:
        assert button.height() <= cell.height(), (
            f"{button.text()!r} is {button.height()}px tall in a "
            f"{cell.height()}px cell — its label is clipped away")
    labelled = [b for b in buttons if isinstance(b, QPushButton)]
    for button in labelled:
        assert button.width() >= button.sizeHint().width(), (
            f"{button.text()!r} is narrower than its own label needs")


def test_a_row_action_keeps_its_own_background(biz, themed):
    """An unscoped ``background: transparent`` on the container also applies to
    its children, which left light button text on a light table row."""
    from PyQt6.QtWidgets import QPushButton

    from zenith_business.ui.design.tokens import Color

    cell = _row_action_cell(_suppliers_page(biz), themed)
    accent = [b for b in cell.findChildren(QPushButton)
              if b.property("variant") == "accent"]
    assert accent, "View Account is expected to be the accent row action"
    painted = accent[0].grab().toImage()
    colors = {painted.pixelColor(x, y).name()
              for y in range(painted.height()) for x in range(painted.width())}
    assert Color.ACCENT.lower() in colors, (
        "the accent fill was stripped by a parent stylesheet")
    assert Color.TEXT_ON_PRIMARY.lower() in colors, "the label is not painted"
