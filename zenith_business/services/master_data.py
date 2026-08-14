"""Master-data services: warehouses, units, categories (Stage 03 §7, §8, §9).

Each service enforces a permission, validates input, and writes + audits inside a
transaction. Referenced records are never hard-deleted — they are deactivated
(§22); the locked FK RESTRICT rules are the last line of defence.
"""

from __future__ import annotations

from zenith_business.database.connection import Database
from zenith_business.repositories.master import (
    CategoryRepository,
    UnitRepository,
    WarehouseRepository,
)
from zenith_business.repositories.system import AuditRepository
from zenith_business.services.authorization import AuthorizationService
from zenith_business.services.exceptions import ValidationError
from zenith_business.services.session import SessionContext


def _require_text(value: str | None, field: str) -> str:
    text = (value or "").strip()
    if not text:
        raise ValidationError(f"{field} is required.",
                              user_message=f"{field} is required.")
    return text


class WarehouseService:
    def __init__(self, db: Database, warehouses: WarehouseRepository,
                 audit: AuditRepository, session: SessionContext,
                 authz: AuthorizationService) -> None:
        self._db = db
        self._wh = warehouses
        self._audit = audit
        self._session = session
        self._authz = authz

    def list(self, *, include_inactive: bool = True) -> list[dict]:
        self._authz.require("warehouses.view")
        return self._wh.list_all(include_inactive=include_inactive)

    def create(self, *, code: str, name: str, address: str | None = None,
               phone: str | None = None, notes: str | None = None,
               is_default: bool = False) -> int:
        self._authz.require("warehouses.manage")
        code = _require_text(code, "Warehouse code")
        name = _require_text(name, "Warehouse name")
        if self._wh.code_exists(code):
            raise ValidationError("Duplicate warehouse code.",
                                  user_message="That warehouse code already exists.")
        with self._db.transaction():
            if is_default:
                self._wh.clear_default()
            wid = self._wh.create(code=code, name=name, address=address, phone=phone,
                                  notes=notes, is_default=is_default)
            self._audit.record(action="warehouses.create", user_id=self._session.user_id,
                               username=self._session.username, entity_type="warehouse",
                               entity_id=wid, details=f"code={code}")
        return wid

    def update(self, warehouse_id: int, *, name: str, address: str | None = None,
               phone: str | None = None, notes: str | None = None) -> None:
        self._authz.require("warehouses.manage")
        name = _require_text(name, "Warehouse name")
        with self._db.transaction():
            self._wh.update(warehouse_id, name=name, address=address, phone=phone, notes=notes)
            self._audit.record(action="warehouses.update", user_id=self._session.user_id,
                               username=self._session.username, entity_type="warehouse",
                               entity_id=warehouse_id)

    def set_default(self, warehouse_id: int) -> None:
        self._authz.require("warehouses.manage")
        with self._db.transaction():
            self._wh.clear_default()
            self._wh.set_default(warehouse_id)
            self._audit.record(action="warehouses.set_default", user_id=self._session.user_id,
                               username=self._session.username, entity_type="warehouse",
                               entity_id=warehouse_id)

    def set_active(self, warehouse_id: int, active: bool) -> None:
        self._authz.require("warehouses.manage")
        with self._db.transaction():
            self._wh.set_active(warehouse_id, active)
            self._audit.record(action="warehouses.activate" if active else "warehouses.deactivate",
                               user_id=self._session.user_id, username=self._session.username,
                               entity_type="warehouse", entity_id=warehouse_id)


