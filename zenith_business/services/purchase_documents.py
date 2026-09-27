"""Stage 04 Purchase document service — real atomic purchases + purchase returns.

Mirror of :mod:`sales_documents`: composes LOCKED repositories into one atomic
transaction, enforces the financial year, uses the unified ``parties`` model via
``purchases.party_id``, tracks supplier payable through the locked ledger, and
supports controlled purchase returns (with a source-stock check and over-return
protection). Decimal throughout.
"""

from __future__ import annotations

from dataclasses import dataclass

from zenith_business.core.clock import today_iso
from zenith_business.core.document_ref import candidates
from zenith_business.core.logging_setup import get_logger
from zenith_business.core.money import D, money, money_to_db, qty_to_db
from zenith_business.database.connection import Database
from zenith_business.repositories.documents import (
    FinancialRepository,
    InventoryRepository,
    PurchaseRepository,
)
from zenith_business.repositories.documents_s4 import (
    PartyBalanceRepository,
    PurchaseExtRepository,
    PurchaseReturnRepository,
)
from zenith_business.repositories.master import (
    AccountRepository,
    CurrencyRepository,
    ItemRepository,
    WarehouseRepository,
)
from zenith_business.repositories.parties import PartyRepository
from zenith_business.repositories.system import AuditRepository
from zenith_business.services.authorization import AuthorizationService
from zenith_business.services.document_math import (
    assert_journal_balanced,
    compute_line,
    parse_money_input,
)
from zenith_business.services.exceptions import InsufficientStockError, ValidationError
from zenith_business.services.financial_year import FinancialYearService
from zenith_business.services.numbering import DocumentNumberService
from zenith_business.services.sales_documents import PostedDocument
from zenith_business.services.session import SessionContext


@dataclass
class PurchaseReturnLine:
    purchase_line_id: int
    quantity: object

_logger = get_logger("services.purchase_doc")

_ACCT_CASH = "1000"
_ACCT_AP = "2000"
_ACCT_INVENTORY = "1200"


@dataclass
class PurchaseLine:
    item_id: int
    unit_id: int
    quantity: object
    unit_price: object
    discount: object = 0


