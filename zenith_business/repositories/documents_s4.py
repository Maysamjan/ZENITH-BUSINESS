"""Stage 04 document repositories — party links, returns, party balances.

Additive: the LOCKED Stage 02 ``SalesRepository``/``PurchaseRepository`` are used
unchanged for header/line writes; this module adds the party link, the return
tables, the returned-quantity queries (for over-return protection), party-aware
list joins, and Decimal-exact party balances derived from the LOCKED ledger.
All money/qty fields serialize through the Decimal helpers.
"""

from __future__ import annotations

from zenith_business.core.clock import now_iso
from zenith_business.core.money import D, money_to_db, qty_to_db, rate_to_db
from zenith_business.repositories.base import BaseRepository


class SalesExtRepository(BaseRepository):
    """Stage 04 extensions to the locked sales tables."""

    def set_party(self, sale_id: int, party_id: int | None) -> None:
        self._exec("UPDATE sales SET party_id = ? WHERE id = ?", (party_id, sale_id))

    def returned_qty_for_line(self, sale_line_id: int) -> str:
        rows = self._all(
            "SELECT srl.quantity FROM sales_return_lines srl"
            " JOIN sales_returns sr ON sr.id = srl.return_id"
            " WHERE srl.sale_line_id = ? AND sr.status = 'POSTED'", (sale_line_id,))
        return qty_to_db(sum((D(r["quantity"]) for r in rows), D(0)))

    def list_documents(self, *, term: str | None = None, status: str | None = None,
                       date_from: str | None = None, date_to: str | None = None,
                       limit: int = 200) -> list[dict]:
        where = ["1=1"]
        params: list = []
        if term:
            where.append("(s.document_no LIKE ? OR p.name LIKE ?)")
            like = f"%{term.strip()}%"; params += [like, like]
        if status:
            where.append("s.status = ?"); params.append(status)
        if date_from:
            where.append("s.sale_date >= ?"); params.append(date_from)
        if date_to:
            where.append("s.sale_date <= ?"); params.append(date_to)
        params.append(limit)
        return self._all(
            "SELECT s.id, s.document_no, s.sale_date, s.grand_total, s.amount_paid,"
            " s.remaining_amount, s.status, s.warehouse_id, p.name AS party_name,"
            " w.name AS warehouse_name, u.full_name AS user_name FROM sales s"
            " LEFT JOIN parties p ON p.id = s.party_id"
            " LEFT JOIN warehouses w ON w.id = s.warehouse_id"
            " LEFT JOIN users u ON u.id = s.created_by"
            f" WHERE {' AND '.join(where)} ORDER BY s.sale_date DESC, s.id DESC LIMIT ?",
            tuple(params))

    def today_total(self, date: str) -> str:
        rows = self._all(
            "SELECT grand_total FROM sales WHERE sale_date = ? AND status = 'POSTED'", (date,))
        return money_to_db(sum((D(r["grand_total"]) for r in rows), D(0)))


class PurchaseExtRepository(BaseRepository):
    def set_party(self, purchase_id: int, party_id: int | None,
                  supplier_reference: str | None = None) -> None:
        self._exec("UPDATE purchases SET party_id = ?, supplier_reference = ? WHERE id = ?",
                   (party_id, supplier_reference, purchase_id))

    def returned_qty_for_line(self, purchase_line_id: int) -> str:
        rows = self._all(
            "SELECT prl.quantity FROM purchase_return_lines prl"
            " JOIN purchase_returns pr ON pr.id = prl.return_id"
            " WHERE prl.purchase_line_id = ? AND pr.status = 'POSTED'", (purchase_line_id,))
        return qty_to_db(sum((D(r["quantity"]) for r in rows), D(0)))

    def list_documents(self, *, term: str | None = None, status: str | None = None,
                       date_from: str | None = None, date_to: str | None = None,
                       limit: int = 200) -> list[dict]:
        where = ["1=1"]
        params: list = []
        if term:
            where.append("(p.document_no LIKE ? OR pa.name LIKE ?)")
            like = f"%{term.strip()}%"; params += [like, like]
        if status:
            where.append("p.status = ?"); params.append(status)
        if date_from:
            where.append("p.purchase_date >= ?"); params.append(date_from)
        if date_to:
            where.append("p.purchase_date <= ?"); params.append(date_to)
        params.append(limit)
        return self._all(
            "SELECT p.id, p.document_no, p.purchase_date, p.grand_total, p.amount_paid,"
            " p.remaining_amount, p.status, p.warehouse_id, p.supplier_reference,"
            " pa.name AS party_name, w.name AS warehouse_name FROM purchases p"
            " LEFT JOIN parties pa ON pa.id = p.party_id"
            " LEFT JOIN warehouses w ON w.id = p.warehouse_id"
            f" WHERE {' AND '.join(where)} ORDER BY p.purchase_date DESC, p.id DESC LIMIT ?",
            tuple(params))

    def today_total(self, date: str) -> str:
        rows = self._all(
            "SELECT grand_total FROM purchases WHERE purchase_date = ? AND status = 'POSTED'",
            (date,))
        return money_to_db(sum((D(r["grand_total"]) for r in rows), D(0)))


