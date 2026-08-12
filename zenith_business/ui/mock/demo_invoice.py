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
