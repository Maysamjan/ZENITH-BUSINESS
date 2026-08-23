"""In-place invoice correction + document-reference lookup.

Correcting a posted invoice amends THAT invoice: same record, same document
number, one row in the Sales List. It is not a new sale and not a void-and-
replace, so revenue, receivable and stock each move by the difference only.

The lookup tests pin the companion rule that a typed invoice reference resolves
the NUMBER (``2`` / ``000002`` / ``SALE-000002`` all name one invoice) instead of
matching a substring.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from zenith_business.core.document_ref import candidates
from zenith_business.services.exceptions import ValidationError
from zenith_business.services.purchase_documents import PurchaseLine
from zenith_business.services.sales_documents import ReturnLine, SaleLine


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
    ctx.oil = ctx.items.create(item_code="OIL", name="Oil", base_unit_id=ctx.bag,
                               purchase_price="60", default_sale_price="120")
    ctx.cust = ctx.parties.create(party_code="C1", name="Ahmad Store", is_customer=True)
    ctx.sup = ctx.parties.create(party_code="S1", name="Sup", is_supplier=True)
    ctx.purchase_documents.post_purchase(
        currency_code="AFN", warehouse_id=ctx.wh, party_id=ctx.sup, amount_paid="0",
        purchase_date="2026-06-01",
        lines=[PurchaseLine(item_id=ctx.rice, unit_id=ctx.bag, quantity="100", unit_price="50"),
               PurchaseLine(item_id=ctx.sugar, unit_id=ctx.bag, quantity="100", unit_price="40"),
               PurchaseLine(item_id=ctx.oil, unit_id=ctx.bag, quantity="100", unit_price="60")])
    return ctx


def _two_item_sale(biz, paid="160"):
    """5 Rice @100 + 2 Sugar @80 = 660."""
    return biz.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=biz.wh, party_id=biz.cust, amount_paid=paid,
        sale_date="2026-06-10",
        lines=[SaleLine(item_id=biz.rice, unit_id=biz.bag, quantity="5", unit_price="100"),
               SaleLine(item_id=biz.sugar, unit_id=biz.bag, quantity="2", unit_price="80")])


def _correct(biz, sale_id, lines, paid="160", reason=None):
    return biz.sales_documents.correct_sale(
        sale_id=sale_id, currency_code="AFN", warehouse_id=biz.wh, party_id=biz.cust,
        amount_paid=paid, sale_date="2026-06-10", lines=lines, reason=reason)


def _ledger_balanced(biz) -> bool:
    rows = biz.db.connection().execute(
        "SELECT debit, credit FROM financial_entry_lines").fetchall()
    return sum(Decimal(r[0]) for r in rows) == sum(Decimal(r[1]) for r in rows)


def _sales_row_count(biz) -> int:
    return biz.db.connection().execute("SELECT COUNT(*) FROM sales").fetchone()[0]


# ---- the owner's six-step scenario ---------------------------------------

def test_correction_keeps_one_invoice_with_the_same_number(biz):
    s = _two_item_sale(biz)
    assert _sales_row_count(biz) == 1

    # remove the Sugar line
    c1 = _correct(biz, s.id,
                  [SaleLine(item_id=biz.rice, unit_id=biz.bag, quantity="5", unit_price="100")])
    assert c1.id == s.id
    assert c1.document_no == s.document_no
    assert _sales_row_count(biz) == 1
    assert len(biz.sales_documents.list()) == 1

    # add an Oil line back
    c2 = _correct(biz, s.id,
                  [SaleLine(item_id=biz.rice, unit_id=biz.bag, quantity="5", unit_price="100"),
                   SaleLine(item_id=biz.oil, unit_id=biz.bag, quantity="3", unit_price="120")])
    assert c2.id == s.id
    assert c2.document_no == s.document_no
    assert _sales_row_count(biz) == 1
    assert biz.sales_repo.get(s.id)["status"] == "POSTED"


def test_correction_creates_no_void_and_consumes_no_number(biz):
    s = _two_item_sale(biz)
    _correct(biz, s.id,
             [SaleLine(item_id=biz.rice, unit_id=biz.bag, quantity="5", unit_price="100")])
    voids = biz.db.connection().execute(
        "SELECT COUNT(*) FROM sales WHERE status = 'VOID'").fetchone()[0]
    assert voids == 0
    # only the original SALE number was ever issued
    nxt = biz.db.connection().execute(
        "SELECT next_number FROM document_sequences WHERE doc_type = 'SALE'").fetchone()[0]
    assert int(nxt) == 2


def test_removing_a_line_returns_its_stock(biz):
    s = _two_item_sale(biz)
    assert biz.inventory.on_hand(biz.sugar, biz.wh) == "98.000"
    _correct(biz, s.id,
             [SaleLine(item_id=biz.rice, unit_id=biz.bag, quantity="5", unit_price="100")])
    assert biz.inventory.on_hand(biz.sugar, biz.wh) == "100.000"   # given back
    assert biz.inventory.on_hand(biz.rice, biz.wh) == "95.000"     # unchanged
    assert len(biz.sales_documents.lines(s.id)) == 1


def test_adding_a_line_takes_its_stock(biz):
    s = _two_item_sale(biz)
    _correct(biz, s.id,
             [SaleLine(item_id=biz.rice, unit_id=biz.bag, quantity="5", unit_price="100"),
              SaleLine(item_id=biz.sugar, unit_id=biz.bag, quantity="2", unit_price="80"),
              SaleLine(item_id=biz.oil, unit_id=biz.bag, quantity="3", unit_price="120")])
    assert biz.inventory.on_hand(biz.oil, biz.wh) == "97.000"
    assert len(biz.sales_documents.lines(s.id)) == 3


def test_quantity_change_recalculates_totals_and_stock(biz):
    s = _two_item_sale(biz)          # 660
    c = _correct(biz, s.id,
                 [SaleLine(item_id=biz.rice, unit_id=biz.bag, quantity="8", unit_price="100"),
                  SaleLine(item_id=biz.sugar, unit_id=biz.bag, quantity="2", unit_price="80")])
    assert c.grand_total == "960.00"          # 800 + 160
    assert biz.inventory.on_hand(biz.rice, biz.wh) == "92.000"
    assert biz.sales_repo.get(s.id)["grand_total"] == "960.00"


def test_receivable_paid_and_credit_follow_the_correction(biz):
    s = _two_item_sale(biz, paid="160")       # 660 total, 500 credit
    assert biz.sales_documents.receivable(biz.cust) == "500.00"
    _correct(biz, s.id,
             [SaleLine(item_id=biz.rice, unit_id=biz.bag, quantity="5", unit_price="100")],
             paid="160")                      # 500 total, 340 credit
    assert biz.sales_documents.receivable(biz.cust) == "340.00"
    row = biz.sales_repo.get(s.id)
    assert row["amount_paid"] == "160.00" and row["remaining_amount"] == "340.00"


def test_ledger_moves_by_the_difference_only(biz):
    """Revenue must land on the corrected figure, not the sum of both versions."""
    s = _two_item_sale(biz)                   # 660
    _correct(biz, s.id,
             [SaleLine(item_id=biz.rice, unit_id=biz.bag, quantity="5", unit_price="100")])
    rev = biz.db.connection().execute(
        "SELECT fel.debit, fel.credit FROM financial_entry_lines fel"
        " JOIN accounts a ON a.id = fel.account_id WHERE a.code = '4000'").fetchall()
    net = sum(Decimal(r[1]) - Decimal(r[0]) for r in rev)
    assert net == Decimal("500.00")           # not 660 and not 1160
    assert _ledger_balanced(biz)
    # exactly one SALE journal and one correction journal — never a second sale
    kinds = biz.db.connection().execute(
        "SELECT source_type, COUNT(*) FROM financial_entries"
        " WHERE source_type LIKE 'SALE%' GROUP BY source_type").fetchall()
    assert dict(kinds) == {"SALE": 1, "SALE_CORRECTION": 1}


def test_correction_with_no_financial_change_posts_no_journal(biz):
    s = _two_item_sale(biz)
    before = biz.db.connection().execute(
        "SELECT COUNT(*) FROM financial_entries").fetchone()[0]
    # same money, only the reason recorded
    _correct(biz, s.id,
             [SaleLine(item_id=biz.rice, unit_id=biz.bag, quantity="5", unit_price="100"),
              SaleLine(item_id=biz.sugar, unit_id=biz.bag, quantity="2", unit_price="80")],
             reason="typo in notes")
    after = biz.db.connection().execute(
        "SELECT COUNT(*) FROM financial_entries").fetchone()[0]
    assert after == before


def test_correction_can_reuse_the_stock_it_already_holds(biz):
    """Selling all stock then trimming the invoice must not read as an oversell."""
    s = biz.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=biz.wh, party_id=biz.cust, amount_paid="0",
        sale_date="2026-06-10",
        lines=[SaleLine(item_id=biz.rice, unit_id=biz.bag, quantity="100", unit_price="100")])
    assert biz.inventory.on_hand(biz.rice, biz.wh) == "0.000"
    c = _correct(biz, s.id,
                 [SaleLine(item_id=biz.rice, unit_id=biz.bag, quantity="60", unit_price="100")],
                 paid="0")
    assert c.grand_total == "6000.00"
    assert biz.inventory.on_hand(biz.rice, biz.wh) == "40.000"


def test_correction_audits_what_changed(biz):
    s = _two_item_sale(biz)
    _correct(biz, s.id,
             [SaleLine(item_id=biz.rice, unit_id=biz.bag, quantity="3", unit_price="100"),
              SaleLine(item_id=biz.oil, unit_id=biz.bag, quantity="4", unit_price="120")],
             reason="fix order")
    row = biz.db.connection().execute(
        "SELECT document_no, details FROM audit_log WHERE action = 'sales.correct'"
        " ORDER BY id DESC").fetchone()
    assert row is not None
    assert row[0] == s.document_no            # audited against the SAME invoice
    details = row[1]
    assert "Rice qty" in details and "Sugar" in details and "Oil" in details
    assert "removed" in details and "added" in details
    assert "old_total=660.00" in details and "new_total=780.00" in details
    assert "reason=fix order" in details


def test_correction_still_blocked_when_a_return_exists(biz):
    s = _two_item_sale(biz)
    sl = biz.sales_repo.lines_for(s.id)[0]["id"]
    biz.sales_documents.post_return(sale_id=s.id, return_date="2026-06-11",
                                    lines=[ReturnLine(sale_line_id=sl, quantity="2")])
    with pytest.raises(ValidationError):
        _correct(biz, s.id,
                 [SaleLine(item_id=biz.rice, unit_id=biz.bag, quantity="5", unit_price="100")])


def test_failed_correction_leaves_the_invoice_untouched(biz):
    s = _two_item_sale(biz)
    with pytest.raises(ValidationError):
        _correct(biz, s.id, [])               # no lines → rejected
    row = biz.sales_repo.get(s.id)
    assert row["grand_total"] == "660.00" and row["status"] == "POSTED"
    assert len(biz.sales_documents.lines(s.id)) == 2
    assert biz.inventory.on_hand(biz.sugar, biz.wh) == "98.000"


def test_corrected_invoice_reports_once_at_the_corrected_value(biz):
    s = _two_item_sale(biz, paid="160")
    _correct(biz, s.id,
             [SaleLine(item_id=biz.rice, unit_id=biz.bag, quantity="5", unit_price="100")],
             paid="160")
    summary = biz.sales_reports.summary(date_from="2026-06-01", date_to="2026-06-30")
    assert summary["invoices"] == 1
    assert summary["gross"] == "500.00"       # corrected value, counted once
    assert summary["paid"] == "160.00"
    assert summary["credit"] == "340.00"


# ---- document reference resolution ---------------------------------------

def test_candidates_resolves_every_typed_form():
    for term in ("SALE-000002", "sale-000002", "000002", "2", "sale-2"):
        assert "SALE-000002" in candidates(term, "SALE-", 6), term
    # a name search yields no number, so the caller falls back to searching
    assert candidates("Ahmad", "SALE-", 6) == ["AHMAD"]
    assert candidates("  ", "SALE-", 6) == []


def test_find_by_reference_accepts_all_three_forms(biz):
    def _filler():
        biz.sales_documents.post_sale(
            currency_code="AFN", warehouse_id=biz.wh, party_id=biz.cust, amount_paid="0",
            sale_date="2026-06-10",
            lines=[SaleLine(item_id=biz.rice, unit_id=biz.bag, quantity="1", unit_price="100")])

    _filler()                                              # SALE-000001
    target = _two_item_sale(biz)                           # SALE-000002
    for _ in range(20):                                    # make '2' non-unique as a substring
        _filler()                                          # … up to SALE-000022
    for term in ("SALE-000002", "000002", "2", "sale-2"):
        found = biz.sales_documents.find_by_reference(term)
        assert found is not None, term
        assert found["id"] == target.id, term
        assert found["document_no"] == "SALE-000002"


def test_find_by_reference_rejects_unknown_and_writes_nothing(biz):
    _two_item_sale(biz)
    before = _sales_row_count(biz)
    assert biz.sales_documents.find_by_reference("SALE-999999") is None
    assert biz.sales_documents.find_by_reference("") is None
    assert _sales_row_count(biz) == before


def test_find_by_reference_still_matches_a_customer_name(biz):
    target = _two_item_sale(biz)
    assert biz.sales_documents.find_by_reference("Ahmad")["id"] == target.id


def test_purchase_reference_resolves_the_same_way(biz):
    p = biz.purchase_documents.list()[0]                   # PUR-000001 from the fixture
    for term in ("PUR-000001", "000001", "1"):
        found = biz.purchase_documents.find_by_reference(term)
        assert found is not None and found["id"] == p["id"], term
