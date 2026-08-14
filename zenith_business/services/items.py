"""Item / product master service (Stage 03 §10, §11, §23).

Enforces item-code uniqueness, optional-but-unique barcode, required name,
Decimal-safe non-negative prices/reorder level (malformed input rejected via the
strict parser), and audits every change. Barcode is optional — many Afghan shops
sell unbarcoded goods (§11).
"""

from __future__ import annotations

from zenith_business.core.money import money
from zenith_business.database.connection import Database
from zenith_business.repositories.master import ItemRepository
from zenith_business.repositories.system import AuditRepository
from zenith_business.services.authorization import AuthorizationService
from zenith_business.services.document_math import parse_money_input
from zenith_business.services.exceptions import ValidationError
from zenith_business.services.session import SessionContext


class ItemService:
    def __init__(self, db: Database, items: ItemRepository, audit: AuditRepository,
                 session: SessionContext, authz: AuthorizationService) -> None:
        self._db = db
        self._items = items
        self._audit = audit
        self._session = session
        self._authz = authz

    def list(self, *, limit: int = 500) -> list[dict]:
        self._authz.require("items.view")
        return self._items.list_active(limit=limit)

    def search(self, term: str, *, limit: int = 10) -> list[dict]:
        self._authz.require("items.view")
        return self._items.search(term, limit=limit)

    def get(self, item_id: int) -> dict | None:
        self._authz.require("items.view")
        return self._items.get(item_id)

    # ---- validation shared by create/edit -------------------------------

    def _validate_prices(self, purchase_price, sale_price, reorder_level):
        pp = money(parse_money_input(purchase_price, field="purchase price"))
        sp = money(parse_money_input(sale_price, field="sale price"))
        rl = parse_money_input(reorder_level, field="minimum stock")
        if pp < 0 or sp < 0:
            raise ValidationError("Prices cannot be negative.",
                                  user_message="Prices cannot be negative.")
        if rl < 0:
            raise ValidationError("Minimum stock cannot be negative.",
                                  user_message="Minimum stock cannot be negative.")
        return pp, sp, rl

    def create(self, *, item_code: str, name: str, base_unit_id: int,
               barcode: str | None = None, alternate_name: str | None = None,
               category_id: int | None = None, purchase_price=0, default_sale_price=0,
               reorder_level=0, track_inventory: bool = True, notes: str | None = None) -> int:
        self._authz.require("items.create")
        item_code = (item_code or "").strip()
        name = (name or "").strip()
        barcode = (barcode or "").strip() or None
        if not item_code:
            raise ValidationError("Item code is required.",
                                  user_message="Item code is required.")
        if not name:
            raise ValidationError("Item name is required.",
                                  user_message="Item name is required.")
        if self._items.id_by_code(item_code) is not None:
            raise ValidationError("Duplicate item code.",
                                  user_message="That item code already exists.")
        if barcode and self._items.barcode_exists(barcode):
            raise ValidationError("Duplicate barcode.",
                                  user_message="That barcode is already used by another item.")
        pp, sp, rl = self._validate_prices(purchase_price, default_sale_price, reorder_level)
        with self._db.transaction():
            item_id = self._items.create(
                item_code=item_code, name=name, base_unit_id=base_unit_id, barcode=barcode,
                alternate_name=(alternate_name or "").strip() or None, category_id=category_id,
                purchase_price=pp, default_sale_price=sp, reorder_level=rl,
                track_inventory=track_inventory, notes=notes)
            self._audit.record(action="items.create", user_id=self._session.user_id,
                               username=self._session.username, entity_type="item",
                               entity_id=item_id, details=f"code={item_code}")
        return item_id

    def update(self, item_id: int, *, name: str, base_unit_id: int,
               barcode: str | None = None, alternate_name: str | None = None,
               category_id: int | None = None, purchase_price=0, default_sale_price=0,
               reorder_level=0, track_inventory: bool = True, notes: str | None = None) -> None:
        self._authz.require("items.edit")
        if self._items.get(item_id) is None:
            raise ValidationError("No such item.")
        name = (name or "").strip()
        barcode = (barcode or "").strip() or None
        if not name:
            raise ValidationError("Item name is required.",
                                  user_message="Item name is required.")
        if barcode and self._items.barcode_exists(barcode, exclude_id=item_id):
            raise ValidationError("Duplicate barcode.",
                                  user_message="That barcode is already used by another item.")
        pp, sp, rl = self._validate_prices(purchase_price, default_sale_price, reorder_level)
        with self._db.transaction():
            self._items.update(
                item_id, name=name, base_unit_id=base_unit_id, barcode=barcode,
                alternate_name=(alternate_name or "").strip() or None, category_id=category_id,
                purchase_price=pp, default_sale_price=sp, reorder_level=rl,
                track_inventory=track_inventory, notes=notes)
            self._audit.record(action="items.update", user_id=self._session.user_id,
                               username=self._session.username, entity_type="item",
                               entity_id=item_id)

    def set_active(self, item_id: int, active: bool) -> None:
        self._authz.require("items.edit")
        with self._db.transaction():
            self._items.set_active(item_id, active)
            self._audit.record(action="items.activate" if active else "items.deactivate",
                               user_id=self._session.user_id, username=self._session.username,
                               entity_type="item", entity_id=item_id)
