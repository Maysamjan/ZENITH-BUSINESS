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
from zenith_business.core.logging_setup import get_logger
from zenith_business.core.money import D, money
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
        self._authz.require("purchases.view")
        return self._ext.list_documents(term=term, status=status, date_from=date_from,
                                        date_to=date_to, limit=limit)

    def get(self, purchase_id: int) -> dict | None:
        self._authz.require("purchases.view")
        return self._purchases.get(purchase_id)

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
