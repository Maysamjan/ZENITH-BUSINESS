"""Inventory service — opening stock and adjustments (Stage 02 §28).

Stock is a signed ledger: every change is a movement row, and on-hand quantity is
the sum of movements. This service records opening balances and manual
adjustments, always attributed and audited, inside a transaction.
"""

from __future__ import annotations

from zenith_business.core.clock import today_iso
from zenith_business.core.money import D, quantity
from zenith_business.database.connection import Database
from zenith_business.repositories.documents import InventoryRepository
from zenith_business.repositories.system import AuditRepository
from zenith_business.services.authorization import AuthorizationService
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
    ) -> None:
        self._db = db
        self._inventory = inventory
        self._audit = audit
        self._session = session
        self._authz = authz

    def record_opening(
        self, *, item_id: int, warehouse_id: int, quantity_on_hand, unit_id: int | None = None,
        movement_date: str | None = None,
    ) -> int:
        self._authz.require("inventory.adjust")
        qty = quantity(quantity_on_hand)
        with self._db.transaction():
            mid = self._inventory.add_movement(
                item_id=item_id, warehouse_id=warehouse_id, movement_type="OPENING",
                quantity=qty, movement_date=movement_date or today_iso(), unit_id=unit_id,
                reference_type="OPENING", created_by=self._session.user_id)
            self._audit.record(
                action="inventory.opening", user_id=self._session.user_id,
                username=self._session.username, entity_type="item", entity_id=item_id,
                details=f"opening={qty} wh={warehouse_id}")
        return mid

    def adjust(
        self, *, item_id: int, warehouse_id: int, delta, reason: str,
        unit_id: int | None = None, movement_date: str | None = None,
    ) -> int:
        """Apply a signed stock adjustment (positive = in, negative = out)."""
        self._authz.require("inventory.adjust")
        qty = quantity(delta)
        if qty == 0:
            raise ValidationError("Adjustment quantity cannot be zero.",
                                  user_message="Enter a non-zero adjustment quantity.")
        movement_type = "ADJUSTMENT_IN" if qty > 0 else "ADJUSTMENT_OUT"
        with self._db.transaction():
            mid = self._inventory.add_movement(
                item_id=item_id, warehouse_id=warehouse_id, movement_type=movement_type,
                quantity=qty, movement_date=movement_date or today_iso(), unit_id=unit_id,
                reference_type="ADJUSTMENT", created_by=self._session.user_id)
            self._audit.record(
                action="inventory.adjust", user_id=self._session.user_id,
                username=self._session.username, entity_type="item", entity_id=item_id,
                details=f"delta={qty} wh={warehouse_id} reason={reason}")
        return mid

    def transfer(
        self, *, item_id: int, from_warehouse_id: int, to_warehouse_id: int, quantity_moved,
        unit_id: int | None = None, movement_date: str | None = None,
        allow_backorder: bool = False,
    ) -> tuple[int, int]:
        """Move stock between warehouses as ONE atomic OUT+IN pair (§8).

        The pair commits together, so a transfer can never leave stock counted in
        both places or in neither. Source stock is checked unless ``allow_backorder``.
        """
        self._authz.require("inventory.transfer")
        qty = quantity(quantity_moved)
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
            out_id = self._inventory.add_movement(
                item_id=item_id, warehouse_id=from_warehouse_id, movement_type="TRANSFER_OUT",
                quantity=-qty, movement_date=date, unit_id=unit_id,
                reference_type="TRANSFER", created_by=self._session.user_id)
            in_id = self._inventory.add_movement(
                item_id=item_id, warehouse_id=to_warehouse_id, movement_type="TRANSFER_IN",
                quantity=qty, movement_date=date, unit_id=unit_id,
                reference_type="TRANSFER", reference_id=out_id, created_by=self._session.user_id)
            self._audit.record(
                action="inventory.transfer", user_id=self._session.user_id,
                username=self._session.username, entity_type="item", entity_id=item_id,
                details=f"qty={qty} from={from_warehouse_id} to={to_warehouse_id}")
        return out_id, in_id

    def on_hand(self, item_id: int, warehouse_id: int | None = None) -> str:
        self._authz.require("inventory.view")
        return self._inventory.stock_on_hand(item_id, warehouse_id)
