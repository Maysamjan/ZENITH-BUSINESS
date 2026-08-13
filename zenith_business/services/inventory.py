"""Inventory service — opening stock and adjustments (Stage 02 §28).

Stock is a signed ledger: every change is a movement row, and on-hand quantity is
the sum of movements. This service records opening balances and manual
adjustments, always attributed and audited, inside a transaction.
"""

from __future__ import annotations

from zenith_business.core.clock import today_iso
from zenith_business.core.money import quantity
from zenith_business.database.connection import Database
from zenith_business.repositories.documents import InventoryRepository
from zenith_business.repositories.system import AuditRepository
from zenith_business.services.authorization import AuthorizationService
from zenith_business.services.exceptions import ValidationError
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

    def on_hand(self, item_id: int, warehouse_id: int | None = None) -> str:
        self._authz.require("inventory.view")
        return self._inventory.stock_on_hand(item_id, warehouse_id)
