"""Reusable production search providers (Stage 03 §12, §16).

Implement the LOCKED Stage 01 ``SearchProvider`` Protocol, backed by Stage 03
repositories. They are intentionally decoupled from any page so future Sales,
Purchases, Receipts and Payments screens can drop them into a ``SearchSelector``
and receive rich, structured payloads (ids, codes, unit, price, balances) without
re-typing known data. Indexed SQL + limited result sets keep them fast on large
datasets (§31).
"""

from __future__ import annotations

from zenith_business.core.money import format_money
from zenith_business.repositories.master import ItemRepository
from zenith_business.repositories.parties import PartyRepository
from zenith_business.ui.widgets.search_selector import SearchColumn, SearchRow


class ItemSearchProvider:
    """Search items by name / alternate name / code / barcode (§12)."""

    def __init__(self, items: ItemRepository) -> None:
        self._items = items

    def columns(self) -> list[SearchColumn]:
        return [
            SearchColumn("Code", width=110),
            SearchColumn("Name", stretch=True),
            SearchColumn("Unit", width=70),
            SearchColumn("Sale Price", align="r", width=110),
        ]

    def search(self, text: str, limit: int = 8) -> list[SearchRow]:
        if not text or not text.strip():
            return []
        rows: list[SearchRow] = []
        for r in self._items.search(text, limit=limit):
            rows.append(SearchRow(
                values=[r["item_code"], r["name"], r.get("unit_symbol") or "",
                        format_money(r["default_sale_price"])],
                payload={
                    "item_id": r["id"], "item_code": r["item_code"], "name": r["name"],
                    "alternate_name": r.get("alternate_name"), "barcode": r.get("barcode"),
                    "base_unit_id": r.get("base_unit_id"), "unit_symbol": r.get("unit_symbol"),
                    "sale_price": r["default_sale_price"],
                }))
        return rows


class PartySearchProvider:
    """Search parties by name / company / code / phone, optionally by role (§16)."""

    def __init__(self, parties: PartyRepository, *, role: str | None = None) -> None:
        self._parties = parties
        self._role = role  # 'customer' | 'supplier' | None

    def columns(self) -> list[SearchColumn]:
        return [
            SearchColumn("Code", width=110),
            SearchColumn("Name", stretch=True),
            SearchColumn("Phone", width=130),
            SearchColumn("Balance", align="r", width=120),
        ]

    def search(self, text: str, limit: int = 8) -> list[SearchRow]:
        if not text or not text.strip():
            return []
        rows: list[SearchRow] = []
        for r in self._parties.search(text, role=self._role, limit=limit):
            rows.append(SearchRow(
                values=[r["party_code"], r["name"], r.get("phone") or "",
                        format_money(r.get("opening_balance") or 0)],
                payload={
                    "party_id": r["id"], "party_code": r["party_code"], "name": r["name"],
                    "company_name": r.get("company_name"), "phone": r.get("phone"),
                    "is_customer": bool(r.get("is_customer")),
                    "is_supplier": bool(r.get("is_supplier")),
                    "credit_limit": r.get("credit_limit"),
                    "opening_balance": r.get("opening_balance"),
                }))
        return rows
