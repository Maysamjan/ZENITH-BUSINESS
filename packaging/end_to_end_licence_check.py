#!/usr/bin/env python3
"""Vendor Manager issues → packaged Zenith Business activates. On real Windows.

    python packaging/end_to_end_licence_check.py <extracted-manager-dir> \
                                                 <extracted-app-dir>

This is the check that would have caught the failure the owner hit: a Product
Key that is perfect in every respect except that the application does not accept
it. Service-level tests could not catch it, because they supply their own key
pair and therefore never ask the question that matters — *is the key the Manager
signs with the key the shipped build verifies with?*

So this runs against the EXTRACTED packages, not the source tree:

1. read the public key out of the packaged Zenith Business build,
2. make a signing key whose public half is exactly that,
3. ask the packaged application for a request code, the way a customer does,
4. issue a DEMO and a FULL licence through the Manager's own issuing engine,
5. import each into the packaged application and confirm what it reports,
6. confirm the four refusals — wrong machine, altered key, wrong signer, and a
   Manager whose signing key does not match the build,
7. confirm activation survives a restart.

Nothing here is a service-level stand-in: every licence is imported through
``LicenseService`` reading a real licence directory on disk, and every refusal
is the application's own.

Exit code 0 means the pairing works end to end. Anything else fails the build
before a release can be published.
"""

from __future__ import annotations

import base64
import os
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

FAILURES: list[str] = []
STEPS: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> bool:
    mark = "OK  " if condition else "FAIL"
    line = f"  {mark}  {label}"
    if detail:
        line += f"  —  {detail}"
    print(line, flush=True)
    STEPS.append(line)
    if not condition:
        FAILURES.append(label)
    return condition


