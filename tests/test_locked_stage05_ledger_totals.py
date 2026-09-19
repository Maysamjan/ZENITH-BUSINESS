"""Party ledger totals must reconcile — §33 amendment 01 to LOCKED Stage 05.

The Customer Ledger and Supplier Ledger each print three figures side by side.
Whatever the history behind them, they have to satisfy:

    total_sales     − total_received == receivable      (customer)
    total_purchases − total_paid     == payable         (supplier)

Before the fix they did not: a supplier with a 1,000 bill, a 400 return and a
200 payment showed Purchases 1,000 − Paid 200 against a Payable of 400. The
balance was right and the two numbers printed beside it were wrong, which is
worse than showing nothing — the reader cannot tell which to believe.

These tests assert the **identity**, not remembered example numbers, so they
keep holding as the engine changes. The scenarios are the ones that broke it:
money settled on the document itself, and documents partly or wholly returned.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from zenith_business.services.purchase_documents import PurchaseLine, PurchaseReturnLine
from zenith_business.services.sales_documents import ReturnLine, SaleLine


@pytest.fixture
def books(admin_context):
    """A live set of books with one customer, one supplier and one item."""
    ctx = admin_context
    ctx.financial_years.create(name="FY26", start_date="2026-01-01",
                               end_date="2026-12-31", make_active=True)
    ctx.main = ctx.warehouses.create(code="MAIN", name="Main Store", is_default=True)
    ctx.bag = ctx.units_repo.id_by_code("BAG")
    ctx.item = ctx.items.create(item_code="RICE", name="Rice", base_unit_id=ctx.bag,
                                purchase_price="100", default_sale_price="150")
    ctx.cash = ctx.accounts_repo.id_by_code("1000")
    ctx.cus = ctx.parties.create(party_code="C1", name="Ahmad Shah", is_customer=True)
    ctx.sup = ctx.parties.create(party_code="S1", name="Karim Ahmadi", is_supplier=True)
    # Stock to sell, bought from someone who is not the supplier under test.
    other = ctx.parties.create(party_code="S9", name="Bulk Import", is_supplier=True)
    ctx.purchase_documents.post_purchase(
        currency_code="AFN", warehouse_id=ctx.main, party_id=other, amount_paid="0",
        purchase_date="2026-01-05",
        lines=[PurchaseLine(item_id=ctx.item, unit_id=ctx.bag,
                            quantity="500", unit_price="100")])
    return ctx


# ---- the identity itself ------------------------------------------------

def assert_customer_totals_reconcile(ctx, party_id):
    t = ctx.party_ledger.customer_ledger(party_id)["totals"]
    assert Decimal(t["total_sales"]) - Decimal(t["total_received"]) \
        == Decimal(t["receivable"]), (
            f"customer summary contradicts itself: sales {t['total_sales']}"
            f" − received {t['total_received']} != receivable {t['receivable']}")
    return t


def assert_supplier_totals_reconcile(ctx, party_id):
    t = ctx.party_ledger.supplier_ledger(party_id)["totals"]
    assert Decimal(t["total_purchases"]) - Decimal(t["total_paid"]) \
        == Decimal(t["payable"]), (
            f"supplier summary contradicts itself: purchases {t['total_purchases']}"
            f" − paid {t['total_paid']} != payable {t['payable']}")
    return t


# ---- helpers ------------------------------------------------------------

def _sell(ctx, quantity="10", price="150", paid="0"):
    return ctx.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=ctx.main, party_id=ctx.cus,
        amount_paid=paid, sale_date="2026-02-01",
        lines=[SaleLine(item_id=ctx.item, unit_id=ctx.bag,
                        quantity=quantity, unit_price=price)])


def _sale_return(ctx, sale, quantity):
    line = ctx.sales_repo.lines_for(sale.id)[0]
    return ctx.sales_documents.post_return(
        sale_id=sale.id, return_date="2026-02-02",
        lines=[ReturnLine(sale_line_id=line["id"], quantity=quantity)])


def _buy(ctx, quantity="10", price="100", paid="0"):
    return ctx.purchase_documents.post_purchase(
        currency_code="AFN", warehouse_id=ctx.main, party_id=ctx.sup,
        amount_paid=paid, purchase_date="2026-02-01",
        lines=[PurchaseLine(item_id=ctx.item, unit_id=ctx.bag,
                            quantity=quantity, unit_price=price)])


def _purchase_return(ctx, purchase, quantity):
    line = ctx.purchases_repo.lines_for(purchase.id)[0]
    return ctx.purchase_documents.post_return(
        purchase_id=purchase.id, return_date="2026-02-02",
        lines=[PurchaseReturnLine(purchase_line_id=line["id"], quantity=quantity)])


# ---- customer ledger ----------------------------------------------------

def test_customer_totals_reconcile_with_no_activity(books):
    totals = assert_customer_totals_reconcile(books, books.cus)
    assert totals["receivable"] == "0.00"


def test_customer_totals_reconcile_on_a_credit_sale(books):
    _sell(books)                                     # 1500 owed
    totals = assert_customer_totals_reconcile(books, books.cus)
    assert totals["total_sales"] == "1500.00"
    assert totals["total_received"] == "0.00"


def test_money_taken_on_the_invoice_counts_as_received(books):
    """Cash handed over at the counter is received money, receipt or not."""
    _sell(books, paid="1500")
    totals = assert_customer_totals_reconcile(books, books.cus)
    assert totals["total_received"] == "1500.00"
    assert totals["receivable"] == "0.00"


def test_customer_totals_reconcile_after_a_receipt(books):
    _sell(books)
    books.receipts.post_receipt(party_id=books.cus, account_id=books.cash,
                                amount="500", currency_code="AFN",
                                receipt_date="2026-02-03")
    totals = assert_customer_totals_reconcile(books, books.cus)
    assert totals["total_received"] == "500.00"


def test_customer_totals_reconcile_after_a_partial_return(books):
    sale = _sell(books)                              # 1500
    _sale_return(books, sale, "4")                   # −600
    totals = assert_customer_totals_reconcile(books, books.cus)
    assert totals["total_sales"] == "900.00"         # net of the return


def test_customer_totals_reconcile_after_a_full_return(books):
    sale = _sell(books)
    _sale_return(books, sale, "10")
    totals = assert_customer_totals_reconcile(books, books.cus)
    assert totals["total_sales"] == "0.00"
    assert totals["receivable"] == "0.00"


def test_customer_totals_reconcile_across_a_mixed_history(books):
    """The owner's real shape: several invoices, a part payment and a return."""
    _sell(books, quantity="10", paid="0")            # 1500 credit
    sale = _sell(books, quantity="4", paid="300")    # 600, 300 paid at the counter
    _sale_return(books, sale, "2")                   # −300
    books.receipts.post_receipt(party_id=books.cus, account_id=books.cash,
                                amount="200", currency_code="AFN",
                                receipt_date="2026-02-04")
    totals = assert_customer_totals_reconcile(books, books.cus)
    assert totals["total_sales"] == "1800.00"        # 1500 + 600 − 300
    assert totals["total_received"] == "500.00"      # 300 on the invoice + 200 receipt


