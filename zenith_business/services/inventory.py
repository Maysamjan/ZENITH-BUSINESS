"""Inventory service — opening stock and adjustments (Stage 02 §28).

Stock is a signed ledger: every change is a movement row, and on-hand quantity is
the sum of movements. This service records opening balances and manual
adjustments, always attributed and audited, inside a transaction.
"""

from __future__ import annotations

from zenith_business.core.clock import today_iso
from zenith_business.core.money import D, qty_to_db, quantity
from zenith_business.database.connection import Database
from zenith_business.repositories.documents import InventoryRepository
from zenith_business.repositories.inventory_s6 import InventoryReadRepository
from zenith_business.repositories.system import AuditRepository
from zenith_business.services.authorization import AuthorizationService
from zenith_business.services.document_math import parse_money_input
from zenith_business.services.exceptions import InsufficientStockError, ValidationError
from zenith_business.services.session import SessionContext


class InventoryService:
    def __init__(
        self,
        db: Database,
        inventory: InventoryRepository,
        audit: AuditRepository,
        session: SessionContext,
        authz: AuthorizationService,
        read: InventoryReadRepository | None = None,
    ) -> None:
        self._db = db
        self._inventory = inventory
        self._audit = audit
        self._session = session
        self._authz = authz
        # Stage 06 read models (movement history, stock positions). Optional so an
        # existing caller that builds this service by hand keeps working.
        self._read = read if read is not None else InventoryReadRepository(db)

    def record_opening(
        self, *, item_id: int, warehouse_id: int | None, quantity_on_hand,
        unit_id: int | None = None, movement_date: str | None = None,
        notes: str | None = None,
    ) -> int:
        self._authz.require("inventory.adjust")
        # Stock has to live somewhere. Refusing here means an operator who enters an
        # opening quantity before creating a warehouse is told so, instead of the
        # quantity being silently dropped and the item selling as "out of stock".
        if warehouse_id is None:
            raise ValidationError(
                "Opening stock needs a warehouse.",
                user_message="Choose a warehouse for the opening stock. Create one under"
                             " Base Data → Warehouses first if there is none.")
        qty = quantity(parse_money_input(quantity_on_hand, field="opening quantity"))
        with self._db.transaction():
            mid = self._inventory.add_movement(
                item_id=item_id, warehouse_id=warehouse_id, movement_type="OPENING",
                quantity=qty, movement_date=movement_date or today_iso(), unit_id=unit_id,
                reference_type="OPENING", created_by=self._session.user_id,
                notes=(notes or "").strip() or None)
            self._audit.record(
                action="inventory.opening", user_id=self._session.user_id,
                username=self._session.username, entity_type="item", entity_id=item_id,
                details=f"opening={qty} wh={warehouse_id}")
        return mid

    def adjust(
        self, *, item_id: int, warehouse_id: int, delta, reason: str,
        unit_id: int | None = None, movement_date: str | None = None,
        allow_negative: bool = False,
    ) -> int:
        """Apply a signed stock adjustment (positive = in, negative = out).

        A reason is mandatory: an unexplained stock change is exactly the kind of
        movement nobody can reconcile later. It is stored on the movement itself,
        so the stock history shows WHY, not just how much.
        """
        self._authz.require("inventory.adjust")
        note = (reason or "").strip()
        if not note:
            raise ValidationError(
                "A stock adjustment needs a reason.",
                user_message="Enter the reason for this stock adjustment.")
        qty = quantity(parse_money_input(delta, field="adjustment"))
        if qty == 0:
            raise ValidationError("Adjustment quantity cannot be zero.",
                                  user_message="Enter a non-zero adjustment quantity.")
        if qty < 0 and not allow_negative:
            on_hand = D(self._inventory.stock_on_hand(item_id, warehouse_id))
            if -qty > on_hand:
                raise InsufficientStockError(
                    f"Adjustment out {-qty} exceeds {on_hand} on hand.",
                    user_message="Cannot remove more than the warehouse holds.")
        movement_type = "ADJUSTMENT_IN" if qty > 0 else "ADJUSTMENT_OUT"
        with self._db.transaction():
            mid = self._inventory.add_movement(
                item_id=item_id, warehouse_id=warehouse_id, movement_type=movement_type,
                quantity=qty, movement_date=movement_date or today_iso(), unit_id=unit_id,
                reference_type="ADJUSTMENT", created_by=self._session.user_id, notes=note)
            self._audit.record(
                action="inventory.adjust", user_id=self._session.user_id,
                username=self._session.username, entity_type="item", entity_id=item_id,
                details=f"delta={qty} wh={warehouse_id} reason={note}")
        return mid

    def transfer(
        self, *, item_id: int, from_warehouse_id: int, to_warehouse_id: int, quantity_moved,
        unit_id: int | None = None, movement_date: str | None = None,
        allow_backorder: bool = False, notes: str | None = None,
    ) -> tuple[int, int]:
        """Move stock between warehouses as ONE atomic OUT+IN pair (§8).

        The pair commits together, so a transfer can never leave stock counted in
        both places or in neither. Source stock is checked unless ``allow_backorder``.
        """
        self._authz.require("inventory.transfer")
        qty = quantity(parse_money_input(quantity_moved, field="transfer quantity"))
        if qty <= 0:
            raise ValidationError("Transfer quantity must be positive.",
                                  user_message="Enter a transfer quantity above zero.")
        if from_warehouse_id == to_warehouse_id:
            raise ValidationError("Source and destination warehouses must differ.",
                                  user_message="Choose two different warehouses.")
        if not allow_backorder:
            on_hand = D(self._inventory.stock_on_hand(item_id, from_warehouse_id))
            if qty > on_hand:
                raise InsufficientStockError(
                    f"Transfer needs {qty}, source has {on_hand}.",
                    user_message="Not enough stock in the source warehouse.")
        date = movement_date or today_iso()
        with self._db.transaction():
            note = (notes or "").strip() or None
            out_id = self._inventory.add_movement(
                item_id=item_id, warehouse_id=from_warehouse_id, movement_type="TRANSFER_OUT",
                quantity=-qty, movement_date=date, unit_id=unit_id,
                reference_type="TRANSFER", created_by=self._session.user_id, notes=note)
            in_id = self._inventory.add_movement(
                item_id=item_id, warehouse_id=to_warehouse_id, movement_type="TRANSFER_IN",
                quantity=qty, movement_date=date, unit_id=unit_id,
                reference_type="TRANSFER", reference_id=out_id,
                created_by=self._session.user_id, notes=note)
            self._audit.record(
                action="inventory.transfer", user_id=self._session.user_id,
                username=self._session.username, entity_type="item", entity_id=item_id,
                details=f"qty={qty} from={from_warehouse_id} to={to_warehouse_id}")
        return out_id, in_id

    def on_hand(self, item_id: int, warehouse_id: int | None = None) -> str:
        self._authz.require("inventory.view")
        return self._inventory.stock_on_hand(item_id, warehouse_id)

    def opening(self, item_id: int, warehouse_id: int | None = None) -> str:
        """The item's opening stock — fixed at creation, never moved by trading."""
        self._authz.require("inventory.view")
        return self._inventory.opening_stock(item_id, warehouse_id)

    def stock_columns(self, item_ids: list[int]) -> dict[int, dict[str, str]]:
        """``item_id -> {opening, current}`` for a list screen, in two queries."""
        self._authz.require("inventory.view")
        opening = self._inventory.opening_stock_map(item_ids)
        current = self._inventory.stock_on_hand_map(item_ids)
        return {i: {"opening": opening.get(i, "0"), "current": current.get(i, "0")}
                for i in item_ids}

    # ---- Stage 06 read models -------------------------------------------

    def movement_history(self, *, item_id: int | None = None,
                         warehouse_id: int | None = None,
                         movement_type: str | None = None,
                         date_from: str | None = None, date_to: str | None = None,
                         limit: int = 500) -> list[dict]:
        """Auditable movement rows with in/out split out for display.

        ``quantity`` stays the signed ledger value; ``qty_in``/``qty_out`` are the
        same number presented the way a stock card reads.
        """
        self._authz.require("inventory.view")
        rows = self._read.movements(
            item_id=item_id, warehouse_id=warehouse_id, movement_type=movement_type,
            date_from=date_from, date_to=date_to, limit=limit)
        out = []
        for r in rows:
            qty = D(r["quantity"])
            out.append({**r,
                        "qty_in": qty_to_db(qty) if qty > 0 else "",
                        "qty_out": qty_to_db(-qty) if qty < 0 else ""})
        return out

    def stock_by_warehouse(self) -> list[dict]:
        """One row per (item, warehouse) holding stock, with its low-stock flag."""
        self._authz.require("inventory.view")
        rows = self._read.stock_by_item_and_warehouse()
        for r in rows:
            r["low"] = D(r["quantity"]) <= D(r["reorder_level"] or 0)
        return rows

    def stock_overview(self) -> list[dict]:
        """Every stockable item with opening, current, warehouses and low-stock state.

        This is the single row shape the Inventory screen and the stock reports
        both render, so the two can never show different numbers.
        """
        self._authz.require("inventory.view")
        items = self._read.items_with_levels()
        ids = [i["id"] for i in items]
        opening = self._inventory.opening_stock_map(ids)
        current = self._inventory.stock_on_hand_map(ids)
        warehouses = self._read.warehouse_names_by_item()
        out = []
        for it in items:
            if not it["track_inventory"]:
                continue
            cur = D(current.get(it["id"], "0"))
            minimum = D(it["reorder_level"] or 0)
            out.append({
                "item_id": it["id"], "item_code": it["item_code"], "item_name": it["name"],
                "unit": it["unit_symbol"] or it["unit_name"] or "",
                "opening": opening.get(it["id"], "0"),
                "current": qty_to_db(cur),
                "minimum": qty_to_db(minimum),
                "warehouses": ", ".join(warehouses.get(it["id"], [])),
                "low": cur <= minimum,
                "is_active": bool(it["is_active"]),
            })
        return out

    def low_stock(self) -> list[dict]:
        """Stockable items at or below their minimum level."""
        return [r for r in self.stock_overview() if r["low"]]
