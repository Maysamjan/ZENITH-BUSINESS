"""Stage 08 — weighted-average costing, valuation, COGS and gross profit.

The owner's own scenario is pinned exactly:

    buy 10 @ 100, buy 10 @ 120  ->  qty 20, average 110, value 2,200
    sell 5 @ 150                ->  net sales 750, COGS 550, profit 200,
                                    remaining qty 15, remaining value 1,650

Everything else asserts **invariants** rather than remembered figures, because
the numbers after six kinds of correction are not worth memorising but the rules
behind them are:

* value on hand == the ledger's own ``total_cost`` sum, always;
* item rows and warehouse rows both add up to the company total;
* a transfer never changes what the company is worth;
* a reversal takes stock back out at the cost it came in at;
* COGS is what the goods that left actually cost, net of returns.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from zenith_business.services.purchase_documents import PurchaseLine, PurchaseReturnLine
from zenith_business.services.sales_documents import ReturnLine, SaleLine

PERIOD = {"date_from": "2026-01-01", "date_to": "2026-12-31"}


@pytest.fixture
def books(admin_context):
    ctx = admin_context
    ctx.financial_years.create(name="FY26", start_date="2026-01-01",
                               end_date="2026-12-31", make_active=True)
    ctx.main = ctx.warehouses.create(code="MAIN", name="Main Store", is_default=True)
    ctx.branch = ctx.warehouses.create(code="BR1", name="Branch Store")
    ctx.bag = ctx.units_repo.id_by_code("BAG")
    ctx.item = ctx.items.create(item_code="RICE", name="Rice", base_unit_id=ctx.bag,
                                purchase_price="100", default_sale_price="150")
    ctx.sup = ctx.parties.create(party_code="S1", name="Karim", is_supplier=True)
    ctx.cus = ctx.parties.create(party_code="C1", name="Ahmad", is_customer=True)
    return ctx


# ---- helpers -------------------------------------------------------------

def _buy(ctx, quantity, price, *, warehouse=None, date="2026-02-01"):
    return ctx.purchase_documents.post_purchase(
        currency_code="AFN", warehouse_id=warehouse or ctx.main, party_id=ctx.sup,
        amount_paid="0", purchase_date=date,
        lines=[PurchaseLine(item_id=ctx.item, unit_id=ctx.bag,
                            quantity=quantity, unit_price=price)])


def _sell(ctx, quantity, price="150", *, warehouse=None, date="2026-02-03"):
    return ctx.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=warehouse or ctx.main, party_id=ctx.cus,
        amount_paid="0", sale_date=date,
        lines=[SaleLine(item_id=ctx.item, unit_id=ctx.bag,
                        quantity=quantity, unit_price=price)])


def position(ctx, warehouse_id=None):
    return ctx.costing_reports.valuation(warehouse_id=warehouse_id)["total"]


def assert_ledger_is_consistent(ctx):
    """The invariants that must hold after ANY operation, whatever it was."""
    report = ctx.costing_reports.valuation()
    total = report["total"]

    # quantity agrees with the inventory ledger the rest of the app reads
    assert Decimal(total["quantity"]) == Decimal(
        ctx.inventory_repo.stock_on_hand(ctx.item)), "valuation quantity left the ledger"

    # the value is the ledger's own sum — no separate store to drift
    raw = ctx.db.connection().execute(
        "SELECT total_cost FROM inventory_movements").fetchall()
    ledger_value = sum((Decimal(r[0]) for r in raw if r[0] is not None), Decimal(0))
    assert Decimal(total["value"]) == ledger_value, "value is not the ledger's sum"

    # every grouping adds up to the same company total
    assert sum((Decimal(r["value"]) for r in report["items"]), Decimal(0)) \
        == Decimal(total["value"]), "item rows do not add up to the total"
    assert sum((Decimal(r["value"]) for r in report["warehouses"]), Decimal(0)) \
        == Decimal(total["value"]), "warehouse rows do not add up to the total"

    # nothing escaped the costing engine
    uncosted = ctx.db.connection().execute(
        "SELECT COUNT(*) FROM inventory_movements"
        " WHERE unit_cost IS NULL OR total_cost IS NULL").fetchone()[0]
    assert uncosted == 0, f"{uncosted} movements were never costed"
    return total


# ---- the owner's mandatory scenario, to the cent -------------------------

def test_weighted_average_after_two_purchases_at_different_prices(books):
    _buy(books, "10", "100")
    _buy(books, "10", "120")
    total = assert_ledger_is_consistent(books)
    assert total["quantity"] == "20.000"
    assert Decimal(total["average_cost"]) == Decimal("110")
    assert total["value"] == "2200.00"


def test_selling_five_gives_the_owners_numbers(books):
    _buy(books, "10", "100")
    _buy(books, "10", "120")
    _sell(books, "5")
    total = assert_ledger_is_consistent(books)
    gp = books.costing_reports.gross_profit(**PERIOD)
    assert gp["net_sales"] == "750.00"
    assert gp["cogs"] == "550.00"
    assert gp["gross_profit"] == "200.00"
    assert total["quantity"] == "15.000"
    assert total["value"] == "1650.00"


def test_a_sale_does_not_move_the_average(books):
    _buy(books, "10", "100")
    _buy(books, "10", "120")
    _sell(books, "5")
    total = position(books)
    assert Decimal(total["average_cost"]) == Decimal("110")


def test_cost_never_comes_from_the_selling_price(books):
    """A 1,000% markup must not make the stock worth more."""
    _buy(books, "10", "100")
    _sell(books, "1", price="1000")
    total = assert_ledger_is_consistent(books)
    assert Decimal(total["average_cost"]) == Decimal("100")
    assert books.costing_reports.gross_profit(**PERIOD)["cogs"] == "100.00"


def test_cogs_is_reported_per_invoice(books):
    _buy(books, "10", "100")
    _buy(books, "10", "120")
    sale = _sell(books, "5")
    assert books.costing_reports.cogs_for_sale(sale.id) == "550.00"


# ---- the six flows that must not break the cost -------------------------

def test_a_sales_return_restores_the_cost_it_left_at(books):
    _buy(books, "10", "100")
    _buy(books, "10", "120")
    sale = _sell(books, "5")
    line = books.sales_repo.lines_for(sale.id)[0]
    books.sales_documents.post_return(
        sale_id=sale.id, return_date="2026-02-04",
        lines=[ReturnLine(sale_line_id=line["id"], quantity="2")])
    total = assert_ledger_is_consistent(books)
    assert total["quantity"] == "17.000"
    assert total["value"] == "1870.00"                 # 17 x 110, exactly
    assert Decimal(total["average_cost"]) == Decimal("110")
    assert books.costing_reports.gross_profit(**PERIOD)["cogs"] == "330.00"


def test_a_purchase_return_leaves_at_what_was_paid_not_at_the_average(books):
    """Returning the expensive goods must remove the expensive cost."""
    _buy(books, "10", "100")
    dear = _buy(books, "10", "120")
    line = books.purchases_repo.lines_for(dear.id)[0]
    books.purchase_documents.post_return(
        purchase_id=dear.id, return_date="2026-02-05",
        lines=[PurchaseReturnLine(purchase_line_id=line["id"], quantity="10")])
    total = assert_ledger_is_consistent(books)
    assert total["quantity"] == "10.000"
    # 2,200 - (10 x 120) = 1,000: what is left is the cheap stock, at its own cost
    assert total["value"] == "1000.00"
    assert Decimal(total["average_cost"]) == Decimal("100")


def test_a_purchase_correction_recosts_the_bill_it_amended(books):
    purchase = _buy(books, "10", "100")
    books.purchase_documents.correct_purchase(
        purchase_id=purchase.id, currency_code="AFN", warehouse_id=books.main,
        party_id=books.sup, amount_paid="0", purchase_date="2026-02-01",
        lines=[PurchaseLine(item_id=books.item, unit_id=books.bag,
                            quantity="10", unit_price="130")])
    total = assert_ledger_is_consistent(books)
    assert total["quantity"] == "10.000"
    assert total["value"] == "1300.00"                 # the corrected price, not the old one
    assert Decimal(total["average_cost"]) == Decimal("130")


def test_a_sale_correction_keeps_the_cost_straight(books):
    _buy(books, "10", "100")
    sale = _sell(books, "4")
    books.sales_documents.correct_sale(
        sale_id=sale.id, currency_code="AFN", warehouse_id=books.main,
        party_id=books.cus, amount_paid="0", sale_date="2026-02-03",
        lines=[SaleLine(item_id=books.item, unit_id=books.bag,
                        quantity="6", unit_price="150")])
    total = assert_ledger_is_consistent(books)
    assert total["quantity"] == "4.000"
    assert total["value"] == "400.00"
    assert books.costing_reports.gross_profit(**PERIOD)["cogs"] == "600.00"


def test_an_adjustment_in_does_not_move_the_average(books):
    _buy(books, "10", "100")
    _buy(books, "10", "120")
    before = Decimal(position(books)["average_cost"])
    books.inventory.adjust(item_id=books.item, warehouse_id=books.main, delta="5",
                           reason="Found stock during a count")
    total = assert_ledger_is_consistent(books)
    assert abs(Decimal(total["average_cost"]) - before) < Decimal("0.0001")
    assert total["quantity"] == "25.000"


def test_an_adjustment_out_removes_stock_at_the_average(books):
    _buy(books, "10", "100")
    _buy(books, "10", "120")
    books.inventory.adjust(item_id=books.item, warehouse_id=books.main, delta="-2",
                           reason="Damaged in the store")
    total = assert_ledger_is_consistent(books)
    assert total["quantity"] == "18.000"
    assert total["value"] == "1980.00"                 # 2,200 - (2 x 110)


def test_a_transfer_never_changes_what_the_company_is_worth(books):
    """The owner's explicit requirement, asserted as an equality."""
    _buy(books, "10", "100")
    _buy(books, "10", "120")
    before = position(books)["value"]
    books.inventory.transfer(item_id=books.item, from_warehouse_id=books.main,
                             to_warehouse_id=books.branch, quantity_moved="8",
                             notes="Stock the branch")
    total = assert_ledger_is_consistent(books)
    assert total["value"] == before, "a transfer changed the company's inventory value"
    main = position(books, books.main)
    branch = position(books, books.branch)
    assert Decimal(main["value"]) + Decimal(branch["value"]) == Decimal(before)
    assert branch["quantity"] == "8.000"
    # the stock arrived carrying the cost it left with
    assert abs(Decimal(branch["average_cost"]) - Decimal("110")) < Decimal("0.01")


