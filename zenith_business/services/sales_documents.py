"""Stage 04 Sales document service — real atomic sales + sales returns.

Composes LOCKED repositories/primitives (SalesRepository, InventoryRepository,
FinancialRepository, DocumentNumberService, AuditRepository) into ONE atomic
transaction and adds Stage 04 behaviour: financial-year enforcement, the unified
``parties`` model (via the additive ``sales.party_id``), party receivable through
the locked ledger, and controlled sales returns with over-return protection.

A posted sale writes: header + lines + signed inventory-out + balanced double-entry
ledger + party receivable + audit + document number — all commit together or all
roll back. Money/quantities are Decimal throughout (never float).
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
    SalesRepository,
)
from zenith_business.repositories.documents_s4 import (
    PartyBalanceRepository,
    SalesExtRepository,
    SalesReturnRepository,
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
from zenith_business.services.session import SessionContext

_logger = get_logger("services.sales_doc")

_ACCT_CASH = "1000"
_ACCT_AR = "1100"
_ACCT_SALES = "4000"


@dataclass
class SaleLine:
    item_id: int
    unit_id: int
    quantity: object
    unit_price: object
    discount: object = 0


@dataclass
class ReturnLine:
    sale_line_id: int
    quantity: object


@dataclass
class PostedDocument:
    id: int
    document_no: str
    grand_total: str
    remaining: str


class SalesDocumentService:
    def __init__(self, db: Database, sales: SalesRepository, sales_ext: SalesExtRepository,
                 returns: SalesReturnRepository, inventory: InventoryRepository,
                 financial: FinancialRepository, accounts: AccountRepository,
                 currencies: CurrencyRepository, items: ItemRepository,
                 warehouses: WarehouseRepository, parties: PartyRepository,
                 balances: PartyBalanceRepository, numbering: DocumentNumberService,
                 audit: AuditRepository, session: SessionContext,
                 authz: AuthorizationService, financial_years: FinancialYearService) -> None:
        self._db = db
        self._sales = sales
        self._ext = sales_ext
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

    # ---- reads ----------------------------------------------------------

    def list(self, *, term=None, status=None, date_from=None, date_to=None,
             limit=200) -> list[dict]:
        """Sales list rows, each carrying its CURRENT position after returns.

        ``grand_total`` stays the amount originally invoiced; ``returned_total``,
        ``net_total`` and ``net_remaining`` are derived from the posted return
        documents, so the list can show what the invoice is worth now without
        storing a second copy of the figure. Money is summed with ``Decimal``,
        never a SQL float.

        ``net_remaining`` = net total − paid: what the customer still owes on this
        invoice after the return, matching the credit the return posted to their
        receivable. It goes negative when a paid invoice is returned against — a
        refund owed back to the customer — which is the financially correct sign
        and agrees with the customer's ledger balance.
        """
        self._authz.require("sales.view")
        rows = self._ext.list_documents(term=term, status=status, date_from=date_from,
                                        date_to=date_to, limit=limit)
        returned: dict[int, D] = {}
        for r in self._returns.posted_totals_for_sales([row["id"] for row in rows]):
            returned[r["sale_id"]] = returned.get(r["sale_id"], D(0)) + D(r["grand_total"])
        for row in rows:
            back = returned.get(row["id"], D(0))
            net = money(row["grand_total"]) - back
            row["returned_total"] = money_to_db(back)
            row["net_total"] = money_to_db(net)
            row["net_remaining"] = money_to_db(net - money(row["amount_paid"]))
        return rows

    def get(self, sale_id: int) -> dict | None:
        self._authz.require("sales.view")
        return self._sales.get(sale_id)

    def find_by_reference(self, term: str, *, status: str | None = "POSTED") -> dict | None:
        """Resolve a typed invoice reference to ONE sale — read-only.

        Accepts the number in any form an operator would type: ``SALE-000002``,
        ``000002`` or just ``2`` all resolve to the same invoice, because the
        *number* is resolved against the live numbering scheme rather than matched
        as a substring (``LIKE '%2%'`` would also hit SALE-000012 and SALE-000020,
        so a bare number could never identify one document). Falls back to a
        search — customer name or a partial number — when that names exactly one
        document. Returns ``None`` when nothing matches. Never writes.
        """
        self._authz.require("sales.view")
        text = (term or "").strip()
        if not text:
            return None
        seq = self._numbering.sequence("SALE") or {}
        refs = candidates(text, seq.get("prefix") or "SALE-", seq.get("padding") or 6)
        found = self._sales.find_by_document_no(refs, status=status)
        if found is not None:
            return found
        matches = self._ext.list_documents(term=text, status=status)
        if len(matches) == 1:
            return self._sales.get(matches[0]["id"])
        return None

    def lines(self, sale_id: int) -> list[dict]:
        self._authz.require("sales.view")
        return self._sales.lines_for(sale_id)

    def receivable(self, party_id: int) -> str:
        self._authz.require("sales.view")
        return self._balances.receivable(party_id)

    def returnable_quantities(self, sale_id: int) -> dict[int, str]:
        """sale_line_id -> quantity still returnable (sold − already returned)."""
        out: dict[int, str] = {}
        for ln in self._sales.lines_for(sale_id):
            sold = D(ln["quantity"])
            returned = D(self._ext.returned_qty_for_line(ln["id"]))
            out[ln["id"]] = str(sold - returned)
        return out

    def net_view(self, sale_id: int) -> dict | None:
        """The invoice's CURRENT position after any posted returns.

        The sale itself is never rewritten by a return — the sold quantities and
        the original total stay on the document as the historical record, and the
        return documents stay intact for audit. What changed is derived here, so
        there is exactly one place that answers "what does this invoice look like
        now": the invoice screen, the printed copy and the Sales List all read it.

        Each line carries ``sold`` / ``returned`` / ``net_quantity`` with the
        recomputed ``net_line_total``; ``active_lines`` drops any line whose whole
        quantity came back. Totals give ``gross_total`` (as invoiced),
        ``returned_total`` and ``net_total`` = gross − returned.
        """
        self._authz.require("sales.view")
        sale = self._sales.get(sale_id)
        if sale is None:
            return None
        lines: list[dict] = []
        returned_total = D(0)
        for ln in self._sales.lines_for(sale_id):
            sold = D(ln["quantity"])
            returned = D(self._ext.returned_qty_for_line(ln["id"]))
            net_qty = sold - returned
            # Discount is spread per unit so a partial return keeps the same
            # effective price the customer was charged.
            per_unit_disc = (money(ln["discount"]) / sold) if sold else D(0)
            net_line_total = money(net_qty * money(ln["unit_price"]) - net_qty * per_unit_disc)
            returned_total += money(returned * money(ln["unit_price"])
                                    - returned * per_unit_disc)
            lines.append({**ln, "sold": qty_to_db(sold), "returned": qty_to_db(returned),
                          "net_quantity": qty_to_db(net_qty),
                          "net_discount": money_to_db(money(net_qty * per_unit_disc)),
                          "net_line_total": money_to_db(net_line_total),
                          "fully_returned": net_qty <= 0})
        gross = money(sale["grand_total"])
        returned_total = money(returned_total)
        return {
            "sale": sale, "lines": lines,
            "active_lines": [ln for ln in lines if not ln["fully_returned"]],
            "gross_total": money_to_db(gross),
            "returned_total": money_to_db(returned_total),
            "net_total": money_to_db(gross - returned_total),
            "net_remaining": money_to_db(gross - returned_total
                                         - money(sale["amount_paid"])),
            "has_returns": returned_total > 0,
        }

    def returned_items(self, sale_id: int) -> list[dict]:
        """Read-only history of what came back off this invoice.

        One row per returned line — item, quantity, amount and the return document
        it belongs to — so the invoice screen can show the returned goods SEPARATELY
        from the lines the customer still owes for, without either view rewriting
        the other. Money is summed by the caller with ``Decimal``.
        """
        self._authz.require("sales.view")
        return self._returns.returned_lines_for_sale(sale_id)

    def balance_before_sale(self, sale_id: int) -> str:
        """The customer's account balance EXCLUDING this invoice's own position.

        Reopening an invoice shows "Previous Balance" — what the customer owed
        before it. Their receivable already contains this invoice's outstanding
        amount (net of any return), so showing the raw receivable would count this
        invoice twice the moment the screen adds the invoice's remaining back on.
        This is derived from the invoice's own net position; it never absorbs
        returned goods to make an invoice total look right.
        """
        self._authz.require("sales.view")
        view = self.net_view(sale_id)
        if view is None or view["sale"]["party_id"] is None:
            return money_to_db(D(0))
        receivable = money(self._balances.receivable(view["sale"]["party_id"]))
        return money_to_db(receivable - money(view["net_remaining"]))

    # ---- post a sale ----------------------------------------------------

    def post_sale(self, *, currency_code: str, lines: list[SaleLine],
                  party_id: int | None = None, warehouse_id: int | None = None,
                  amount_paid=0, exchange_rate=1, sale_date: str | None = None,
                  notes: str | None = None, allow_backorder: bool = False,
                  walkin_name: str | None = None, walkin_phone: str | None = None,
                  walkin_address: str | None = None) -> PostedDocument:
        self._authz.require("sales.create")
        self._authz.require("sales.post")
        prep = self._prepare_sale(
            currency_code=currency_code, lines=lines, party_id=party_id,
            warehouse_id=warehouse_id, amount_paid=amount_paid, sale_date=sale_date,
            allow_backorder=allow_backorder, walkin_name=walkin_name,
            walkin_phone=walkin_phone, walkin_address=walkin_address)
        uid = self._session.user_id
        with self._db.transaction():
            sale_id, document_no = self._do_post_sale(
                prep, party_id=party_id, warehouse_id=warehouse_id,
                exchange_rate=exchange_rate, notes=notes, uid=uid)
        _logger.info("Posted sale %s (total=%s)", document_no, prep["grand_total"])
        return PostedDocument(sale_id, document_no, str(prep["grand_total"]),
                              str(prep["remaining"]))

    # ---- shared sale preparation + transaction body ---------------------

    def _prepare_sale(self, *, currency_code, lines, party_id, warehouse_id, amount_paid,
                      sale_date, allow_backorder, walkin_name, walkin_phone, walkin_address,
                      released=None):
        """Validate + compute a sale (no writes). Shared by post and correct.

        ``released`` maps ``(item_id, warehouse_id)`` to a quantity that this same
        invoice is currently holding and will give back as part of the operation.
        A correction adds it to the available stock, so amending an invoice that
        already consumed the stock it is re-using is not rejected as an oversell.
        """
        date = sale_date or today_iso()
        self._fy.assert_postable(date)  # financial-year enforcement (§7)
        if not lines:
            raise ValidationError("A sale needs at least one line.",
                                  user_message="Add at least one item to the invoice.")
        currency = self._currencies.get_by_code(currency_code)
        if currency is None:
            raise ValidationError(f"Unknown currency {currency_code!r}.")
        self._resolve_party(party_id, role="customer")
        wk_name = (walkin_name or "").strip() or None
        wk_phone = (walkin_phone or "").strip() or None
        wk_address = (walkin_address or "").strip() or None

        paid = money(parse_money_input(amount_paid, field="amount paid"))
        if paid < 0:
            raise ValidationError("Amount paid cannot be negative.",
                                  user_message="Amount paid cannot be negative.")

        subtotal = D(0); discount_total = D(0)
        computed = []; needed: dict[tuple, object] = {}
        for ln in lines:
            c = compute_line(ln.quantity, ln.unit_price, ln.discount)
            item = self._require_active_item(ln.item_id)
            wh = self._resolve_warehouse(warehouse_id, bool(item["track_inventory"]))
            if item["track_inventory"]:
                key = (ln.item_id, wh)
                needed[key] = D(needed.get(key, D(0))) + c.quantity
            subtotal += c.gross; discount_total += c.discount
            computed.append((ln, c, wh, bool(item["track_inventory"])))

        if not allow_backorder:
            back = released or {}
            for (item_id, wh), qty in needed.items():
                on_hand = D(self._inventory.stock_on_hand(item_id, wh)) + D(back.get((item_id, wh), 0))
                if qty > on_hand:
                    raise InsufficientStockError(
                        f"Item {item_id} @ wh {wh}: need {qty}, have {on_hand}.",
                        user_message="Not enough stock for one or more items.")

        grand_total = money(subtotal - discount_total)
        if paid > grand_total:
            raise ValidationError("Amount paid exceeds the total (overpayment not supported).",
                                  user_message="Amount received cannot exceed the total.")
        remaining = money(grand_total - paid)
        # Never create an anonymous receivable (defect #2): credit requires a party.
        if party_id is None and remaining > 0:
            raise ValidationError(
                "Walk-in/cash sales cannot be left on credit (no party account).",
                user_message="A walk-in sale must be paid in full. For credit, select a"
                             " registered customer.")
        return {"date": date, "currency": currency, "computed": computed,
                "subtotal": subtotal, "discount_total": discount_total,
                "grand_total": grand_total, "paid": paid, "remaining": remaining,
                "wk": (wk_name, wk_phone, wk_address)}

    def _do_post_sale(self, prep, *, party_id, warehouse_id, exchange_rate, notes, uid,
                      corrected_from_id=None):
        """Write header + lines + inventory-out + balanced ledger + audit. Must run
        inside an open transaction (composed atomically by post and correct)."""
        date = prep["date"]; currency_id = prep["currency"]["id"]
        grand_total = prep["grand_total"]; paid = prep["paid"]; remaining = prep["remaining"]
        document_no = self._numbering.allocate("SALE")
        sale_id = self._sales.create_header(
            document_no=document_no, sale_date=date, currency_id=currency_id,
            customer_id=None, warehouse_id=warehouse_id, salesperson_id=uid,
            exchange_rate=exchange_rate, subtotal=prep["subtotal"],
            discount_total=prep["discount_total"], grand_total=grand_total, amount_paid=paid,
            remaining_amount=remaining, status="POSTED", notes=notes, created_by=uid)
        self._ext.set_party(sale_id, party_id)
        wk_name, wk_phone, wk_address = prep["wk"]
        if party_id is None and (wk_name or wk_phone or wk_address):
            self._ext.set_walkin(sale_id, wk_name, wk_phone, wk_address)
        if corrected_from_id is not None:
            self._ext.set_corrected_from(sale_id, corrected_from_id)
        for idx, (ln, c, wh, stockable) in enumerate(prep["computed"], start=1):
            line_id = self._sales.add_line(
                sale_id=sale_id, line_no=idx, item_id=ln.item_id, unit_id=ln.unit_id,
                warehouse_id=wh, quantity=c.quantity, unit_price=c.unit_price,
                discount=c.discount, line_total=c.line_total)
            if stockable:
                self._inventory.add_movement(
                    item_id=ln.item_id, warehouse_id=wh, movement_type="SALE",
                    quantity=-c.quantity, movement_date=date, unit_id=ln.unit_id,
                    reference_type="SALE", reference_id=sale_id,
                    reference_line_id=line_id, created_by=uid)
        self._post_sale_ledger(sale_id, document_no, date, grand_total, paid, remaining,
                               party_id, currency_id, uid)
        self._sales.mark_posted(sale_id, uid)
        self._audit.record(action="sales.post", user_id=uid, username=self._session.username,
                           entity_type="sale", entity_id=sale_id, document_no=document_no,
                           details=f"total={grand_total} paid={paid} remaining={remaining}")
        return sale_id, document_no

    def _post_sale_ledger(self, sale_id, doc_no, date, grand_total, paid, remaining,
                          party_id, currency_id, uid) -> None:
        entry_no = self._numbering.allocate("JV")
        entry_id = self._financial.create_entry(
            entry_no=entry_no, entry_date=date, source_type="SALE", source_id=sale_id,
            description=f"Sale {doc_no}", created_by=uid)
        if paid > 0:
            self._financial.add_line(entry_id=entry_id,
                                     account_id=self._accounts.id_by_code(_ACCT_CASH),
                                     debit=paid, currency_id=currency_id, memo="Cash received")
        if remaining > 0:
            self._financial.add_line(entry_id=entry_id,
                                     account_id=self._accounts.id_by_code(_ACCT_AR),
                                     debit=remaining, party_type="CUSTOMER", party_id=party_id,
                                     currency_id=currency_id, memo="On account")
        self._financial.add_line(entry_id=entry_id,
                                 account_id=self._accounts.id_by_code(_ACCT_SALES),
                                 credit=grand_total, currency_id=currency_id, memo="Sales revenue")
        assert_journal_balanced(self._financial, entry_id)

    # ---- void a posted sale (safe reversal) -----------------------------

    def void_sale(self, *, sale_id: int, reason: str | None = None,
                  void_date: str | None = None) -> PostedDocument:
        """Reverse a whole posted sale without rewriting history (defect #3).

        Adds compensating records — stock back in (ADJUSTMENT_IN), a reversing
        journal that nets the original entry to zero, and a VOID status stamp with
        audit — so inventory, the customer balance and the accounts all return to
        their pre-sale state while the original document and journal remain intact.
        """
        self._authz.require("sales.void")
        sale = self._sales.get(sale_id)
        if sale is None or sale["status"] != "POSTED":
            raise ValidationError("Only a posted sale can be voided.",
                                  user_message="This sale cannot be voided.")
        # If the sale already has returns, reversing it as well would double-count;
        # the return mechanism is the correct correction in that case.
        if self._returns.list_for_sale(sale_id):
            raise ValidationError(
                "Sale has returns; cannot void.",
                user_message="This sale already has returns. Reverse those instead of voiding.")
        date = void_date or today_iso()
        self._fy.assert_postable(date)
        uid = self._session.user_id

        with self._db.transaction():
            self._do_void_sale(sale, date, uid, reason=reason, action="sales.void")
        _logger.info("Voided sale %s", sale["document_no"])
        return PostedDocument(sale_id, sale["document_no"], str(sale["grand_total"]), "0.00")

    def _do_void_sale(self, sale, date, uid, *, reason, action="sales.void") -> None:
        """Reverse a posted sale's stock + ledger and stamp VOID. Runs inside an
        open transaction (composed atomically by void and correct)."""
        for ln in self._sales.lines_for(sale["id"]):
            if ln["warehouse_id"] is not None:
                self._inventory.add_movement(
                    item_id=ln["item_id"], warehouse_id=ln["warehouse_id"],
                    movement_type="ADJUSTMENT_IN", quantity=D(ln["quantity"]),
                    movement_date=date, unit_id=ln["unit_id"],
                    reference_type="SALE_VOID", reference_id=sale["id"],
                    reference_line_id=ln["id"], created_by=uid)
        self._post_void_ledger(sale, date, uid)
        self._sales.mark_void(sale["id"], uid, reason)
        self._audit.record(action=action, user_id=uid, username=self._session.username,
                           entity_type="sale", entity_id=sale["id"],
                           document_no=sale["document_no"],
                           details=f"void total={sale['grand_total']} reason={reason or ''}")

    # ---- correct a posted sale (in-place amendment) ---------------------

    def _correction_diff(self, old_lines: list[dict], new_lines: list[SaleLine]) -> str:
        """Human-readable summary of what a correction changed, per item.

        Aggregates by item so the audit note reads like 'Rice qty 5 → 3;
        Sugar 2 removed; Oil 4 added'. Pure text for the audit log — it does not
        affect any posting.
        """
        def _name(item_id: int) -> str:
            it = self._items.get(item_id)
            return (it or {}).get("name") or (it or {}).get("item_code") or f"item {item_id}"

        old_q: dict[int, D] = {}
        for ln in old_lines:
            old_q[ln["item_id"]] = old_q.get(ln["item_id"], D(0)) + D(ln["quantity"])
        new_q: dict[int, D] = {}
        for sl in new_lines:
            new_q[sl.item_id] = new_q.get(sl.item_id, D(0)) + D(sl.quantity)

        parts: list[str] = []
        for item_id in sorted(set(old_q) | set(new_q)):
            o, n = old_q.get(item_id), new_q.get(item_id)
            if o is not None and n is None:
                parts.append(f"{_name(item_id)} {o} removed")
            elif o is None and n is not None:
                parts.append(f"{_name(item_id)} {n} added")
            elif o != n:
                parts.append(f"{_name(item_id)} qty {o} → {n}")
        return "; ".join(parts)

    def _assert_correction_keeps_returns_valid(self, old_lines, new_lines) -> None:
        """Refuse a correction that would contradict an already-posted return.

        Returned goods are a fact: the customer physically brought them back. So a
        correction may not delete an item that has returns, nor reduce a quantity
        below what came back — either would leave the return referring to something
        that never happened.
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
        for sl in new_lines:
            new_by_item[sl.item_id] = (new_by_item.get(sl.item_id, D(0))
                                       + D(parse_money_input(sl.quantity, field="quantity")))
        for item_id, back in returned_by_item.items():
            name = (self._items.get(item_id) or {}).get("name") or f"item {item_id}"
            kept = new_by_item.get(item_id)
            if kept is None:
                raise ValidationError(
                    f"Item {item_id} has {back} returned; it cannot be removed.",
                    user_message=f"{name} already has {back} returned, so it cannot be"
                                 " removed from this invoice. Reverse the return first.")
            if kept < back:
                raise ValidationError(
                    f"Item {item_id}: corrected qty {kept} is below {back} already returned.",
                    user_message=f"{name} already has {back} returned, so the quantity"
                                 f" cannot be corrected below {back}.")

    def correct_sale(self, *, sale_id: int, currency_code: str, lines: list[SaleLine],
                     party_id: int | None = None, warehouse_id: int | None = None,
                     amount_paid=0, exchange_rate=1, sale_date: str | None = None,
                     notes: str | None = None, walkin_name: str | None = None,
                     walkin_phone: str | None = None, walkin_address: str | None = None,
                     reason: str | None = None) -> PostedDocument:
        """Correct a POSTED sale **in place** — same record, same document number.

        Amending an invoice is not a new sale, so no second document is created and
        no number is consumed: the operator sees exactly ONE invoice in the Sales
        List before and after. Inside a single atomic transaction the correction

        * gives back the stock the old lines consumed (a compensating
          ``ADJUSTMENT_IN`` per line, so the movement history stays truthful),
        * replaces the lines with the new set and takes the new stock out,
        * updates the header totals / amount paid / remaining in place,
        * posts a **difference-only** adjusting journal (revenue, cash and
          receivable each move by new − old) so the accounts land on the corrected
          figures without a duplicate sale entry, and
        * writes an audit record describing what changed.

        An invoice that already has a return CAN be corrected: the surviving lines
        keep their ids so the return still points at them. Only two things are
        refused — dropping an item that has already been returned, and correcting a
        quantity below what the customer already gave back.
        """
        self._authz.require("sales.correct")
        original = self._sales.get(sale_id)
        if original is None or original["status"] != "POSTED":
            raise ValidationError("Only a posted sale can be corrected.",
                                  user_message="This invoice cannot be corrected.")
        old_lines = self._sales.lines_for(sale_id)
        self._assert_correction_keeps_returns_valid(old_lines, lines)
        # Stock this invoice currently holds — released by the correction, so
        # re-using it (e.g. trimming 5 Rice to 3) is not rejected as an oversell.
        released: dict[tuple, D] = {}
        for ln in old_lines:
            if ln["warehouse_id"] is not None:
                key = (ln["item_id"], ln["warehouse_id"])
                released[key] = D(released.get(key, D(0))) + D(ln["quantity"])
        prep = self._prepare_sale(
            currency_code=currency_code, lines=lines, party_id=party_id,
            warehouse_id=warehouse_id, amount_paid=amount_paid, sale_date=sale_date,
            allow_backorder=False, walkin_name=walkin_name, walkin_phone=walkin_phone,
            walkin_address=walkin_address, released=released)
        uid = self._session.user_id
        document_no = original["document_no"]
        # Human-readable line diff, built BEFORE the old lines are replaced.
        change_summary = self._correction_diff(old_lines, lines)

        with self._db.transaction():
            self._do_correct_sale(original, old_lines, prep, party_id=party_id,
                                  warehouse_id=warehouse_id, exchange_rate=exchange_rate,
                                  notes=notes, uid=uid)
            self._audit.record(
                action="sales.correct", user_id=uid, username=self._session.username,
                entity_type="sale", entity_id=sale_id, document_no=document_no,
                details=(f"corrected {document_no} in place "
                         f"old_total={original['grand_total']} new_total={prep['grand_total']}; "
                         f"changes: {change_summary or 'none'}"
                         + (f"; reason={reason}" if reason else "")))
        _logger.info("Corrected sale %s in place (total %s → %s)", document_no,
                     original["grand_total"], prep["grand_total"])
        return PostedDocument(sale_id, document_no, str(prep["grand_total"]),
                              str(prep["remaining"]))

    def _do_correct_sale(self, original, old_lines, prep, *, party_id, warehouse_id,
                         exchange_rate, notes, uid) -> None:
        """Amend one posted sale in place. Runs inside an open transaction."""
        sale_id = original["id"]
        date = prep["date"]

        # 1. Give back the stock the current lines consumed.
        for ln in old_lines:
            if ln["warehouse_id"] is not None:
                self._inventory.add_movement(
                    item_id=ln["item_id"], warehouse_id=ln["warehouse_id"],
                    movement_type="ADJUSTMENT_IN", quantity=D(ln["quantity"]),
                    movement_date=date, unit_id=ln["unit_id"],
                    reference_type="SALE_CORRECTION", reference_id=sale_id,
                    reference_line_id=ln["id"], created_by=uid)

        # 2. Rewrite the lines and take the corrected stock out. A line whose item
        #    survives the correction KEEPS its id, so any sales return pointing at
        #    it stays valid; only lines whose item is gone are deleted, and only
        #    genuinely new items are inserted.
        reusable: dict[int, list[int]] = {}
        for ln in old_lines:
            reusable.setdefault(ln["item_id"], []).append(ln["id"])
        consumed: set[int] = set()
        for idx, (ln, c, wh, stockable) in enumerate(prep["computed"], start=1):
            pool = reusable.get(ln.item_id) or []
            line_id = pool.pop(0) if pool else None
            if line_id is not None:
                consumed.add(line_id)
                self._sales.update_line(
                    line_id, line_no=idx, item_id=ln.item_id, unit_id=ln.unit_id,
                    warehouse_id=wh, quantity=c.quantity, unit_price=c.unit_price,
                    discount=c.discount, line_total=c.line_total)
            else:
                line_id = self._sales.add_line(
                    sale_id=sale_id, line_no=idx, item_id=ln.item_id, unit_id=ln.unit_id,
                    warehouse_id=wh, quantity=c.quantity, unit_price=c.unit_price,
                    discount=c.discount, line_total=c.line_total)
            if stockable:
                self._inventory.add_movement(
                    item_id=ln.item_id, warehouse_id=wh, movement_type="SALE",
                    quantity=-c.quantity, movement_date=date, unit_id=ln.unit_id,
                    reference_type="SALE", reference_id=sale_id,
                    reference_line_id=line_id, created_by=uid)
        for ln in old_lines:
            if ln["id"] not in consumed:
                self._sales.delete_line(ln["id"])

        # 3. Header in place — document_no, status and posting stamps untouched.
        self._sales.update_header(
            sale_id, sale_date=date, currency_id=prep["currency"]["id"],
            warehouse_id=warehouse_id, exchange_rate=exchange_rate,
            subtotal=prep["subtotal"], discount_total=prep["discount_total"],
            grand_total=prep["grand_total"], amount_paid=prep["paid"],
            remaining_amount=prep["remaining"], notes=notes)
        self._ext.set_party(sale_id, party_id)
        wk_name, wk_phone, wk_address = prep["wk"]
        if party_id is None:
            self._ext.set_walkin(sale_id, wk_name, wk_phone, wk_address)

        # 4. Difference-only journal so the accounts reach the corrected figures.
        self._post_correction_ledger(original, prep, date, party_id, uid)

    def _post_correction_ledger(self, original, prep, date, party_id, uid) -> None:
        """Post the new − old delta for revenue, cash and receivable.

        Only the movement is journalled, never the whole invoice again, so a
        corrected sale is never counted twice in the accounts. A correction that
        changes nothing financial posts no journal at all.
        """
        d_revenue = money(D(prep["grand_total"]) - D(original["grand_total"]))
        d_cash = money(D(prep["paid"]) - D(original["amount_paid"]))
        d_ar = money(D(prep["remaining"]) - D(original["remaining_amount"]))
        if d_revenue == 0 and d_cash == 0 and d_ar == 0:
            return
        currency_id = prep["currency"]["id"]
        entry_no = self._numbering.allocate("JV")
        entry_id = self._financial.create_entry(
            entry_no=entry_no, entry_date=date, source_type="SALE_CORRECTION",
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

        # Revenue is naturally credited; cash and receivable are naturally debited.
        _line(_ACCT_SALES, d_revenue, natural_debit=False, memo="Correction: revenue change")
        _line(_ACCT_CASH, d_cash, natural_debit=True, memo="Correction: cash change")
        _line(_ACCT_AR, d_ar, natural_debit=True, party_type="CUSTOMER",
              party_id=party_id if party_id is not None else original["party_id"],
              memo="Correction: receivable change")
        assert_journal_balanced(self._financial, entry_id)

    def _post_void_ledger(self, sale, date, uid) -> None:
        grand = money(sale["grand_total"]); paid = money(sale["amount_paid"])
        remaining = money(sale["remaining_amount"])
        entry_no = self._numbering.allocate("JV")
        entry_id = self._financial.create_entry(
            entry_no=entry_no, entry_date=date, source_type="SALE_VOID", source_id=sale["id"],
            description=f"Void sale {sale['document_no']}", created_by=uid)
        # Exact mirror of _post_sale_ledger so every affected account nets to zero.
        self._financial.add_line(entry_id=entry_id,
                                 account_id=self._accounts.id_by_code(_ACCT_SALES),
                                 debit=grand, currency_id=sale["currency_id"],
                                 memo="Void: reverse revenue")
        if paid > 0:
            self._financial.add_line(entry_id=entry_id,
                                     account_id=self._accounts.id_by_code(_ACCT_CASH),
                                     credit=paid, currency_id=sale["currency_id"],
                                     memo="Void: reverse cash")
        if remaining > 0:
            self._financial.add_line(entry_id=entry_id,
                                     account_id=self._accounts.id_by_code(_ACCT_AR),
                                     credit=remaining, party_type="CUSTOMER",
                                     party_id=sale["party_id"], currency_id=sale["currency_id"],
                                     memo="Void: reverse receivable")
        assert_journal_balanced(self._financial, entry_id)

    # ---- post a sales return -------------------------------------------

    def _return_note(self, computed) -> str:
        """Readable summary of a return — 'Rice — Qty 1 returned; Sugar — Qty 2 returned.'

        Used when the caller supplies no note of its own, so every return document
        carries a human-readable record of what came back.
        """
        parts = []
        for src, qty, *_rest in computed:
            item = self._items.get(src["item_id"]) or {}
            name = item.get("name") or item.get("item_code") or f"item {src['item_id']}"
            parts.append(f"{name} — Qty {qty.normalize():f} returned")
        return "; ".join(parts) + ("." if parts else "")

    def post_return(self, *, sale_id: int, lines: list[ReturnLine],
                    reason: str | None = None, notes: str | None = None,
                    return_date: str | None = None) -> PostedDocument:
        self._authz.require("sales.return")
        sale = self._sales.get(sale_id)
        if sale is None or sale["status"] != "POSTED":
            raise ValidationError("Only a posted sale can be returned.",
                                  user_message="This sale cannot be returned.")
        date = return_date or today_iso()
        self._fy.assert_postable(date)
        if not lines:
            raise ValidationError("A return needs at least one line.",
                                  user_message="Select at least one line to return.")

        sale_lines = {ln["id"]: ln for ln in self._sales.lines_for(sale_id)}
        subtotal = D(0); discount_total = D(0); computed = []
        for rl in lines:
            src = sale_lines.get(rl.sale_line_id)
            if src is None:
                raise ValidationError("Return line does not belong to this sale.")
            qty = D(parse_money_input(rl.quantity, field="return quantity"))
            if qty <= 0:
                raise ValidationError("Return quantity must be positive.",
                                      user_message="Return quantity must be above zero.")
            already = D(self._ext.returned_qty_for_line(rl.sale_line_id))
            sold = D(src["quantity"])
            if already + qty > sold:
                raise ValidationError(
                    f"Over-return: line {rl.sale_line_id} sold {sold}, already {already},"
                    f" requested {qty}.",
                    user_message="You cannot return more than was sold.")
            unit_price = money(src["unit_price"])
            # proportional discount per unit keeps return value consistent with the sale
            per_unit_disc = (money(src["discount"]) / D(src["quantity"])) if D(src["quantity"]) else D(0)
            line_total = money(qty * unit_price - qty * per_unit_disc)
            subtotal += money(qty * unit_price)
            discount_total += money(qty * per_unit_disc)
            computed.append((src, qty, unit_price, money(qty * per_unit_disc), line_total))

        grand_total = money(subtotal - discount_total)
        uid = self._session.user_id
        party_id = sale["party_id"]
        # Always leave a readable record of what came back. The caller may supply
        # its own note (the UI passes a localized one); otherwise summarise the
        # returned lines — "Rice — Qty 1 returned."
        notes = (notes or "").strip() or self._return_note(computed)

        with self._db.transaction():
            document_no = self._numbering.allocate("SRET")
            return_id = self._returns.create_header(
                document_no=document_no, return_date=date, sale_id=sale_id,
                currency_id=sale["currency_id"], party_id=party_id,
                warehouse_id=sale["warehouse_id"], exchange_rate=sale["exchange_rate"],
                subtotal=subtotal, discount_total=discount_total, grand_total=grand_total,
                reason=reason, notes=notes, created_by=uid)
            for idx, (src, qty, unit_price, disc, line_total) in enumerate(computed, start=1):
                self._returns.add_line(
                    return_id=return_id, line_no=idx, sale_line_id=src["id"],
                    item_id=src["item_id"], unit_id=src["unit_id"],
                    warehouse_id=src["warehouse_id"], quantity=qty, unit_price=unit_price,
                    discount=disc, line_total=line_total)
                if src["warehouse_id"] is not None:
                    self._inventory.add_movement(
                        item_id=src["item_id"], warehouse_id=src["warehouse_id"],
                        movement_type="SALE_RETURN", quantity=qty, movement_date=date,
                        unit_id=src["unit_id"], reference_type="SALES_RETURN",
                        reference_id=return_id, created_by=uid)
            self._post_return_ledger(return_id, document_no, date, grand_total, party_id,
                                     sale["currency_id"], uid)
            self._audit.record(action="sales.return", user_id=uid,
                               username=self._session.username, entity_type="sales_return",
                               entity_id=return_id, document_no=document_no,
                               details=f"sale={sale['document_no']} total={grand_total}")
        _logger.info("Posted sales return %s (total=%s)", document_no, grand_total)
        return PostedDocument(return_id, document_no, str(grand_total), "0.00")

    def _post_return_ledger(self, return_id, doc_no, date, total, party_id, currency_id, uid):
        entry_no = self._numbering.allocate("JV")
        entry_id = self._financial.create_entry(
            entry_no=entry_no, entry_date=date, source_type="SALES_RETURN",
            source_id=return_id, description=f"Sales return {doc_no}", created_by=uid)
        # Reverse revenue; credit the customer's receivable (reduces balance / credit note).
        self._financial.add_line(entry_id=entry_id,
                                 account_id=self._accounts.id_by_code(_ACCT_SALES),
                                 debit=total, currency_id=currency_id, memo="Sales return")
        self._financial.add_line(entry_id=entry_id,
                                 account_id=self._accounts.id_by_code(_ACCT_AR),
                                 credit=total, party_type="CUSTOMER", party_id=party_id,
                                 currency_id=currency_id, memo="Return credit")
        assert_journal_balanced(self._financial, entry_id)

    # ---- helpers --------------------------------------------------------

    def _resolve_party(self, party_id, *, role):
        if party_id is None:
            return None  # walk-in / cash customer
        party = self._parties.get(party_id)
        if party is None or not party["is_active"]:
            raise ValidationError("Unknown or inactive party.",
                                  user_message="The selected party is not available.")
        if role == "customer" and not party["is_customer"]:
            raise ValidationError("Party is not a customer.",
                                  user_message="That party is not a customer.")
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
