"""Stage 09 accounting reads — every statement from the one double-entry ledger.

There is no reporting store and no cached figure here. A Trial Balance, a Profit
& Loss, a Balance Sheet and a General Ledger are four questions asked of
``financial_entry_lines``, so they cannot disagree with each other or with the
party ledgers — they are readings of the same rows (§4.19, §4.20).

Money is summed with ``Decimal`` in Python, never a SQL aggregate (§24).
"""

from __future__ import annotations

from decimal import Decimal

from zenith_business.core.money import D, money_to_db
from zenith_business.repositories.base import BaseRepository

#: Cost of Goods Sold is an EXPENSE account, but it is not an OPERATING expense —
#: it sits above the gross-profit line. Everything else of type EXPENSE is
#: operating, so adding an expense account needs no code change here.
COGS_CODE = "5000"
#: Seeded but unused: purchases go to Inventory, not to a purchases expense.
#: Kept out of operating expenses so an empty account cannot distort a P&L.
PURCHASES_CODE = "5100"


class AccountingReadRepository(BaseRepository):
    """Ledger reads behind the financial statements."""

    # ---- accounts ---------------------------------------------------------

    def accounts(self) -> list[dict]:
        return self._all(
            "SELECT id, code, name, type, is_active, is_fund FROM accounts"
            " ORDER BY code")

    # ---- the core slice ---------------------------------------------------

    def movements(self, *, date_from: str | None = None, date_to: str | None = None,
                  account_id: int | None = None) -> list[dict]:
        """Ledger lines joined to their entry and account, oldest first.

        One query serves the Trial Balance, the General Ledger and the statements;
        each of them folds these rows differently rather than asking its own
        question of the database.
        """
        where = ["1=1"]
        params: list = []
        if date_from:
            where.append("e.entry_date >= ?"); params.append(date_from)
        if date_to:
            where.append("e.entry_date <= ?"); params.append(date_to)
        if account_id is not None:
            where.append("l.account_id = ?"); params.append(account_id)
        return self._all(
            "SELECT l.id, l.account_id, l.debit, l.credit, l.memo,"
            "       l.party_type, l.party_id,"
            "       e.entry_no, e.entry_date, e.source_type, e.source_id,"
            "       e.description,"
            "       a.code AS account_code, a.name AS account_name, a.type AS account_type"
            "  FROM financial_entry_lines l"
            "  JOIN financial_entries e ON e.id = l.entry_id"
            "  LEFT JOIN accounts a ON a.id = l.account_id"
            f" WHERE {' AND '.join(where)}"
            " ORDER BY e.entry_date, e.id, l.id", params)

    def balances_before(self, date_from: str | None) -> dict[int, Decimal]:
        """Net (debit − credit) per account strictly BEFORE a date.

        This is the opening column. With no start date there is no "before", so
        every account opens at zero and the period covers all of history.
        """
        if not date_from:
            return {}
        rows = self._all(
            "SELECT l.account_id, l.debit, l.credit FROM financial_entry_lines l"
            "  JOIN financial_entries e ON e.id = l.entry_id"
            " WHERE e.entry_date < ?", (date_from,))
        opening: dict[int, Decimal] = {}
        for r in rows:
            if r["account_id"] is None:
                continue
            opening[r["account_id"]] = (opening.get(r["account_id"], D(0))
                                        + D(r["debit"]) - D(r["credit"]))
        return opening

    # ---- party positions --------------------------------------------------

    def party_balances(self, party_type: str, *, as_of: str | None = None) -> list[dict]:
        """Outstanding balance per party, from the ledger lines that carry a party.

        The same lines the customer and supplier ledgers read, so a receivables
        report cannot disagree with the account it came from.
        """
        where = ["l.party_type = ?", "l.party_id IS NOT NULL"]
        params: list = [party_type]
        if as_of:
            where.append("e.entry_date <= ?"); params.append(as_of)
        rows = self._all(
            "SELECT l.party_id, p.party_code, p.name, p.phone,"
            "       l.debit, l.credit, e.entry_date"
            "  FROM financial_entry_lines l"
            "  JOIN financial_entries e ON e.id = l.entry_id"
            "  LEFT JOIN parties p ON p.id = l.party_id"
            f" WHERE {' AND '.join(where)}", params)
        folded: dict = {}
        for r in rows:
            entry = folded.setdefault(r["party_id"], {
                "party_id": r["party_id"], "party_code": r["party_code"],
                "name": r["name"], "phone": r["phone"], "_bal": D(0)})
            entry["_bal"] += D(r["debit"]) - D(r["credit"])
        out = []
        for entry in folded.values():
            balance = entry.pop("_bal")
            # A customer's receivable is a debit balance; a supplier's payable is
            # a credit balance. Report each as a positive amount owed.
            amount = balance if party_type == "CUSTOMER" else -balance
            if amount == 0:
                continue
            entry["balance"] = money_to_db(amount)
            out.append(entry)
        return sorted(out, key=lambda r: str(r.get("party_code") or ""))

    def party_documents(self, party_type: str, *, as_of: str | None = None) -> list[dict]:
        """Dated charges and settlements per party — the raw material for ageing.

        A charge is what put the party in debt (an invoice for a customer, a bill
        for a supplier); a settlement is what reduced it.
        """
        where = ["l.party_type = ?", "l.party_id IS NOT NULL"]
        params: list = [party_type]
        if as_of:
            where.append("e.entry_date <= ?"); params.append(as_of)
        rows = self._all(
            "SELECT l.party_id, l.debit, l.credit, e.entry_date, e.entry_no,"
            "       e.source_type, e.source_id"
            "  FROM financial_entry_lines l"
            "  JOIN financial_entries e ON e.id = l.entry_id"
            f" WHERE {' AND '.join(where)}"
            " ORDER BY e.entry_date, e.id", params)
        out = []
        for r in rows:
            net = D(r["debit"]) - D(r["credit"])
            amount = net if party_type == "CUSTOMER" else -net
            if amount == 0:
                continue
            out.append({"party_id": r["party_id"], "date": r["entry_date"],
                        "reference": r["entry_no"], "source_type": r["source_type"],
                        "amount": amount})
        return out
