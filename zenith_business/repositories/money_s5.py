"""Stage 05 money-movement repositories — receipts, payments, expenses, funds.

Additive: the LOCKED Stage 02 ``ReceiptRepository`` / ``PaymentRepository`` /
``ExpenseRepository`` are reused unchanged for the base header INSERTs; this
module adds the Stage 05 metadata writes (unified ``party_id``, ``payment_method``,
posting stamps), party/account-aware list joins for the history screens, the fund
(cash/bank) account list, and the expense-category master read. Party balances
reuse the Stage 04 ``PartyBalanceRepository`` (ledger-derived, Decimal-exact).
"""

from __future__ import annotations

from zenith_business.core.clock import now_iso
from zenith_business.core.money import D, money_to_db
from zenith_business.repositories.base import BaseRepository


class ReceiptExtRepository(BaseRepository):
    def set_meta(self, receipt_id: int, *, party_id: int | None, payment_method: str | None,
                 posted_at: str | None = None, posted_by: int | None = None) -> None:
        self._exec(
            "UPDATE receipts SET party_id = ?, payment_method = ?, posted_at = ?, posted_by = ?"
            " WHERE id = ?",
            (party_id, payment_method, posted_at or now_iso(), posted_by, receipt_id))

    def get_full(self, receipt_id: int) -> dict | None:
        return self._one(
            "SELECT r.*, p.name AS party_name, p.party_code, p.phone AS party_phone,"
            " p.address AS party_address, a.name AS account_name, a.code AS account_code,"
            " cur.code AS currency_code, u.full_name AS user_name FROM receipts r"
            " LEFT JOIN parties p ON p.id = r.party_id"
            " LEFT JOIN accounts a ON a.id = r.account_id"
            " LEFT JOIN currencies cur ON cur.id = r.currency_id"
            " LEFT JOIN users u ON u.id = r.created_by WHERE r.id = ?", (receipt_id,))

    def list_documents(self, *, term=None, status=None, account_id=None,
                       date_from=None, date_to=None, limit=200) -> list[dict]:
        where = ["1=1"]; params: list = []
        if term:
            where.append("(r.document_no LIKE ? OR p.name LIKE ?)")
            like = f"%{term.strip()}%"; params += [like, like]
        if status:
            where.append("r.status = ?"); params.append(status)
        if account_id:
            where.append("r.account_id = ?"); params.append(account_id)
        if date_from:
            where.append("r.receipt_date >= ?"); params.append(date_from)
        if date_to:
            where.append("r.receipt_date <= ?"); params.append(date_to)
        params.append(limit)
        return self._all(
            "SELECT r.id, r.document_no, r.receipt_date, r.amount, r.payment_method, r.reference,"
            " r.status, r.party_id, p.name AS party_name, a.name AS account_name,"
            " cur.code AS currency_code"
            " FROM receipts r LEFT JOIN parties p ON p.id = r.party_id"
            " LEFT JOIN accounts a ON a.id = r.account_id"
            " LEFT JOIN currencies cur ON cur.id = r.currency_id"
            f" WHERE {' AND '.join(where)} ORDER BY r.receipt_date DESC, r.id DESC LIMIT ?",
            tuple(params))

    def today_total(self, date: str) -> str:
        rows = self._all(
            "SELECT amount FROM receipts WHERE receipt_date = ? AND status = 'POSTED'", (date,))
        return money_to_db(sum((D(r["amount"]) for r in rows), D(0)))


class PaymentExtRepository(BaseRepository):
    def set_meta(self, payment_id: int, *, party_id: int | None, payment_method: str | None,
                 posted_at: str | None = None, posted_by: int | None = None) -> None:
        self._exec(
            "UPDATE payments SET party_id = ?, payment_method = ?, posted_at = ?, posted_by = ?"
            " WHERE id = ?",
            (party_id, payment_method, posted_at or now_iso(), posted_by, payment_id))

    def get_full(self, payment_id: int) -> dict | None:
        return self._one(
            "SELECT pm.*, p.name AS party_name, p.party_code, p.phone AS party_phone,"
            " p.address AS party_address, a.name AS account_name, a.code AS account_code,"
            " cur.code AS currency_code, u.full_name AS user_name FROM payments pm"
            " LEFT JOIN parties p ON p.id = pm.party_id"
            " LEFT JOIN accounts a ON a.id = pm.account_id"
            " LEFT JOIN currencies cur ON cur.id = pm.currency_id"
            " LEFT JOIN users u ON u.id = pm.created_by WHERE pm.id = ?", (payment_id,))

    def list_documents(self, *, term=None, status=None, account_id=None,
                       date_from=None, date_to=None, limit=200) -> list[dict]:
        where = ["1=1"]; params: list = []
        if term:
            where.append("(pm.document_no LIKE ? OR p.name LIKE ?)")
            like = f"%{term.strip()}%"; params += [like, like]
        if status:
            where.append("pm.status = ?"); params.append(status)
        if account_id:
            where.append("pm.account_id = ?"); params.append(account_id)
        if date_from:
            where.append("pm.payment_date >= ?"); params.append(date_from)
        if date_to:
            where.append("pm.payment_date <= ?"); params.append(date_to)
        params.append(limit)
        return self._all(
            "SELECT pm.id, pm.document_no, pm.payment_date, pm.amount, pm.payment_method,"
            " pm.reference, pm.status, pm.party_id, p.name AS party_name,"
            " a.name AS account_name, cur.code AS currency_code FROM payments pm"
            " LEFT JOIN parties p ON p.id = pm.party_id"
            " LEFT JOIN accounts a ON a.id = pm.account_id"
            " LEFT JOIN currencies cur ON cur.id = pm.currency_id"
            f" WHERE {' AND '.join(where)} ORDER BY pm.payment_date DESC, pm.id DESC LIMIT ?",
            tuple(params))

    def today_total(self, date: str) -> str:
        rows = self._all(
            "SELECT amount FROM payments WHERE payment_date = ? AND status = 'POSTED'", (date,))
        return money_to_db(sum((D(r["amount"]) for r in rows), D(0)))


