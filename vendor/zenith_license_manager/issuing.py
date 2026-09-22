"""Turning a request code into a signed licence (Vendor Manager §1, §2, §4).

This is the only place a signature is produced. It imports the **customer-side
codec** on purpose: `zenith_business.security.product_key` decides the exact
bytes a licence is packed into, and both sides calling the same function is what
makes "the key the vendor signed is the key the customer verifies" true rather
than hopeful. Two independent packers would drift on the first field anybody
added.

What the Manager contributes on top of the codec is the part a customer must
never have: the private key, and the decision of what to put in the licence —
which machine, which type, and for a demo, how many days.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# The Manager lives beside the application in the repository but is never
# packaged with it; this makes the codec importable when running from source.
_REPO = Path(__file__).resolve().parent.parent.parent
if str(_REPO) not in sys.path:                      # pragma: no cover - path setup
    sys.path.insert(0, str(_REPO))

from zenith_business.security import product_key                     # noqa: E402
from zenith_business.security.license_format import (                # noqa: E402
    LICENSE_FORMAT,
    canonical_bytes,
)
from vendor.zenith_license_manager import keystore                   # noqa: E402
from vendor.zenith_license_manager import preflight                  # noqa: E402
from vendor.zenith_license_manager.products import Product           # noqa: E402


class IssueError(Exception):
    """The licence could not be issued, with a reason the vendor can act on."""


@dataclass(frozen=True)
class IssuedLicense:
    """Everything one issue produced, for display, history and export."""

    product_id: str
    license_id: str
    license_type: str
    serial: int
    machine_fingerprint: str
    machine_short: str
    issued_to: str
    phone: str
    city: str
    notes: str
    issued_at: str
    expires_at: str | None
    product_key: str
    created_at: str

    @property
    def is_demo(self) -> bool:
        return self.license_type == "DEMO"

    @property
    def demo_days(self) -> int | None:
        if not self.expires_at:
            return None
        try:
            return (date.fromisoformat(self.expires_at)
                    - date.fromisoformat(self.issued_at)).days
        except ValueError:
            return None


def parse_request(text: str):
    """Read a customer's request code, or say why it cannot be read.

    A checksum failure is reported as such rather than as a machine id: issuing
    a licence against a mangled code would bind it to a computer that does not
    exist, and the customer would be told their own machine is the wrong one.
    """
    try:
        return product_key.decode_request(text)
    except product_key.ProductKeyError as exc:
        raise IssueError(str(exc)) from exc


def expiry_for(license_type: str, *, days: int | None, explicit: str | None,
               issued_at: str) -> str | None:
    """Work out the expiry date, with the vendor's choice taking precedence."""
    if explicit:
        try:
            date.fromisoformat(explicit)
        except ValueError as exc:
            raise IssueError(f"{explicit!r} is not a date (YYYY-MM-DD).") from exc
        return explicit
    if license_type.upper() != "DEMO":
        return None                     # FULL has no expiry unless one is given
    if not days or days < 1:
        raise IssueError("A demo licence needs a length in days.")
    try:
        start = date.fromisoformat(issued_at)
    except ValueError:
        start = date.today()
    return (start + timedelta(days=days)).isoformat()


def issue(*, product: Product, seed: bytes, request_code: str, license_type: str,
          serial: int, issued_to: str = "", phone: str = "", city: str = "",
          notes: str = "", demo_days: int | None = None,
          expires_at: str | None = None, issued_at: str | None = None,
          license_id: str | None = None) -> IssuedLicense:
    """Sign one licence and return it. The seed is used here and nowhere else."""
    if not product.supported:
        raise IssueError(f"{product.display_name} cannot be issued by this "
                         f"version. {product.notes}")
    license_type = (license_type or "").upper()
    if license_type not in product.types:
        raise IssueError(f"{product.display_name} has no {license_type!r} licence.")

    # The signing key must be the one the product's application verifies with.
    # This is checked HERE rather than only in the interface, because an issue
    # made from a script or a test would otherwise skip it — and a licence
    # signed by the wrong key is indistinguishable from a good one until it
    # reaches the customer, where it is refused as "not genuine".
    check = preflight.self_test(product, seed)
    if not check.ok:
        raise IssueError(check.summary)

    request = parse_request(request_code)
    issued_at = issued_at or date.today().isoformat()
    expiry = expiry_for(license_type, days=demo_days, explicit=expires_at,
                        issued_at=issued_at)

    payload = product_key.build_license_payload(
        license_type=license_type, fingerprint=request.fingerprint,
        traits=request.traits, issued_at=issued_at, expires_at=expiry,
        serial=int(serial), issued_to=issued_to)
    key = product_key.encode_license(payload, keystore.sign(seed, payload))

    # Read the finished key back through the CUSTOMER's parser and verifier
    # before anyone can see it. A key that fails here is never returned, so it
    # cannot be copied, saved, recorded in the history or sent to anybody.
    try:
        preflight.verify_issued(product, key, expect_fingerprint=request.fingerprint,
                                expect_type=license_type, expect_expiry=expiry)
    except preflight.PreflightError as exc:
        raise IssueError(
            "The license was signed but failed verification, so it has not "
            f"been issued. Technical reason: {exc}") from exc

    return IssuedLicense(
        product_id=product.product_id,
        license_id=license_id or product.license_id(license_type, serial),
        license_type=license_type, serial=int(serial),
        machine_fingerprint=request.fingerprint,
        machine_short=request.machine_short,
        issued_to=issued_to, phone=phone, city=city, notes=notes,
        issued_at=issued_at, expires_at=expiry, product_key=key,
        created_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))


def write_zlic(issued: IssuedLicense, seed: bytes, target: Path | str) -> Path:
    """Also write the licence as a ``.zlic`` file — the advanced fallback.

    Signed separately over the JSON payload, because the two formats commit to
    different bytes. Both carry the same facts and both are verified the same
    way by the application; the file exists for the case a long code is mangled
    in transit, which a file cannot be.
    """
    import base64
    import json

    payload = {
        "product_id": issued.product_id,
        "license_id": issued.license_id,
        "license_type": issued.license_type,
        "issued_to": issued.issued_to,
        "issued_at": issued.issued_at,
        "machine": {"fingerprint": issued.machine_fingerprint,
                    "traits": _traits_from_key(issued.product_key)},
    }
    if issued.expires_at:
        payload["expires_at"] = issued.expires_at
    signature = keystore.sign(seed, canonical_bytes(payload))
    document = {"format": LICENSE_FORMAT, "payload": payload,
                "signature": base64.b64encode(signature).decode("ascii")}

    target = Path(target)
    if target.is_dir() or target.suffix == "":
        target = target / f"{issued.license_id}.zlic"
    elif target.suffix.lower() != ".zlic":
        target = target.with_suffix(".zlic")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document, indent=2, sort_keys=True,
                                 ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def _traits_from_key(key_text: str) -> dict[str, str]:
    """The traits already packed into the product key, so both formats agree."""
    try:
        return dict(product_key.decode_license(key_text).machine_traits)
    except product_key.ProductKeyError:      # pragma: no cover - we just made it
        return {}
