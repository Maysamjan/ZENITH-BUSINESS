"""Stage 09 printed-report polish: ageing totals, ledger naming, ledger header.

Three owner-reported report issues. Each is pinned by what the report actually
produces — the payload the screen renders and the sheet prints — rather than by
the shape of the code behind it.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from zenith_business.core.i18n import LANG_DARI, LANG_ENGLISH, Translator
from zenith_business.services.purchase_documents import PurchaseLine
from zenith_business.services.sales_documents import SaleLine

AS_OF = "2026-06-30"
BUCKETS = ("current", "d1_30", "d31_60", "d61_90", "d90_plus")


@pytest.fixture
def shop(admin_context):
    ctx = admin_context
    ctx.financial_years.create(name="FY26", start_date="2026-01-01",
                               end_date="2026-12-31", make_active=True)
    ctx.main = ctx.warehouses.create(code="MAIN", name="Main Store", is_default=True)
    ctx.bag = ctx.units_repo.id_by_code("BAG")
    ctx.rice = ctx.items.create(item_code="RICE", name="Rice", base_unit_id=ctx.bag,
                                purchase_price="100", default_sale_price="200")
    ctx.sup = ctx.parties.create(party_code="S1", name="Karim", is_supplier=True)
    ctx.cus = ctx.parties.create(party_code="C1", name="Ahmad", is_customer=True)
    ctx.cus2 = ctx.parties.create(party_code="C2", name="Zarmina", is_customer=True)
    ctx.purchase_documents.post_purchase(
        currency_code="AFN", warehouse_id=ctx.main, party_id=ctx.sup,
        amount_paid="0", purchase_date="2026-01-05",
        lines=[PurchaseLine(item_id=ctx.rice, unit_id=ctx.bag, quantity="100",
                            unit_price="100")])
    # Two customers, invoices spread so more than one bucket is populated.
    for party, date, qty in ((ctx.cus, "2026-01-10", "5"),      # 171 days -> 90+
                             (ctx.cus, "2026-06-20", "3"),      #  10 days -> 1-30
                             (ctx.cus2, "2026-06-30", "2")):    #   0 days -> current
        ctx.sales_documents.post_sale(
            currency_code="AFN", warehouse_id=ctx.main, party_id=party,
            amount_paid="0", sale_date=date,
            lines=[SaleLine(item_id=ctx.rice, unit_id=ctx.bag,
                            quantity=qty, unit_price="200")])
    return ctx


def _page(ctx, language=LANG_ENGLISH):
    from zenith_business.ui.documents.accounting_report_page import AccountingReportPage

    page = AccountingReportPage(ctx, Translator(language))
    page._from_edit.setDate(page._from_edit.date().fromString("2026-01-01", "yyyy-MM-dd"))
    page._to_edit.setDate(page._to_edit.date().fromString(AS_OF, "yyyy-MM-dd"))
    return page


# ---- 1. the ageing totals row --------------------------------------------

def test_the_receivables_payload_carries_a_totals_row(shop, qapp):
    page = _page(shop)
    page._set_kind("receivables")
    total_row = page._last["total_row"]
    assert total_row is not None, "the ageing report has no totals row"

    report = shop.accounting_reports.receivables(as_of=AS_OF)
    for key in BUCKETS:
        assert total_row[key] == report["totals"][key]
    assert total_row["balance"] == report["total"]


def test_the_totals_row_is_the_sum_of_the_bucket_columns(shop, qapp):
    page = _page(shop)
    page._set_kind("receivables")
    rows, total_row = page._last["rows"], page._last["total_row"]
    for key in BUCKETS + ("balance",):
        column = sum((Decimal(r[key]) for r in rows), Decimal(0))
        assert Decimal(total_row[key]) == column, (
            f"the {key} total says {total_row[key]} but the column adds to {column}")


def test_the_payables_report_has_one_too(shop, qapp):
    shop.purchase_documents.post_purchase(
        currency_code="AFN", warehouse_id=shop.main, party_id=shop.sup,
        amount_paid="0", purchase_date="2026-06-25",
        lines=[PurchaseLine(item_id=shop.rice, unit_id=shop.bag, quantity="4",
                            unit_price="100")])
    page = _page(shop)
    page._set_kind("payables")
    total_row = page._last["total_row"]
    report = shop.accounting_reports.payables(as_of=AS_OF)
    assert total_row["balance"] == report["total"]
    assert sum((Decimal(total_row[k]) for k in BUCKETS), Decimal(0)) \
        == Decimal(report["total"])


def test_the_totals_row_is_on_screen_below_the_parties(shop, qapp):
    page = _page(shop)
    page._set_kind("receivables")
    report = shop.accounting_reports.receivables(as_of=AS_OF)
    # one row per party, plus the totals row
    assert page._table.rowCount() == len(report["rows"]) + 1

    last = page._table.rowCount() - 1
    texts = [page._table.item(last, c).text()
             for c in range(page._table.columnCount())]
    assert texts[-1] == f"{Decimal(report['total']):,.2f}"
    assert page._table.item(last, 0).font().bold(), "the totals row is not emphasised"


def test_a_statement_without_bucket_totals_has_no_totals_row(shop, qapp):
    """A trial balance's totals are not per-column, and it must not grow a row."""
    page = _page(shop)
    for kind in ("trial_balance", "profit_loss", "balance_sheet", "general_ledger",
                 "cash_bank"):
        page._set_kind(kind)
        assert page._last["total_row"] is None, kind
        assert page._table.rowCount() == len(page._last["rows"]), kind


