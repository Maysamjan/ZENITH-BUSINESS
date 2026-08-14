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
from zenith_business.core.logging_setup import get_logger
from zenith_business.core.money import D, money
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
        self._authz.require("sales.view")
        return self._ext.list_documents(term=term, status=status, date_from=date_from,
                                        date_to=date_to, limit=limit)

    def get(self, sale_id: int) -> dict | None:
        self._authz.require("sales.view")
        return self._sales.get(sale_id)

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

    # ---- post a sale ----------------------------------------------------

    def post_sale(self, *, currency_code: str, lines: list[SaleLine],
                  party_id: int | None = None, warehouse_id: int | None = None,
                  amount_paid=0, exchange_rate=1, sale_date: str | None = None,
                  notes: str | None = None, allow_backorder: bool = False) -> PostedDocument:
        self._authz.require("sales.create")
        self._authz.require("sales.post")
        date = sale_date or today_iso()
        self._fy.assert_postable(date)  # financial-year enforcement (§7)

        if not lines:
            raise ValidationError("A sale needs at least one line.",
                                  user_message="Add at least one item to the invoice.")
        currency = self._currencies.get_by_code(currency_code)
        if currency is None:
            raise ValidationError(f"Unknown currency {currency_code!r}.")
        self._resolve_party(party_id, role="customer")

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
            for (item_id, wh), qty in needed.items():
                on_hand = D(self._inventory.stock_on_hand(item_id, wh))
                if qty > on_hand:
                    raise InsufficientStockError(
                        f"Item {item_id} @ wh {wh}: need {qty}, have {on_hand}.",
                        user_message="Not enough stock for one or more items.")

        grand_total = money(subtotal - discount_total)
        if paid > grand_total:
            raise ValidationError("Amount paid exceeds the total (overpayment not supported).",
                                  user_message="Amount received cannot exceed the total.")
        remaining = money(grand_total - paid)
        uid = self._session.user_id

        with self._db.transaction():
            document_no = self._numbering.allocate("SALE")
            sale_id = self._sales.create_header(
                document_no=document_no, sale_date=date, currency_id=currency["id"],
                customer_id=None, warehouse_id=warehouse_id, salesperson_id=uid,
                exchange_rate=exchange_rate, subtotal=subtotal, discount_total=discount_total,
                grand_total=grand_total, amount_paid=paid, remaining_amount=remaining,
                status="POSTED", notes=notes, created_by=uid)
            self._ext.set_party(sale_id, party_id)
            for idx, (ln, c, wh, stockable) in enumerate(computed, start=1):
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
                                   party_id, currency["id"], uid)
            self._sales.mark_posted(sale_id, uid)
            self._audit.record(action="sales.post", user_id=uid, username=self._session.username,
                               entity_type="sale", entity_id=sale_id, document_no=document_no,
                               details=f"total={grand_total} paid={paid} remaining={remaining}")
        _logger.info("Posted sale %s (total=%s)", document_no, grand_total)
        return PostedDocument(sale_id, document_no, str(grand_total), str(remaining))

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

    # ---- post a sales return -------------------------------------------

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