class PurchaseDocumentService:
    def __init__(self, db: Database, purchases: PurchaseRepository,
                 purchases_ext: PurchaseExtRepository, returns: PurchaseReturnRepository,
                 inventory: InventoryRepository, financial: FinancialRepository,
                 accounts: AccountRepository, currencies: CurrencyRepository,
                 items: ItemRepository, warehouses: WarehouseRepository,
                 parties: PartyRepository, balances: PartyBalanceRepository,
                 numbering: DocumentNumberService, audit: AuditRepository,
                 session: SessionContext, authz: AuthorizationService,
                 financial_years: FinancialYearService) -> None:
        self._db = db
        self._purchases = purchases
        self._ext = purchases_ext
        self._returns = returns
        self._inventory = inventory
        self._financial = financial
        self._accounts = accounts
        self._currencies = currencies
        self._items = items
        self._warehouses = warehouses
        self._parties = parties
        self._balances = balances
        self._numbering = numbering
        self._audit = audit
        self._session = session
        self._authz = authz
        self._fy = financial_years

    def list(self, *, term=None, status=None, date_from=None, date_to=None,
             limit=200) -> list[dict]:
        """Purchase list rows, each carrying its CURRENT position after returns.

        ``grand_total`` stays the amount originally billed; ``returned_total``,
        ``net_total`` and ``net_remaining`` are derived from the posted return
        documents, so the list shows what the bill is worth now without storing a
        second copy of the figure. Money is summed with ``Decimal``, never a SQL
        float (§24).

        ``net_remaining`` = net total − paid: what is still owed to the supplier
        after the return. It goes negative when a paid bill is returned against —
        a refund due back from the supplier — which is the financially correct
        sign and agrees with the supplier's ledger balance.
        """
        self._authz.require("purchases.view")
        rows = self._ext.list_documents(term=term, status=status, date_from=date_from,
                                        date_to=date_to, limit=limit)
        returned: dict[int, D] = {}
        for r in self._returns.posted_totals_for_purchases([row["id"] for row in rows]):
            returned[r["purchase_id"]] = (returned.get(r["purchase_id"], D(0))
                                          + D(r["grand_total"]))
        for row in rows:
            back = returned.get(row["id"], D(0))
            net = money(row["grand_total"]) - back
            row["returned_total"] = money_to_db(back)
            row["net_total"] = money_to_db(net)
            row["net_remaining"] = money_to_db(net - money(row["amount_paid"]))
        return rows

    def net_view(self, purchase_id: int) -> dict | None:
        """The bill's CURRENT position after any posted returns.

        The purchase itself is never rewritten by a return — the bought quantities
        and the billed total stay on the document as the historical record, and the
        return documents stay intact for audit. What changed is derived here, so
        there is exactly one place that answers "what does this bill look like
        now": the Purchase List, the reopened bill, the printed copy and the
        supplier balance all read it. Mirrors ``SalesDocumentService.net_view``.
        """
        self._authz.require("purchases.view")
        purchase = self._purchases.get(purchase_id)
        if purchase is None:
            return None
        lines: list[dict] = []
        returned_total = D(0)
        for ln in self._purchases.lines_for(purchase_id):
            bought = D(ln["quantity"])
            returned = D(self._ext.returned_qty_for_line(ln["id"]))
            net_qty = bought - returned
            # Discount is spread per unit so a partial return keeps the same
            # effective cost the supplier charged.
            per_unit_disc = (money(ln["discount"]) / bought) if bought else D(0)
            net_line_total = money(net_qty * money(ln["unit_price"]) - net_qty * per_unit_disc)
            returned_total += money(returned * money(ln["unit_price"])
                                    - returned * per_unit_disc)
            lines.append({**ln, "bought": qty_to_db(bought), "returned": qty_to_db(returned),
                          "net_quantity": qty_to_db(net_qty),
                          "net_discount": money_to_db(money(net_qty * per_unit_disc)),
                          "net_line_total": money_to_db(net_line_total),
                          "fully_returned": net_qty <= 0})
        gross = money(purchase["grand_total"])
        returned_total = money(returned_total)
        return {
            "purchase": purchase, "lines": lines,
            "active_lines": [ln for ln in lines if not ln["fully_returned"]],
            "gross_total": money_to_db(gross),
            "returned_total": money_to_db(returned_total),
            "net_total": money_to_db(gross - returned_total),
            "net_remaining": money_to_db(gross - returned_total
                                         - money(purchase["amount_paid"])),
            "has_returns": returned_total > 0,
        }

    def returned_items(self, purchase_id: int) -> list[dict]:
        """Read-only history of what went back off this bill — item, qty, amount,
        return document — so the bill screen shows returned goods SEPARATELY from
        what is still owed, without either view rewriting the other."""
        self._authz.require("purchases.view")
        return self._returns.returned_lines_for_purchase(purchase_id)

    def balance_before_purchase(self, purchase_id: int) -> str:
        """The supplier's payable EXCLUDING this bill's own position.

        Reopening a bill shows "Previous Balance" — what was owed before it. The
        supplier's payable already contains this bill's outstanding amount (net of
        any return), so showing the raw payable would count the bill twice the
        moment the screen adds its remaining back on. Never absorbs returned goods
        to make a bill total look right.
        """
        self._authz.require("purchases.view")
        view = self.net_view(purchase_id)
        if view is None or view["purchase"]["party_id"] is None:
            return money_to_db(D(0))
        payable = money(self._balances.payable(view["purchase"]["party_id"]))
        return money_to_db(payable - money(view["net_remaining"]))

    def get(self, purchase_id: int) -> dict | None:
        self._authz.require("purchases.view")
        return self._purchases.get(purchase_id)

    def find_by_reference(self, term: str, *, status: str | None = "POSTED") -> dict | None:
        """Resolve a typed purchase reference to ONE purchase — read-only.

        Same rule as the sales lookup: ``PUR-000002``, ``000002`` and ``2`` all name
        the same document, with a search fallback when the term names exactly one.
        """
        self._authz.require("purchases.view")
        text = (term or "").strip()
        if not text:
            return None
        seq = self._numbering.sequence("PUR") or {}
        refs = candidates(text, seq.get("prefix") or "PUR-", seq.get("padding") or 6)
        found = self._purchases.find_by_document_no(refs, status=status)
        if found is not None:
            return found
        matches = self._ext.list_documents(term=text, status=status)
        if len(matches) == 1:
            return self._purchases.get(matches[0]["id"])
        return None

    def lines(self, purchase_id: int) -> list[dict]:
        self._authz.require("purchases.view")
        return self._purchases.lines_for(purchase_id)

    def payable(self, party_id: int) -> str:
        self._authz.require("purchases.view")
        return self._balances.payable(party_id)

    def returnable_quantities(self, purchase_id: int) -> dict[int, str]:
        out: dict[int, str] = {}
        for ln in self._purchases.lines_for(purchase_id):
            out[ln["id"]] = str(D(ln["quantity"]) - D(self._ext.returned_qty_for_line(ln["id"])))
        return out

    def post_purchase(self, *, currency_code: str, lines: list[PurchaseLine],
                      party_id: int | None = None, warehouse_id: int | None = None,
                      amount_paid=0, exchange_rate=1, supplier_reference: str | None = None,
                      purchase_date: str | None = None, notes: str | None = None) -> PostedDocument:
        self._authz.require("purchases.create")
        self._authz.require("purchases.post")
        prep = self._prepare_purchase(
            currency_code=currency_code, lines=lines, party_id=party_id,
            warehouse_id=warehouse_id, amount_paid=amount_paid, purchase_date=purchase_date)
        date = prep["date"]; currency = prep["currency"]; computed = prep["computed"]
        subtotal = prep["subtotal"]; discount_total = prep["discount_total"]
        grand_total = prep["grand_total"]; paid = prep["paid"]; remaining = prep["remaining"]
        uid = self._session.user_id

        with self._db.transaction():
            document_no = self._numbering.allocate("PUR")
            purchase_id = self._purchases.create_header(
                document_no=document_no, purchase_date=date, currency_id=currency["id"],
                supplier_id=None, warehouse_id=warehouse_id, exchange_rate=exchange_rate,
                subtotal=subtotal, discount_total=discount_total, grand_total=grand_total,
                amount_paid=paid, remaining_amount=remaining, status="POSTED", notes=notes,
                created_by=uid)
            self._ext.set_party(purchase_id, party_id, supplier_reference)
            for idx, (ln, c, wh, stockable) in enumerate(computed, start=1):
                line_id = self._purchases.add_line(
                    purchase_id=purchase_id, line_no=idx, item_id=ln.item_id,
                    unit_id=ln.unit_id, warehouse_id=wh, quantity=c.quantity,
                    unit_price=c.unit_price, discount=c.discount, line_total=c.line_total)
                if stockable:
                    self._inventory.add_movement(
                        item_id=ln.item_id, warehouse_id=wh, movement_type="PURCHASE",
                        quantity=c.quantity, movement_date=date, unit_id=ln.unit_id,
                        reference_type="PURCHASE", reference_id=purchase_id,
                        reference_line_id=line_id, created_by=uid)
            self._post_purchase_ledger(purchase_id, document_no, date, grand_total, paid,
                                       remaining, party_id, currency["id"], uid)
            self._purchases.mark_posted(purchase_id, uid)
            self._audit.record(action="purchases.post", user_id=uid,
                               username=self._session.username, entity_type="purchase",
                               entity_id=purchase_id, document_no=document_no,
                               details=f"total={grand_total} paid={paid} remaining={remaining}")
        _logger.info("Posted purchase %s (total=%s)", document_no, grand_total)
        return PostedDocument(purchase_id, document_no, str(grand_total), str(remaining))

    def _prepare_purchase(self, *, currency_code, lines, party_id, warehouse_id,
                          amount_paid, purchase_date) -> dict:
        """Validate a bill and compute its figures — shared by posting and correction.

        Nothing is written here, so a correction can validate against exactly the
        same rules a fresh bill goes through.
        """
        date = purchase_date or today_iso()
        self._fy.assert_postable(date)
        if not lines:
            raise ValidationError("A purchase needs at least one line.",
                                  user_message="Add at least one item to the purchase.")
        currency = self._currencies.get_by_code(currency_code)
        if currency is None:
            raise ValidationError(f"Unknown currency {currency_code!r}.")
        self._resolve_party(party_id, role="supplier")
        paid = money(parse_money_input(amount_paid, field="amount paid"))
        if paid < 0:
            raise ValidationError("Amount paid cannot be negative.",
                                  user_message="Amount paid cannot be negative.")

        subtotal = D(0); discount_total = D(0); computed = []
        for ln in lines:
            c = compute_line(ln.quantity, ln.unit_price, ln.discount)
            item = self._require_active_item(ln.item_id)
            wh = self._resolve_warehouse(warehouse_id, bool(item["track_inventory"]))
            subtotal += c.gross; discount_total += c.discount
            computed.append((ln, c, wh, bool(item["track_inventory"])))
        grand_total = money(subtotal - discount_total)
        if paid > grand_total:
            raise ValidationError("Amount paid exceeds the total.",
                                  user_message="Amount paid cannot exceed the total.")
        remaining = money(grand_total - paid)
        # Anything left owing has to be owed to SOMEBODY. Without a registered
        # supplier the payable would post with no party, so no supplier ledger
        # could ever show it and the debt would be owed to nobody. This is the
        # mirror of the walk-in-credit rejection on the sales side. A fully paid
        # (cash) purchase from an unregistered supplier stays allowed.
        if remaining > 0 and party_id is None:
            raise ValidationError(
                "A purchase with an unpaid balance needs a registered supplier.",
                user_message="Select a supplier before recording an unpaid amount —"
                             " an unpaid bill has to be owed to someone.")
        return {"date": date, "currency": currency, "computed": computed,
                "subtotal": subtotal, "discount_total": discount_total,
                "grand_total": grand_total, "paid": paid, "remaining": remaining}

    def _post_purchase_ledger(self, purchase_id, doc_no, date, grand_total, paid, remaining,
                              party_id, currency_id, uid):
        entry_no = self._numbering.allocate("JV")
        entry_id = self._financial.create_entry(
            entry_no=entry_no, entry_date=date, source_type="PURCHASE", source_id=purchase_id,
            description=f"Purchase {doc_no}", created_by=uid)
        self._financial.add_line(entry_id=entry_id,
                                 account_id=self._accounts.id_by_code(_ACCT_INVENTORY),
                                 debit=grand_total, currency_id=currency_id,
                                 memo="Inventory received")
        if paid > 0:
            self._financial.add_line(entry_id=entry_id,
                                     account_id=self._accounts.id_by_code(_ACCT_CASH),
                                     credit=paid, currency_id=currency_id, memo="Cash paid")
        if remaining > 0:
            self._financial.add_line(entry_id=entry_id,
                                     account_id=self._accounts.id_by_code(_ACCT_AP),
                                     credit=remaining, party_type="SUPPLIER", party_id=party_id,
                                     currency_id=currency_id, memo="On account")
        assert_journal_balanced(self._financial, entry_id)

    # ---- correct a posted purchase IN PLACE -----------------------------

    def _correction_diff(self, old_lines: list[dict], new_lines: list[PurchaseLine]) -> str:
        """Readable "what changed" summary for the audit record."""
        def _name(item_id: int) -> str:
            item = self._items.get(item_id) or {}
            return item.get("name") or item.get("item_code") or f"item {item_id}"

        old_by_item: dict[int, D] = {}
        for ln in old_lines:
            old_by_item[ln["item_id"]] = old_by_item.get(ln["item_id"], D(0)) + D(ln["quantity"])
        new_by_item: dict[int, D] = {}
        for nl in new_lines:
            new_by_item[nl.item_id] = (new_by_item.get(nl.item_id, D(0))
                                       + D(parse_money_input(nl.quantity, field="quantity")))
        parts: list[str] = []
        for item_id in sorted(set(old_by_item) | set(new_by_item)):
            before = old_by_item.get(item_id, D(0))
            after = new_by_item.get(item_id, D(0))
            if before == after:
                continue
            if before == 0:
                parts.append(f"{_name(item_id)} {after.normalize():f} added")
            elif after == 0:
                parts.append(f"{_name(item_id)} removed")
            else:
                parts.append(f"{_name(item_id)} qty {before.normalize():f}"
                             f" → {after.normalize():f}")
        return "; ".join(parts)

    def _assert_correction_keeps_returns_valid(self, old_lines, new_lines) -> None:
        """Refuse a correction that would contradict an already-posted return.

        Returned goods are a fact: they physically went back to the supplier. A
        correction may not delete an item that has returns, nor reduce a quantity
        below what went back — either would leave the return referring to something
        that never happened. Mirrors the sales rule.
        """
        returned_by_item: dict[int, D] = {}
        for ln in old_lines:
            back = D(self._ext.returned_qty_for_line(ln["id"]))
            if back > 0:
                returned_by_item[ln["item_id"]] = (
                    returned_by_item.get(ln["item_id"], D(0)) + back)
        if not returned_by_item:
            return
        new_by_item: dict[int, D] = {}
        for pl in new_lines:
            new_by_item[pl.item_id] = (new_by_item.get(pl.item_id, D(0))
                                       + D(parse_money_input(pl.quantity, field="quantity")))
        for item_id, back in returned_by_item.items():
            name = (self._items.get(item_id) or {}).get("name") or f"item {item_id}"
            kept = new_by_item.get(item_id)
            if kept is None:
                raise ValidationError(
                    f"Item {item_id} has {back} returned; it cannot be removed.",
                    user_message=f"{name} already has {back} returned to the supplier, so"
                                 " it cannot be removed from this bill. Reverse the"
                                 " return first.")
            if kept < back:
                raise ValidationError(
                    f"Item {item_id}: corrected qty {kept} is below {back} already returned.",
                    user_message=f"{name} already has {back} returned, so the quantity"
                                 f" cannot be corrected below {back}.")

    def correct_purchase(self, *, purchase_id: int, currency_code: str,
                         lines: list[PurchaseLine], party_id: int | None = None,
                         warehouse_id: int | None = None, amount_paid=0, exchange_rate=1,
                         purchase_date: str | None = None, notes: str | None = None,
                         supplier_reference: str | None = None,
                         reason: str | None = None) -> PostedDocument:
        """Correct a POSTED purchase **in place** — same record, same document number.

        Exactly the contract locked on the sales side: amending a bill is not a new
        purchase, so no second document is created and no number is consumed. In one
        atomic transaction the correction takes back the stock the old lines brought
        in, replaces the lines and receives the corrected stock, updates the header
        in place, posts a **difference-only** journal (inventory, cash and payable
        each move by new − old) and writes an audit record.

        A bill that already has a return CAN be corrected: surviving lines keep their
        ids so the return still points at them. Only two things are refused —
        dropping an item that has already been returned, and correcting a quantity
        below what already went back.
        """
        self._authz.require("purchases.correct")
        original = self._purchases.get(purchase_id)
        if original is None or original["status"] != "POSTED":
            raise ValidationError("Only a posted purchase can be corrected.",
                                  user_message="This bill cannot be corrected.")
        old_lines = self._purchases.lines_for(purchase_id)
        self._assert_correction_keeps_returns_valid(old_lines, lines)
        prep = self._prepare_purchase(
            currency_code=currency_code, lines=lines, party_id=party_id,
            warehouse_id=warehouse_id, amount_paid=amount_paid,
            purchase_date=purchase_date)
        uid = self._session.user_id
        document_no = original["document_no"]
        change_summary = self._correction_diff(old_lines, lines)
        date = prep["date"]

        with self._db.transaction():
            # 1. Take back the stock the current lines brought in. A compensating
            #    ADJUSTMENT_OUT keeps the movement history truthful rather than
            #    deleting movements that really happened.
            for ln in old_lines:
                if ln["warehouse_id"] is not None:
                    self._inventory.add_movement(
                        item_id=ln["item_id"], warehouse_id=ln["warehouse_id"],
                        movement_type="ADJUSTMENT_OUT", quantity=-D(ln["quantity"]),
                        movement_date=date, unit_id=ln["unit_id"],
                        reference_type="PURCHASE_CORRECTION", reference_id=purchase_id,
                        reference_line_id=ln["id"], created_by=uid)

            # 2. Rewrite the lines and receive the corrected stock. A line whose
            #    item survives KEEPS its id so a purchase return pointing at it
            #    stays valid; only lines whose item is gone are deleted.
            reusable: dict[int, list[int]] = {}
            for ln in old_lines:
                reusable.setdefault(ln["item_id"], []).append(ln["id"])
            consumed: set[int] = set()
            for idx, (ln, c, wh, stockable) in enumerate(prep["computed"], start=1):
                pool = reusable.get(ln.item_id) or []
                line_id = pool.pop(0) if pool else None
                if line_id is not None:
                    consumed.add(line_id)
                    self._purchases.update_line(
                        line_id, line_no=idx, item_id=ln.item_id, unit_id=ln.unit_id,
                        warehouse_id=wh, quantity=c.quantity, unit_price=c.unit_price,
                        discount=c.discount, line_total=c.line_total)
                else:
                    line_id = self._purchases.add_line(
                        purchase_id=purchase_id, line_no=idx, item_id=ln.item_id,
                        unit_id=ln.unit_id, warehouse_id=wh, quantity=c.quantity,
                        unit_price=c.unit_price, discount=c.discount,
                        line_total=c.line_total)
                if stockable:
                    self._inventory.add_movement(
                        item_id=ln.item_id, warehouse_id=wh, movement_type="PURCHASE",
                        quantity=c.quantity, movement_date=date, unit_id=ln.unit_id,
                        reference_type="PURCHASE", reference_id=purchase_id,
                        reference_line_id=line_id, created_by=uid)
            for ln in old_lines:
                if ln["id"] not in consumed:
                    self._purchases.delete_line(ln["id"])

            # 3. Header in place — document_no, status and posting stamps untouched.
            self._purchases.update_header(
                purchase_id, purchase_date=date, currency_id=prep["currency"]["id"],
                warehouse_id=warehouse_id, exchange_rate=exchange_rate,
                subtotal=prep["subtotal"], discount_total=prep["discount_total"],
                grand_total=prep["grand_total"], amount_paid=prep["paid"],
                remaining_amount=prep["remaining"], notes=notes)
            self._ext.set_party(purchase_id, party_id, supplier_reference)

            # 4. Difference-only journal so the accounts reach the corrected figures.
            self._post_correction_ledger(original, prep, date, party_id, uid)
            self._audit.record(
                action="purchases.correct", user_id=uid, username=self._session.username,
                entity_type="purchase", entity_id=purchase_id, document_no=document_no,
                details=(f"corrected {document_no} in place "
                         f"old_total={original['grand_total']} new_total={prep['grand_total']}; "
                         f"changes: {change_summary or 'none'}"
                         + (f"; reason={reason}" if reason else "")))
        _logger.info("Corrected purchase %s in place (total=%s)", document_no,
                     prep["grand_total"])
        return PostedDocument(purchase_id, document_no, str(prep["grand_total"]),
                              str(prep["remaining"]))

    def _post_correction_ledger(self, original, prep, date, party_id, uid) -> None:
        """Post the new − old delta for inventory, cash and payable.

        Only the movement is journalled, never the whole bill again, so a corrected
        purchase is never counted twice. A correction that changes nothing
        financial posts no journal at all.
        """
        d_inventory = money(D(prep["grand_total"]) - D(original["grand_total"]))
        d_cash = money(D(prep["paid"]) - D(original["amount_paid"]))
        d_ap = money(D(prep["remaining"]) - D(original["remaining_amount"]))
        if d_inventory == 0 and d_cash == 0 and d_ap == 0:
            return
        currency_id = prep["currency"]["id"]
        entry_no = self._numbering.allocate("JV")
        entry_id = self._financial.create_entry(
            entry_no=entry_no, entry_date=date, source_type="PURCHASE_CORRECTION",
            source_id=original["id"],
            description=f"Correction {original['document_no']}", created_by=uid)

        def _line(account_code, amount, **kw):
            """Post |amount| on the natural side, flipping when the delta is negative."""
            if amount == 0:
                return
            account_id = self._accounts.id_by_code(account_code)
            natural_debit = kw.pop("natural_debit")
            debit_side = natural_debit if amount > 0 else not natural_debit
            value = abs(amount)
            if debit_side:
                self._financial.add_line(entry_id=entry_id, account_id=account_id,
                                         debit=value, currency_id=currency_id, **kw)
            else:
                self._financial.add_line(entry_id=entry_id, account_id=account_id,
                                         credit=value, currency_id=currency_id, **kw)

        # Inventory is naturally debited; cash and payable are naturally credited.
        _line(_ACCT_INVENTORY, d_inventory, natural_debit=True,
              memo="Correction: inventory change")
        _line(_ACCT_CASH, d_cash, natural_debit=False, memo="Correction: cash change")
        _line(_ACCT_AP, d_ap, natural_debit=False, party_type="SUPPLIER",
              party_id=party_id if party_id is not None else original["party_id"],
              memo="Correction: payable change")
        assert_journal_balanced(self._financial, entry_id)

    # ---- void a posted purchase -----------------------------------------

    def void_purchase(self, *, purchase_id: int, reason: str | None = None,
                      void_date: str | None = None) -> None:
        """Reverse a posted purchase completely, keeping the document as VOID.

        Mirrors ``void_sale``: stock, ledger and payable are reversed, the document
        and its number stay, and a bill that already has a return is refused —
        reverse the return first, or the return would reference a voided bill.
        """
        self._authz.require("purchases.void")
        purchase = self._purchases.get(purchase_id)
        if purchase is None:
            raise ValidationError("Unknown purchase.",
                                  user_message="This bill was not found.")
        if purchase["status"] != "POSTED":
            raise ValidationError("Only a posted purchase can be voided.",
                                  user_message="This bill is not posted, so it cannot"
                                               " be voided.")
        if self._returns.list_for_purchase(purchase_id):
            raise ValidationError("Purchase has returns; void is blocked.",
                                  user_message="This bill already has a return. Reverse"
                                               " the return before voiding the bill.")
        date = void_date or today_iso()
        self._fy.assert_postable(date)
        uid = self._session.user_id
        with self._db.transaction():
            for ln in self._purchases.lines_for(purchase_id):
                if ln["warehouse_id"] is not None:
                    self._inventory.add_movement(
                        item_id=ln["item_id"], warehouse_id=ln["warehouse_id"],
                        movement_type="ADJUSTMENT_OUT", quantity=-D(ln["quantity"]),
                        movement_date=date, unit_id=ln["unit_id"],
                        reference_type="PURCHASE_VOID", reference_id=purchase_id,
                        reference_line_id=ln["id"], created_by=uid)
            self._post_void_ledger(purchase, date, uid)
            self._purchases.mark_void(purchase_id, uid, reason)
            self._audit.record(
                action="purchases.void", user_id=uid, username=self._session.username,
                entity_type="purchase", entity_id=purchase_id,
                document_no=purchase["document_no"],
                details=f"voided total={purchase['grand_total']}"
                        + (f"; reason={reason}" if reason else ""))
        _logger.info("Voided purchase %s", purchase["document_no"])

    def _post_void_ledger(self, purchase, date, uid) -> None:
        """Exact mirror of the purchase journal, so every account nets to zero."""
        grand = money(purchase["grand_total"]); paid = money(purchase["amount_paid"])
        remaining = money(purchase["remaining_amount"])
        entry_no = self._numbering.allocate("JV")
        entry_id = self._financial.create_entry(
            entry_no=entry_no, entry_date=date, source_type="PURCHASE_VOID",
            source_id=purchase["id"], description=f"Void purchase {purchase['document_no']}",
            created_by=uid)
        self._financial.add_line(entry_id=entry_id,
                                 account_id=self._accounts.id_by_code(_ACCT_INVENTORY),
                                 credit=grand, currency_id=purchase["currency_id"],
                                 memo="Void: reverse inventory")
        if paid > 0:
            self._financial.add_line(entry_id=entry_id,
                                     account_id=self._accounts.id_by_code(_ACCT_CASH),
                                     debit=paid, currency_id=purchase["currency_id"],
                                     memo="Void: reverse cash")
        if remaining > 0:
            self._financial.add_line(entry_id=entry_id,
                                     account_id=self._accounts.id_by_code(_ACCT_AP),
                                     debit=remaining, party_type="SUPPLIER",
                                     party_id=purchase["party_id"],
                                     currency_id=purchase["currency_id"],
                                     memo="Void: reverse payable")
        assert_journal_balanced(self._financial, entry_id)

    # ---- post a purchase return -----------------------------------------

    def _return_note(self, computed) -> str:
        """Readable summary of a return — 'Rice — Qty 4 returned.'

        Used when the caller supplies no note of its own, so every purchase return
        carries a human-readable record of what went back.
        """
        parts = []
        for src, qty, *_rest in computed:
            item = self._items.get(src["item_id"]) or {}
            name = item.get("name") or item.get("item_code") or f"item {src['item_id']}"
            parts.append(f"{name} — Qty {qty.normalize():f} returned")
        return "; ".join(parts) + ("." if parts else "")

    def post_return(self, *, purchase_id: int, lines: list[PurchaseReturnLine],
                    reason: str | None = None, notes: str | None = None,
                    return_date: str | None = None, allow_backorder: bool = False) -> PostedDocument:
        self._authz.require("purchases.return")
        purchase = self._purchases.get(purchase_id)
        if purchase is None or purchase["status"] != "POSTED":
            raise ValidationError("Only a posted purchase can be returned.",
                                  user_message="This purchase cannot be returned.")
        date = return_date or today_iso()
        self._fy.assert_postable(date)
        if not lines:
            raise ValidationError("A return needs at least one line.",
                                  user_message="Select at least one line to return.")

        p_lines = {ln["id"]: ln for ln in self._purchases.lines_for(purchase_id)}
        subtotal = D(0); discount_total = D(0); computed = []
        need: dict[tuple, object] = {}
        for rl in lines:
            src = p_lines.get(rl.purchase_line_id)
            if src is None:
                raise ValidationError("Return line does not belong to this purchase.")
            qty = D(parse_money_input(rl.quantity, field="return quantity"))
            if qty <= 0:
                raise ValidationError("Return quantity must be positive.",
                                      user_message="Return quantity must be above zero.")
            already = D(self._ext.returned_qty_for_line(src["id"]))
            bought = D(src["quantity"])
            if already + qty > bought:
                raise ValidationError(
                    f"Over-return: line {src['id']} bought {bought}, already {already},"
                    f" requested {qty}.",
                    user_message="You cannot return more than was purchased.")
            unit_price = money(src["unit_price"])
            per_unit_disc = (money(src["discount"]) / D(src["quantity"])) if D(src["quantity"]) else D(0)
            line_total = money(qty * unit_price - qty * per_unit_disc)
            subtotal += money(qty * unit_price); discount_total += money(qty * per_unit_disc)
            if src["warehouse_id"] is not None:
                need[(src["item_id"], src["warehouse_id"])] = \
                    D(need.get((src["item_id"], src["warehouse_id"]), D(0))) + qty
            computed.append((src, qty, unit_price, money(qty * per_unit_disc), line_total))

        # A purchase return removes stock — must have enough on hand.
        if not allow_backorder:
            for (item_id, wh), qty in need.items():
                on_hand = D(self._inventory.stock_on_hand(item_id, wh))
                if qty > on_hand:
                    raise InsufficientStockError(
                        f"Return needs {qty}, have {on_hand}.",
                        user_message="Not enough stock to return to the supplier.")

        grand_total = money(subtotal - discount_total)
        uid = self._session.user_id
        party_id = purchase["party_id"]
        # Always leave a readable record of what went back. The caller may supply
        # its own note (the UI passes a localized one); otherwise summarise the
        # returned lines — "Rice — Qty 4 returned."
        notes = (notes or "").strip() or self._return_note(computed)
        with self._db.transaction():
            document_no = self._numbering.allocate("PRET")
            return_id = self._returns.create_header(
                document_no=document_no, return_date=date, purchase_id=purchase_id,
                currency_id=purchase["currency_id"], party_id=party_id,
                warehouse_id=purchase["warehouse_id"], exchange_rate=purchase["exchange_rate"],
                subtotal=subtotal, discount_total=discount_total, grand_total=grand_total,
                reason=reason, notes=notes, created_by=uid)
            for idx, (src, qty, unit_price, disc, line_total) in enumerate(computed, start=1):
                self._returns.add_line(
                    return_id=return_id, line_no=idx, purchase_line_id=src["id"],
                    item_id=src["item_id"], unit_id=src["unit_id"],
                    warehouse_id=src["warehouse_id"], quantity=qty, unit_price=unit_price,
                    discount=disc, line_total=line_total)
                if src["warehouse_id"] is not None:
                    self._inventory.add_movement(
                        item_id=src["item_id"], warehouse_id=src["warehouse_id"],
                        movement_type="PURCHASE_RETURN", quantity=-qty, movement_date=date,
                        unit_id=src["unit_id"], reference_type="PURCHASE_RETURN",
                        reference_id=return_id, created_by=uid)
            self._post_return_ledger(return_id, document_no, date, grand_total, party_id,
                                     purchase["currency_id"], uid)
            self._audit.record(action="purchases.return", user_id=uid,
                               username=self._session.username, entity_type="purchase_return",
                               entity_id=return_id, document_no=document_no,
                               details=f"purchase={purchase['document_no']} total={grand_total}")
        _logger.info("Posted purchase return %s (total=%s)", document_no, grand_total)
        return PostedDocument(return_id, document_no, str(grand_total), "0.00")

    def _post_return_ledger(self, return_id, doc_no, date, total, party_id, currency_id, uid):
        entry_no = self._numbering.allocate("JV")
        entry_id = self._financial.create_entry(
            entry_no=entry_no, entry_date=date, source_type="PURCHASE_RETURN",
            source_id=return_id, description=f"Purchase return {doc_no}", created_by=uid)
        # Reduce payable (Dr A/P party); reduce inventory value (Cr Inventory).
        self._financial.add_line(entry_id=entry_id,
                                 account_id=self._accounts.id_by_code(_ACCT_AP),
                                 debit=total, party_type="SUPPLIER", party_id=party_id,
                                 currency_id=currency_id, memo="Return debit")
        self._financial.add_line(entry_id=entry_id,
                                 account_id=self._accounts.id_by_code(_ACCT_INVENTORY),
                                 credit=total, currency_id=currency_id, memo="Inventory returned")
        assert_journal_balanced(self._financial, entry_id)

    def _resolve_party(self, party_id, *, role):
        if party_id is None:
            return None
        party = self._parties.get(party_id)
        if party is None or not party["is_active"]:
            raise ValidationError("Unknown or inactive party.",
                                  user_message="The selected party is not available.")
        if role == "supplier" and not party["is_supplier"]:
            raise ValidationError("Party is not a supplier.",
                                  user_message="That party is not a supplier.")
        return party

    def _require_active_item(self, item_id):
        item = self._items.get(item_id)
        if item is None or not item["is_active"]:
            raise ValidationError("Unknown or inactive item.",
                                  user_message="One of the selected items is not available.")
        return item

    def _resolve_warehouse(self, warehouse_id, stockable):
        if stockable and warehouse_id is None:
            raise ValidationError("A warehouse is required for stock-tracked items.",
                                  user_message="Select a warehouse for stocked items.")
        if warehouse_id is not None:
            wh = self._warehouses.get(warehouse_id)
            if wh is None or not wh["is_active"]:
                raise ValidationError("Unknown or inactive warehouse.",
                                      user_message="The selected warehouse is not available.")
        return warehouse_id
