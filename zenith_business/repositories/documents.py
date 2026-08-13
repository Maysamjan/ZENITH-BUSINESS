"""Transactional-document repositories (Stage 02 §25-§31, §34, §47).

Sales, purchases, inventory movements, receipts, payments, expenses and the
double-entry financial ledger. Money/quantity/rate fields are serialized through
the Decimal helpers; every write here is expected to run inside a service-opened
transaction so a whole document (header + lines + inventory + ledger) commits or
rolls back atomically.
"""

from __future__ import annotations

from zenith_business.core.clock import now_iso
from zenith_business.core.money import D, money_to_db, qty_to_db, rate_to_db
from zenith_business.repositories.base import BaseRepository


class SalesRepository(BaseRepository):
    def create_header(
        self,
        *,
        document_no: str,
        sale_date: str,
        currency_id: int,
        customer_id: int | None = None,
        warehouse_id: int | None = None,
        salesperson_id: int | None = None,
        exchange_rate=1,
        subtotal=0,
        discount_total=0,
        grand_total=0,
        amount_paid=0,
        remaining_amount=0,
        status: str = "DRAFT",
        notes: str | None = None,
        created_by: int | None = None,
    ) -> int:
        ts = now_iso()
        return self._insert(
            "INSERT INTO sales (document_no, sale_date, customer_id, warehouse_id,"
            " salesperson_id, currency_id, exchange_rate, subtotal, discount_total,"
            " grand_total, amount_paid, remaining_amount, status, notes, created_by,"
            " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (document_no, sale_date, customer_id, warehouse_id, salesperson_id, currency_id,
             rate_to_db(exchange_rate), money_to_db(subtotal), money_to_db(discount_total),
             money_to_db(grand_total), money_to_db(amount_paid), money_to_db(remaining_amount),
             status, notes, created_by, ts, ts))

    def add_line(
        self,
        *,
        sale_id: int,
        line_no: int,
        item_id: int,
        unit_id: int,
        quantity,
        unit_price,
        line_total,
        warehouse_id: int | None = None,
        discount=0,
    ) -> int:
        return self._insert(
            "INSERT INTO sales_lines (sale_id, line_no, item_id, unit_id, warehouse_id,"
            " quantity, unit_price, discount, line_total, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (sale_id, line_no, item_id, unit_id, warehouse_id, qty_to_db(quantity),
             money_to_db(unit_price), money_to_db(discount), money_to_db(line_total), now_iso()))

    def get(self, sale_id: int) -> dict | None:
        return self._one("SELECT * FROM sales WHERE id = ?", (sale_id,))

    def get_by_document_no(self, document_no: str) -> dict | None:
        return self._one("SELECT * FROM sales WHERE document_no = ?", (document_no,))

    def lines_for(self, sale_id: int) -> list[dict]:
        return self._all(
            "SELECT * FROM sales_lines WHERE sale_id = ? ORDER BY line_no", (sale_id,))

    def mark_posted(self, sale_id: int, user_id: int | None) -> None:
        ts = now_iso()
        self._exec(
            "UPDATE sales SET status = 'POSTED', posted_at = ?, posted_by = ?, updated_at = ?"
            " WHERE id = ?", (ts, user_id, ts, sale_id))

    def mark_void(self, sale_id: int, user_id: int | None, reason: str | None) -> None:
        ts = now_iso()
        self._exec(
            "UPDATE sales SET status = 'VOID', voided_at = ?, voided_by = ?, void_reason = ?,"
            " updated_at = ? WHERE id = ?", (ts, user_id, reason, ts, sale_id))

    def list_recent(self, limit: int = 50) -> list[dict]:
        return self._all(
            "SELECT s.id, s.document_no, s.sale_date, s.grand_total, s.status,"
            " c.name AS customer_name FROM sales s"
            " LEFT JOIN customers c ON c.id = s.customer_id"
            " ORDER BY s.sale_date DESC, s.id DESC LIMIT ?", (limit,))


