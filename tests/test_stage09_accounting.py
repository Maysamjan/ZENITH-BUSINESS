"""Stage 09 — financial statements that reconcile with the ledger.

The owner's scenario is pinned exactly:

    net sales 1,000, COGS 625, expenses 100
    -> gross profit 375, net profit 275

Everything else asserts **invariants**, because the figures after a return or a
correction are not worth memorising but the rules behind them are:

* total debits equal total credits, always;
* Assets = Liabilities + Equity, always;
* the General Ledger closing for an account equals its Trial Balance closing;
* receivables and payables equal the party ledgers they came from;
* the COGS charged to the accounts equals the Stage 08 movement cost;
* GL Inventory equals the Stage 08 valuation — the two halves of the same fact;
* a movement is charged to COGS exactly once, whatever runs and however often.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from zenith_business.services.purchase_documents import PurchaseLine, PurchaseReturnLine
from zenith_business.services.sales_documents import ReturnLine, SaleLine

PERIOD = {"date_from": "2026-01-01", "date_to": "2026-12-31"}
AS_OF = "2026-12-31"


@pytest.fixture
def books(admin_context):
    ctx = admin_context
    ctx.financial_years.create(name="FY26", start_date="2026-01-01",
                               end_date="2026-12-31", make_active=True)
    ctx.main = ctx.warehouses.create(code="MAIN", name="Main Store", is_default=True)
    ctx.bag = ctx.units_repo.id_by_code("BAG")
    ctx.item = ctx.items.create(item_code="RICE", name="Rice", base_unit_id=ctx.bag,
                                purchase_price="125", default_sale_price="200")
    ctx.sup = ctx.parties.create(party_code="S1", name="Karim", is_supplier=True)
    ctx.cus = ctx.parties.create(party_code="C1", name="Ahmad", is_customer=True)
    ctx.cash = ctx.accounts_repo.id_by_code("1000")
    return ctx


def _buy(ctx, quantity="8", price="125", *, date="2026-03-01", paid="0"):
    return ctx.purchase_documents.post_purchase(
        currency_code="AFN", warehouse_id=ctx.main, party_id=ctx.sup,
        amount_paid=paid, purchase_date=date,
        lines=[PurchaseLine(item_id=ctx.item, unit_id=ctx.bag,
                            quantity=quantity, unit_price=price)])


def _sell(ctx, quantity="5", price="200", *, date="2026-03-05", paid="0"):
    return ctx.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=ctx.main, party_id=ctx.cus,
        amount_paid=paid, sale_date=date,
        lines=[SaleLine(item_id=ctx.item, unit_id=ctx.bag,
                        quantity=quantity, unit_price=price)])


def _spend(ctx, amount="100", *, date="2026-03-06"):
    category = next(c for c in ctx.expenses.categories() if c["code"] == "RENT")
    return ctx.expenses.post_expense(
        category_id=category["id"], account_id=ctx.cash, amount=amount,
        currency_code="AFN", expense_date=date, payee="Landlord")


def _owners_scenario(ctx):
    _buy(ctx)
    sale = _sell(ctx)
    _spend(ctx)
    return sale


def assert_buckets_add_up(report):
    """Ageing may move money between buckets; it may never create or lose any."""
    buckets = sum((Decimal(v) for v in report["totals"].values()), Decimal(0))
    assert buckets == Decimal(report["total"]), (
        f"buckets total {buckets}, the balance is {report['total']}")
    for row in report["rows"]:
        row_total = sum((Decimal(row[k]) for k in
                         ("current", "d1_30", "d31_60", "d61_90", "d90_plus")),
                        Decimal(0))
        assert row_total == Decimal(row["balance"]), (
            f"{row.get('party_code')}: buckets {row_total} vs balance {row['balance']}")


def assert_statements_reconcile(ctx):
    """Everything that must hold after ANY activity, whatever it was."""
    reports = ctx.accounting_reports
    tb = reports.trial_balance(**PERIOD)
    assert Decimal(tb["total_debit"]) == Decimal(tb["total_credit"]), (
        "the trial balance does not balance")
    assert tb["balanced"] is True

    bs = reports.balance_sheet(as_of=AS_OF)
    assert Decimal(bs["total_assets"]) == Decimal(bs["total_liabilities_equity"]), (
        "assets do not equal liabilities plus equity")
    assert bs["balanced"] is True

    # every account's own ledger must close where the trial balance says it does
    for row in tb["rows"]:
        gl = reports.general_ledger(account_id=row["account_id"], **PERIOD)
        assert gl["closing"] == row["closing"], (
            f"account {row['code']}: GL closes {gl['closing']},"
            f" trial balance says {row['closing']}")

    # the accounts and Stage 08 are two halves of one fact
    inventory = [r for r in tb["rows"] if r["code"] == "1200"]
    if inventory:
        assert inventory[0]["closing"] == ctx.costing_reports.valuation()["total"]["value"], (
            "GL Inventory has drifted from the Stage 08 valuation")
    pl = reports.profit_loss(**PERIOD)
    assert pl["cogs"] == ctx.costing_reports.gross_profit(**PERIOD)["cogs"], (
        "the COGS charged to the accounts is not the Stage 08 cost")
    return tb, bs, pl


# ---- the owner's mandatory numbers ---------------------------------------

def test_the_profit_and_loss_gives_the_owners_figures(books):
    _owners_scenario(books)
    pl = books.accounting_reports.profit_loss(**PERIOD)
    assert pl["net_sales"] == "1000.00"
    assert pl["cogs"] == "625.00"
    assert pl["gross_profit"] == "375.00"
    assert pl["operating_expenses"] == "100.00"
    assert pl["net_profit"] == "275.00"


def test_the_profit_and_loss_formulas_hold(books):
    _owners_scenario(books)
    pl = books.accounting_reports.profit_loss(**PERIOD)
    assert Decimal(pl["gross_profit"]) == Decimal(pl["net_sales"]) - Decimal(pl["cogs"])
    assert Decimal(pl["net_profit"]) == (Decimal(pl["gross_profit"])
                                         - Decimal(pl["operating_expenses"]))


def test_everything_reconciles_on_the_owners_scenario(books):
    _owners_scenario(books)
    tb, bs, pl = assert_statements_reconcile(books)
    assert tb["total_debit"] == "2725.00"
    assert bs["total_assets"] == "1275.00"
    assert bs["retained_result"] == "275.00"
    assert pl["net_profit"] == "275.00"


# ---- trial balance --------------------------------------------------------

def test_the_trial_balance_shows_opening_debit_credit_and_closing(books):
    _buy(books, date="2026-01-10")
    _sell(books, date="2026-02-10")
    rows = {r["code"]: r for r in books.accounting_reports.trial_balance(
        date_from="2026-02-01", date_to="2026-12-31")["rows"]}
    inventory = rows["1200"]
    # bought in January, sold in February: the purchase is the opening balance
    assert inventory["opening"] == "1000.00"
    assert inventory["credit"] == "625.00"
    assert inventory["closing"] == "375.00"
    assert Decimal(inventory["closing"]) == (Decimal(inventory["opening"])
                                             + Decimal(inventory["debit"])
                                             - Decimal(inventory["credit"]))


def test_an_empty_period_still_balances(books):
    _owners_scenario(books)
    tb = books.accounting_reports.trial_balance(date_from="2027-01-01",
                                                date_to="2027-12-31")
    assert tb["balanced"] is True
    assert tb["total_debit"] == tb["total_credit"]


# ---- balance sheet --------------------------------------------------------

def test_the_balance_sheet_carries_the_period_result_into_equity(books):
    """Without a year close the profit has nowhere else to sit, and A=L+E fails."""
    _owners_scenario(books)
    bs = books.accounting_reports.balance_sheet(as_of=AS_OF)
    assert bs["retained_result"] == "275.00"
    assert bs["total_equity"] == "275.00"
    assert bs["balanced"] is True


def test_the_balance_sheet_balances_with_no_activity_at_all(books):
    bs = books.accounting_reports.balance_sheet(as_of=AS_OF)
    assert bs["balanced"] is True
    assert bs["total_assets"] == "0.00"


# ---- general ledger -------------------------------------------------------

def test_the_general_ledger_runs_a_balance_and_can_be_filtered(books):
    _owners_scenario(books)
    inventory_id = books.accounts_repo.id_by_code("1200")
    gl = books.accounting_reports.general_ledger(account_id=inventory_id, **PERIOD)
    assert [r["debit"] for r in gl["rows"]] == ["1000.00", "0.00"]
    assert [r["credit"] for r in gl["rows"]] == ["0.00", "625.00"]
    assert [r["balance"] for r in gl["rows"]] == ["1000.00", "375.00"]
    assert gl["closing"] == "375.00"
    for row in gl["rows"]:
        assert row["date"] and row["reference"], "a ledger line needs a date and a reference"


def test_the_general_ledger_respects_the_date_filter(books):
    _buy(books, date="2026-01-10")
    _sell(books, date="2026-06-10")
    inventory_id = books.accounts_repo.id_by_code("1200")
    gl = books.accounting_reports.general_ledger(
        account_id=inventory_id, date_from="2026-06-01", date_to="2026-12-31")
    assert len(gl["rows"]) == 1
    assert gl["opening"] == "1000.00"           # January carried in as opening
    assert gl["closing"] == "375.00"


# ---- cash & bank ----------------------------------------------------------

def test_cash_and_bank_reports_the_fund_accounts(books):
    _buy(books, paid="400")
    _spend(books)
    cash = {a["code"]: a for a in books.accounting_reports.cash_bank(**PERIOD)["accounts"]}
    assert cash["1000"]["money_out"] == "500.00"        # 400 paid + 100 rent
    assert cash["1000"]["closing"] == "-500.00"
    tb = {r["code"]: r for r in books.accounting_reports.trial_balance(**PERIOD)["rows"]}
    assert cash["1000"]["closing"] == tb["1000"]["closing"]


# ---- receivables / payables ----------------------------------------------

def test_receivables_and_payables_agree_with_the_party_ledgers(books):
    _owners_scenario(books)
    ar = books.accounting_reports.receivables(as_of=AS_OF)
    ap = books.accounting_reports.payables(as_of=AS_OF)
    assert ar["total"] == books.party_ledger.customer_ledger(
        books.cus)["totals"]["receivable"]
    assert ap["total"] == books.party_ledger.supplier_ledger(
        books.sup)["totals"]["payable"]


def test_receivables_agree_with_the_trial_balance(books):
    _owners_scenario(books)
    ar = books.accounting_reports.receivables(as_of=AS_OF)
    tb = {r["code"]: r for r in books.accounting_reports.trial_balance(**PERIOD)["rows"]}
    assert ar["total"] == tb["1100"]["closing"]


def test_the_ageing_buckets_add_up_to_the_balance(books):
    _owners_scenario(books)
    ar = books.accounting_reports.receivables(as_of=AS_OF)
    buckets = sum((Decimal(v) for v in ar["totals"].values()), Decimal(0))
    assert buckets == Decimal(ar["total"]), "the ageing does not add up to the receivable"
    for row in ar["rows"]:
        row_buckets = sum((Decimal(row[k]) for k in
                           ("current", "d1_30", "d31_60", "d61_90", "d90_plus")),
                          Decimal(0))
        assert row_buckets == Decimal(row["balance"])


def test_an_old_invoice_ages_into_the_right_bucket(books):
    _buy(books, date="2026-01-01")
    _sell(books, date="2026-03-05")
    ar = books.accounting_reports.receivables(as_of="2026-05-01")   # 57 days later
    assert ar["totals"]["d31_60"] == "1000.00"
    assert ar["totals"]["d1_30"] == "0.00"


def test_a_payment_clears_the_oldest_debt_first(books):
    _buy(books, quantity="20", date="2026-01-01")
    _sell(books, quantity="1", date="2026-01-10")     # old invoice, 200
    _sell(books, quantity="2", date="2026-06-10")     # recent invoice, 400
    books.receipts.post_receipt(party_id=books.cus, account_id=books.cash,
                                amount="200", currency_code="AFN",
                                receipt_date="2026-06-20")
    ar = books.accounting_reports.receivables(as_of="2026-06-25")
    # the January invoice is settled; only the June one is left, and it is recent
    assert ar["total"] == "400.00"
    assert ar["totals"]["d1_30"] == "400.00"
    assert ar["totals"]["d90_plus"] == "0.00"


def test_a_return_credits_its_own_invoice_not_the_oldest_one(books):
    """A credit note names its document, so it must not pay down an older one.

    Found on real data during the Stage 09 verification: a return against a
    recent invoice was being applied oldest-first like an unallocated payment,
    which left the recent invoice standing at full value and made an untouched
    old invoice look part-paid. The balance was right and the ageing was not,
    which is the one thing an ageing report exists to get right.
    """
    _buy(books, quantity="40", date="2026-01-01")
    _sell(books, quantity="10", price="200", date="2026-01-10")    # old, 2,000
    recent = _sell(books, quantity="5", price="200", date="2026-06-10")  # 1,000
    line = books.sales_repo.lines_for(recent.id)[0]
    books.sales_documents.post_return(
        sale_id=recent.id, return_date="2026-06-15",
        lines=[ReturnLine(sale_line_id=line["id"], quantity="2")])   # credit 400

    ar = books.accounting_reports.receivables(as_of="2026-06-25")
    assert ar["total"] == "2600.00"
    # the 400 belongs to the June invoice: 1,000 - 400 = 600 still recent
    assert ar["totals"]["d1_30"] == "600.00"
    # and the January invoice is untouched, not 400 lighter
    assert ar["totals"]["d90_plus"] == "2000.00"
    assert_buckets_add_up(ar)


def test_a_voided_invoice_leaves_the_ageing_entirely(books):
    _buy(books, quantity="40", date="2026-01-01")
    _sell(books, quantity="10", price="200", date="2026-01-10")    # old, 2,000
    doomed = _sell(books, quantity="5", price="200", date="2026-06-10")
    books.sales_documents.void_sale(sale_id=doomed.id, reason="Test",
                                    void_date="2026-06-12")

    ar = books.accounting_reports.receivables(as_of="2026-06-25")
    assert ar["total"] == "2000.00"
    # the voided invoice is gone from its own bucket ...
    assert ar["totals"]["d1_30"] == "0.00"
    # ... and did not quietly pay down the January one
    assert ar["totals"]["d90_plus"] == "2000.00"
    assert_buckets_add_up(ar)


def test_a_correction_ages_with_the_invoice_it_amends(books):
    _buy(books, quantity="40", date="2026-01-01")
    _sell(books, quantity="10", price="200", date="2026-01-10")    # old, 2,000
    amended = _sell(books, quantity="5", price="200", date="2026-06-10")
    books.sales_documents.correct_sale(
        sale_id=amended.id, currency_code="AFN", warehouse_id=books.main,
        party_id=books.cus, amount_paid="0", sale_date="2026-06-10",
        lines=[SaleLine(item_id=books.item, unit_id=books.bag,
                        quantity="3", unit_price="200")])           # 1,000 -> 600

    ar = books.accounting_reports.receivables(as_of="2026-06-25")
    assert ar["total"] == "2600.00"
    assert ar["totals"]["d1_30"] == "600.00"
    assert ar["totals"]["d90_plus"] == "2000.00"
    assert_buckets_add_up(ar)


def test_a_purchase_return_credits_its_own_bill(books):
    """The same rule on the supplier side."""
    old = _buy(books, quantity="10", price="100", date="2026-01-05")   # 1,000
    recent = _buy(books, quantity="5", price="100", date="2026-06-10")  # 500
    line = books.purchases_repo.lines_for(recent.id)[0]
    books.purchase_documents.post_return(
        purchase_id=recent.id, return_date="2026-06-15",
        lines=[PurchaseReturnLine(purchase_line_id=line["id"], quantity="2")])

    ap = books.accounting_reports.payables(as_of="2026-06-25")
    assert ap["total"] == "1300.00"
    assert ap["totals"]["d1_30"] == "300.00"     # 500 - 200, on its own bill
    assert ap["totals"]["d90_plus"] == "1000.00"  # January bill untouched
    assert_buckets_add_up(ap)


def test_an_unallocated_receipt_still_clears_the_oldest_debt(books):
    """The oldest-first rule stays where it belongs: money that names nothing."""
    _buy(books, quantity="40", date="2026-01-01")
    old = _sell(books, quantity="10", price="200", date="2026-01-10")   # 2,000
    _sell(books, quantity="5", price="200", date="2026-06-10")         # 1,000
    line = books.sales_repo.lines_for(old.id)[0]
    # a return on the OLD invoice, plus a receipt that names no invoice at all
    books.sales_documents.post_return(
        sale_id=old.id, return_date="2026-06-14",
        lines=[ReturnLine(sale_line_id=line["id"], quantity="2")])     # 400
    books.receipts.post_receipt(party_id=books.cus, account_id=books.cash,
                                amount="600", currency_code="AFN",
                                receipt_date="2026-06-20")
    ar = books.accounting_reports.receivables(as_of="2026-06-25")
    assert ar["total"] == "2000.00"
    # the return took its own invoice to 1,600; the receipt then cleared the
    # oldest 600 of that, leaving 1,000 old and the June 1,000 recent
    assert ar["totals"]["d90_plus"] == "1000.00"
    assert ar["totals"]["d1_30"] == "1000.00"
    assert_buckets_add_up(ar)


# ---- COGS posting ---------------------------------------------------------

def test_the_cogs_journal_equals_the_stage_08_cost(books):
    _owners_scenario(books)
    books.accounting_reports.trial_balance(**PERIOD)       # reading posts it
    assert books.cogs_posting.posted_total(**PERIOD) == "625.00"
    assert books.cogs_posting.posted_total(**PERIOD) == \
        books.costing_reports.gross_profit(**PERIOD)["cogs"]


def test_the_posting_happens_exactly_once(books):
    _owners_scenario(books)
    for _ in range(4):
        books.accounting_reports.trial_balance(**PERIOD)
        books.accounting_reports.profit_loss(**PERIOD)
    assert books.cogs_posting.sync() == 0
    count = books.db.connection().execute(
        "SELECT COUNT(*) FROM financial_entries WHERE source_type = 'COGS'").fetchone()[0]
    assert count == 1, f"{count} COGS journals for one sale"


def test_the_database_itself_refuses_a_second_charge(books):
    """The guarantee is an index, not a hopeful check in the service."""
    import sqlite3

    _owners_scenario(books)
    books.cogs_posting.sync()
    movement = books.db.connection().execute(
        "SELECT source_id FROM financial_entries WHERE source_type = 'COGS'").fetchone()[0]
    with pytest.raises(sqlite3.IntegrityError):
        books.db.connection().execute(
            "INSERT INTO financial_entries (entry_no, entry_date, source_type,"
            " source_id, created_at) VALUES ('JV-DUP', '2026-03-05', 'COGS', ?, 'now')",
            (movement,))


def test_a_sales_return_reverses_the_cost(books):
    sale = _owners_scenario(books)
    line = books.sales_repo.lines_for(sale.id)[0]
    books.sales_documents.post_return(
        sale_id=sale.id, return_date="2026-03-10",
        lines=[ReturnLine(sale_line_id=line["id"], quantity="2")])
    _tb, _bs, pl = assert_statements_reconcile(books)
    assert pl["cogs"] == "375.00"                   # 3 of 5 still sold
    assert pl["net_sales"] == "600.00"
    assert pl["gross_profit"] == "225.00"


def test_a_sale_correction_reconciles(books):
    sale = _owners_scenario(books)
    books.sales_documents.correct_sale(
        sale_id=sale.id, currency_code="AFN", warehouse_id=books.main,
        party_id=books.cus, amount_paid="0", sale_date="2026-03-05",
        lines=[SaleLine(item_id=books.item, unit_id=books.bag,
                        quantity="6", unit_price="200")])
    _tb, _bs, pl = assert_statements_reconcile(books)
    assert pl["net_sales"] == "1200.00"
    assert pl["cogs"] == "750.00"                   # 6 at 125


def test_voiding_a_sale_takes_the_cost_back_out(books):
    sale = _owners_scenario(books)
    books.sales_documents.void_sale(sale_id=sale.id, reason="entered twice")
    _tb, _bs, pl = assert_statements_reconcile(books)
    assert pl["net_sales"] == "0.00"
    assert pl["cogs"] == "0.00"
    assert pl["net_profit"] == "-100.00"            # the rent still happened


def test_a_purchase_return_leaves_the_accounts_reconciled(books):
    purchase = _buy(books)
    _sell(books, quantity="2")
    line = books.purchases_repo.lines_for(purchase.id)[0]
    books.purchase_documents.post_return(
        purchase_id=purchase.id, return_date="2026-03-20",
        lines=[PurchaseReturnLine(purchase_line_id=line["id"], quantity="3")])
    assert_statements_reconcile(books)


def test_the_cost_never_comes_from_the_selling_price(books):
    """A huge markup must not inflate what the accounts call cost."""
    _buy(books, quantity="2", price="125")
    _sell(books, quantity="1", price="9999")
    pl = books.accounting_reports.profit_loss(**PERIOD)
    assert pl["cogs"] == "125.00"
    assert pl["net_sales"] == "9999.00"


def test_the_cogs_entry_is_dated_by_the_movement_not_by_the_run(books):
    """A cost belongs to the period the goods moved in."""
    _buy(books, date="2026-01-05")
    _sell(books, date="2026-01-20")
    books.cogs_posting.sync()
    entry_date = books.db.connection().execute(
        "SELECT entry_date FROM financial_entries WHERE source_type = 'COGS'").fetchone()[0]
    assert entry_date == "2026-01-20"
    # so a January statement includes it, and a March one does not
    assert books.accounting_reports.profit_loss(
        date_from="2026-01-01", date_to="2026-01-31")["cogs"] == "625.00"
    assert books.accounting_reports.profit_loss(
        date_from="2026-03-01", date_to="2026-03-31")["cogs"] == "0.00"


def test_the_ledger_traces_back_to_the_movement(books):
    """Ledger → movement → document, the §8 rule."""
    _owners_scenario(books)
    books.cogs_posting.sync()
    pending = books.db.connection().execute(
        "SELECT source_id FROM financial_entries WHERE source_type = 'COGS'").fetchone()[0]
    entry = books.cogs_posting.entry_for_movement(pending)
    assert entry is not None
    assert entry["entry_no"].startswith("JV-")


# ---- permission -----------------------------------------------------------

def test_the_statements_require_the_accounting_permission(books, monkeypatch):
    from zenith_business.services.exceptions import AuthorizationError

    def deny(code):
        if code == "accounting.reports":
            raise AuthorizationError("accounting.reports")

    monkeypatch.setattr(books.authz, "require", deny)
    with pytest.raises(AuthorizationError):
        books.accounting_reports.trial_balance(**PERIOD)
