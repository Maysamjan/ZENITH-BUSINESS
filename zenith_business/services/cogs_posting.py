"""Stage 09 — charging the cost of goods sold to the accounts.

Stage 08 established what every stock movement was worth. Nothing charged that
cost to the ledger, so the accounts told a story that was plainly wrong: a
purchase debited Inventory and a sale credited only Revenue, which meant
**Inventory never came down** and **Cost of Goods Sold never moved off zero**.
On the owner's own scenario the GL held Inventory 1,000 against stock genuinely
worth 375 — overstated by exactly the 625 of cost that was never posted.

The posting
-----------
For every SALES-side inventory movement, exactly one journal::

    Dr  Cost of Goods Sold     the cost the goods left at
        Cr  Inventory

The amount is **taken from the movement**, never recomputed, and never from the
selling price: `total_cost` is the Stage 08 figure, so the journal cannot drift
from the valuation. Because the value comes from the movement, everything else
falls out on its own rather than needing special cases:

* a **sales return** posts a movement that brings the goods back at the cost they
  left at, so its journal is the exact reverse;
* a **correction** or **void** posts its compensating movement the same way;
* a corrected invoice is never double-charged, because each movement is charged
  once and the reversal that undoes the first one is itself a movement.

Why this does not touch locked code
-----------------------------------
Posting from inside the sale would mean editing LOCKED Stage 05/07 services, or
turning the Stage 08 repository choke point into a journal-posting orchestrator —
a repository posting double-entry is the wrong place for it, and both would
change a locked contract. Instead this service **reads** the costed ledger and
posts what is missing. Two properties make that equivalent to posting inline:

* each entry is dated with **the movement's own date**, not the day the posting
  ran, so a Trial Balance for any past period is correct once posted; and
* every accounting report calls :meth:`sync` before it reads, so the accounts a
  user sees are always complete.

"Exactly once" is guaranteed by the database: a COGS entry is keyed
``source_type='COGS'``, ``source_id=<movement id>`` under a unique index, so a
concurrent or repeated run cannot produce a second charge for the same movement.
"""

from __future__ import annotations

import sqlite3

from zenith_business.core.money import D, money, money_to_db

#: Sales-side movements, by the document that caused them. The same set Stage 08
#: locked for COGS reporting — selecting by reference_type rather than movement
#: type is what stops a corrected invoice being counted twice.
COGS_REFERENCE_TYPES = ("SALE", "SALES_RETURN", "SALE_CORRECTION", "SALE_VOID")

_ACCT_COGS = "5000"
_ACCT_INVENTORY = "1200"

#: The ledger's own marker for a cost charge.
SOURCE_TYPE = "COGS"

#: What each kind of cost charge is called in the General Ledger. A reader of the
#: ledger is the business owner, not a developer, so the line names the DOCUMENT
#: that caused the cost — never an internal movement id.
COGS_DESCRIPTION_LABELS: dict[str, str] = {
    "SALE": "COGS",
    "SALES_RETURN": "COGS Reversal",
    "SALE_CORRECTION": "COGS Correction",
    "SALE_VOID": "COGS Void",
}


def cogs_description(reference_type: str, document_no: str | None) -> str:
    """The General Ledger text for a cost charge, e.g. ``COGS — SALE-000009``.

    With no document to name — which should not happen, but a ledger line must
    still read sensibly if it does — the label stands alone rather than falling
    back to an internal identifier.
    """
    label = COGS_DESCRIPTION_LABELS.get(reference_type, "COGS")
    document = (document_no or "").strip()
    return f"{label} — {document}" if document else label


