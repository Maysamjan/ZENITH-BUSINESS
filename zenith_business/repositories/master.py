"""Master-data repositories (Stage 02 §7, §17-§23)."""

from __future__ import annotations

from zenith_business.core.clock import now_iso
from zenith_business.core.money import money_to_db, qty_to_db, rate_to_db
from zenith_business.repositories.base import BaseRepository


class UnitRepository(BaseRepository):
    def create(self, *, code: str, name_en: str, name_fa: str, symbol: str | None = None,
               decimal_allowed: bool = True) -> int:
        ts = now_iso()
        return self._insert(
            "INSERT INTO units (code, name_en, name_fa, symbol, decimal_allowed,"
            " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (code, name_en, name_fa, symbol, 1 if decimal_allowed else 0, ts, ts))

    def update(self, unit_id: int, *, name_en: str, name_fa: str, symbol: str | None = None,
               decimal_allowed: bool = True) -> None:
        self._exec(
            "UPDATE units SET name_en=?, name_fa=?, symbol=?, decimal_allowed=?, updated_at=?"
            " WHERE id=?",
            (name_en, name_fa, symbol, 1 if decimal_allowed else 0, now_iso(), unit_id))

    def list_all(self, *, include_inactive: bool = True) -> list[dict]:
        sql = "SELECT * FROM units"
        if not include_inactive:
            sql += " WHERE is_active = 1"
        return self._all(sql + " ORDER BY name_en")

    def list_active(self) -> list[dict]:
        return self._all("SELECT * FROM units WHERE is_active = 1 ORDER BY name_en")

    def get(self, unit_id: int) -> dict | None:
        return self._one("SELECT * FROM units WHERE id = ?", (unit_id,))

    def id_by_code(self, code: str) -> int | None:
        return self._scalar("SELECT id FROM units WHERE code = ?", (code,))

    def code_exists(self, code: str) -> bool:
        return self._scalar("SELECT 1 FROM units WHERE code = ?", (code,)) is not None

    def set_active(self, unit_id: int, active: bool) -> None:
        self._exec("UPDATE units SET is_active = ?, updated_at = ? WHERE id = ?",
                   (1 if active else 0, now_iso(), unit_id))


class CategoryRepository(BaseRepository):
    def create(self, *, code: str, name_en: str, name_fa: str,
               parent_id: int | None = None, description: str | None = None) -> int:
        ts = now_iso()
        return self._insert(
            "INSERT INTO categories (parent_id, code, name_en, name_fa, description,"
            " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (parent_id, code, name_en, name_fa, description, ts, ts))

    def update(self, category_id: int, *, name_en: str, name_fa: str,
               parent_id: int | None = None, description: str | None = None) -> None:
        self._exec(
            "UPDATE categories SET parent_id=?, name_en=?, name_fa=?, description=?, updated_at=?"
            " WHERE id=?",
            (parent_id, name_en, name_fa, description, now_iso(), category_id))

    def list_all(self, *, include_inactive: bool = True) -> list[dict]:
        sql = "SELECT * FROM categories"
        if not include_inactive:
            sql += " WHERE is_active = 1"
        return self._all(sql + " ORDER BY name_en")

    def list_active(self) -> list[dict]:
        return self._all("SELECT * FROM categories WHERE is_active = 1 ORDER BY name_en")

    def get(self, category_id: int) -> dict | None:
        return self._one("SELECT * FROM categories WHERE id = ?", (category_id,))

    def code_exists(self, code: str) -> bool:
        return self._scalar("SELECT 1 FROM categories WHERE code = ?", (code,)) is not None

    def set_active(self, category_id: int, active: bool) -> None:
        self._exec("UPDATE categories SET is_active = ?, updated_at = ? WHERE id = ?",
                   (1 if active else 0, now_iso(), category_id))


class WarehouseRepository(BaseRepository):
    def create(self, *, code: str, name: str, address: str | None = None,
               phone: str | None = None, is_default: bool = False,
               manager_user_id: int | None = None, notes: str | None = None) -> int:
        ts = now_iso()
        return self._insert(
            "INSERT INTO warehouses (code, name, address, phone, manager_user_id, is_default,"
            " notes, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (code, name, address, phone, manager_user_id, 1 if is_default else 0, notes, ts, ts))

    def update(self, warehouse_id: int, *, name: str, address: str | None = None,
               phone: str | None = None, manager_user_id: int | None = None,
               notes: str | None = None) -> None:
        self._exec(
            "UPDATE warehouses SET name=?, address=?, phone=?, manager_user_id=?, notes=?,"
            " updated_at=? WHERE id=?",
            (name, address, phone, manager_user_id, notes, now_iso(), warehouse_id))

    def list_all(self, *, include_inactive: bool = True) -> list[dict]:
        sql = "SELECT * FROM warehouses"
        if not include_inactive:
            sql += " WHERE is_active = 1"
        return self._all(sql + " ORDER BY is_default DESC, name")

    def list_active(self) -> list[dict]:
        return self._all("SELECT * FROM warehouses WHERE is_active = 1 ORDER BY name")

    def get(self, warehouse_id: int) -> dict | None:
        return self._one("SELECT * FROM warehouses WHERE id = ?", (warehouse_id,))

    def id_by_code(self, code: str) -> int | None:
        return self._scalar("SELECT id FROM warehouses WHERE code = ?", (code,))

    def code_exists(self, code: str) -> bool:
        return self._scalar("SELECT 1 FROM warehouses WHERE code = ?", (code,)) is not None

    def get_default(self) -> dict | None:
        return self._one(
            "SELECT * FROM warehouses WHERE is_active = 1 ORDER BY is_default DESC, id LIMIT 1")

    def clear_default(self) -> None:
        self._exec("UPDATE warehouses SET is_default = 0, updated_at = ? WHERE is_default = 1",
                   (now_iso(),))

    def set_default(self, warehouse_id: int) -> None:
        self._exec("UPDATE warehouses SET is_default = 1, updated_at = ? WHERE id = ?",
                   (now_iso(), warehouse_id))

    def set_active(self, warehouse_id: int, active: bool) -> None:
        self._exec("UPDATE warehouses SET is_active = ?, updated_at = ? WHERE id = ?",
                   (1 if active else 0, now_iso(), warehouse_id))


class CurrencyRepository(BaseRepository):
    def list_active(self) -> list[dict]:
        return self._all("SELECT * FROM currencies WHERE is_active = 1 ORDER BY is_base DESC, code")

    def get(self, currency_id: int) -> dict | None:
        return self._one("SELECT * FROM currencies WHERE id = ?", (currency_id,))

    def get_by_code(self, code: str) -> dict | None:
        return self._one("SELECT * FROM currencies WHERE code = ?", (code,))

    def base_currency(self) -> dict | None:
        return self._one("SELECT * FROM currencies WHERE is_base = 1 LIMIT 1")


class ExchangeRateRepository(BaseRepository):
    def add(self, *, currency_id: int, rate_to_base, effective_at: str,
            created_by: int | None = None) -> int:
        return self._insert(
            "INSERT INTO exchange_rates (currency_id, rate_to_base, effective_at, created_by,"
            " created_at) VALUES (?, ?, ?, ?, ?)",
            (currency_id, rate_to_db(rate_to_base), effective_at, created_by, now_iso()))

    def latest(self, currency_id: int, as_of: str | None = None) -> dict | None:
        if as_of:
            return self._one(
                "SELECT * FROM exchange_rates WHERE currency_id = ? AND effective_at <= ?"
                " ORDER BY effective_at DESC, id DESC LIMIT 1", (currency_id, as_of))
        return self._one(
            "SELECT * FROM exchange_rates WHERE currency_id = ?"
            " ORDER BY effective_at DESC, id DESC LIMIT 1", (currency_id,))


class ItemRepository(BaseRepository):
    def create(self, *, item_code: str, name: str, base_unit_id: int,
               barcode: str | None = None, category_id: int | None = None,
               purchase_price=0, default_sale_price=0, min_sale_price=None,
               reorder_level=0, track_inventory: bool = True,
               name_en: str | None = None, name_fa: str | None = None,
               alternate_name: str | None = None,  # Stage 03 (additive)
               notes: str | None = None) -> int:
        ts = now_iso()
        return self._insert(
            "INSERT INTO items (item_code, barcode, name, name_en, name_fa, alternate_name,"
            " category_id, base_unit_id, purchase_price, default_sale_price, min_sale_price,"
            " reorder_level, track_inventory, notes, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (item_code, barcode, name, name_en, name_fa, alternate_name, category_id,
             base_unit_id, money_to_db(purchase_price), money_to_db(default_sale_price),
             None if min_sale_price is None else money_to_db(min_sale_price),
             qty_to_db(reorder_level), 1 if track_inventory else 0, notes, ts, ts))

    def update(self, item_id: int, *, name: str, base_unit_id: int,
               barcode: str | None = None, category_id: int | None = None,
               purchase_price=0, default_sale_price=0, min_sale_price=None,
               reorder_level=0, track_inventory: bool = True,
               alternate_name: str | None = None, notes: str | None = None) -> None:
        self._exec(
            "UPDATE items SET name=?, alternate_name=?, barcode=?, category_id=?, base_unit_id=?,"
            " purchase_price=?, default_sale_price=?, min_sale_price=?, reorder_level=?,"
            " track_inventory=?, notes=?, updated_at=? WHERE id=?",
            (name, alternate_name, barcode, category_id, base_unit_id,
             money_to_db(purchase_price), money_to_db(default_sale_price),
             None if min_sale_price is None else money_to_db(min_sale_price),
             qty_to_db(reorder_level), 1 if track_inventory else 0, notes, now_iso(), item_id))

    def barcode_exists(self, barcode: str, exclude_id: int | None = None) -> bool:
        if exclude_id is not None:
            return self._scalar("SELECT 1 FROM items WHERE barcode = ? AND id <> ?",
                                (barcode, exclude_id)) is not None
        return self._scalar("SELECT 1 FROM items WHERE barcode = ?", (barcode,)) is not None

    def get(self, item_id: int) -> dict | None:
        return self._one("SELECT * FROM items WHERE id = ?", (item_id,))

    def id_by_code(self, code: str) -> int | None:
        return self._scalar("SELECT id FROM items WHERE item_code = ?", (code,))

    def search(self, term: str, limit: int = 10) -> list[dict]:
        """Search by name, alternate name, item code or barcode (Stage 03 §12).

        Returns enough structured data for a future Sales line: id, code, name,
        unit, sale price. (Stage 03 additively broadened this to also match the
        alternate name and to expose the base unit id.)
        """
        like = f"%{term.strip()}%"
        return self._all(
            "SELECT i.id, i.item_code, i.name, i.alternate_name, i.barcode,"
            " i.default_sale_price, i.base_unit_id, u.symbol AS unit_symbol,"
            " u.name_en AS unit_name FROM items i"
            " JOIN units u ON u.id = i.base_unit_id"
            " WHERE i.is_active = 1 AND (i.name LIKE ? OR i.alternate_name LIKE ?"
            " OR i.item_code LIKE ? OR i.barcode LIKE ?)"
            " ORDER BY i.name LIMIT ?", (like, like, like, like, limit))

    def find_by_barcode(self, barcode: str) -> dict | None:
        return self._one("SELECT * FROM items WHERE barcode = ? AND is_active = 1", (barcode,))

    def list_active(self, limit: int = 200) -> list[dict]:
        return self._all("SELECT * FROM items WHERE is_active = 1 ORDER BY name LIMIT ?", (limit,))

    def set_active(self, item_id: int, active: bool) -> None:
        self._exec("UPDATE items SET is_active = ?, updated_at = ? WHERE id = ?",
                   (1 if active else 0, now_iso(), item_id))


class CustomerRepository(BaseRepository):
    def create(self, *, customer_code: str, name: str, phone: str | None = None,
               company_name: str | None = None, email: str | None = None,
               address: str | None = None, city: str | None = None,
               tax_id: str | None = None, credit_limit=0, opening_balance=0,
               secondary_phone: str | None = None, notes: str | None = None) -> int:
        ts = now_iso()
        return self._insert(
            "INSERT INTO customers (customer_code, name, company_name, phone, secondary_phone,"
            " email, address, city, tax_id, credit_limit, opening_balance, notes,"
            " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (customer_code, name, company_name, phone, secondary_phone, email, address, city,
             tax_id, money_to_db(credit_limit), money_to_db(opening_balance), notes, ts, ts))

    def get(self, customer_id: int) -> dict | None:
        return self._one("SELECT * FROM customers WHERE id = ?", (customer_id,))

    def search(self, term: str, limit: int = 10) -> list[dict]:
        like = f"%{term.strip()}%"
        return self._all(
            "SELECT id, customer_code, name, phone, credit_limit, opening_balance FROM customers"
            " WHERE is_active = 1 AND (name LIKE ? OR customer_code LIKE ? OR phone LIKE ?)"
            " ORDER BY name LIMIT ?", (like, like, like, limit))

    def list_active(self, limit: int = 200) -> list[dict]:
        return self._all("SELECT * FROM customers WHERE is_active = 1 ORDER BY name LIMIT ?", (limit,))

    def set_active(self, customer_id: int, active: bool) -> None:
        self._exec("UPDATE customers SET is_active = ?, updated_at = ? WHERE id = ?",
                   (1 if active else 0, now_iso(), customer_id))


class SupplierRepository(BaseRepository):
    def create(self, *, supplier_code: str, name: str, phone: str | None = None,
               company_name: str | None = None, email: str | None = None,
               address: str | None = None, city: str | None = None,
               tax_id: str | None = None, opening_balance=0, notes: str | None = None) -> int:
        ts = now_iso()
        return self._insert(
            "INSERT INTO suppliers (supplier_code, name, company_name, phone, email, address,"
            " city, tax_id, opening_balance, notes, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (supplier_code, name, company_name, phone, email, address, city, tax_id,
             money_to_db(opening_balance), notes, ts, ts))

    def get(self, supplier_id: int) -> dict | None:
        return self._one("SELECT * FROM suppliers WHERE id = ?", (supplier_id,))

    def list_active(self, limit: int = 200) -> list[dict]:
        return self._all("SELECT * FROM suppliers WHERE is_active = 1 ORDER BY name LIMIT ?", (limit,))

    def set_active(self, supplier_id: int, active: bool) -> None:
        self._exec("UPDATE suppliers SET is_active = ?, updated_at = ? WHERE id = ?",
                   (1 if active else 0, now_iso(), supplier_id))