def test_the_printed_sheet_renders_the_totals_row(shop, qapp):
    from zenith_business.ui.documents.print_builder import build_accounting_report_print
    from zenith_business.ui.print.accounting_report_document import (
        AccountingReportPrintDocument,
    )

    page = _page(shop)
    page._set_kind("receivables")
    data = build_accounting_report_print(shop, page._last)
    assert data.total_row is not None
    # the row is NOT one of the data rows — the Stage 08 lesson
    assert data.total_row not in data.rows

    from PyQt6.QtWidgets import QTableWidget

    doc = AccountingReportPrintDocument(data, Translator(LANG_ENGLISH))
    table = doc.findChild(QTableWidget)
    assert table.rowCount() == len(data.rows) + 1
    last = table.rowCount() - 1
    assert table.item(last, table.columnCount() - 1).text() == \
        f"{Decimal(data.total_row['balance']):,.2f}"
    assert table.item(last, 0).font().bold()
    doc.deleteLater()


def test_a_statement_without_a_totals_row_prints_unchanged(shop, qapp):
    from PyQt6.QtWidgets import QTableWidget

    from zenith_business.ui.documents.print_builder import build_accounting_report_print
    from zenith_business.ui.print.accounting_report_document import (
        AccountingReportPrintDocument,
    )

    page = _page(shop)
    page._set_kind("trial_balance")
    data = build_accounting_report_print(shop, page._last)
    assert data.total_row is None
    doc = AccountingReportPrintDocument(data, Translator(LANG_ENGLISH))
    assert doc.findChild(QTableWidget).rowCount() == len(data.rows)
    doc.deleteLater()


# ---- 2. the ledger names the document, not a movement id ------------------

def test_no_general_ledger_line_exposes_an_internal_movement_id(shop, qapp):
    page = _page(shop)
    page._set_kind("general_ledger")
    for row in page._last["rows"]:
        assert "movement" not in str(row["description"]).lower(), row["description"]


def test_the_cogs_lines_name_the_sales_document(shop, qapp):
    cogs = shop.accounts_repo.id_by_code("5000")
    page = _page(shop)
    page._set_kind("general_ledger")
    index = page._account_combo.findData(cogs)
    page._account_combo.setCurrentIndex(index)

    documents = {r[0] for r in shop.db.connection().execute(
        "SELECT document_no FROM sales")}
    assert page._last["rows"], "no COGS lines"
    for row in page._last["rows"]:
        assert row["description"].startswith("COGS"), row["description"]
        named = row["description"].split("— ")[-1]
        assert named in documents, f"{named!r} is not a real sales document"


# ---- 3. the printed ledger says which account it is -----------------------

def test_the_general_ledger_title_names_the_selected_account(shop, qapp):
    cogs = shop.accounts_repo.id_by_code("5000")
    page = _page(shop)
    page._set_kind("general_ledger")
    page._account_combo.setCurrentIndex(page._account_combo.findData(cogs))
    assert page._last["title"] == "General Ledger — 5000 Cost of Goods Sold"


def test_the_title_falls_back_when_every_account_is_shown(shop, qapp):
    page = _page(shop)
    page._set_kind("general_ledger")
    page._account_combo.setCurrentIndex(0)           # "All accounts"
    assert page._last["title"] == "General Ledger"