class CogsPostingService:
    """Posts the Stage 08 movement cost to Cost of Goods Sold / Inventory."""

    def __init__(self, db, financial, accounts, numbering, session, authz,
                 audit=None) -> None:
        self._db = db
        self._financial = financial
        self._accounts = accounts
        self._numbering = numbering
        self._session = session
        self._authz = authz
        self._audit = audit

    # ---- what still needs charging ---------------------------------------

    def unposted_movements(self) -> list[dict]:
        """Costed sales-side movements with no COGS journal yet, oldest first."""
        marks = ",".join("?" * len(COGS_REFERENCE_TYPES))
        rows = self._db.connection().execute(
            "SELECT m.id, m.movement_date, m.total_cost, m.reference_type,"
            "       m.reference_id, m.item_id,"
            # The document that caused the movement, so the journal can name it.
            "       COALESCE(s.document_no, sr.document_no) AS document_no"
            "  FROM inventory_movements m"
            "  LEFT JOIN sales s ON s.id = m.reference_id"
            "       AND m.reference_type IN ('SALE', 'SALE_CORRECTION', 'SALE_VOID')"
            "  LEFT JOIN sales_returns sr ON sr.id = m.reference_id"
            "       AND m.reference_type = 'SALES_RETURN'"
            f" WHERE m.reference_type IN ({marks})"
            "   AND m.total_cost IS NOT NULL"
            "   AND NOT EXISTS (SELECT 1 FROM financial_entries e"
            "                    WHERE e.source_type = ? AND e.source_id = m.id)"
            " ORDER BY m.id",
            (*COGS_REFERENCE_TYPES, SOURCE_TYPE)).fetchall()
        return [{"id": r[0], "movement_date": r[1], "total_cost": r[2],
                 "reference_type": r[3], "reference_id": r[4], "item_id": r[5],
                 "document_no": r[6]}
                for r in rows]

    # ---- posting ---------------------------------------------------------

    def sync(self) -> int:
        """Charge every movement that has not been charged. Returns entries posted.

        Idempotent by construction, so it is safe to call before every report —
        which is exactly what the reports do, so the accounts are never stale.
        """
        pending = self.unposted_movements()
        if not pending:
            return 0
        posted = 0
        with self._db.transaction():
            for movement in pending:
                if self._post_one(movement):
                    posted += 1
        if posted and self._audit is not None:
            self._audit.record(
                action="accounting.cogs_posted", user_id=self._session.user_id,
                username=self._session.username, entity_type="financial_entry",
                entity_id=None, document_no=None,
                details=f"movements={posted}")
        return posted

    def _post_one(self, movement: dict) -> bool:
        """One movement, one journal. Returns False when there is nothing to post."""
        # A sale takes stock OUT, so its total_cost is negative; the cost charged
        # is the positive mirror of it. A return or a reversal brings stock back
        # and therefore charges a negative cost — a credit to COGS.
        charge = money(-D(movement["total_cost"]))
        if charge == 0:
            return False

        cogs_id = self._accounts.id_by_code(_ACCT_COGS)
        inventory_id = self._accounts.id_by_code(_ACCT_INVENTORY)
        entry_no = self._numbering.allocate("JV")
        try:
            entry_id = self._financial.create_entry(
                entry_no=entry_no,
                # The movement's OWN date: a cost belongs to the period the goods
                # moved in, not to the day this ran.
                entry_date=movement["movement_date"],
                source_type=SOURCE_TYPE, source_id=movement["id"],
                description=cogs_description(movement["reference_type"],
                                             movement.get("document_no")),
                created_by=self._session.user_id)
        except sqlite3.IntegrityError:
            # The unique index refused a duplicate: another run got there first,
            # which is precisely the guarantee working.
            return False

        if charge > 0:
            self._financial.add_line(entry_id=entry_id, account_id=cogs_id,
                                     debit=charge, memo="Cost of goods sold")
            self._financial.add_line(entry_id=entry_id, account_id=inventory_id,
                                     credit=charge, memo="Inventory relieved")
        else:
            amount = money(-charge)
            self._financial.add_line(entry_id=entry_id, account_id=inventory_id,
                                     debit=amount, memo="Inventory returned")
            self._financial.add_line(entry_id=entry_id, account_id=cogs_id,
                                     credit=amount, memo="Cost of goods sold reversed")
        return True

    # ---- reads -----------------------------------------------------------

    def posted_total(self, *, date_from: str | None = None,
                     date_to: str | None = None) -> str:
        """Net COGS actually charged to the accounts, for reconciliation."""
        where = ["e.source_type = ?"]
        params: list = [SOURCE_TYPE]
        if date_from:
            where.append("e.entry_date >= ?"); params.append(date_from)
        if date_to:
            where.append("e.entry_date <= ?"); params.append(date_to)
        cogs_id = self._accounts.id_by_code(_ACCT_COGS)
        params.append(cogs_id)
        rows = self._db.connection().execute(
            "SELECT l.debit, l.credit FROM financial_entry_lines l"
            "  JOIN financial_entries e ON e.id = l.entry_id"
            f" WHERE {' AND '.join(where)} AND l.account_id = ?", params).fetchall()
        return money_to_db(sum((D(r[0]) - D(r[1]) for r in rows), D(0)))

    def entry_for_movement(self, movement_id: int) -> dict | None:
        """The journal charged for one movement — ledger back to its source (§8)."""
        row = self._db.connection().execute(
            "SELECT id, entry_no, entry_date, description FROM financial_entries"
            " WHERE source_type = ? AND source_id = ?",
            (SOURCE_TYPE, movement_id)).fetchone()
        if row is None:
            return None
        return {"id": row[0], "entry_no": row[1], "entry_date": row[2],
                "description": row[3]}
