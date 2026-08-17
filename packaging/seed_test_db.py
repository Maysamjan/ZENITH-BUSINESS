"""Generate a fresh, pre-loaded TEST database for owner acceptance of Stage 05.

This does NOT change any Stage 01-05 functionality. It only *drives the existing
services* to create sample master data and a few posted documents, so the owner
can exercise every acceptance scenario against a realistic database without
typing setup data first.

Design of the sample data
--------------------------
The database is seeded so that each of the 8 owner test scenarios is directly
testable, AND so the Receipt / Payment / Expense lists and their printed
vouchers already have content on first launch:

  * Two customers and two suppliers.
  * One customer ("Kabul General Store") is left with an OPEN receivable so the
    owner can post a *partial receipt* and watch the remaining balance fall.
  * One supplier ("National Foods") is left with an OPEN payable so the owner
    can post a *partial payment* and watch the remaining payable fall.
  * The other customer / supplier are available for the owner to create a fresh
    credit sale / credit purchase from scratch.
  * Plenty of stock is on hand so a new credit sale posts without a stock error.
  * One receipt, one payment and one expense are already posted, so the three
    list screens and the three printed vouchers work immediately.
  * Cash and Bank funds already carry a non-zero balance from those postings.

Usage:
    python packaging/seed_test_db.py <ZENITH_DATA_HOME dir>

The script writes the database exactly where the application will look for it
when ZENITH_DATA_HOME points at the same directory (see core/paths.py).
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

# Make ZENITH_DATA_HOME resolution unnecessary here: we write the DB straight to
# the application's resolved database path under the given data home.
DATA_HOME = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path("appdata").resolve()
import os

os.environ["ZENITH_DATA_HOME"] = str(DATA_HOME)

from zenith_business.core.paths import resolve_paths
from zenith_business.database.connection import Database
from zenith_business.database.health import check_health
from zenith_business.services.context import open_application_context
from zenith_business.services.purchase_documents import PurchaseLine
from zenith_business.services.sales_documents import SaleLine

ADMIN_USER = "admin"
ADMIN_PASS = "Admin@123"


def main() -> None:
    paths = resolve_paths().ensure()
    db_path = paths.database_file
    if db_path.exists():
        db_path.unlink()
    print(f"Seeding test database at: {db_path}")

    db = Database(str(db_path))
    ctx = open_application_context(db, backups_dir=paths.backups_dir,
                                  logo_dir=paths.data_dir / "company")

    # --- initial setup + login -------------------------------------------
    ctx.setup.create_administrator(username=ADMIN_USER, password=ADMIN_PASS,
                                   full_name="Business Owner",
                                   company_name="Zenith Trading Co.")
    ctx.auth.login(ADMIN_USER, ADMIN_PASS)

    # --- accounting period + warehouse -----------------------------------
    ctx.financial_years.create(name="FY 2026", start_date="2026-01-01",
                               end_date="2026-12-31", make_active=True)
    wh = ctx.warehouses.create(code="MAIN", name="Main Store", is_default=True)

    bag = ctx.units_repo.id_by_code("BAG")
    ctn = ctx.units_repo.id_by_code("CTN")
    ltr = ctx.units_repo.id_by_code("LTR")

    # --- items -----------------------------------------------------------
    rice = ctx.items.create(item_code="RICE", name="Rice (Sella)", base_unit_id=bag,
                            purchase_price="1600", default_sale_price="1980")
    sugar = ctx.items.create(item_code="SUGAR", name="Sugar", base_unit_id=bag,
                             purchase_price="1400", default_sale_price="1750")
    oil = ctx.items.create(item_code="OIL", name="Cooking Oil 5L", base_unit_id=ltr,
                           purchase_price="640", default_sale_price="820")
    tea = ctx.items.create(item_code="TEA", name="Black Tea", base_unit_id=ctn,
                           purchase_price="2200", default_sale_price="2650")

    # --- parties ---------------------------------------------------------
    cust_open = ctx.parties.create(party_code="C-1001", name="Kabul General Store",
                                   is_customer=True, phone="070 111 2233")
    cust_free = ctx.parties.create(party_code="C-1002", name="Herat Traders",
                                   is_customer=True, phone="079 444 5566")
    sup_open = ctx.parties.create(party_code="S-2001", name="National Foods",
                                  is_supplier=True, phone="070 333 4444")
    sup_free = ctx.parties.create(party_code="S-2002", name="Kabul Wholesale Co.",
                                  is_supplier=True, phone="078 999 0011")

    # --- funds + expense category ids ------------------------------------
    cash = next(f for f in ctx.funds_repo.list_funds() if f["code"] == "1000")["id"]
    bank = next(f for f in ctx.funds_repo.list_funds() if f["code"] == "1010")["id"]
    rent = next(c for c in ctx.expense_categories_repo.list_active()
                if c["code"] == "RENT")["id"]

    # --- stock in (pure credit purchases; leaves supplier payables) ------
    # National Foods supplies rice + sugar on credit -> OPEN payable for owner
    # to pay against (scenario 4).
    ctx.purchase_documents.post_purchase(
        currency_code="AFN", warehouse_id=wh, party_id=sup_open, amount_paid="0",
        purchase_date="2026-06-01",
        lines=[PurchaseLine(item_id=rice, unit_id=bag, quantity="200", unit_price="1600"),
               PurchaseLine(item_id=sugar, unit_id=bag, quantity="150", unit_price="1400")])
    # Kabul Wholesale supplies oil + tea on credit (extra payable-list content).
    ctx.purchase_documents.post_purchase(
        currency_code="AFN", warehouse_id=wh, party_id=sup_free, amount_paid="0",
        purchase_date="2026-06-01",
        lines=[PurchaseLine(item_id=oil, unit_id=ltr, quantity="300", unit_price="640"),
               PurchaseLine(item_id=tea, unit_id=ctn, quantity="80", unit_price="2200")])

    # --- credit sale (leaves customer receivable, scenario 2) ------------
    ctx.sales_documents.post_sale(
        currency_code="AFN", warehouse_id=wh, party_id=cust_open, amount_paid="0",
        sale_date="2026-06-02",
        lines=[SaleLine(item_id=rice, unit_id=bag, quantity="40", unit_price="1980")])

    # --- one posted RECEIPT (Cash) — leaves remaining receivable ---------
    ctx.receipts.post_receipt(party_id=cust_open, account_id=cash, amount="30000",
                              currency_code="AFN", payment_method="CASH",
                              reference="INV-collection", receipt_date="2026-06-03")

    # --- one posted PAYMENT (Bank) — leaves remaining payable ------------
    ctx.payments.post_payment(party_id=sup_open, account_id=bank, amount="100000",
                              currency_code="AFN", payment_method="BANK",
                              reference="Bank transfer", payment_date="2026-06-04")

    # --- one posted EXPENSE (Cash) ---------------------------------------
    ctx.expenses.post_expense(category_id=rent, account_id=cash, amount="8000",
                              currency_code="AFN", payee="Shar-e-Naw Property",
                              payment_method="CASH", reference="Shop rent June",
                              description="Monthly shop rent", expense_date="2026-06-05")

    # --- verification ----------------------------------------------------
    recv = ctx.receipts.receivable(cust_open)
    pay = ctx.payments.payable(sup_open)
    cash_bal = ctx.funds_repo.balance(cash)
    bank_bal = ctx.funds_repo.balance(bank)
    conn = db.connection()
    lines = conn.execute("SELECT debit, credit FROM financial_entry_lines").fetchall()
    dr = sum(Decimal(r[0]) for r in lines)
    cr = sum(Decimal(r[1]) for r in lines)
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    fkeys = conn.execute("PRAGMA foreign_key_check").fetchall()
    health = check_health(db)

    print("\n--- seeded state ---------------------------------------------")
    print(f"Admin login          : {ADMIN_USER} / {ADMIN_PASS}")
    print(f"Kabul General Store   receivable = {recv} AFN  (owner posts a partial receipt)")
    print(f"National Foods        payable    = {pay} AFN  (owner posts a partial payment)")
    print(f"Cash fund (1000)      balance    = {cash_bal} AFN")
    print(f"Bank fund (1010)      balance    = {bank_bal} AFN")
    print(f"Ledger balanced       : {dr == cr}  (Dr {dr} == Cr {cr})")
    print(f"integrity_check       : {integrity}")
    print(f"foreign_key_check     : {'clean' if not fkeys else fkeys}")
    print(f"schema/health         : ok={health.ok}, sqlite={health.sqlite_version}")

    assert recv == "49200.00", recv
    assert pay == "430000.00", pay
    assert dr == cr, (dr, cr)
    assert integrity == "ok"
    assert not fkeys
    db.close()
    print("\nSeed OK.")


if __name__ == "__main__":
    main()
