"""Party account-ledger queries (owner-fix defect #4) — read-only, derived.

A registered person's complete financial history is DERIVED from the authoritative
LOCKED double-entry ledger (``financial_entry_lines`` tagged with the party) joined
to its journal header and the originating business document, so nothing here stores
or duplicates a balance. The running balance is accumulated by the service from
these ordered rows. Customer view uses the receivable convention (debit − credit);
supplier view uses the payable convention (credit − debit).
"""

from __future__ import annotations

from zenith_business.core.money import D, money_to_db
from zenith_business.repositories.base import BaseRepository

# Business document number resolved from the journal's source, so the ledger shows
# real doc numbers (SALE-…, RCP-…, SRET-…, PUR-…, PAY-…, PRET-…) not the JV number.
_DOC_JOINS = (
    " LEFT JOIN sales s ON fe.source_type IN ('SALE','SALE_VOID','SALE_CORRECTION')"
    " AND s.id = fe.source_id"
    " LEFT JOIN sales_returns sr ON fe.source_type = 'SALES_RETURN' AND sr.id = fe.source_id"
    " LEFT JOIN purchases pu ON fe.source_type IN ('PURCHASE','PURCHASE_VOID') AND pu.id = fe.source_id"
    " LEFT JOIN purchase_returns pr ON fe.source_type = 'PURCHASE_RETURN' AND pr.id = fe.source_id"
    " LEFT JOIN receipts rc ON fe.source_type = 'RECEIPT' AND rc.id = fe.source_id"
    " LEFT JOIN payments pm ON fe.source_type = 'PAYMENT' AND pm.id = fe.source_id"
)
_DOC_NO = ("COALESCE(s.document_no, sr.document_no, pu.document_no, pr.document_no,"
           " rc.document_no, pm.document_no, fe.entry_no)")


class PartyLedgerRepository(BaseRepository):
    def _entries(self, party_type: str, party_id: int) -> list[dict]:
        return self._all(
            "SELECT fe.entry_date AS date, fe.source_type AS source_type,"
            f" {_DOC_NO} AS doc_no, fe.entry_no AS entry_no, fe.description AS description,"
            " fel.debit AS debit, fel.credit AS credit"
            " FROM financial_entry_lines fel"
            " JOIN financial_entries fe ON fe.id = fel.entry_id"
            f"{_DOC_JOINS}"
            " WHERE fel.party_type = ? AND fel.party_id = ?"
            " ORDER BY fe.entry_date ASC, fe.id ASC, fel.id ASC",
            (party_type, party_id))

    def customer_entries(self, party_id: int) -> list[dict]:
        return self._entries("CUSTOMER", party_id)

    def supplier_entries(self, party_id: int) -> list[dict]:
        return self._entries("SUPPLIER", party_id)

    # ---- summaries (authoritative persisted data) -----------------------

    def _sum_credit(self, party_type: str, party_id: int, source_types: tuple[str, ...]) -> str:
        marks = ",".join("?" for _ in source_types)
        rows = self._all(
            "SELECT fel.credit AS credit FROM financial_entry_lines fel"
            " JOIN financial_entries fe ON fe.id = fel.entry_id"
            f" WHERE fel.party_type = ? AND fel.party_id = ? AND fe.source_type IN ({marks})",
            (party_type, party_id, *source_types))
        return money_to_db(sum((D(r["credit"]) for r in rows), D(0)))

    def _sum_debit(self, party_type: str, party_id: int, source_types: tuple[str, ...]) -> str:
        marks = ",".join("?" for _ in source_types)
        rows = self._all(
            "SELECT fel.debit AS debit FROM financial_entry_lines fel"
            " JOIN financial_entries fe ON fe.id = fel.entry_id"
            f" WHERE fel.party_type = ? AND fel.party_id = ? AND fe.source_type IN ({marks})",
            (party_type, party_id, *source_types))
        return money_to_db(sum((D(r["debit"]) for r in rows), D(0)))

    def customer_totals(self, party_id: int) -> dict:
        """Net sales, everything received, and the receivable — and they add up.

        The three figures a summary shows must satisfy
        ``total_sales - total_received == receivable``, or the screen invites the
        reader to distrust all three. Two things are needed for that:

        * sales are counted **net of posted returns**, because a return credits the
          receivable, and
        * "received" counts the money taken **on the invoice itself** as well as
          later Receipt documents — cash handed over at the counter is money
          received just as much as a receipt is.

        Money is summed with ``Decimal``, never a SQL aggregate (§24).
        """
        sales = self._all(
            "SELECT id, grand_total, amount_paid FROM sales"
            " WHERE party_id = ? AND status = 'POSTED'", (party_id,))
        gross = sum((D(r["grand_total"]) for r in sales), D(0))
        paid_on_invoices = sum((D(r["amount_paid"]) for r in sales), D(0))
        returned = D(0)
        if sales:
            marks = ",".join("?" * len(sales))
            returned = sum((D(r["grand_total"]) for r in self._all(
                f"SELECT grand_total FROM sales_returns"
                f" WHERE status = 'POSTED' AND sale_id IN ({marks})",
                tuple(r["id"] for r in sales))), D(0))
        total_sales = money_to_db(gross - returned)
        total_received = money_to_db(
            paid_on_invoices + D(self._sum_credit("CUSTOMER", party_id, ("RECEIPT",))))
        rows = self._all(
            "SELECT debit, credit FROM financial_entry_lines"
            " WHERE party_type = 'CUSTOMER' AND party_id = ?", (party_id,))
        receivable = money_to_db(sum((D(r["debit"]) - D(r["credit"]) for r in rows), D(0)))
        return {"total_sales": total_sales, "total_received": total_received,
                "receivable": receivable}

    def supplier_totals(self, party_id: int) -> dict:
        """Net purchases, everything paid, and the payable — and they add up.

        The supplier mirror of :meth:`customer_totals`, and for the same reason:
        ``total_purchases - total_paid == payable`` must hold. Purchases are net of
        posted returns (a return debits the payable), and "paid" counts the money
        handed over **on the bill** as well as later Payment documents.
        """
        purchases = self._all(
            "SELECT id, grand_total, amount_paid FROM purchases"
            " WHERE party_id = ? AND status = 'POSTED'", (party_id,))
        gross = sum((D(r["grand_total"]) for r in purchases), D(0))
        paid_on_bills = sum((D(r["amount_paid"]) for r in purchases), D(0))
        returned = D(0)
        if purchases:
            marks = ",".join("?" * len(purchases))
            returned = sum((D(r["grand_total"]) for r in self._all(
                f"SELECT grand_total FROM purchase_returns"
                f" WHERE status = 'POSTED' AND purchase_id IN ({marks})",
                tuple(r["id"] for r in purchases))), D(0))
        total_purchases = money_to_db(gross - returned)
        total_paid = money_to_db(
            paid_on_bills + D(self._sum_debit("SUPPLIER", party_id, ("PAYMENT",))))
        rows = self._all(
            "SELECT debit, credit FROM financial_entry_lines"
            " WHERE party_type = 'SUPPLIER' AND party_id = ?", (party_id,))
        payable = money_to_db(sum((D(r["credit"]) - D(r["debit"]) for r in rows), D(0)))
        return {"total_purchases": total_purchases, "total_paid": total_paid,
                "payable": payable}
