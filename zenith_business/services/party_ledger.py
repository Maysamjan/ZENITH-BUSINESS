"""Customer / Supplier account-ledger service (owner-fix defect #4).

Read-only. Presents a registered person's complete financial history and the
top-line summary, both derived from the authoritative LOCKED ledger via
:class:`PartyLedgerRepository`. The running balance is accumulated here from the
ordered persisted rows (Decimal-exact, never a float SQL aggregate). A person who
is both a customer and a supplier is the SAME ``parties`` row — the two ledgers are
just two views of that one identity, so no duplicate record is created.
"""

from __future__ import annotations

from zenith_business.core.money import D, money_to_db
from zenith_business.repositories.ledger_s6 import PartyLedgerRepository
from zenith_business.repositories.parties import PartyRepository
from zenith_business.services.authorization import AuthorizationService
from zenith_business.services.exceptions import ValidationError


class PartyLedgerService:
    def __init__(self, ledger: PartyLedgerRepository, parties: PartyRepository,
                 authz: AuthorizationService) -> None:
        self._ledger = ledger
        self._parties = parties
        self._authz = authz

    def _party_or_error(self, party_id: int) -> dict:
        party = self._parties.get(party_id)
        if party is None:
            raise ValidationError("Unknown party.", user_message="This person was not found.")
        return party

    def customer_ledger(self, party_id: int) -> dict:
        self._authz.require("parties.ledger")
        party = self._party_or_error(party_id)
        rows = self._ledger.customer_entries(party_id)
        running = D(0)
        out = []
        for r in rows:
            running += D(r["debit"]) - D(r["credit"])  # receivable convention
            out.append({**r, "running": money_to_db(running)})
        return {"party": party, "role": "customer",
                "totals": self._ledger.customer_totals(party_id), "rows": out}

    def supplier_ledger(self, party_id: int) -> dict:
        self._authz.require("parties.ledger")
        party = self._party_or_error(party_id)
        rows = self._ledger.supplier_entries(party_id)
        running = D(0)
        out = []
        for r in rows:
            running += D(r["credit"]) - D(r["debit"])  # payable convention
            out.append({**r, "running": money_to_db(running)})
        return {"party": party, "role": "supplier",
                "totals": self._ledger.supplier_totals(party_id), "rows": out}
