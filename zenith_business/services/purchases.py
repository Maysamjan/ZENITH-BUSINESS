"""Purchase service — atomic purchase posting (Stage 02 §27, §28, §29, §34).

Mirror of :mod:`sales`: a purchase posts header + lines + inventory IN + ledger +
audit atomically. Inventory movements are POSITIVE (stock increases). Money and
quantities are Decimal throughout.
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
from zenith_business.repositories.master import (
    AccountRepository,
    CurrencyRepository,
    ItemRepository,
)
from zenith_business.repositories.system import AuditRepository
from zenith_business.services.authorization import AuthorizationService
from zenith_business.services.document_math import (
    assert_journal_balanced,
    compute_line,
    parse_money_input,
)
from zenith_business.services.exceptions import ValidationError
from zenith_business.services.numbering import DocumentNumberService
from zenith_business.services.session import SessionContext

_logger = get_logger("services.purchases")

_ACCT_CASH = "1000"
_ACCT_AP = "2000"
_ACCT_INVENTORY = "1200"


@dataclass
class PurchaseLineInput:
    item_id: int
    unit_id: int
    quantity: object
    unit_price: object
    discount: object = 0
    warehouse_id: int | None = None


@dataclass
class PostedPurchase:
    purchase_id: int
    document_no: str
    grand_total: str
    remaining: str


class PurchaseService:
    def __init__(
        self,
        db: Database,
        purchases: PurchaseRepository,
        inventory: InventoryRepository,
        financial: FinancialRepository,
        accounts: AccountRepository,
        currencies: CurrencyRepository,
        items: ItemRepository,
        numbering: DocumentNumberService,
        audit: AuditRepository,
        session: SessionContext,
        authz: AuthorizationService,
    ) -> None:
        self._db = db
        self._purchases = purchases
        self._inventory = inventory
        self._financial = financial
        self._accounts = accounts
        self._currencies = currencies
        self._items = items
        self._numbering = numbering
        self._audit = audit
        self._session = session
        self._authz = authz

    def create_and_post(
        self,
        *,
        currency_code: str,
        lines: list[PurchaseLineInput],
        supplier_id: int | None = None,
        warehouse_id: int | None = None,
        amount_paid=0,
        exchange_rate=1,
        purchase_date: str | None = None,
        notes: str | None = None,
    ) -> PostedPurchase:
        self._authz.require("purchases.create")
        self._authz.require("purchases.post")

        if not lines:
            raise ValidationError("A purchase needs at least one line.",
                                  user_message="Add at least one item to the purchase.")
        paid = money(parse_money_input(amount_paid, field="amount paid"))
        if paid < 0:
            raise ValidationError("Amount paid cannot be negative.",
                                  user_message="Amount paid cannot be negative.")
        currency = self._currencies.get_by_code(currency_code)
        if currency is None:
            raise ValidationError(f"Unknown currency {currency_code!r}.")

        subtotal = D(0)
        discount_total = D(0)
        computed = []
        for ln in lines:
            c = compute_line(ln.quantity, ln.unit_price, ln.discount)
            item = self._items.get(ln.item_id)
            if item is None:
                raise ValidationError(f"Unknown item id {ln.item_id}.",
                                      user_message="One of the selected items no longer exists.")
            stockable = bool(item["track_inventory"])
            wh = ln.warehouse_id or warehouse_id
            if stockable and wh is None:
                raise ValidationError(
                    "A warehouse is required to receive a stock-tracked item.",
                    user_message="Select a warehouse before purchasing stocked items.")
            subtotal += c.gross
            discount_total += c.discount
            computed.append((ln, c, wh, stockable))
        grand_total = money(subtotal - discount_total)
        remaining = money(grand_total - paid)

        user_id = self._session.user_id
        date = purchase_date or today_iso()

        with self._db.transaction():
            document_no = self._numbering.allocate("PUR")
            purchase_id = self._purchases.create_header(
                document_no=document_no, purchase_date=date, currency_id=currency["id"],
                supplier_id=supplier_id, warehouse_id=warehouse_id,
                exchange_rate=exchange_rate, subtotal=subtotal,
                discount_total=discount_total, grand_total=grand_total, amount_paid=paid,
                remaining_amount=remaining, status="POSTED", notes=notes, created_by=user_id)

            for idx, (ln, c, wh, stockable) in enumerate(computed, start=1):
                line_id = self._purchases.add_line(
                    purchase_id=purchase_id, line_no=idx, item_id=ln.item_id,
                    unit_id=ln.unit_id, warehouse_id=wh,
                    quantity=c.quantity, unit_price=c.unit_price,
                    discount=c.discount, line_total=c.line_total)
                if stockable:
                    self._inventory.add_movement(
                        item_id=ln.item_id, warehouse_id=wh, movement_type="PURCHASE",
                        quantity=c.quantity, movement_date=date, unit_id=ln.unit_id,
                        reference_type="PURCHASE", reference_id=purchase_id,
                        reference_line_id=line_id, created_by=user_id)

            self._post_ledger(purchase_id, document_no, date, grand_total, paid, remaining,
                              supplier_id, currency["id"], user_id)
            self._purchases.mark_posted(purchase_id, user_id)
            self._audit.record(
                action="purchases.post", user_id=user_id, username=self._session.username,
                entity_type="purchase", entity_id=purchase_id, document_no=document_no,
                details=f"grand_total={grand_total} paid={paid} remaining={remaining}")

        _logger.info("Posted purchase %s (id=%d, total=%s)",
                     document_no, purchase_id, grand_total)
        return PostedPurchase(purchase_id=purchase_id, document_no=document_no,
                              grand_total=str(grand_total), remaining=str(remaining))

    def _post_ledger(self, purchase_id, document_no, date, grand_total, paid, remaining,
                     supplier_id, currency_id, user_id) -> None:
        """Balanced double entry: Dr Inventory  =  Cr Cash + Cr A/P (§29)."""
        entry_no = self._numbering.allocate("JV")
        entry_id = self._financial.create_entry(
            entry_no=entry_no, entry_date=date, source_type="PURCHASE",
            source_id=purchase_id, description=f"Purchase {document_no}", created_by=user_id)
        inv_id = self._accounts.id_by_code(_ACCT_INVENTORY)
        cash_id = self._accounts.id_by_code(_ACCT_CASH)
        ap_id = self._accounts.id_by_code(_ACCT_AP)
        self._financial.add_line(
            entry_id=entry_id, account_id=inv_id, debit=grand_total,
            currency_id=currency_id, memo="Inventory received")
        if paid > 0:
            self._financial.add_line(
                entry_id=entry_id, account_id=cash_id, credit=paid,
                currency_id=currency_id, memo="Cash paid")
        if remaining > 0:
            self._financial.add_line(
                entry_id=entry_id, account_id=ap_id, credit=remaining,
                party_type="SUPPLIER", party_id=supplier_id, currency_id=currency_id,
                memo="On account")
        # Safety net: an unbalanced journal must never commit (§29).
        assert_journal_balanced(self._financial, entry_id)
