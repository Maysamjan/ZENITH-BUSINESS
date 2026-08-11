"""Mock search providers for the Sales Invoice prototype (Prompt 01D §13).

DEMONSTRATION DATA ONLY — not real inventory or customers, no persistence.
These implement :class:`SearchProvider` so the exact same UI works unchanged
once Stage 02+ supplies repository-backed providers.
"""

from __future__ import annotations

from dataclasses import dataclass

from zenith_business.ui.widgets.search_selector import SearchColumn, SearchRow


@dataclass(frozen=True)
class _Item:
    code: str
    name: str
    unit: str
    stock: float
    price: float
    last_sale: float
    avg_cost: float


# Obviously-fake catalogue; 'bas' surfaces the Basmati group (Prompt 01D §1).
_ITEMS = [
    _Item("IT-1001", "Basmati Rice 10kg", "Bag", 120, 850.00, 860.00, 812.00),
    _Item("IT-1002", "Basmati Rice 25kg", "Bag", 64, 1980.00, 2000.00, 1920.00),
    _Item("IT-1003", "Basmati Premium 50kg", "Bag", 22, 4100.00, 4150.00, 3980.00),
    _Item("IT-1004", "Cooking Oil 5L", "Ctn", 142, 320.00, 325.00, 308.40),
    _Item("IT-1005", "Green Tea 500g", "Box", 300, 120.00, 118.00, 96.00),
    _Item("IT-1006", "Sugar 50kg", "Bag", 40, 2600.00, 2620.00, 2555.00),
    _Item("IT-1007", "Sunflower Oil 1L", "Ctn", 210, 95.00, 96.50, 88.00),
    _Item("IT-1008", "Black Tea 250g", "Box", 180, 80.00, 82.00, 70.00),
]


@dataclass(frozen=True)
class _Customer:
    code: str
    name: str
    phone: str
    balance: float
    credit_limit: float
    address: str


_CUSTOMERS = [
    _Customer("C-1001", "Kabul General Store", "070 111 2222", 12500.00, 50000.00, "Kabul, Shar-e-Naw"),
    _Customer("C-1002", "Herat Traders", "079 333 4444", 0.00, 30000.00, "Herat, Bazaar"),
    _Customer("C-1003", "Mazar Wholesale", "077 555 6666", 45200.00, 80000.00, "Mazar-e-Sharif"),
    _Customer("C-1004", "Kandahar Mart", "070 777 8888", -3000.00, 20000.00, "Kandahar"),
]


class DemoItemProvider:
    """Mock item search (name / code / stock / price)."""

    def columns(self) -> list[SearchColumn]:
        return [
            SearchColumn("Code", "l", width=96),
            SearchColumn("Item Name", "l", stretch=True),
            SearchColumn("Unit", "l", width=60),
            SearchColumn("Stock", "r", width=76),
            SearchColumn("Price", "r", width=96),
        ]

    def search(self, text: str, limit: int = 8) -> list[SearchRow]:
        q = text.strip().lower()
        rows: list[SearchRow] = []
        for it in _ITEMS:
            if q in it.code.lower() or q in it.name.lower():
                rows.append(SearchRow(
                    values=[it.code, it.name, it.unit, f"{it.stock:,.0f}", f"{it.price:,.2f}"],
                    payload={
                        "code": it.code, "name": it.name, "unit": it.unit,
                        "stock": it.stock, "price": it.price,
                        "last_sale": it.last_sale, "avg_cost": it.avg_cost,
                    },
                ))
            if len(rows) >= limit:
                break
        return rows


class DemoCustomerProvider:
    """Mock customer search (name / code / phone / balance)."""

    def columns(self) -> list[SearchColumn]:
        return [
            SearchColumn("Customer", "l", stretch=True),
            SearchColumn("Code", "l", width=84),
            SearchColumn("Phone", "l", width=120),
            SearchColumn("Balance", "r", width=110),
        ]

    def search(self, text: str, limit: int = 8) -> list[SearchRow]:
        q = text.strip().lower()
        rows: list[SearchRow] = []
        for c in _CUSTOMERS:
            if (q in c.name.lower() or q in c.code.lower()
                    or q in c.phone.replace(" ", "").lower()):
                rows.append(SearchRow(
                    values=[c.name, c.code, c.phone, f"{c.balance:,.2f}"],
                    payload={
                        "code": c.code, "name": c.name, "phone": c.phone,
                        "balance": c.balance, "credit_limit": c.credit_limit,
                        "address": c.address,
                    },
                ))
            if len(rows) >= limit:
                break
        return rows
