"""Sales Invoice payment behaviour: manual Cash/Credit, derived Paid/Remaining.

The operator picks the payment type; the app never infers it from the numbers.
Whatever they pick, Paid and Remaining are derived from the SAME grand total the
invoice already computes, and they follow it live as lines are added, removed,
re-priced or discounted — the amount is never typed by hand.
"""

from __future__ import annotations

import pytest

from zenith_business.core.i18n import LANG_ENGLISH, Translator
from zenith_business.services.purchase_documents import PurchaseLine


@pytest.fixture
def biz(admin_context):
    ctx = admin_context
    ctx.financial_years.create(name="FY26", start_date="2026-01-01", end_date="2026-12-31",
                               make_active=True)
    ctx.wh = ctx.warehouses.create(code="MAIN", name="Main", is_default=True)
    ctx.bag = ctx.units_repo.id_by_code("BAG")
    ctx.rice = ctx.items.create(item_code="RICE", name="Rice", base_unit_id=ctx.bag,
                                purchase_price="50", default_sale_price="100")
    ctx.sugar = ctx.items.create(item_code="SUGAR", name="Sugar", base_unit_id=ctx.bag,
                                 purchase_price="40", default_sale_price="80")
    ctx.cust = ctx.parties.create(party_code="C1", name="Ahmad Store", is_customer=True)
    ctx.sup = ctx.parties.create(party_code="S1", name="Sup", is_supplier=True)
    ctx.purchase_documents.post_purchase(
        currency_code="AFN", warehouse_id=ctx.wh, party_id=ctx.sup, amount_paid="0",
        purchase_date="2026-06-01",
        lines=[PurchaseLine(item_id=ctx.rice, unit_id=ctx.bag, quantity="100", unit_price="50"),
               PurchaseLine(item_id=ctx.sugar, unit_id=ctx.bag, quantity="100", unit_price="40")])
    return ctx


def _page(biz):
    from zenith_business.ui.documents.entry_page import DocumentEntryPage
    from zenith_business.ui.widgets.search_selector import SearchRow
    page = DocumentEntryPage(biz, Translator(LANG_ENGLISH), mode="sale")
    page.set_party(SearchRow(values=["C1", "Ahmad Store"], payload={"party_id": biz.cust}))
    return page


def _payload(biz, item_id, code, name):
    return {"item_id": item_id, "base_unit_id": biz.bag, "item_code": code,
            "name": name, "unit_symbol": "bag", "sale_price": "100"}


def _rice(biz):
    return _payload(biz, biz.rice, "RICE", "Rice")


def _sugar(biz):
    return _payload(biz, biz.sugar, "SUGAR", "Sugar")


def _money(text: str) -> str:
    return text.replace(",", "")


def _totals(page) -> tuple[str, str, str]:
    """(grand, paid, remaining) as plain strings."""
    return (_money(page._grand_value.text()), _money(page.amount_paid),
            _money(page.remaining))


# ---- 1. Cash invoice auto-paid -------------------------------------------

def test_cash_invoice_is_auto_paid_in_full(qapp, biz):
    page = _page(biz)
    page.add_line(_rice(biz), qty="5", price="100")     # 500
    page.add_line(_sugar(biz), qty="3", price="100")    # 300  -> 800
    page.set_payment_type("cash")
    grand, paid, remaining = _totals(page)
    assert grand == "800.00"
    assert paid == "800.00"          # never typed by the operator
    assert remaining == "0.00"


# ---- 2. Credit invoice auto-credit ---------------------------------------

def test_credit_invoice_leaves_the_whole_total_outstanding(qapp, biz):
    page = _page(biz)
    page.add_line(_rice(biz), qty="5", price="100")
    page.add_line(_sugar(biz), qty="3", price="100")
    page.set_payment_type("credit")
    grand, paid, remaining = _totals(page)
    assert grand == "800.00"
    assert paid == "0.00"
    assert remaining == "800.00"


def test_the_two_types_are_mutually_exclusive(qapp, biz):
    page = _page(biz)
    assert page._seg_cash.isChecked() and not page._seg_credit.isChecked()
    page.set_payment_type("credit")
    assert page._seg_credit.isChecked() and not page._seg_cash.isChecked()
    page.set_payment_type("cash")
    assert page._seg_cash.isChecked() and not page._seg_credit.isChecked()


def test_payment_type_is_never_inferred_from_the_numbers(qapp, biz):
    """A fully-priced invoice stays Credit until the operator says otherwise."""
    page = _page(biz)
    page.set_payment_type("credit")
    page.add_line(_rice(biz), qty="5", price="100")
    assert page.payment_type() == "credit"
    assert _totals(page) == ("500.00", "0.00", "500.00")


# ---- 3. Adding an item updates payment -----------------------------------

def test_adding_an_item_updates_payment(qapp, biz):
    page = _page(biz)
    page.set_payment_type("cash")
    page.add_line(_rice(biz), qty="5", price="100")
    assert _totals(page) == ("500.00", "500.00", "0.00")
    page.add_line(_sugar(biz), qty="3", price="100")     # +300
    assert _totals(page) == ("800.00", "800.00", "0.00")