def test_each_warehouse_keeps_its_own_average(books):
    """Averaging per warehouse is what makes per-warehouse valuation truthful."""
    _buy(books, "10", "100", warehouse=books.main)
    _buy(books, "10", "200", warehouse=books.branch)
    assert_ledger_is_consistent(books)
    assert Decimal(position(books, books.main)["average_cost"]) == Decimal("100")
    assert Decimal(position(books, books.branch)["average_cost"]) == Decimal("200")
    # and the company average is value/quantity, not the average of two averages
    assert Decimal(position(books)["average_cost"]) == Decimal("150")


# ---- reports -------------------------------------------------------------

def test_valuation_reports_quantity_average_and_value_per_item(books):
    _buy(books, "10", "100")
    rows = books.costing_reports.valuation()["items"]
    assert len(rows) == 1
    row = rows[0]
    assert row["item_code"] == "RICE"
    assert row["quantity"] == "10.000"
    assert row["value"] == "1000.00"
    assert Decimal(row["average_cost"]) == Decimal("100")


def test_valuation_can_be_asked_per_warehouse(books):
    _buy(books, "10", "100", warehouse=books.main)
    _buy(books, "4", "100", warehouse=books.branch)
    by_wh = {r["warehouse_name"]: r for r in
             books.costing_reports.valuation()["warehouses"]}
    assert by_wh["Main Store"]["quantity"] == "10.000"
    assert by_wh["Branch Store"]["quantity"] == "4.000"