# ---- supplier ledger ----------------------------------------------------

def test_supplier_totals_reconcile_with_no_activity(books):
    totals = assert_supplier_totals_reconcile(books, books.sup)
    assert totals["payable"] == "0.00"


def test_supplier_totals_reconcile_on_a_credit_bill(books):
    _buy(books)
    totals = assert_supplier_totals_reconcile(books, books.sup)
    assert totals["total_purchases"] == "1000.00"
    assert totals["total_paid"] == "0.00"


def test_money_paid_on_the_bill_counts_as_paid(books):
    _buy(books, paid="400")                          # partial payment on the bill
    totals = assert_supplier_totals_reconcile(books, books.sup)
    assert totals["total_paid"] == "400.00"
    assert totals["payable"] == "600.00"


def test_supplier_totals_reconcile_after_a_payment(books):
    _buy(books)
    books.payments.post_payment(party_id=books.sup, account_id=books.cash,
                                amount="200", currency_code="AFN",
                                payment_date="2026-02-03")
    totals = assert_supplier_totals_reconcile(books, books.sup)
    assert totals["total_paid"] == "200.00"


def test_supplier_totals_reconcile_after_a_partial_return(books):
    purchase = _buy(books)                           # 1000
    _purchase_return(books, purchase, "4")           # −400
    totals = assert_supplier_totals_reconcile(books, books.sup)
    assert totals["total_purchases"] == "600.00"


