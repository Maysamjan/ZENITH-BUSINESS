"""Stage 05 — receipts, payments, expenses engine + failure-safety (§16)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from zenith_business.services.exceptions import (
    AuthorizationError,
    ValidationError,
)
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
    ctx.cust = ctx.parties.create(party_code="C1", name="Cust", is_customer=True)
    ctx.sup = ctx.parties.create(party_code="S1", name="Sup", is_supplier=True)
    ctx.cash = next(f for f in ctx.funds_repo.list_funds() if f["code"] == "1000")["id"]
    ctx.bank = next(f for f in ctx.funds_repo.list_funds() if f["code"] == "1010")["id"]
    ctx.rent = next(c for c in ctx.expense_categories_repo.list_active()
                    if c["code"] == "RENT")["id"]
    return ctx


def _credit_sale(ctx, qty="10", price="100"):
    ctx.purchase_documents.post_purchase(
        currency_code="AFN", warehouse_id=ctx.wh, party_id=ctx.sup, amount_paid="0",
        purchase_date="2026-06-01",
        lines=[PurchaseLine(item_id=ctx.item, unit_id=ctx.bag, quantity="100", unit_price="50")])
    return ctx.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=ctx.wh, party_id=ctx.cust, amount_paid="0",
        sale_date="2026-06-02",
        lines=[SaleLine(item_id=ctx.item, unit_id=ctx.bag, quantity=qty, unit_price=price)])


def _credit_purchase(ctx, qty="100", price="50"):
    return ctx.purchase_documents.post_purchase(
        currency_code="AFN", warehouse_id=ctx.wh, party_id=ctx.sup, amount_paid="0",
        purchase_date="2026-06-01",
        lines=[PurchaseLine(item_id=ctx.item, unit_id=ctx.bag, quantity=qty, unit_price=price)])


def _balanced(ctx) -> bool:
    rows = ctx.db.connection().execute(
        "SELECT debit, credit FROM financial_entry_lines").fetchall()
    return sum(Decimal(r[0]) for r in rows) == sum(Decimal(r[1]) for r in rows)


# ---- receipts -----------------------------------------------------------

def test_receipt_reduces_receivable(biz):
    _credit_sale(biz)  # receivable 1000
    assert biz.receipts.receivable(biz.cust) == "1000.00"
    r = biz.receipts.post_receipt(party_id=biz.cust, account_id=biz.cash, amount="400",
                                  currency_code="AFN", payment_method="CASH",
                                  receipt_date="2026-06-03")
    assert r.amount == "400.00" and r.remaining == "600.00"
    assert biz.receipts.receivable(biz.cust) == "600.00"
    assert biz.funds_repo.balance(biz.cash) == "400.00"
    assert _balanced(biz)


def test_receipt_example_workflow(biz):
    # owner's example: owes 13,440 → pays 5,000 → remaining 8,440
    biz.purchase_documents.post_purchase(
        currency_code="AFN", warehouse_id=biz.wh, party_id=biz.sup, amount_paid="0",
        purchase_date="2026-06-01",
        lines=[PurchaseLine(item_id=biz.item, unit_id=biz.bag, quantity="200", unit_price="50")])
    biz.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=biz.wh, party_id=biz.cust, amount_paid="0",
        sale_date="2026-06-02",
        lines=[SaleLine(item_id=biz.item, unit_id=biz.bag, quantity="112", unit_price="120")])
    assert biz.receipts.receivable(biz.cust) == "13440.00"
    r = biz.receipts.post_receipt(party_id=biz.cust, account_id=biz.cash, amount="5000",
                                  currency_code="AFN", receipt_date="2026-06-03")
    assert r.remaining == "8440.00"


def test_receipt_overpayment_creates_credit(biz):
    _credit_sale(biz)  # receivable 1000
    r = biz.receipts.post_receipt(party_id=biz.cust, account_id=biz.cash, amount="1500",
                                  currency_code="AFN", receipt_date="2026-06-03")
    # customer now has a 500 advance/credit → negative receivable
    assert Decimal(r.remaining) == Decimal("-500.00")
    assert _balanced(biz)


# ---- payments -----------------------------------------------------------

def test_payment_reduces_payable(biz):
    _credit_purchase(biz)  # payable 5000
    assert biz.payments.payable(biz.sup) == "5000.00"
    p = biz.payments.post_payment(party_id=biz.sup, account_id=biz.bank, amount="2000",
                                  currency_code="AFN", payment_method="BANK",
                                  payment_date="2026-06-03")
    assert p.remaining == "3000.00"
    assert biz.payments.payable(biz.sup) == "3000.00"
    assert biz.funds_repo.balance(biz.bank) == "-2000.00"
    assert _balanced(biz)


# ---- expenses -----------------------------------------------------------

def test_expense_posts_to_expense_account(biz):
    e = biz.expenses.post_expense(category_id=biz.rent, account_id=biz.cash, amount="1500",
                                  currency_code="AFN", payee="Landlord", payment_method="CASH",
                                  expense_date="2026-06-03")
    assert e.amount == "1500.00"
    assert biz.funds_repo.balance(biz.cash) == "-1500.00"
    rent_acct = biz.accounts_repo.id_by_code("6100")
    assert biz.funds_repo.balance(rent_acct) == "1500.00"  # Dr expense
    assert _balanced(biz)


# ---- validation / failure safety (§14) ---------------------------------

@pytest.mark.parametrize("bad", ["0", "-5", "abc", "NaN", "Infinity", "1e999", ""])
def test_receipt_rejects_bad_amount(biz, bad):
    with pytest.raises(ValidationError):
        biz.receipts.post_receipt(party_id=biz.cust, account_id=biz.cash, amount=bad,
                                  currency_code="AFN", receipt_date="2026-06-03")
    # nothing persisted
    assert biz.receipts.list() == []


@pytest.mark.parametrize("bad_rate", ["0", "-1", "NaN", "Infinity", "x"])
def test_receipt_rejects_bad_rate(biz, bad_rate):
    with pytest.raises(ValidationError):
        biz.receipts.post_receipt(party_id=biz.cust, account_id=biz.cash, amount="100",
                                  currency_code="AFN", exchange_rate=bad_rate,
                                  receipt_date="2026-06-03")


def test_receipt_requires_fund_account(biz):
    with pytest.raises(ValidationError):
        biz.receipts.post_receipt(party_id=biz.cust, account_id=None, amount="100",
                                  currency_code="AFN", receipt_date="2026-06-03")


def test_receipt_rejects_non_fund_account(biz):
    ar = biz.accounts_repo.id_by_code("1100")  # receivable is not a fund
    with pytest.raises(ValidationError):
        biz.receipts.post_receipt(party_id=biz.cust, account_id=ar, amount="100",
                                  currency_code="AFN", receipt_date="2026-06-03")


def test_receipt_requires_customer(biz):
    with pytest.raises(ValidationError):
        biz.receipts.post_receipt(party_id=biz.sup, account_id=biz.cash, amount="100",
                                  currency_code="AFN", receipt_date="2026-06-03")


def test_payment_requires_supplier(biz):
    with pytest.raises(ValidationError):
        biz.payments.post_payment(party_id=biz.cust, account_id=biz.cash, amount="100",
                                  currency_code="AFN", payment_date="2026-06-03")


def test_inactive_party_rejected(biz):
    biz.parties.set_active(biz.cust, False)
    with pytest.raises(ValidationError):
        biz.receipts.post_receipt(party_id=biz.cust, account_id=biz.cash, amount="100",
                                  currency_code="AFN", receipt_date="2026-06-03")


def test_bad_method_rejected(biz):
    with pytest.raises(ValidationError):
        biz.receipts.post_receipt(party_id=biz.cust, account_id=biz.cash, amount="100",
                                  currency_code="AFN", payment_method="GOLD_BARS",
                                  receipt_date="2026-06-03")


def test_closed_financial_year_rejected(biz):
    with pytest.raises(ValidationError):
        biz.receipts.post_receipt(party_id=biz.cust, account_id=biz.cash, amount="100",
                                  currency_code="AFN", receipt_date="2027-01-01")


def test_expense_bad_category_rejected(biz):
    with pytest.raises(ValidationError):
        biz.expenses.post_expense(category_id=999999, account_id=biz.cash, amount="100",
                                  currency_code="AFN", expense_date="2026-06-03")


# ---- RBAC (§13) ---------------------------------------------------------

def test_rbac_receipts_blocked_for_salesperson(admin_context):
    ctx = admin_context
    ctx.financial_years.create(name="FY26", start_date="2026-01-01", end_date="2026-12-31",
                               make_active=True)
    cust = ctx.parties.create(party_code="C1", name="Cust", is_customer=True)
    cash = next(f for f in ctx.funds_repo.list_funds() if f["code"] == "1000")["id"]
    # a Salesperson has receipts.view but NOT receipts.create
    ctx.users.create_user(username="sp", password="Str0ngPass!", full_name="Sales P",
                          role_codes=["SALESPERSON"])
    ctx.auth.logout(); ctx.auth.login("sp", "Str0ngPass!")
    with pytest.raises(AuthorizationError):
        ctx.receipts.post_receipt(party_id=cust, account_id=cash, amount="100",
                                  currency_code="AFN", receipt_date="2026-06-03")


# ---- rollback / persistence --------------------------------------------

def test_failed_post_leaves_no_partial_state(biz):
    _credit_sale(biz)
    before_receipts = len(biz.receipts.list())
    before_entries = biz.db.connection().execute(
        "SELECT COUNT(*) FROM financial_entries").fetchone()[0]
    with pytest.raises(ValidationError):
        biz.receipts.post_receipt(party_id=biz.cust, account_id=biz.cash, amount="-1",
                                  currency_code="AFN", receipt_date="2026-06-03")
    assert len(biz.receipts.list()) == before_receipts
    after_entries = biz.db.connection().execute(
        "SELECT COUNT(*) FROM financial_entries").fetchone()[0]
    assert after_entries == before_entries  # no partial journal
    assert _balanced(biz)


def test_document_numbers_unique_and_sequential(biz):
    _credit_sale(biz, qty="30")
    r1 = biz.receipts.post_receipt(party_id=biz.cust, account_id=biz.cash, amount="100",
                                   currency_code="AFN", receipt_date="2026-06-03")
    r2 = biz.receipts.post_receipt(party_id=biz.cust, account_id=biz.cash, amount="100",
                                   currency_code="AFN", receipt_date="2026-06-03")
    assert r1.document_no == "RCP-000001" and r2.document_no == "RCP-000002"


def test_multicurrency_rate_preserved(biz):
    _credit_sale(biz)
    r = biz.receipts.post_receipt(party_id=biz.cust, account_id=biz.cash, amount="10",
                                  currency_code="AFN", exchange_rate="70",
                                  receipt_date="2026-06-03")
    row = biz.receipts.get(r.id)
    assert row["exchange_rate"] == "70.0000" and row["amount"] == "10.00"