def test_gross_profit_is_net_sales_minus_cogs(books):
    _buy(books, "10", "100")
    _sell(books, "4")
    gp = books.costing_reports.gross_profit(**PERIOD)
    assert Decimal(gp["gross_profit"]) == Decimal(gp["net_sales"]) - Decimal(gp["cogs"])


def test_gross_profit_uses_the_locked_sales_definition_of_net_sales(books):
    """Net sales must not be redefined here — two definitions means two answers."""
    _buy(books, "10", "100")
    sale = _sell(books, "4")
    line = books.sales_repo.lines_for(sale.id)[0]
    books.sales_documents.post_return(
        sale_id=sale.id, return_date="2026-02-04",
        lines=[ReturnLine(sale_line_id=line["id"], quantity="1")])
    gp = books.costing_reports.gross_profit(**PERIOD)
    sales = books.sales_reports.summary(**PERIOD)
    assert gp["net_sales"] == sales["net"]


def test_margin_is_blank_rather_than_zero_when_there_are_no_sales(books):
    _buy(books, "10", "100")
    assert books.costing_reports.gross_profit(**PERIOD)["margin_percent"] == ""


def test_the_cogs_report_agrees_with_the_gross_profit_figure(books):
    _buy(books, "10", "100")
    _sell(books, "4")
    cogs = books.costing_reports.cogs(**PERIOD)
    gp = books.costing_reports.gross_profit(**PERIOD)
    assert cogs["total"] == gp["cogs"]
    assert sum((Decimal(r["cogs"]) for r in cogs["items"]), Decimal(0)) \
        == Decimal(cogs["total"])


