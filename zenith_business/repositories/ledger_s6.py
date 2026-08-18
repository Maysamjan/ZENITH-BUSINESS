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
    " LEFT JOIN sales s ON fe.source_type IN ('SALE','SALE_VOID') AND s.id = fe.source_id"
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
        """Total invoiced (posted sales), total received on account, receivable."""
        sales = self._all(
            "SELECT grand_total FROM sales WHERE party_id = ? AND status = 'POSTED'", (party_id,))
        total_sales = money_to_db(sum((D(r["grand_total"]) for r in sales), D(0)))
        total_received = self._sum_credit("CUSTOMER", party_id, ("RECEIPT",))
        rows = self._all(
            "SELECT debit, credit FROM financial_entry_lines"
            " WHERE party_type = 'CUSTOMER' AND party_id = ?", (party_id,))
        receivable = money_to_db(sum((D(r["debit"]) - D(r["credit"]) for r in rows), D(0)))
        return {"total_sales": total_sales, "total_received": total_received,
                "receivable": receivable}

    def supplier_totals(self, party_id: int) -> dict:
        """Total purchased (posted purchases), total paid, payable."""
        purchases = self._all(
            "SELECT grand_total FROM purchases WHERE party_id = ? AND status = 'POSTED'",
            (party_id,))
        total_purchases = money_to_db(sum((D(r["grand_total"]) for r in purchases), D(0)))
        total_paid = self._sum_debit("SUPPLIER", party_id, ("PAYMENT",))
        rows = self._all(
            "SELECT debit, credit FROM financial_entry_lines"
            " WHERE party_type = 'SUPPLIER' AND party_id = ?", (party_id,))
        payable = money_to_db(sum((D(r["credit"]) - D(r["debit"]) for r in rows), D(0)))
        return {"total_purchases": total_purchases, "total_paid": total_paid,
                "payable": payable}