class SalesReturnRepository(BaseRepository):
    def create_header(self, *, document_no: str, return_date: str, sale_id: int,
                      currency_id: int, party_id: int | None = None,
                      warehouse_id: int | None = None, exchange_rate=1, subtotal=0,
                      discount_total=0, grand_total=0, reason: str | None = None,
                      notes: str | None = None, created_by: int | None = None) -> int:
        ts = now_iso()
        return self._insert(
            "INSERT INTO sales_returns (document_no, return_date, sale_id, party_id,"
            " warehouse_id, currency_id, exchange_rate, subtotal, discount_total, grand_total,"
            " status, reason, notes, created_by, created_at, updated_at, posted_at, posted_by)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'POSTED', ?, ?, ?, ?, ?, ?, ?)",
            (document_no, return_date, sale_id, party_id, warehouse_id, currency_id,
             rate_to_db(exchange_rate), money_to_db(subtotal), money_to_db(discount_total),
             money_to_db(grand_total), reason, notes, created_by, ts, ts, ts, created_by))

    def add_line(self, *, return_id: int, line_no: int, sale_line_id: int, item_id: int,
                 unit_id: int, quantity, unit_price, line_total, warehouse_id: int | None = None,
                 discount=0) -> int:
        return self._insert(
            "INSERT INTO sales_return_lines (return_id, line_no, sale_line_id, item_id, unit_id,"
            " warehouse_id, quantity, unit_price, discount, line_total, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (return_id, line_no, sale_line_id, item_id, unit_id, warehouse_id, qty_to_db(quantity),
             money_to_db(unit_price), money_to_db(discount), money_to_db(line_total), now_iso()))

    def get(self, return_id: int) -> dict | None:
        return self._one("SELECT * FROM sales_returns WHERE id = ?", (return_id,))

    def lines_for(self, return_id: int) -> list[dict]:
        return self._all("SELECT * FROM sales_return_lines WHERE return_id = ? ORDER BY line_no",
                         (return_id,))

    def list_for_sale(self, sale_id: int) -> list[dict]:
        return self._all("SELECT * FROM sales_returns WHERE sale_id = ? ORDER BY id DESC",
                         (sale_id,))

    def list_recent(self, limit: int = 200) -> list[dict]:
        return self._all(
            "SELECT sr.id, sr.document_no, sr.return_date, sr.grand_total, sr.status,"
            " s.document_no AS sale_no, p.name AS party_name FROM sales_returns sr"
            " JOIN sales s ON s.id = sr.sale_id"
            " LEFT JOIN parties p ON p.id = sr.party_id"
            " ORDER BY sr.return_date DESC, sr.id DESC LIMIT ?", (limit,))


class PurchaseReturnRepository(BaseRepository):
    def create_header(self, *, document_no: str, return_date: str, purchase_id: int,
                      currency_id: int, party_id: int | None = None,
                      warehouse_id: int | None = None, exchange_rate=1, subtotal=0,
                      discount_total=0, grand_total=0, reason: str | None = None,
                      notes: str | None = None, created_by: int | None = None) -> int:
        ts = now_iso()
        return self._insert(
            "INSERT INTO purchase_returns (document_no, return_date, purchase_id, party_id,"
            " warehouse_id, currency_id, exchange_rate, subtotal, discount_total, grand_total,"
            " status, reason, notes, created_by, created_at, updated_at, posted_at, posted_by)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'POSTED', ?, ?, ?, ?, ?, ?, ?)",
            (document_no, return_date, purchase_id, party_id, warehouse_id, currency_id,
             rate_to_db(exchange_rate), money_to_db(subtotal), money_to_db(discount_total),
             money_to_db(grand_total), reason, notes, created_by, ts, ts, ts, created_by))

    def add_line(self, *, return_id: int, line_no: int, purchase_line_id: int, item_id: int,
                 unit_id: int, quantity, unit_price, line_total, warehouse_id: int | None = None,
                 discount=0) -> int:
        return self._insert(
            "INSERT INTO purchase_return_lines (return_id, line_no, purchase_line_id, item_id,"
            " unit_id, warehouse_id, quantity, unit_price, discount, line_total, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (return_id, line_no, purchase_line_id, item_id, unit_id, warehouse_id,
             qty_to_db(quantity), money_to_db(unit_price), money_to_db(discount),
             money_to_db(line_total), now_iso()))

    def get(self, return_id: int) -> dict | None:
        return self._one("SELECT * FROM purchase_returns WHERE id = ?", (return_id,))

    def lines_for(self, return_id: int) -> list[dict]:
        return self._all(
            "SELECT * FROM purchase_return_lines WHERE return_id = ? ORDER BY line_no",
            (return_id,))

    def list_recent(self, limit: int = 200) -> list[dict]:
        return self._all(
            "SELECT pr.id, pr.document_no, pr.return_date, pr.grand_total, pr.status,"
            " p.document_no AS purchase_no, pa.name AS party_name FROM purchase_returns pr"
            " JOIN purchases p ON p.id = pr.purchase_id"
            " LEFT JOIN parties pa ON pa.id = pr.party_id"
            " ORDER BY pr.return_date DESC, pr.id DESC LIMIT ?", (limit,))


class PartyBalanceRepository(BaseRepository):
    """Decimal-exact party balances derived from the LOCKED double-entry ledger.

    Receivable = net debit on lines tagged party_type='CUSTOMER'; payable = net
    credit on lines tagged party_type='SUPPLIER'. party_id holds ``parties.id``.
    """

    def receivable(self, party_id: int) -> str:
        rows = self._all(
            "SELECT debit, credit FROM financial_entry_lines"
            " WHERE party_type = 'CUSTOMER' AND party_id = ?", (party_id,))
        return money_to_db(sum((D(r["debit"]) - D(r["credit"]) for r in rows), D(0)))

    def payable(self, party_id: int) -> str:
        rows = self._all(
            "SELECT debit, credit FROM financial_entry_lines"
            " WHERE party_type = 'SUPPLIER' AND party_id = ?", (party_id,))
        return money_to_db(sum((D(r["credit"]) - D(r["debit"]) for r in rows), D(0)))