class PurchaseRepository(BaseRepository):
    def create_header(
        self,
        *,
        document_no: str,
        purchase_date: str,
        currency_id: int,
        supplier_id: int | None = None,
        warehouse_id: int | None = None,
        exchange_rate=1,
        subtotal=0,
        discount_total=0,
        grand_total=0,
        amount_paid=0,
        remaining_amount=0,
        status: str = "DRAFT",
        notes: str | None = None,
        created_by: int | None = None,
    ) -> int:
        ts = now_iso()
        return self._insert(
            "INSERT INTO purchases (document_no, purchase_date, supplier_id, warehouse_id,"
            " currency_id, exchange_rate, subtotal, discount_total, grand_total, amount_paid,"
            " remaining_amount, status, notes, created_by, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (document_no, purchase_date, supplier_id, warehouse_id, currency_id,
             rate_to_db(exchange_rate), money_to_db(subtotal), money_to_db(discount_total),
             money_to_db(grand_total), money_to_db(amount_paid), money_to_db(remaining_amount),
             status, notes, created_by, ts, ts))

    def add_line(
        self,
        *,
        purchase_id: int,
        line_no: int,
        item_id: int,
        unit_id: int,
        quantity,
        unit_price,
        line_total,
        warehouse_id: int | None = None,
        discount=0,
    ) -> int:
        return self._insert(
            "INSERT INTO purchase_lines (purchase_id, line_no, item_id, unit_id, warehouse_id,"
            " quantity, unit_price, discount, line_total, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (purchase_id, line_no, item_id, unit_id, warehouse_id, qty_to_db(quantity),
             money_to_db(unit_price), money_to_db(discount), money_to_db(line_total), now_iso()))

    def get(self, purchase_id: int) -> dict | None:
        return self._one("SELECT * FROM purchases WHERE id = ?", (purchase_id,))

    def lines_for(self, purchase_id: int) -> list[dict]:
        return self._all(
            "SELECT * FROM purchase_lines WHERE purchase_id = ? ORDER BY line_no", (purchase_id,))

    def mark_posted(self, purchase_id: int, user_id: int | None) -> None:
        ts = now_iso()
        self._exec(
            "UPDATE purchases SET status = 'POSTED', posted_at = ?, posted_by = ?, updated_at = ?"
            " WHERE id = ?", (ts, user_id, ts, purchase_id))


class InventoryRepository(BaseRepository):
    def add_movement(
        self,
        *,
        item_id: int,
        warehouse_id: int,
        movement_type: str,
        quantity,
        movement_date: str,
        unit_id: int | None = None,
        reference_type: str | None = None,
        reference_id: int | None = None,
        reference_line_id: int | None = None,
        created_by: int | None = None,
    ) -> int:
        return self._insert(
            "INSERT INTO inventory_movements (item_id, warehouse_id, movement_type, quantity,"
            " unit_id, reference_type, reference_id, reference_line_id, movement_date,"
            " created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (item_id, warehouse_id, movement_type, qty_to_db(quantity), unit_id,
             reference_type, reference_id, reference_line_id, movement_date,
             created_by, now_iso()))

    def stock_on_hand(self, item_id: int, warehouse_id: int | None = None) -> str:
        """Signed sum of movement quantities → current stock (canonical string).

        Summed with Decimal in Python — never a float SQL aggregate — so the
        result is exact regardless of magnitude (§24).
        """
        if warehouse_id is not None:
            rows = self._all(
                "SELECT quantity FROM inventory_movements WHERE item_id = ? AND warehouse_id = ?",
                (item_id, warehouse_id))
        else:
            rows = self._all(
                "SELECT quantity FROM inventory_movements WHERE item_id = ?", (item_id,))
        total = sum((D(r["quantity"]) for r in rows), D(0))
        return qty_to_db(total)

    def movements_for(self, item_id: int, limit: int = 100) -> list[dict]:
        return self._all(
            "SELECT * FROM inventory_movements WHERE item_id = ?"
            " ORDER BY movement_date DESC, id DESC LIMIT ?", (item_id, limit))


class ReceiptRepository(BaseRepository):
    def create(
        self,
        *,
        document_no: str,
        receipt_date: str,
        currency_id: int,
        amount,
        customer_id: int | None = None,
        account_id: int | None = None,
        exchange_rate=1,
        reference: str | None = None,
        notes: str | None = None,
        status: str = "POSTED",
        created_by: int | None = None,
    ) -> int:
        ts = now_iso()
        return self._insert(
            "INSERT INTO receipts (document_no, receipt_date, customer_id, account_id,"
            " currency_id, exchange_rate, amount, reference, notes, status, created_by,"
            " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (document_no, receipt_date, customer_id, account_id, currency_id,
             rate_to_db(exchange_rate), money_to_db(amount), reference, notes, status,
             created_by, ts, ts))

    def get(self, receipt_id: int) -> dict | None:
        return self._one("SELECT * FROM receipts WHERE id = ?", (receipt_id,))