def test_supplier_totals_reconcile_after_a_full_return(books):
    purchase = _buy(books)
    _purchase_return(books, purchase, "10")
    totals = assert_supplier_totals_reconcile(books, books.sup)
    assert totals["total_purchases"] == "0.00"
    assert totals["payable"] == "0.00"


def test_the_exact_case_that_was_reported(books):
    """1,000 bill − 400 return, 200 paid: it read 1,000 − 200 against 400."""
    purchase = _buy(books)
    _purchase_return(books, purchase, "4")
    books.payments.post_payment(party_id=books.sup, account_id=books.cash,
                                amount="200", currency_code="AFN",
                                payment_date="2026-02-03")
    totals = assert_supplier_totals_reconcile(books, books.sup)
    assert totals["total_purchases"] == "600.00"
    assert totals["total_paid"] == "200.00"
    assert totals["payable"] == "400.00"


def test_supplier_totals_reconcile_across_a_mixed_history(books):
    _buy(books, quantity="10")                       # 1000 credit
    purchase = _buy(books, quantity="5", paid="200")  # 500, 200 paid on the bill
    _purchase_return(books, purchase, "4")           # −400
    books.payments.post_payment(party_id=books.sup, account_id=books.cash,
                                amount="150", currency_code="AFN",
                                payment_date="2026-02-04")
    totals = assert_supplier_totals_reconcile(books, books.sup)
    assert totals["total_purchases"] == "1100.00"    # 1000 + 500 − 400
    assert totals["total_paid"] == "350.00"          # 200 on the bill + 150 payment


# ---- both sides of one party, and what the screens read -----------------

def test_a_dual_role_party_reconciles_on_both_sides_independently(books):
    """One record, two obligations — neither summary may borrow from the other."""
    both = books.parties.create(party_code="B1", name="Nasir Trading",
                                is_customer=True, is_supplier=True)
    books.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=books.main, party_id=both,
        amount_paid="100", sale_date="2026-03-01",
        lines=[SaleLine(item_id=books.item, unit_id=books.bag,
                        quantity="4", unit_price="150")])
    books.purchase_documents.post_purchase(
        currency_code="AFN", warehouse_id=books.main, party_id=both,
        amount_paid="50", purchase_date="2026-03-02",
        lines=[PurchaseLine(item_id=books.item, unit_id=books.bag,
                            quantity="3", unit_price="100")])
    assert_customer_totals_reconcile(books, both)
    assert_supplier_totals_reconcile(books, both)


def test_the_suppliers_screen_shows_figures_that_reconcile(books, qapp):
    """What the reader actually sees, not only what the repository returns."""
    from zenith_business.core.i18n import LANG_ENGLISH, Translator
    from zenith_business.ui.master.pages import SuppliersPage

    purchase = _buy(books)
    _purchase_return(books, purchase, "4")
    books.payments.post_payment(party_id=books.sup, account_id=books.cash,
                                amount="200", currency_code="AFN",
                                payment_date="2026-02-03")
    page = SuppliersPage(books, Translator(LANG_ENGLISH))
    row = {r["party_code"]: r for r in page.page._rows}["S1"]
    shown = {k: Decimal(row[k].replace(",", ""))
             for k in ("purchases_display", "paid_display", "payable_display")}
    assert shown["purchases_display"] - shown["paid_display"] \
        == shown["payable_display"], f"the Suppliers row contradicts itself: {row}"
