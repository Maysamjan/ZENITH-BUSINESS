"""Shared DEMONSTRATION Sales Invoice transaction (Prompt 01E §19).

A single mock transaction consumed by BOTH the on-screen Sales Invoice and the
A4 print preview so the printed document matches exactly what is shown in the
app. Everything here is fake/configurable placeholder data — NO persistence, NO
accounting logic, NO database.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CompanyInfo:
    name: str
    address: str
    phone: str
    email: str
    tax_id: str


@dataclass(frozen=True)
class InvoiceLine:
    code: str
    name: str
    unit: str
    qty: float
    price: float
    discount: float

    @property
    def gross(self) -> float:
        return self.qty * self.price

    @property
    def total(self) -> float:
        return self.gross - self.discount


@dataclass(frozen=True)
class InvoiceData:
    company: CompanyInfo
    number: str
    date: str
    currency: str
    salesperson: str
    customer_code: str
    customer_name: str
    customer_phone: str
    customer_address: str
    lines: list[InvoiceLine] = field(default_factory=list)
    additional: float = 0.0
    tax: float = 0.0
    paid: float = 0.0

    @property
    def subtotal(self) -> float:
        return sum(line.gross for line in self.lines)

    @property
    def discount_total(self) -> float:
        return sum(line.discount for line in self.lines)

    @property
    def grand_total(self) -> float:
        return self.subtotal - self.discount_total + self.additional + self.tax

    @property
    def remaining(self) -> float:
        return self.grand_total - self.paid


# Mock/configurable company identity (clearly a demonstration placeholder).
_DEMO_COMPANY = CompanyInfo(
    name="Zenith Trading Co. (Demo)",
    address="Kabul, Shar-e-Naw, Street 4",
    phone="+93 70 000 0000",
    email="sales@zenith-demo.af",
    tax_id="TIN 100 234 567",
)


def build_demo_invoice() -> InvoiceData:
    """The one demonstration transaction shared by the screen and the print."""
    return InvoiceData(
        company=_DEMO_COMPANY,
        number="SALE-000001",
        date="1404/02/03",
        currency="AFN",
        salesperson="Ahmad",
        customer_code="C-1001",
        customer_name="Kabul General Store",
        customer_phone="070 111 2222",
        customer_address="Kabul, Shar-e-Naw",
        lines=[
            InvoiceLine("IT-1004", "Cooking Oil 5L", "Ctn", 10, 320.00, 0.00),
            InvoiceLine("IT-1002", "Basmati Rice 25kg", "Bag", 25, 1980.00, 50.00),
            InvoiceLine("IT-1006", "Sugar 50kg", "Bag", 8, 2600.00, 0.00),
        ],
        paid=40000.00,
    )


# Catalogue used to synthesize invoices of arbitrary length (print reflow tests).
_CATALOGUE = [
    ("IT-1004", "Cooking Oil 5L", "Ctn", 320.00),
    ("IT-1002", "Basmati Rice 25kg", "Bag", 1980.00),
    ("IT-1006", "Sugar 50kg", "Bag", 2600.00),
    ("IT-1005", "Green Tea 500g", "Box", 120.00),
    ("IT-1007", "Sunflower Oil 1L", "Ctn", 95.00),
    ("IT-1008", "Black Tea 250g", "Box", 80.00),
    ("IT-1001", "Basmati Rice 10kg", "Bag", 850.00),
    ("IT-1003", "Basmati Premium 50kg", "Bag", 4100.00),
]


def build_demo_invoice_n(n_items: int, *, paid: float | None = None) -> InvoiceData:
    """A demonstration invoice with ``n_items`` lines (for print reflow tests)."""
    base = build_demo_invoice()
    lines: list[InvoiceLine] = []
    for i in range(max(1, n_items)):
        code, name, unit, price = _CATALOGUE[i % len(_CATALOGUE)]
        qty = 5 + (i % 7) * 3
        disc = 0.0 if i % 4 else 25.0
        lines.append(InvoiceLine(code, f"{name}", unit, qty, price, disc))
    subtotal = sum(l.gross - l.discount for l in lines)
    return InvoiceData(
        company=base.company, number=base.number, date=base.date,
        currency=base.currency, salesperson=base.salesperson,
        customer_code=base.customer_code, customer_name=base.customer_name,
        customer_phone=base.customer_phone, customer_address=base.customer_address,
        lines=lines,
        paid=subtotal * 0.5 if paid is None else paid,
    )