# ---- the ledger is the one source of truth ------------------------------

def test_every_movement_is_costed_whatever_created_it(books):
    """No posting path may create stock that nobody valued."""
    purchase = _buy(books, "10", "100")
    sale = _sell(books, "2")
    line = books.sales_repo.lines_for(sale.id)[0]
    books.sales_documents.post_return(
        sale_id=sale.id, return_date="2026-02-04",
        lines=[ReturnLine(sale_line_id=line["id"], quantity="1")])
    books.inventory.adjust(item_id=books.item, warehouse_id=books.main, delta="1",
                           reason="count")
    books.inventory.transfer(item_id=books.item, from_warehouse_id=books.main,
                             to_warehouse_id=books.branch, quantity_moved="2")
    books.purchase_documents.correct_purchase(
        purchase_id=purchase.id, currency_code="AFN", warehouse_id=books.main,
        party_id=books.sup, amount_paid="0", purchase_date="2026-02-01",
        lines=[PurchaseLine(item_id=books.item, unit_id=books.bag,
                            quantity="12", unit_price="100")])
    assert_ledger_is_consistent(books)


def test_opening_stock_is_valued_at_the_items_purchase_price(books):
    item = books.items.create(item_code="TEA", name="Tea", base_unit_id=books.bag,
                              purchase_price="55", default_sale_price="90")
    books.inventory.record_opening(item_id=item, warehouse_id=books.main,
                                   quantity_on_hand="4")
    row = [r for r in books.costing_reports.valuation()["items"]
           if r["item_code"] == "TEA"][0]
    assert row["value"] == "220.00"
    assert Decimal(row["average_cost"]) == Decimal("55")


def test_a_void_takes_the_stock_back_out_at_the_cost_it_came_in_at(books):
    purchase = _buy(books, "10", "100")
    _buy(books, "10", "120")
    books.purchase_documents.void_purchase(purchase_id=purchase.id, reason="wrong supplier")
    total = assert_ledger_is_consistent(books)
    assert total["quantity"] == "10.000"
    # the 100 stock left at 100, so what remains is the 120 stock at its own cost
    assert total["value"] == "1200.00"
    assert Decimal(total["average_cost"]) == Decimal("120")


def test_the_migration_backfills_an_existing_uncosted_ledger(books):
    """A live database must not report its stock as worthless after upgrading."""
    from zenith_business.database.schema_stage08 import backfill_costs

    _buy(books, "10", "100")
    _buy(books, "10", "120")
    _sell(books, "5")
    expected = position(books)["value"]

    conn = books.db.connection()
    conn.execute("UPDATE inventory_movements SET unit_cost = NULL, total_cost = NULL")
    assert position(books)["value"] == "0.00"          # the pre-Stage-08 state

    costed = backfill_costs(conn)
    assert costed == 3
    assert position(books)["value"] == expected
    assert_ledger_is_consistent(books)


def test_the_backfill_never_revalues_what_is_already_costed(books):
    from zenith_business.database.schema_stage08 import backfill_costs

    _buy(books, "10", "100")
    before = position(books)["value"]
    assert backfill_costs(books.db.connection()) == 0
    assert position(books)["value"] == before