class PaymentRepository(BaseRepository):
    def create(
        self,
        *,
        document_no: str,
        payment_date: str,
        currency_id: int,
        amount,
        supplier_id: int | None = None,
        account_id: int | None = None,
        exchange_rate=1,
        reference: str | None = None,
        notes: str | None = None,
        status: str = "POSTED",
        created_by: int | None = None,
    ) -> int:
        ts = now_iso()
        return self._insert(
            "INSERT INTO payments (document_no, payment_date, supplier_id, account_id,"
            " currency_id, exchange_rate, amount, reference, notes, status, created_by,"
            " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (document_no, payment_date, supplier_id, account_id, currency_id,
             rate_to_db(exchange_rate), money_to_db(amount), reference, notes, status,
             created_by, ts, ts))

    def get(self, payment_id: int) -> dict | None:
        return self._one("SELECT * FROM payments WHERE id = ?", (payment_id,))


class ExpenseRepository(BaseRepository):
    def create(
        self,
        *,
        document_no: str,
        expense_date: str,
        currency_id: int,
        amount,
        expense_category_id: int | None = None,
        account_id: int | None = None,
        exchange_rate=1,
        payee: str | None = None,
        description: str | None = None,
        reference: str | None = None,
        status: str = "POSTED",
        created_by: int | None = None,
    ) -> int:
        return self._insert(
            "INSERT INTO expenses (document_no, expense_date, expense_category_id, account_id,"
            " amount, currency_id, exchange_rate, payee, description, reference, status,"
            " created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (document_no, expense_date, expense_category_id, account_id, money_to_db(amount),
             currency_id, rate_to_db(exchange_rate), payee, description, reference, status,
             created_by, now_iso()))

    def get(self, expense_id: int) -> dict | None:
        return self._one("SELECT * FROM expenses WHERE id = ?", (expense_id,))

    def add_category(self, *, code: str, name: str) -> int:
        ts = now_iso()
        return self._insert(
            "INSERT INTO expense_categories (code, name, created_at, updated_at)"
            " VALUES (?, ?, ?, ?)", (code, name, ts, ts))


class FinancialRepository(BaseRepository):
    """Double-entry ledger foundation (§29). Each entry has balanced debit/credit lines."""

    def create_entry(
        self,
        *,
        entry_no: str,
        entry_date: str,
        source_type: str,
        source_id: int | None = None,
        description: str | None = None,
        created_by: int | None = None,
    ) -> int:
        return self._insert(
            "INSERT INTO financial_entries (entry_no, entry_date, source_type, source_id,"
            " description, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (entry_no, entry_date, source_type, source_id, description, created_by, now_iso()))

    def add_line(
        self,
        *,
        entry_id: int,
        account_id: int | None = None,
        debit=0,
        credit=0,
        party_type: str | None = None,
        party_id: int | None = None,
        currency_id: int | None = None,
        memo: str | None = None,
    ) -> int:
        return self._insert(
            "INSERT INTO financial_entry_lines (entry_id, account_id, party_type, party_id,"
            " debit, credit, currency_id, memo) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (entry_id, account_id, party_type, party_id, money_to_db(debit),
             money_to_db(credit), currency_id, memo))

    def lines_for(self, entry_id: int) -> list[dict]:
        return self._all(
            "SELECT * FROM financial_entry_lines WHERE entry_id = ? ORDER BY id", (entry_id,))

    def account_balance(self, account_id: int) -> str:
        """Net (debit − credit) balance for an account as a canonical money string.

        Summed with Decimal in Python for exactness (§24, §29).
        """
        rows = self._all(
            "SELECT debit, credit FROM financial_entry_lines WHERE account_id = ?", (account_id,))
        total = sum((D(r["debit"]) - D(r["credit"]) for r in rows), D(0))
        return money_to_db(total)

    def entry_balance(self, entry_id: int) -> str:
        """Net (debit − credit) across all lines of one entry (Decimal-exact).

        Zero means the entry balances. Used by the posting guard (§29).
        """
        rows = self._all(
            "SELECT debit, credit FROM financial_entry_lines WHERE entry_id = ?", (entry_id,))
        total = sum((D(r["debit"]) - D(r["credit"]) for r in rows), D(0))
        return money_to_db(total)
