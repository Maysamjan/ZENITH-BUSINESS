"""Financial/ledger service — the sanctioned journal-posting API (Stage 02 §29).

Repositories are low-level SQL primitives; this service is the ONLY blessed way to
write a journal entry. It builds the header + lines and refuses to commit anything
that does not balance (total debit == total credit), so every future module
(receipts, payments, expenses, adjustments) posts accounting that is correct by
construction.
"""

from __future__ import annotations

from dataclasses import dataclass

from zenith_business.core.clock import today_iso
from zenith_business.database.connection import Database
from zenith_business.repositories.documents import FinancialRepository
from zenith_business.services.document_math import assert_journal_balanced, parse_money_input
from zenith_business.services.exceptions import ValidationError
from zenith_business.services.numbering import DocumentNumberService
from zenith_business.services.session import SessionContext


@dataclass
class JournalLine:
    account_id: int | None = None
    debit: object = 0
    credit: object = 0
    party_type: str | None = None
    party_id: int | None = None
    currency_id: int | None = None
    memo: str | None = None


class FinancialService:
    def __init__(
        self,
        db: Database,
        financial: FinancialRepository,
        numbering: DocumentNumberService,
        session: SessionContext,
    ) -> None:
        self._db = db
        self._financial = financial
        self._numbering = numbering
        self._session = session

    def post_entry(
        self,
        *,
        source_type: str,
        lines: list[JournalLine],
        entry_date: str | None = None,
        source_id: int | None = None,
        description: str | None = None,
        entry_no: str | None = None,
    ) -> int:
        """Create a balanced journal entry atomically. Raises if it does not balance."""
        if len(lines) < 2:
            raise ValidationError("A journal needs at least two lines.",
                                  user_message="An accounting entry needs at least two lines.")
        date = entry_date or today_iso()
        with self._db.transaction():
            number = entry_no or self._numbering.allocate("JV")
            entry_id = self._financial.create_entry(
                entry_no=number, entry_date=date, source_type=source_type,
                source_id=source_id, description=description,
                created_by=self._session.user_id)
            for ln in lines:
                # Strict-parse amounts so malformed input is rejected, never
                # silently zeroed into a wrong-but-"balanced" entry.
                debit = parse_money_input(ln.debit, field="debit")
                credit = parse_money_input(ln.credit, field="credit")
                self._financial.add_line(
                    entry_id=entry_id, account_id=ln.account_id, debit=debit,
                    credit=credit, party_type=ln.party_type, party_id=ln.party_id,
                    currency_id=ln.currency_id, memo=ln.memo)
            assert_journal_balanced(self._financial, entry_id)
        return entry_id