class AccountRepository(BaseRepository):
    """Chart-of-accounts lookups (ledger foundation §29)."""

    def list_all(self) -> list[dict]:
        return self._all("SELECT * FROM accounts WHERE is_active = 1 ORDER BY code")

    def get(self, account_id: int) -> dict | None:
        return self._one("SELECT * FROM accounts WHERE id = ?", (account_id,))

    def get_by_code(self, code: str) -> dict | None:
        return self._one("SELECT * FROM accounts WHERE code = ?", (code,))

    def id_by_code(self, code: str) -> int | None:
        return self._scalar("SELECT id FROM accounts WHERE code = ?", (code,))


class CompanyRepository(BaseRepository):
    def get(self) -> dict | None:
        return self._one("SELECT * FROM companies ORDER BY id LIMIT 1")

    def upsert(self, *, legal_name: str, trade_name: str | None = None,
               address: str | None = None, city: str | None = None, country: str | None = None,
               phone: str | None = None, secondary_phone: str | None = None,
               email: str | None = None, website: str | None = None, tax_id: str | None = None,
               default_currency_id: int | None = None, default_language: str = "fa_AF",
               logo_path: str | None = None, invoice_footer: str | None = None,
               invoice_terms: str | None = None,
               display_name: str | None = None, registration_number: str | None = None,
               default_warehouse_id: int | None = None) -> int:
        ts = now_iso()
        existing = self.get()
        if existing:
            self._exec(
                "UPDATE companies SET legal_name=?, trade_name=?, display_name=?, address=?,"
                " city=?, country=?, phone=?, secondary_phone=?, email=?, website=?, tax_id=?,"
                " registration_number=?, default_currency_id=?, default_warehouse_id=?,"
                " default_language=?, logo_path=?, invoice_footer=?, invoice_terms=?, updated_at=?"
                " WHERE id=?",
                (legal_name, trade_name, display_name, address, city, country, phone,
                 secondary_phone, email, website, tax_id, registration_number,
                 default_currency_id, default_warehouse_id, default_language, logo_path,
                 invoice_footer, invoice_terms, ts, existing["id"]))
            return existing["id"]
        return self._insert(
            "INSERT INTO companies (legal_name, trade_name, display_name, address, city, country,"
            " phone, secondary_phone, email, website, tax_id, registration_number,"
            " default_currency_id, default_warehouse_id, default_language, logo_path,"
            " invoice_footer, invoice_terms, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (legal_name, trade_name, display_name, address, city, country, phone, secondary_phone,
             email, website, tax_id, registration_number, default_currency_id,
             default_warehouse_id, default_language, logo_path, invoice_footer, invoice_terms,
             ts, ts))