def test_adding_an_item_updates_credit(qapp, biz):
    page = _page(biz)
    page.set_payment_type("credit")
    page.add_line(_rice(biz), qty="5", price="100")
    assert _totals(page) == ("500.00", "0.00", "500.00")
    page.add_line(_sugar(biz), qty="3", price="100")
    assert _totals(page) == ("800.00", "0.00", "800.00")


# ---- 4. Removing an item updates payment ---------------------------------

def test_removing_an_item_updates_payment_before_saving(qapp, biz):
    """The owner's example: 800 cash, remove the 300 line, paid becomes 500."""
    page = _page(biz)
    page.set_payment_type("cash")
    page.add_line(_rice(biz), qty="5", price="100")      # 500
    page.add_line(_sugar(biz), qty="3", price="100")     # 300
    assert _totals(page) == ("800.00", "800.00", "0.00")
    page._table.selectRow(1)
    page._delete_selected()
    assert _totals(page) == ("500.00", "500.00", "0.00")


def test_removing_an_item_updates_credit_before_saving(qapp, biz):
    page = _page(biz)
    page.set_payment_type("credit")
    page.add_line(_rice(biz), qty="5", price="100")
    page.add_line(_sugar(biz), qty="3", price="100")
    assert _totals(page) == ("800.00", "0.00", "800.00")
    page._table.selectRow(1)
    page._delete_selected()
    assert _totals(page) == ("500.00", "0.00", "500.00")


# ---- 5. Changing quantity updates payment --------------------------------

def test_changing_quantity_updates_payment(qapp, biz):
    from zenith_business.ui.documents.entry_page import C_QTY
    page = _page(biz)
    page.set_payment_type("cash")
    page.add_line(_rice(biz), qty="2", price="100")      # 200
    assert _totals(page) == ("200.00", "200.00", "0.00")
    page._table.item(0, C_QTY).setText("5")              # -> 500
    assert _totals(page) == ("500.00", "500.00", "0.00")


# ---- 6. Changing price updates payment -----------------------------------

def test_changing_price_updates_payment(qapp, biz):
    from zenith_business.ui.documents.entry_page import C_PRICE
    page = _page(biz)
    page.set_payment_type("credit")
    page.add_line(_rice(biz), qty="4", price="100")      # 400
    assert _totals(page) == ("400.00", "0.00", "400.00")
    page._table.item(0, C_PRICE).setText("150")          # -> 600
    assert _totals(page) == ("600.00", "0.00", "600.00")


# ---- 7. Changing discount updates payment --------------------------------

def test_changing_discount_updates_payment(qapp, biz):
    from zenith_business.ui.documents.entry_page import C_DISC
    page = _page(biz)
    page.set_payment_type("cash")
    page.add_line(_rice(biz), qty="5", price="100")      # 500
    assert _totals(page) == ("500.00", "500.00", "0.00")
    page._table.item(0, C_DISC).setText("50")            # -> 450
    assert _totals(page) == ("450.00", "450.00", "0.00")


# ---- 8. Switching Cash <-> Credit recalculates ---------------------------

def test_switching_cash_to_credit_and_back(qapp, biz):
    page = _page(biz)
    page.add_line(_rice(biz), qty="5", price="100")
    page.add_line(_sugar(biz), qty="3", price="100")     # 800
    page.set_payment_type("cash")
    assert _totals(page) == ("800.00", "800.00", "0.00")
    page.set_payment_type("credit")
    assert _totals(page) == ("800.00", "0.00", "800.00")
    page.set_payment_type("cash")
    assert _totals(page) == ("800.00", "800.00", "0.00")


# ---- what gets posted -----------------------------------------------------

def test_cash_invoice_posts_fully_paid(qapp, biz):
    page = _page(biz)
    page.add_line(_rice(biz), qty="5", price="100")
    page.set_payment_type("cash")
    page._post(print_after=False)
    sale = biz.sales_documents.get(page.last_saved_id)
    assert sale["grand_total"] == "500.00"
    assert sale["amount_paid"] == "500.00"
    assert sale["remaining_amount"] == "0.00"
    assert biz.sales_documents.receivable(biz.cust) == "0.00"


def test_credit_invoice_posts_fully_outstanding(qapp, biz):
    page = _page(biz)
    page.add_line(_rice(biz), qty="5", price="100")
    page.set_payment_type("credit")
    page._post(print_after=False)
    sale = biz.sales_documents.get(page.last_saved_id)
    assert sale["amount_paid"] == "0.00"
    assert sale["remaining_amount"] == "500.00"
    assert biz.sales_documents.receivable(biz.cust) == "500.00"


def test_amount_paid_is_not_typed_by_hand(qapp, biz):
    """The field is derived, so it cannot drift away from the invoice total."""
    page = _page(biz)
    assert page._recv_edit.isReadOnly()


def test_form_resets_to_cash_for_the_next_invoice(qapp, biz):
    page = _page(biz)
    page.add_line(_rice(biz), qty="5", price="100")
    page.set_payment_type("credit")
    page._post(print_after=False)
    assert page.payment_type() == "cash"
    assert _totals(page) == ("0.00", "0.00", "0.00")
