"""Sales service — atomic sale posting (Stage 02 §25, §26, §29, §31, §34, §48).

Posting a sale is ONE atomic unit of work: header + lines + inventory movements +
double-entry ledger + audit all commit together, or the whole thing rolls back and
the document number is reclaimed. Money and quantities are Decimal throughout;
never float. Permission is enforced at this layer.
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
from zenith_business.repositories.master import (
    AccountRepository,
    CurrencyRepository,
    ItemRepository,
)
from zenith_business.repositories.system import AuditRepository
from zenith_business.services.authorization import AuthorizationService
from zenith_business.services.document_math import assert_journal_balanced, compute_line
from zenith_business.services.exceptions import InsufficientStockError, ValidationError
from zenith_business.services.numbering import DocumentNumberService
from zenith_business.services.session import SessionContext

_logger = get_logger("services.sales")

_ACCT_CASH = "1000"
_ACCT_AR = "1100"
_ACCT_SALES = "4000"


@dataclass
class SaleLineInput:
    item_id: int
    unit_id: int
    quantity: object          # Decimal-coercible
    unit_price: object
    discount: object = 0
    warehouse_id: int | None = None


@dataclass
class PostedSale:
    sale_id: int
    document_no: str
    grand_total: str
    remaining: str


class SalesService:
    def __init__(
        self,
        db: Database,
        sales: SalesRepository,
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
        self._sales = sales
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
        lines: list[SaleLineInput],
        customer_id: int | None = None,
        warehouse_id: int | None = None,
        amount_paid=0,
        exchange_rate=1,
        sale_date: str | None = None,
        notes: str | None = None,
        allow_backorder: bool = False,
    ) -> PostedSale:
        """Create and POST a sale atomically. Requires ``sales.create`` + ``sales.post``.

        A stockable item must have a warehouse and enough on-hand stock (unless
        ``allow_backorder`` is explicitly set), so a posted sale can never leave a
        silent inventory hole or drive stock negative (§28, §33).
        """
        self._authz.require("sales.create")
        self._authz.require("sales.post")

        if not lines:
            raise ValidationError("A sale needs at least one line.",
                                  user_message="Add at least one item to the invoice.")
        if money(amount_paid) < 0:
            raise ValidationError("Amount paid cannot be negative.",
                                  user_message="Amount paid cannot be negative.")

        currency = self._currencies.get_by_code(currency_code)
        if currency is None:
            raise ValidationError(f"Unknown currency {currency_code!r}.")

        # ---- validate + compute lines with Decimal (never float) ----
        subtotal = D(0)
        discount_total = D(0)
        computed: list[tuple[SaleLineInput, object, int | None, bool]] = []
        needed: dict[tuple[int, int], object] = {}  # (item, warehouse) -> qty
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
                    "A warehouse is required to sell a stock-tracked item.",
                    user_message="Select a warehouse before selling stocked items.")
            if stockable:
                key = (ln.item_id, wh)
                needed[key] = D(needed.get(key, D(0))) + c.quantity
            subtotal += c.gross
            discount_total += c.discount
            computed.append((ln, c, wh, stockable))

        # ---- enforce stock availability before writing anything ----
        if not allow_backorder:
            for (item_id, wh), qty in needed.items():
                on_hand = D(self._inventory.stock_on_hand(item_id, wh))
                if qty > on_hand:
                    raise InsufficientStockError(
                        f"Item {item_id} at warehouse {wh}: need {qty}, have {on_hand}.",
                        user_message="Not enough stock for one or more items.")

        grand_total = money(subtotal - discount_total)
        paid = money(amount_paid)
        remaining = money(grand_total - paid)
        user_id = self._session.user_id
        date = sale_date or today_iso()

        with self._db.transaction():
            document_no = self._numbering.allocate("SALE")
            sale_id = self._sales.create_header(
                document_no=document_no, sale_date=date, currency_id=currency["id"],
                customer_id=customer_id, warehouse_id=warehouse_id,
                salesperson_id=user_id, exchange_rate=exchange_rate,
                subtotal=subtotal, discount_total=discount_total, grand_total=grand_total,
                amount_paid=paid, remaining_amount=remaining, status="POSTED",
                notes=notes, created_by=user_id)

            for idx, (ln, c, wh, stockable) in enumerate(computed, start=1):
                line_id = self._sales.add_line(
                    sale_id=sale_id, line_no=idx, item_id=ln.item_id, unit_id=ln.unit_id,
                    warehouse_id=wh, quantity=c.quantity, unit_price=c.unit_price,
                    discount=c.discount, line_total=c.line_total)
                # Inventory OUT — signed negative so SUM(quantity) = stock (§28).
                if stockable:
                    self._inventory.add_movement(
                        item_id=ln.item_id, warehouse_id=wh, movement_type="SALE",
                        quantity=-c.quantity, movement_date=date, unit_id=ln.unit_id,
                        reference_type="SALE", reference_id=sale_id,
                        reference_line_id=line_id, created_by=user_id)

            self._post_ledger(sale_id, document_no, date, grand_total, paid, remaining,
                              customer_id, currency["id"], user_id)

            self._sales.mark_posted(sale_id, user_id)
            self._audit.record(
                action="sales.post", user_id=user_id, username=self._session.username,
                entity_type="sale", entity_id=sale_id, document_no=document_no,
                details=f"grand_total={grand_total} paid={paid} remaining={remaining}")

        _logger.info("Posted sale %s (id=%d, total=%s)", document_no, sale_id, grand_total)
        return PostedSale(sale_id=sale_id, document_no=document_no,
                          grand_total=str(grand_total), remaining=str(remaining))

    def _post_ledger(self, sale_id, document_no, date, grand_total, paid, remaining,
                     customer_id, currency_id, user_id) -> None:
        """Balanced double entry: Dr Cash + Dr A/R  =  Cr Sales Revenue (§29)."""
        entry_no = self._numbering.allocate("JV")
        entry_id = self._financial.create_entry(
            entry_no=entry_no, entry_date=date, source_type="SALE", source_id=sale_id,
            description=f"Sale {document_no}", created_by=user_id)
        cash_id = self._accounts.id_by_code(_ACCT_CASH)
        ar_id = self._accounts.id_by_code(_ACCT_AR)
        sales_id = self._accounts.id_by_code(_ACCT_SALES)
        if paid > 0:
            self._financial.add_line(
                entry_id=entry_id, account_id=cash_id, debit=paid, currency_id=currency_id,
                memo="Cash received")
        if remaining > 0:
            self._financial.add_line(
                entry_id=entry_id, account_id=ar_id, debit=remaining, party_type="CUSTOMER",
                party_id=customer_id, currency_id=currency_id, memo="On account")
        self._financial.add_line(
            entry_id=entry_id, account_id=sales_id, credit=grand_total,
            currency_id=currency_id, memo="Sales revenue")
        # Safety net: an unbalanced journal must never commit (§29).
        assert_journal_balanced(self._financial, entry_id)

    # ---- reads ----
    def stock_on_hand(self, item_id: int, warehouse_id: int | None = None) -> str:
        self._authz.require("inventory.view")
        return self._inventory.stock_on_hand(item_id, warehouse_id)

    def recent(self, limit: int = 50) -> list[dict]:
        self._authz.require("sales.view")
        return self._sales.list_recent(limit)
