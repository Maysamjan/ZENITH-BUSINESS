"""Products this Manager can issue licences for (Vendor Manager §10).

One application, several products. Zenith Business is implemented fully; the
shape exists so D-Clinic and whatever comes next are a registry entry and a
signing key, not a second program to maintain.

Each product owns:

* its **product id**, which is signed into every licence and checked by that
  product's application — a licence for one product is refused by another;
* its **own keypair**, so a key that leaks compromises one product rather than
  the catalogue;
* its **licence rules** — which types exist, whether FULL may carry an expiry,
  the demo lengths offered, and how licence numbers are written.

A product is added here. Nothing else in the Manager knows product names.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Product:
    """One Zenith Soft product the Manager can issue licences for."""

    product_id: str
    display_name: str
    #: The file name its signing key gets in the vendor key directory.
    key_filename: str
    #: How a licence number is written for this product.
    license_id_prefix: str = "ZB"
    types: tuple[str, ...] = ("FULL", "DEMO")
    #: Demo lengths offered as buttons. "Custom" is always available as well.
    demo_days: tuple[int, ...] = (7, 14, 15, 30)
    #: Whether this product's Product Key format is implemented here.
    supported: bool = True
    notes: str = ""

    def license_id(self, license_type: str, serial: int) -> str:
        return f"{self.license_id_prefix}-{license_type.upper()}-{serial:06d}"


ZENITH_BUSINESS = Product(
    product_id="ZENITH-BUSINESS",
    display_name="Zenith Business",
    key_filename="zenith-business.zkey",
    license_id_prefix="ZB",
)

#: Registered but not yet issuable: D-Clinic has its own key format and its own
#: application, and claiming support before that exists would produce keys that
#: silently do not work. It appears in the product list, greyed out, so the
#: shape is visible and the limitation is honest.
D_CLINIC = Product(
    product_id="D-CLINIC",
    display_name="D-Clinic",
    key_filename="d-clinic.zkey",
    license_id_prefix="DCL",
    supported=False,
    notes="Registered for a future release. D-Clinic uses its own key format, "
          "so this Manager cannot issue for it yet.",
)

CATALOGUE: tuple[Product, ...] = (ZENITH_BUSINESS, D_CLINIC)


def by_id(product_id: str) -> Product | None:
    for product in CATALOGUE:
        if product.product_id == product_id:
            return product
    return None


def supported() -> list[Product]:
    return [p for p in CATALOGUE if p.supported]
