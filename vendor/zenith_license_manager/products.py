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

import base64
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path

# The Manager lives beside the applications in the repository but is never
# packaged with them. Importing the customer side here is deliberate: the key a
# product's application VERIFIES with is the one fact this Manager must not be
# allowed to guess, so it is read from the application itself rather than copied
# into a constant that would drift the first time a build was re-keyed.
_REPO = Path(__file__).resolve().parent.parent.parent
if str(_REPO) not in sys.path:                      # pragma: no cover - path setup
    sys.path.insert(0, str(_REPO))

from zenith_business.security import vendor_key as _zb_vendor_key   # noqa: E402


def fingerprint(public_key: bytes | str | None) -> str:
    """A short, readable name for a public key, for humans comparing two.

    SHA-256 over the raw 32 bytes, first 8 shown in groups of four. Comparing
    ``9F2C-41A0-…`` by eye is something a person can actually do; comparing two
    44-character base64 blobs is something a person only believes they did.
    """
    raw = _as_raw(public_key)
    if raw is None:
        return "—"
    digest = hashlib.sha256(raw).hexdigest().upper()
    return "-".join(digest[i:i + 4] for i in range(0, 16, 4))


def _as_raw(public_key: bytes | str | None) -> bytes | None:
    """Accept raw bytes or base64 and return the 32 raw bytes, or None."""
    if public_key is None:
        return None
    if isinstance(public_key, bytes):
        return public_key if len(public_key) == 32 else None
    text = (public_key or "").strip()
    if not text:
        return None
    try:
        raw = base64.b64decode(text.encode("ascii"), validate=True)
    except Exception:
        return None
    return raw if len(raw) == 32 else None


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

    # ---- the key the PRODUCT verifies with -------------------------------
    #
    # A signing key that is merely "a valid Ed25519 key" is not good enough. It
    # has to be the counterpart of the public key the shipped application checks
    # against, and nothing about a key file says whether it is. Every licence
    # issued under the wrong one looks perfect here and is refused there, with a
    # message that blames the customer's copy of the key.

    def expected_public_key(self) -> bytes | None:
        """The public key this product's shipped build verifies with.

        Read from the application, not stored here, so the two cannot disagree.
        ``None`` means that build carries no key, and then no signing key can be
        confirmed as the right one.
        """
        if self.product_id == "ZENITH-BUSINESS":
            return _zb_vendor_key.public_key()
        return None

    def expected_fingerprint(self) -> str:
        return fingerprint(self.expected_public_key())

    def key_matches(self, public_key: bytes | None) -> bool:
        """Is this the signing key whose licences the product will accept?"""
        expected = self.expected_public_key()
        raw = _as_raw(public_key)
        return bool(expected) and raw is not None and raw == expected


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