class ExpenseExtRepository(BaseRepository):
    def set_meta(self, expense_id: int, *, payment_method: str | None, notes: str | None = None,
                 posted_at: str | None = None, posted_by: int | None = None) -> None:
        self._exec(
            "UPDATE expenses SET payment_method = ?, notes = ?, posted_at = ?, posted_by = ?"
            " WHERE id = ?",
            (payment_method, notes, posted_at or now_iso(), posted_by, expense_id))

    def get_full(self, expense_id: int) -> dict | None:
        return self._one(
            "SELECT e.*, ec.name AS category_name, ec.account_id AS expense_account_id,"
            " a.name AS account_name, a.code AS account_code, cur.code AS currency_code,"
            " u.full_name AS user_name FROM expenses e"
            " LEFT JOIN expense_categories ec ON ec.id = e.expense_category_id"
            " LEFT JOIN accounts a ON a.id = e.account_id"
            " LEFT JOIN currencies cur ON cur.id = e.currency_id"
            " LEFT JOIN users u ON u.id = e.created_by WHERE e.id = ?", (expense_id,))

    def list_documents(self, *, term=None, status=None, account_id=None, category_id=None,
                       date_from=None, date_to=None, limit=200) -> list[dict]:
        where = ["1=1"]; params: list = []
        if term:
            where.append("(e.document_no LIKE ? OR e.payee LIKE ? OR ec.name LIKE ?)")
            like = f"%{term.strip()}%"; params += [like, like, like]
        if status:
            where.append("e.status = ?"); params.append(status)
        if account_id:
            where.append("e.account_id = ?"); params.append(account_id)
        if category_id:
            where.append("e.expense_category_id = ?"); params.append(category_id)
        if date_from:
            where.append("e.expense_date >= ?"); params.append(date_from)
        if date_to:
            where.append("e.expense_date <= ?"); params.append(date_to)
        params.append(limit)
        return self._all(
            "SELECT e.id, e.document_no, e.expense_date, e.amount, e.payee, e.payment_method,"
            " e.reference, e.status, ec.name AS category_name, a.name AS account_name,"
            " cur.code AS currency_code FROM expenses e"
            " LEFT JOIN expense_categories ec ON ec.id = e.expense_category_id"
            " LEFT JOIN accounts a ON a.id = e.account_id"
            " LEFT JOIN currencies cur ON cur.id = e.currency_id"
            f" WHERE {' AND '.join(where)} ORDER BY e.expense_date DESC, e.id DESC LIMIT ?",
            tuple(params))

    def today_total(self, date: str) -> str:
        rows = self._all(
            "SELECT amount FROM expenses WHERE expense_date = ? AND status = 'POSTED'", (date,))
        return money_to_db(sum((D(r["amount"]) for r in rows), D(0)))


class FundRepository(BaseRepository):
    """Cash / bank / fund accounts — the money source/destination for Stage 05."""

    def list_funds(self) -> list[dict]:
        return self._all(
            "SELECT id, code, name, type FROM accounts"
            " WHERE is_fund = 1 AND is_active = 1 ORDER BY code")

    def get(self, account_id: int) -> dict | None:
        return self._one("SELECT * FROM accounts WHERE id = ?", (account_id,))

    def balance(self, account_id: int) -> str:
        rows = self._all(
            "SELECT debit, credit FROM financial_entry_lines WHERE account_id = ?", (account_id,))
        return money_to_db(sum((D(r["debit"]) - D(r["credit"]) for r in rows), D(0)))


class ExpenseCategoryRepository(BaseRepository):
    def list_active(self) -> list[dict]:
        return self._all(
            "SELECT id, code, name, account_id FROM expense_categories"
            " WHERE is_active = 1 ORDER BY name")

    def get(self, category_id: int) -> dict | None:
        return self._one("SELECT * FROM expense_categories WHERE id = ?", (category_id,))
