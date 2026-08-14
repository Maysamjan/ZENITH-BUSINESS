"""Unified party (person/company) repository (Stage 03 §15, §16).

One record represents a person or company that may be a customer, a supplier, or
both — no duplicate rows for dual roles. All SQL is parameterized; money fields
are serialized through the Decimal helpers.
"""

from __future__ import annotations

from zenith_business.core.clock import now_iso
from zenith_business.core.money import money_to_db
from zenith_business.repositories.base import BaseRepository


class PartyRepository(BaseRepository):
    def create(
        self,
        *,
        party_code: str,
        name: str,
        is_customer: bool = False,
        is_supplier: bool = False,
        company_name: str | None = None,
        phone: str | None = None,
        secondary_phone: str | None = None,
        email: str | None = None,
        address: str | None = None,
        city: str | None = None,
        tax_id: str | None = None,
        credit_limit=0,
        opening_balance=0,
        notes: str | None = None,
    ) -> int:
        ts = now_iso()
        return self._insert(
            "INSERT INTO parties (party_code, name, company_name, is_customer, is_supplier,"
            " phone, secondary_phone, email, address, city, tax_id, credit_limit,"
            " opening_balance, notes, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (party_code, name, company_name, 1 if is_customer else 0,
             1 if is_supplier else 0, phone, secondary_phone, email, address, city,
             tax_id, money_to_db(credit_limit), money_to_db(opening_balance), notes, ts, ts))

    def update(
        self,
        party_id: int,
        *,
        name: str,
        is_customer: bool,
        is_supplier: bool,
        company_name: str | None = None,
        phone: str | None = None,
        secondary_phone: str | None = None,
        email: str | None = None,
        address: str | None = None,
        city: str | None = None,
        tax_id: str | None = None,
        credit_limit=0,
        opening_balance=0,
        notes: str | None = None,
    ) -> None:
        self._exec(
            "UPDATE parties SET name=?, company_name=?, is_customer=?, is_supplier=?,"
            " phone=?, secondary_phone=?, email=?, address=?, city=?, tax_id=?,"
            " credit_limit=?, opening_balance=?, notes=?, updated_at=? WHERE id=?",
            (name, company_name, 1 if is_customer else 0, 1 if is_supplier else 0, phone,
             secondary_phone, email, address, city, tax_id, money_to_db(credit_limit),
             money_to_db(opening_balance), notes, now_iso(), party_id))

    def get(self, party_id: int) -> dict | None:
        return self._one("SELECT * FROM parties WHERE id = ?", (party_id,))

    def get_by_code(self, code: str) -> dict | None:
        return self._one("SELECT * FROM parties WHERE party_code = ?", (code,))

    def code_exists(self, code: str) -> bool:
        return self._scalar("SELECT 1 FROM parties WHERE party_code = ?", (code,)) is not None

    def set_active(self, party_id: int, active: bool) -> None:
        self._exec("UPDATE parties SET is_active = ?, updated_at = ? WHERE id = ?",
                   (1 if active else 0, now_iso(), party_id))

    def count(self) -> int:
        return int(self._scalar("SELECT COUNT(*) FROM parties") or 0)

    def list(
        self,
        *,
        role: str | None = None,          # 'customer' | 'supplier' | 'both' | None
        include_inactive: bool = True,
        limit: int = 500,
    ) -> list[dict]:
        where = []
        params: list = []
        if role == "customer":
            where.append("is_customer = 1")
        elif role == "supplier":
            where.append("is_supplier = 1")
        elif role == "both":
            where.append("is_customer = 1 AND is_supplier = 1")
        if not include_inactive:
            where.append("is_active = 1")
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        params.append(limit)
        return self._all(
            f"SELECT * FROM parties{clause} ORDER BY name LIMIT ?", tuple(params))

    def search(self, term: str, *, role: str | None = None, limit: int = 10) -> list[dict]:
        """Reusable search by name, company name, code or phone (§16)."""
        like = f"%{term.strip()}%"
        params: list = [like, like, like, like]
        role_clause = ""
        if role == "customer":
            role_clause = " AND is_customer = 1"
        elif role == "supplier":
            role_clause = " AND is_supplier = 1"
        params.append(limit)
        return self._all(
            "SELECT id, party_code, name, company_name, phone, is_customer, is_supplier,"
            " credit_limit, opening_balance FROM parties"
            " WHERE is_active = 1 AND (name LIKE ? OR company_name LIKE ?"
            f" OR party_code LIKE ? OR phone LIKE ?){role_clause}"
            " ORDER BY name LIMIT ?", tuple(params))