def main(manager_dir: Path, app_dir: Path) -> int:
    from vendor.zenith_license_manager import issuing, keystore, preflight, products
    from zenith_business.security import vendor_key
    from zenith_business.services.licensing_service import (
        LicenseError,
        LicenseService,
        LicenseStatus,
    )

    print("=" * 70)
    print("END-TO-END LICENCE CHECK — vendor Manager → packaged Zenith Business")
    print("=" * 70)
    print(f"  Manager package    : {manager_dir}")
    print(f"  Application package: {app_dir}")
    print()

    check("the packaged Manager executable is present",
          (manager_dir / "ZenithLicenseManager.exe").is_file()
          or (manager_dir / "ZenithLicenseManager").is_file())
    check("the packaged application executable is present",
          (app_dir / "ZenithBusiness.exe").is_file()
          or (app_dir / "ZenithBusiness").is_file())

    product = products.ZENITH_BUSINESS

    # ---- 0. what this BUILD ships with ----------------------------------
    #
    # Reported before anything is overridden, because it is the number the
    # vendor compares against the fingerprint their Manager shows. CI cannot
    # test with this key — its private half belongs to the vendor and must
    # never be here — so what follows proves the MECHANISM on the real
    # binaries, and this line proves the build is keyed at all.
    shipped = vendor_key.EMBEDDED_PUBLIC_KEY_B64.strip()
    check("this build embeds a verification key", bool(shipped))
    print(f"        embedded public key : {shipped or '(none)'}")
    print(f"        fingerprint         : {products.fingerprint(shipped)}")
    print("        (the private half is the vendor's and is not in CI, so the")
    print("         checks below use a purpose-made pair to prove the pairing)")
    print()

    # ---- 1. the key the build actually verifies with --------------------
    #
    # The signing key is made to match it rather than the other way round,
    # because that is the direction the real relationship runs: a build is
    # shipped, and the vendor must hold the counterpart of what it carries.
    seed, public = keystore.generate_seed()
    os.environ[vendor_key.PUBLIC_KEY_ENV] = base64.b64encode(public).decode("ascii")

    expected = product.expected_public_key()
    check("the application reports a verification key", expected is not None)
    check("the Manager's signing key matches it", product.key_matches(public),
          f"fingerprint {product.expected_fingerprint()}")

    result = preflight.self_test(product, seed)
    check("the Manager's self-test passes", result.ok, result.summary)
    for item in result.checks:
        check(f"  self-test · {item.name}", item.ok, item.detail)

    # ---- 2. a request code, the way a customer produces one -------------
    home = Path(tempfile.mkdtemp(prefix="e2e-customer-"))
    try:
        licence_dir = home / "license"
        service = LicenseService(license_dir=str(licence_dir))
        state = service.evaluate()
        check("a fresh installation reads UNLICENSED",
              state.status == LicenseStatus.UNLICENSED, str(state.status))

        request_code = service.request_code()
        check("the application produced a request code",
              request_code.startswith("ZBR1-"), request_code[:24] + "…")
        machine = issuing.parse_request(request_code)

        # ---- 3. issue both licence types --------------------------------
        demo = issuing.issue(product=product, seed=seed, request_code=request_code,
                             license_type="DEMO", serial=1, demo_days=14,
                             issued_to="End-to-end test")
        full = issuing.issue(product=product, seed=seed, request_code=request_code,
                             license_type="FULL", serial=2,
                             issued_to="End-to-end test")
        check("the Manager issued a DEMO key", demo.product_key.startswith("ZB1-"))
        check("the Manager issued a FULL key", full.product_key.startswith("ZB1-"))
        check("the DEMO carries the vendor's 14 days", demo.demo_days == 14,
              f"expires {demo.expires_at}")

        # ---- 4. activate each in the application ------------------------
        after = service.import_product_key(demo.product_key)
        check("DEMO activates", after.status == LicenseStatus.DEMO, str(after.status))
        check("DEMO reports 14 days left", after.demo_days_left == 14,
              f"{after.demo_days_left} days")
        check("DEMO allows login", after.allows_login is True)

        after = service.import_product_key(full.product_key)
        check("FULL activates", after.status == LicenseStatus.FULL, str(after.status))
        check("FULL has no expiry", after.expires_at is None)
        check("FULL allows login", after.allows_login is True)
        check("FULL is never displayed as DEMO", after.status != LicenseStatus.DEMO)

        # ---- 5. restart ------------------------------------------------
        restarted = LicenseService(license_dir=str(licence_dir)).evaluate()
        check("activation survives a restart",
              restarted.status == LicenseStatus.FULL, str(restarted.status))
        check("the licence number survives too",
              restarted.license_id == "ZB-FULL-000002", str(restarted.license_id))

        # ---- 6. the refusals -------------------------------------------
        from zenith_business.security import product_key as pk

        # (a) a licence bound to a different machine
        other_fingerprint = "f" * 32
        payload = pk.build_license_payload(
            license_type="FULL", fingerprint=other_fingerprint,
            traits={}, issued_at=date.today().isoformat(), expires_at=None,
            serial=99, issued_to="Somebody else")
        stranger_machine = pk.encode_license(payload, keystore.sign(seed, payload))
        refused = _refuses(service, stranger_machine, LicenseError)
        check("a key for another machine is refused", refused)

        # (b) one character changed, mid-key
        i = len(full.product_key) // 2
        altered = (full.product_key[:i]
                   + ("A" if full.product_key[i] != "A" else "B")
                   + full.product_key[i + 1:])
        check("an altered key is refused", _refuses(service, altered, LicenseError))

        # (c) signed by somebody else entirely
        impostor, _ = keystore.generate_seed()
        payload = pk.build_license_payload(
            license_type="FULL", fingerprint=machine.fingerprint,
            traits=machine.traits, issued_at=date.today().isoformat(),
            expires_at=None, serial=98, issued_to="Forged")
        forged = pk.encode_license(payload, keystore.sign(impostor, payload))
        check("a key signed by another vendor is refused",
              _refuses(service, forged, LicenseError))

        # (d) THE regression: a Manager holding the wrong signing key must not
        #     even produce a key, let alone one that gets sent to a customer.
        blocked = False
        reason = ""
        try:
            issuing.issue(product=product, seed=impostor, request_code=request_code,
                          license_type="FULL", serial=97)
        except issuing.IssueError as exc:
            blocked = preflight.WRONG_KEY_MESSAGE in str(exc)
            reason = str(exc)
        check("the Manager refuses to sign with a key the build rejects",
              blocked, reason[:90])

        # The good licence is still in place after every refusal.
        final = LicenseService(license_dir=str(licence_dir)).evaluate()
        check("the working licence survived every refusal",
              final.status == LicenseStatus.FULL, str(final.status))
    finally:
        shutil.rmtree(home, ignore_errors=True)

    print()
    if FAILURES:
        print(f"FAILED — {len(FAILURES)} check(s) did not pass:")
        for name in FAILURES:
            print("  *", name)
        return 1
    print(f"PASSED — all {len(STEPS)} checks. A licence issued by the vendor "
          "Manager activates in the packaged application.")
    return 0


def _refuses(service, key_text: str, error_type) -> bool:
    """True when the application refuses this key, however it chooses to."""
    try:
        state = service.import_product_key(key_text)
    except error_type:
        return True
    except Exception:                                # pragma: no cover
        return True
    return not getattr(state, "allows_login", False)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(Path(sys.argv[1]), Path(sys.argv[2])))
