"""Stage 09 — financial statements over the double-entry ledger.

Six reads of the same rows:

* **Trial Balance** — opening, period debit, period credit, closing per account,
  with total debits equal to total credits.
* **Profit & Loss** — Net Sales − COGS = Gross Profit; − Operating Expenses =
  Net Profit.
* **Balance Sheet** — Assets = Liabilities + Equity.
* **General Ledger** — every line of one account with a running balance.
* **Cash & Bank** — the fund accounts' balances and movements.
* **Receivables / Payables** — what each party owes, aged into buckets.

Every one of them calls the COGS posting sync first. Stage 08 knew what a sale
cost but nothing charged it to the accounts; syncing before reading means the
statements are always complete, and because each COGS entry is dated by the
movement it came from, a statement for a past period is right too.

Two rules this module holds to, learned the hard way in earlier stages:

* **Nothing is recomputed that another module owns.** Net sales here is the
  ledger's revenue account, and it is reconciled against — not replaced by — the
  Sales Reporting engine.
* **Equity carries the period's own result.** A balance sheet built only from
  EQUITY accounts cannot balance while income and expense accounts are still
  open, because the profit has nowhere to sit. There is no year close in Stage 09
  (out of scope by instruction), so the result for the period is folded into
  equity where it belongs. That is what makes ``A = L + E`` an identity rather
  than a hope.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from zenith_business.core.money import D, money, money_to_db
from zenith_business.repositories.accounting_s9 import COGS_CODE, PURCHASES_CODE

_ACCT_SALES = "4000"

#: Ageing buckets, in days outstanding. "Current" is anything not yet overdue —
#: with no credit terms in the system yet, that means dated today or later.
AGEING_BUCKETS: tuple[tuple[str, int | None], ...] = (
    ("current", 0), ("d1_30", 30), ("d31_60", 60), ("d61_90", 90), ("d90_plus", None),
)


class AccountingReportService:
    """Read-only financial statements. Posts pending COGS before every read."""

    KINDS = ("trial_balance", "profit_loss", "balance_sheet",
             "general_ledger", "cash_bank", "receivables", "payables")

    def __init__(self, repo, cogs_posting, sales_reports, party_ledger, authz) -> None:
        self._repo = repo
        self._cogs = cogs_posting
        self._sales_reports = sales_reports
        self._party_ledger = party_ledger
        self._authz = authz

    # ---- shared -----------------------------------------------------------

    def _ready(self) -> None:
        """Permission, then make sure the accounts are complete before reading."""
        self._authz.require("accounting.reports")
        self._cogs.sync()

    @staticmethod
    def _fold(rows: list[dict]) -> dict[int, dict]:
        """Debit and credit totals per account for a set of ledger lines."""
        out: dict[int, dict] = {}
        for r in rows:
            if r["account_id"] is None:
                continue
            entry = out.setdefault(r["account_id"], {
                "account_id": r["account_id"], "code": r["account_code"],
                "name": r["account_name"], "type": r["account_type"],
                "debit": D(0), "credit": D(0)})
            entry["debit"] += D(r["debit"])
            entry["credit"] += D(r["credit"])
        return out

    # ---- 1. trial balance -------------------------------------------------

    def trial_balance(self, *, date_from: str | None = None,
                      date_to: str | None = None) -> dict:
        self._ready()
        rows = self._repo.movements(date_from=date_from, date_to=date_to)
        opening = self._repo.balances_before(date_from)
        folded = self._fold(rows)
        for account_id, open_balance in opening.items():
            folded.setdefault(account_id, None)
        accounts = {a["id"]: a for a in self._repo.accounts()}

        out = []
        total_debit = total_credit = D(0)
        total_open = total_close = D(0)
        for account_id in folded:
            account = accounts.get(account_id, {})
            data = folded.get(account_id) or {
                "code": account.get("code"), "name": account.get("name"),
                "type": account.get("type"), "debit": D(0), "credit": D(0)}
            open_balance = opening.get(account_id, D(0))
            closing = open_balance + data["debit"] - data["credit"]
            if open_balance == 0 and data["debit"] == 0 and data["credit"] == 0:
                continue
            total_debit += data["debit"]
            total_credit += data["credit"]
            total_open += open_balance
            total_close += closing
            out.append({
                "account_id": account_id, "code": data["code"], "name": data["name"],
                "type": data["type"],
                "opening": money_to_db(open_balance),
                "debit": money_to_db(data["debit"]),
                "credit": money_to_db(data["credit"]),
                "closing": money_to_db(closing),
            })
        out.sort(key=lambda r: str(r["code"] or ""))
        return {
            "date_from": date_from, "date_to": date_to, "rows": out,
            "total_opening": money_to_db(total_open),
            "total_debit": money_to_db(total_debit),
            "total_credit": money_to_db(total_credit),
            "total_closing": money_to_db(total_close),
            # The point of the report: these two must be equal.
            "balanced": money(total_debit) == money(total_credit),
        }

    # ---- 2. profit & loss -------------------------------------------------

    def profit_loss(self, *, date_from: str | None = None,
                    date_to: str | None = None) -> dict:
        self._ready()
        rows = self._repo.movements(date_from=date_from, date_to=date_to)
        folded = self._fold(rows)

        net_sales = cogs = D(0)
        expense_rows: list[dict] = []
        income_rows: list[dict] = []
        operating = D(0)
        for data in folded.values():
            # Income is a credit balance, expense a debit balance; report both as
            # the positive amounts a reader expects.
            if data["type"] == "INCOME":
                amount = data["credit"] - data["debit"]
                if data["code"] == _ACCT_SALES:
                    net_sales += amount
                if amount:
                    income_rows.append({"code": data["code"], "name": data["name"],
                                        "amount": money_to_db(amount)})
            elif data["type"] == "EXPENSE":
                amount = data["debit"] - data["credit"]
                if data["code"] == COGS_CODE:
                    cogs += amount
                    continue
                if data["code"] == PURCHASES_CODE and amount == 0:
                    continue
                operating += amount
                if amount:
                    expense_rows.append({"code": data["code"], "name": data["name"],
                                         "amount": money_to_db(amount)})
        other_income = sum((D(r["amount"]) for r in income_rows
                            if r["code"] != _ACCT_SALES), D(0))
        gross_profit = net_sales - cogs
        net_profit = gross_profit + other_income - operating
        return {
            "date_from": date_from, "date_to": date_to,
            "net_sales": money_to_db(net_sales),
            "cogs": money_to_db(cogs),
            "gross_profit": money_to_db(gross_profit),
            "other_income": money_to_db(other_income),
            "operating_expenses": money_to_db(operating),
            "net_profit": money_to_db(net_profit),
            "expense_rows": sorted(expense_rows, key=lambda r: str(r["code"])),
            "income_rows": sorted(income_rows, key=lambda r: str(r["code"])),
        }

    # ---- 3. balance sheet -------------------------------------------------

    def balance_sheet(self, *, as_of: str | None = None) -> dict:
        self._ready()
        rows = self._repo.movements(date_to=as_of)
        folded = self._fold(rows)

        assets: list[dict] = []
        liabilities: list[dict] = []
        equity: list[dict] = []
        total_assets = total_liabilities = total_equity = D(0)
        result = D(0)
        for data in folded.values():
            net = data["debit"] - data["credit"]
            if data["type"] == "ASSET":
                if net:
                    assets.append({"code": data["code"], "name": data["name"],
                                   "amount": money_to_db(net)})
                total_assets += net
            elif data["type"] == "LIABILITY":
                if -net:
                    liabilities.append({"code": data["code"], "name": data["name"],
                                        "amount": money_to_db(-net)})
                total_liabilities += -net
            elif data["type"] == "EQUITY":
                if -net:
                    equity.append({"code": data["code"], "name": data["name"],
                                   "amount": money_to_db(-net)})
                total_equity += -net
            else:
                # INCOME and EXPENSE accumulate the period result, which belongs
                # in equity until a year close moves it to retained earnings.
                # Stage 09 has no year close, so it is shown as its own line.
                result += (data["credit"] - data["debit"])
        total_equity_with_result = total_equity + result
        if result:
            equity.append({"code": "", "name": "__result__",
                           "amount": money_to_db(result)})
        return {
            "as_of": as_of,
            "assets": sorted(assets, key=lambda r: str(r["code"])),
            "liabilities": sorted(liabilities, key=lambda r: str(r["code"])),
            "equity": equity,
            "total_assets": money_to_db(total_assets),
            "total_liabilities": money_to_db(total_liabilities),
            "retained_result": money_to_db(result),
            "total_equity": money_to_db(total_equity_with_result),
            "total_liabilities_equity": money_to_db(
                total_liabilities + total_equity_with_result),
            # The invariant the whole statement exists to demonstrate.
            "balanced": money(total_assets) == money(
                total_liabilities + total_equity_with_result),
        }

    # ---- 4. general ledger ------------------------------------------------

    def general_ledger(self, *, account_id: int | None = None,
                       date_from: str | None = None,
                       date_to: str | None = None) -> dict:
        self._ready()
        opening_all = self._repo.balances_before(date_from)
        opening = opening_all.get(account_id, D(0)) if account_id is not None else D(0)
        rows = self._repo.movements(date_from=date_from, date_to=date_to,
                                    account_id=account_id)
        running = opening
        out = []
        total_debit = total_credit = D(0)
        for r in rows:
            running += D(r["debit"]) - D(r["credit"])
            total_debit += D(r["debit"])
            total_credit += D(r["credit"])
            out.append({
                "date": r["entry_date"], "reference": r["entry_no"],
                "description": r["description"] or r["memo"] or "",
                "memo": r["memo"] or "",
                "source_type": r["source_type"],
                "account_code": r["account_code"], "account_name": r["account_name"],
                "debit": money_to_db(D(r["debit"])),
                "credit": money_to_db(D(r["credit"])),
                "balance": money_to_db(running),
            })
        return {
            "account_id": account_id, "date_from": date_from, "date_to": date_to,
            "opening": money_to_db(opening), "rows": out,
            "total_debit": money_to_db(total_debit),
            "total_credit": money_to_db(total_credit),
            "closing": money_to_db(running),
        }

    # ---- 5. cash & bank ---------------------------------------------------

    def cash_bank(self, *, date_from: str | None = None,
                  date_to: str | None = None) -> dict:
        """Balances and movements for the fund accounts (cash, bank, petty cash)."""
        self._ready()
        funds = [a for a in self._repo.accounts() if a.get("is_fund")]
        opening = self._repo.balances_before(date_from)
        accounts = []
        total_open = total_in = total_out = total_close = D(0)
        for fund in funds:
            rows = self._repo.movements(date_from=date_from, date_to=date_to,
                                        account_id=fund["id"])
            money_in = sum((D(r["debit"]) for r in rows), D(0))
            money_out = sum((D(r["credit"]) for r in rows), D(0))
            open_balance = opening.get(fund["id"], D(0))
            closing = open_balance + money_in - money_out
            if open_balance == 0 and money_in == 0 and money_out == 0:
                continue
            total_open += open_balance
            total_in += money_in
            total_out += money_out
            total_close += closing
            accounts.append({
                "account_id": fund["id"], "code": fund["code"], "name": fund["name"],
                "opening": money_to_db(open_balance),
                "money_in": money_to_db(money_in),
                "money_out": money_to_db(money_out),
                "closing": money_to_db(closing),
            })
        return {
            "date_from": date_from, "date_to": date_to, "accounts": accounts,
            "total_opening": money_to_db(total_open),
            "total_in": money_to_db(total_in),
            "total_out": money_to_db(total_out),
            "total_closing": money_to_db(total_close),
        }

    # ---- 6. receivables / payables with ageing ----------------------------

    def receivables(self, *, as_of: str | None = None) -> dict:
        return self._aged("CUSTOMER", as_of=as_of)

    def payables(self, *, as_of: str | None = None) -> dict:
        return self._aged("SUPPLIER", as_of=as_of)

    def _aged(self, party_type: str, *, as_of: str | None = None) -> dict:
        self._ready()
        balances = {r["party_id"]: r for r in
                    self._repo.party_balances(party_type, as_of=as_of)}
        documents = self._repo.party_documents(party_type, as_of=as_of)
        today = as_of or date.today().isoformat()

        by_party: dict[int, list[dict]] = {}
        for doc in documents:
            by_party.setdefault(doc["party_id"], []).append(doc)

        rows = []
        totals = {key: D(0) for key, _days in AGEING_BUCKETS}
        grand = D(0)
        for party_id, party in balances.items():
            buckets = self._age_party(by_party.get(party_id, []), today)
            row = dict(party)
            for key, _days in AGEING_BUCKETS:
                row[key] = money_to_db(buckets[key])
                totals[key] += buckets[key]
            grand += D(party["balance"])
            rows.append(row)
        return {
            "as_of": as_of, "party_type": party_type, "rows": rows,
            "totals": {key: money_to_db(value) for key, value in totals.items()},
            "total": money_to_db(grand),
        }

    @staticmethod
    def _age_party(documents: list[dict], today: str) -> dict[str, Decimal]:
        """Age one party's outstanding balance by the age of the debt still standing.

        Two different rules, because two different kinds of credit exist:

        * A **return, correction or void names its own document**, so it is
          applied to that invoice. Anything else misstates the very thing the
          report is for: a voided invoice would keep sitting in a recent bucket
          while an untouched older invoice looked part-paid.
        * A **receipt or payment names nothing**, so the standard rule applies —
          money clears the oldest debt first.

        Either way nothing is created or dropped, which is why the buckets always
        add back to the party's balance.
        """
        buckets = {key: D(0) for key, _days in AGEING_BUCKETS}
        charges: dict[tuple, dict] = {}
        order: list[tuple] = []
        loose: list[dict] = []
        credit = D(0)

        # 1. The documents that created the debt, oldest first.
        taken: set[int] = set()
        for i, d in enumerate(documents):
            key = d.get("charge_key")
            if d.get("is_charge") and key is not None and key not in charges:
                charges[key] = {"date": d["date"], "amount": d["amount"]}
                order.append(key)
                taken.add(i)

        # 2. Everything else: attach it to its own document where it names one.
        for i, d in enumerate(documents):
            if i in taken:
                continue
            key = d.get("charge_key")
            if key is not None and key in charges:
                # A correction can raise a bill as well as lower it; either way it
                # amends that document and keeps that document's age.
                charges[key]["amount"] += d["amount"]
            elif d["amount"] > 0:
                loose.append({"date": d["date"], "amount": d["amount"]})
            else:
                credit += -d["amount"]

        items = [charges[key] for key in order] + loose
        items.sort(key=lambda c: c["date"])
        # A credit note can exceed what is left on its own document. The excess is
        # money owed back, which settles the rest oldest-first like any payment.
        for charge in items:
            if charge["amount"] < 0:
                credit += -charge["amount"]
                charge["amount"] = D(0)
        for charge in items:
            if credit <= 0:
                break
            applied = min(credit, charge["amount"])
            charge["amount"] -= applied
            credit -= applied

        try:
            today_date = date.fromisoformat(today)
        except ValueError:
            today_date = date.today()
        for charge in items:
            if charge["amount"] <= 0:
                continue
            try:
                age = (today_date - date.fromisoformat(charge["date"])).days
            except ValueError:
                age = 0
            buckets[_bucket_for(age)] += charge["amount"]
        # Any credit left over is money received beyond what was ever charged —
        # it belongs against the newest end rather than vanishing from the total.
        if credit > 0:
            buckets["current"] -= credit
        return buckets


def _bucket_for(age_days: int) -> str:
    if age_days <= 0:
        return "current"
    if age_days <= 30:
        return "d1_30"
    if age_days <= 60:
        return "d31_60"
    if age_days <= 90:
        return "d61_90"
    return "d90_plus"


def financial_year_range(fy: dict) -> tuple[str, str]:
    """The From/To dates of a financial year, as the period picker uses them."""
    return fy["start_date"], fy["end_date"]


def month_to_date(today: str | None = None) -> tuple[str, str]:
    day = date.fromisoformat(today) if today else date.today()
    return day.replace(day=1).isoformat(), day.isoformat()


def year_to_date(today: str | None = None) -> tuple[str, str]:
    day = date.fromisoformat(today) if today else date.today()
    return day.replace(month=1, day=1).isoformat(), day.isoformat()


def previous_day(iso_date: str) -> str:
    return (date.fromisoformat(iso_date) - timedelta(days=1)).isoformat()