def test_the_account_reaches_the_printed_sheet_with_the_period(shop, qapp):
    from zenith_business.ui.documents.print_builder import build_accounting_report_print

    cogs = shop.accounts_repo.id_by_code("5000")
    page = _page(shop)
    page._set_kind("general_ledger")
    page._account_combo.setCurrentIndex(page._account_combo.findData(cogs))
    data = build_accounting_report_print(shop, page._last)
    assert data.title.startswith("General Ledger — 5000 Cost of Goods Sold")
    assert AS_OF in data.title                      # the period still travels too


def test_the_dari_ledger_title_names_the_account_and_stays_rtl(shop, qapp):
    from zenith_business.core.i18n import Direction, resolve_direction

    cogs = shop.accounts_repo.id_by_code("5000")
    page = _page(shop, LANG_DARI)
    page._set_kind("general_ledger")
    page._account_combo.setCurrentIndex(page._account_combo.findData(cogs))
    title = page._last["title"]
    assert "5000" in title and "Cost of Goods Sold" in title
    assert title.startswith(Translator(LANG_DARI).gettext("acc.rep_general_ledger"))
    assert resolve_direction(LANG_DARI) == Direction.RTL


def test_other_statements_keep_their_plain_title(shop, qapp):
    page = _page(shop)
    for kind, expected in (("trial_balance", "Trial Balance"),
                           ("profit_loss", "Profit & Loss"),
                           ("receivables", "Receivables")):
        page._set_kind(kind)
        assert page._last["title"] == expected


# ---- the printed header must stay legible ---------------------------------

def test_a_long_title_wraps_instead_of_printing_over_the_business_name(shop, qapp):
    """Found on the real sheet: "Kabul Traders Ltd ods Sold".

    The Stage 08 title is two or three words, so an unbounded label was fine
    there. A ledger title carries the account AND the period, overflowed left,
    and printed on top of the customer's own name — hiding both the business
    identity and the account the page was asked to show.
    """
    from PyQt6.QtWidgets import QLabel

    from zenith_business.ui.documents.print_builder import build_accounting_report_print
    from zenith_business.ui.print.accounting_report_document import (
        AccountingReportPrintDocument,
    )

    shop.company.save(legal_name="Kabul Traders Ltd", display_name="Kabul Traders Ltd",
                      address="Shar-e-Naw", city="Kabul")
    cogs = shop.accounts_repo.id_by_code("5000")
    page = _page(shop)
    page._set_kind("general_ledger")
    page._account_combo.setCurrentIndex(page._account_combo.findData(cogs))
    data = build_accounting_report_print(shop, page._last)
    doc = AccountingReportPrintDocument(data, Translator(LANG_ENGLISH))
    doc.show()
    qapp.processEvents()

    title = next(w for w in doc.findChildren(QLabel) if w.property("p") == "title")
    name = next(w for w in doc.findChildren(QLabel) if w.property("p") == "company")
    assert title.wordWrap(), "the title cannot wrap, so a long one overflows"
    bound = doc.width() * AccountingReportPrintDocument._TITLE_WIDTH
    assert title.width() <= bound + 1, "the title is not bounded"
    # and it must be wide enough to wrap in two lines rather than a narrow column
    assert title.height() < title.fontMetrics().height() * 4, (
        "the title is squeezed into too many lines to read")
    # the two must not occupy the same pixels
    assert not title.geometry().intersects(name.geometry()), (
        f"the title {title.geometry()} prints over the business name {name.geometry()}")
    assert title.text().startswith("General Ledger — 5000 Cost of Goods Sold")
    doc.deleteLater()


def test_the_ageing_total_is_not_printed_twice(shop, qapp):
    from zenith_business.ui.documents.print_builder import build_accounting_report_print

    page = _page(shop)
    page._set_kind("receivables")
    data = build_accounting_report_print(shop, page._last)
    # the total is in the row, so the block beneath must not repeat it
    assert data.totals == []
    assert data.total_row["balance"] == shop.accounting_reports.receivables(
        as_of=AS_OF)["total"]


def test_a_statement_without_a_totals_row_still_prints_its_totals_block(shop, qapp):
    from zenith_business.ui.documents.print_builder import build_accounting_report_print

    page = _page(shop)
    page._set_kind("trial_balance")
    data = build_accounting_report_print(shop, page._last)
    assert data.totals, "the trial balance lost its totals block"
