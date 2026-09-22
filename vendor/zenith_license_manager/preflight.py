"""Checks run BEFORE a licence is issued, and again on the licence produced.

Why this module exists
----------------------
A signing key that opens, derives a valid public key and signs correctly can
still be the *wrong key*. Nothing about the key file says which application
build will accept its signatures — so the Manager used to issue licences that
were flawless in every respect except the one that mattered, and the customer
was told their Product Key "is not genuine, or it was changed after it was
issued". The vendor had no way to see the real cause, and neither did the
customer.

Two checks close that, and they answer different questions:

``self_test`` — *may this key issue at all?*
    Asked when a key is unlocked, created or imported. It opens the key, derives
    the public half, signs and verifies a sample, confirms the key file claims
    the right product, and finally compares the public half against the key the
    product's application actually verifies with. A failure here disables
    issuing rather than warning about it, because a warning is something a busy
    person clicks past on the way to producing a broken licence.

``verify_issued`` — *is the licence we just made one this product will accept?*
    Asked on every issue, after signing. It re-reads the finished Product Key
    through the **customer's own parser and verifier**, not the Manager's, and
    checks the signature, the product, the machine binding, the licence type and
    the expiry against what was asked for. Verifying with the code that issued
    it would only prove the Manager agrees with itself.

Both deliberately use ``zenith_business`` code. That is the whole point: the
only verification worth running here is the one the customer will run.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent.parent
if str(_REPO) not in sys.path:                      # pragma: no cover - path setup
    sys.path.insert(0, str(_REPO))

from zenith_business.security import product_key as _pk              # noqa: E402
from zenith_business.security.signatures import (                    # noqa: E402
    backend_available,
    verify,
)
from vendor.zenith_license_manager import keystore                   # noqa: E402
from vendor.zenith_license_manager.products import (                 # noqa: E402
    Product,
    fingerprint,
)

#: The message the vendor sees when the loaded key is not the product's key.
WRONG_KEY_MESSAGE = ("Signing key does not match the Zenith Business "
                     "verification key.")


class PreflightError(Exception):
    """A licence must not be issued, or must not be shown, and why."""


@dataclass(frozen=True)
class Check:
    """One question asked of a signing key, and the answer."""

    name: str
    ok: bool
    detail: str = ""


@dataclass(frozen=True)
class SelfTest:
    """The result of every check, and whether issuing is allowed at all."""

    product_id: str
    checks: tuple[Check, ...] = ()
    public_key_b64: str = ""
    fingerprint: str = "—"
    expected_fingerprint: str = "—"

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks) and bool(self.checks)

    @property
    def failures(self) -> tuple[Check, ...]:
        return tuple(check for check in self.checks if not check.ok)

    @property
    def summary(self) -> str:
        """One line naming the first thing that is wrong, or that all is well."""
        bad = self.failures
        if not self.checks:
            return "No signing key loaded."
        if not bad:
            return "Signing key verified against the product's own key."
        return bad[0].detail or bad[0].name


def self_test(product: Product, seed: bytes | None, *,
              key_product_id: str | None = None) -> SelfTest:
    """Ask whether this key may issue licences for this product.

    ``key_product_id`` is what the key FILE says it is for, read from its
    authenticated header. Passing it lets a D-Clinic key loaded under Zenith
    Business be caught by name as well as by fingerprint.

    Never raises and never returns key material: the caller shows this straight
    on screen, so everything in it is safe to display.
    """
    import base64

    checks: list[Check] = []
    expected_fp = product.expected_fingerprint()

    if seed is None:
        return SelfTest(product_id=product.product_id,
                        checks=(Check("Signing key loaded", False,
                                      "No signing key is unlocked."),),
                        expected_fingerprint=expected_fp)

    checks.append(Check("Signing key loaded", True, "Key file decrypted."))

    if not backend_available():
        checks.append(Check("Crypto backend", False,
                            "No Ed25519 backend is available in this build."))
        return SelfTest(product_id=product.product_id, checks=tuple(checks),
                        expected_fingerprint=expected_fp)
    checks.append(Check("Crypto backend", True, "Ed25519 available."))

    # 1. The private key must yield a usable public key.
    try:
        public = keystore.public_key_for(seed)
    except Exception as exc:
        checks.append(Check("Public key derives", False,
                            f"The private key is not usable: {exc}"))
        return SelfTest(product_id=product.product_id, checks=tuple(checks),
                        expected_fingerprint=expected_fp)
    if len(public) != 32:
        checks.append(Check("Public key derives", False,
                            "The derived public key is not 32 bytes."))
        return SelfTest(product_id=product.product_id, checks=tuple(checks),
                        expected_fingerprint=expected_fp)
    checks.append(Check("Public key derives", True, "32-byte Ed25519 key."))

    public_b64 = base64.b64encode(public).decode("ascii")
    own_fp = fingerprint(public)

    # 2. A signature this key makes must verify under the key it derives.
    sample = b"zenith-license-manager self test"
    try:
        signature = keystore.sign(seed, sample)
        round_trip = verify(public, sample, signature)
    except Exception as exc:                        # pragma: no cover - defensive
        round_trip = False
        checks.append(Check("Sign/verify round-trip", False, f"Signing failed: {exc}"))
    else:
        checks.append(Check(
            "Sign/verify round-trip", round_trip,
            "A test signature verified." if round_trip
            else "This key signs, but its own signature does not verify."))

    # 3. A key filed under one product must not be used for another.
    if key_product_id and key_product_id != product.product_id:
        checks.append(Check(
            "Product", False,
            f"This key file is for {key_product_id}, not "
            f"{product.product_id}."))
    else:
        checks.append(Check("Product", True,
                            f"{product.display_name} ({product.product_id})"))

    # 4. The check the whole module exists for.
    expected = product.expected_public_key()
    if expected is None:
        checks.append(Check(
            "Matches the application's key", False,
            f"{product.display_name} in this build carries no verification "
            "key, so no signing key can be confirmed as the right one."))
    elif expected != public:
        checks.append(Check(
            "Matches the application's key", False,
            f"{WRONG_KEY_MESSAGE} This key is {own_fp}; "
            f"{product.display_name} accepts {expected_fp}."))
    else:
        checks.append(Check("Matches the application's key", True,
                            f"{own_fp} — the key {product.display_name} verifies with."))

    return SelfTest(product_id=product.product_id, checks=tuple(checks),
                    public_key_b64=public_b64, fingerprint=own_fp,
                    expected_fingerprint=expected_fp)


def verify_issued(product: Product, product_key_text: str, *,
                  expect_fingerprint: str, expect_type: str,
                  expect_expiry: str | None) -> None:
    """Re-read a freshly signed Product Key the way the CUSTOMER will.

    Raises :class:`PreflightError` with a technical reason if anything differs.
    The caller must not display, copy or save a key this rejects.
    """
    expected_public = product.expected_public_key()
    if expected_public is None:
        raise PreflightError(
            f"{product.display_name} in this build carries no verification key, "
            "so a generated Product Key cannot be checked before it is shown.")

    # The customer's parser, not ours.
    try:
        decoded = _pk.decode_license(product_key_text)
    except _pk.ProductKeyError as exc:
        raise PreflightError(f"the generated key does not decode: {exc}") from exc

    if not verify(expected_public, decoded.signed_bytes, decoded.signature):
        raise PreflightError(
            "the signature on the generated key does not verify against "
            f"{product.display_name}'s public key ({product.expected_fingerprint()}). "
            "The signing key in use is not the one this build accepts.")

    actual_type = (decoded.license_type or "").upper()
    if actual_type != (expect_type or "").upper():
        raise PreflightError(
            f"licence type is {actual_type!r}, expected {expect_type!r}")

    if (decoded.machine_fingerprint or "").lower() != (expect_fingerprint or "").lower():
        raise PreflightError(
            "the key is bound to the wrong machine: "
            f"{decoded.machine_fingerprint} instead of {expect_fingerprint}")

    actual_expiry = decoded.expires_at or None
    if actual_expiry != (expect_expiry or None):
        raise PreflightError(
            f"expiry is {actual_expiry or 'never'}, expected "
            f"{expect_expiry or 'never'}")

    if actual_type == "DEMO" and not actual_expiry:
        raise PreflightError("a DEMO licence was produced with no expiry date")