class UnitService:
    def __init__(self, db: Database, units: UnitRepository, audit: AuditRepository,
                 session: SessionContext, authz: AuthorizationService) -> None:
        self._db = db
        self._units = units
        self._audit = audit
        self._session = session
        self._authz = authz

    def list(self, *, include_inactive: bool = True) -> list[dict]:
        self._authz.require("units.view")
        return self._units.list_all(include_inactive=include_inactive)

    def create(self, *, code: str, name_en: str, name_fa: str, symbol: str | None = None,
               decimal_allowed: bool = True) -> int:
        self._authz.require("units.manage")
        code = _require_text(code, "Unit code")
        name_en = _require_text(name_en, "Unit name (English)")
        name_fa = _require_text(name_fa, "Unit name (Dari)")
        if self._units.code_exists(code):
            raise ValidationError("Duplicate unit code.",
                                  user_message="That unit code already exists.")
        with self._db.transaction():
            uid = self._units.create(code=code, name_en=name_en, name_fa=name_fa,
                                     symbol=symbol, decimal_allowed=decimal_allowed)
            self._audit.record(action="units.create", user_id=self._session.user_id,
                               username=self._session.username, entity_type="unit",
                               entity_id=uid, details=f"code={code}")
        return uid

    def update(self, unit_id: int, *, name_en: str, name_fa: str, symbol: str | None = None,
               decimal_allowed: bool = True) -> None:
        self._authz.require("units.manage")
        with self._db.transaction():
            self._units.update(unit_id, name_en=_require_text(name_en, "Unit name (English)"),
                               name_fa=_require_text(name_fa, "Unit name (Dari)"), symbol=symbol,
                               decimal_allowed=decimal_allowed)
            self._audit.record(action="units.update", user_id=self._session.user_id,
                               username=self._session.username, entity_type="unit",
                               entity_id=unit_id)

    def set_active(self, unit_id: int, active: bool) -> None:
        self._authz.require("units.manage")
        with self._db.transaction():
            self._units.set_active(unit_id, active)
            self._audit.record(action="units.activate" if active else "units.deactivate",
                               user_id=self._session.user_id, username=self._session.username,
                               entity_type="unit", entity_id=unit_id)


class CategoryService:
    def __init__(self, db: Database, categories: CategoryRepository, audit: AuditRepository,
                 session: SessionContext, authz: AuthorizationService) -> None:
        self._db = db
        self._cats = categories
        self._audit = audit
        self._session = session
        self._authz = authz

    def list(self, *, include_inactive: bool = True) -> list[dict]:
        self._authz.require("categories.view")
        return self._cats.list_all(include_inactive=include_inactive)

    def create(self, *, code: str, name_en: str, name_fa: str,
               parent_id: int | None = None, description: str | None = None) -> int:
        self._authz.require("categories.manage")
        code = _require_text(code, "Category code")
        name_en = _require_text(name_en, "Category name (English)")
        name_fa = _require_text(name_fa, "Category name (Dari)")
        if self._cats.code_exists(code):
            raise ValidationError("Duplicate category code.",
                                  user_message="That category code already exists.")
        with self._db.transaction():
            cid = self._cats.create(code=code, name_en=name_en, name_fa=name_fa,
                                    parent_id=parent_id, description=description)
            self._audit.record(action="categories.create", user_id=self._session.user_id,
                               username=self._session.username, entity_type="category",
                               entity_id=cid, details=f"code={code}")
        return cid

    def update(self, category_id: int, *, name_en: str, name_fa: str,
               parent_id: int | None = None, description: str | None = None) -> None:
        self._authz.require("categories.manage")
        if parent_id == category_id:
            raise ValidationError("A category cannot be its own parent.",
                                  user_message="A category cannot be its own parent.")
        with self._db.transaction():
            self._cats.update(category_id,
                              name_en=_require_text(name_en, "Category name (English)"),
                              name_fa=_require_text(name_fa, "Category name (Dari)"),
                              parent_id=parent_id, description=description)
            self._audit.record(action="categories.update", user_id=self._session.user_id,
                               username=self._session.username, entity_type="category",
                               entity_id=category_id)

    def set_active(self, category_id: int, active: bool) -> None:
        self._authz.require("categories.manage")
        with self._db.transaction():
            self._cats.set_active(category_id, active)
            self._audit.record(
                action="categories.activate" if active else "categories.deactivate",
                user_id=self._session.user_id, username=self._session.username,
                entity_type="category", entity_id=category_id)
