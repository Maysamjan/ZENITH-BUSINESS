"""Licensing — the customer side, and the only place a licence is judged (Stage 10 §7, §9).

Every question about entitlement goes through :meth:`LicenseService.evaluate`,
which re-reads the licence file and re-checks it. There is deliberately **no**
"activated = True" computed once at startup: a single boolean is a single place
to defeat, and the owner's brief rules it out explicitly. Callers ask
:meth:`state`, :meth:`is_full`, :meth:`demo_days_left` or :meth:`require_full`,
and each of those runs the same evaluation.

What is checked, in order, and why the order matters
---------------------------------------------------
1. **Is there a vendor key?** Without one nothing can be verified, and the build
   says so rather than accepting anything.
2. **Is there a licence file?** No file is not an error — it is DEMO.
3. **Does it parse?** A truncated or edited file is INVALID, not "ignore it".
4. **Is the signature valid over the canonical payload?** This is the gate the
   other checks depend on: the product id, the machine and the expiry are only
   worth reading *because* a signature proves the vendor wrote them. Checking
   them first would let an attacker's values steer the logic.
5. **Is it this product?** A licence for another Zenith product is not valid here.
6. **Is it this machine?** See :mod:`zenith_business.security.machine_id`.
7. **Has it expired?** Only where an expiry was issued.

Customer data is never touched by any of this. A licence that fails leaves the
database exactly as it was: this module reads files and reports a state, and the
harshest thing the application does with an invalid licence is refuse to open
the workspace — backup and activation stay reachable, so a customer can always
protect and recover their own data (§6, §10).
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from zenith_business.core.identity import APP_VERSION
from zenith_business.core.logging_setup import get_logger
from zenith_business.security import machine_id as machine
from zenith_business.security import vendor_key
from zenith_business.security.ed25519_verify import verify
from zenith_business.security.license_format import (
    LICENSE_SUFFIX,
    PRODUCT_ID,
    REQUEST_SUFFIX,
    TYPE_DEMO,
    TYPE_FULL,
    LicenseFile,
    LicenseFormatError,
    build_request,
    parse_license,
)

_logger = get_logger("services.licensing")

#: Canonical licence file name inside the licence directory.
LICENSE_FILENAME = f"license{LICENSE_SUFFIX}"

#: Settings key holding the day demo mode began on this installation.
DEMO_START_KEY = "license.demo_started_at"


class LicenseStatus(str):
    """Coarse states the application reacts to (string-valued for storage)."""

    FULL = "FULL"
    DEMO = "DEMO"
    DEMO_EXPIRED = "DEMO_EXPIRED"
    INVALID = "INVALID"
    NO_VENDOR_KEY = "NO_VENDOR_KEY"


class LicenseReason(str):
    """Why an evaluation came out the way it did — shown to the customer."""

    OK = "ok"
    NO_LICENSE_FILE = "no_license_file"
    MALFORMED = "malformed"
    BAD_SIGNATURE = "bad_signature"
    WRONG_PRODUCT = "wrong_product"
    WRONG_MACHINE = "wrong_machine"
    EXPIRED = "expired"
    UNKNOWN_TYPE = "unknown_type"
    DEMO_PERIOD_OVER = "demo_period_over"
    NO_VENDOR_KEY = "no_vendor_key"


@dataclass(frozen=True)
class DemoPolicy:
    """What DEMO mode allows. Defined once, here, and read everywhere (§10).

    Expiry restricts **access**, never data: nothing in demo mode deletes a row,
    trims history or rewrites the database. An expired demo shows an activation
    requirement and keeps backup and licence import available, so the customer
    can always take their data with them.
    """

    days: int = 30
    #: Shown on screen so the limit is never a surprise.
    label: str = "DEMO"

    def expiry_date(self, started_on: date) -> date:
        return started_on + timedelta(days=self.days)


DEFAULT_DEMO_POLICY = DemoPolicy()


@dataclass(frozen=True)
class LicenseEvaluation:
    """The full answer, re-computed on every ask."""

    status: str
    reason: str
    machine_id: str
    machine_short: str
    license_id: str = ""
    license_type: str = ""
    issued_at: str = ""
    issued_to: str = ""
    expires_at: str | None = None
    demo_expires_on: str | None = None
    demo_days_left: int | None = None
    detail: str = ""

    @property
    def is_full(self) -> bool:
        return self.status == LicenseStatus.FULL

    @property
    def is_demo(self) -> bool:
        return self.status == LicenseStatus.DEMO

    @property
    def allows_workspace(self) -> bool:
        """Whether the business screens may be opened at all.

        An invalid or expired licence still leaves backup and activation
        reachable — see the module docstring.
        """
        return self.status in (LicenseStatus.FULL, LicenseStatus.DEMO)


class LicenseError(Exception):
    """Raised when an action needs an entitlement the installation does not have."""

    def __init__(self, message: str, *, user_message: str | None = None) -> None:
        super().__init__(message)
        self.user_message = user_message or message


class LicenseService:
    """Reads, verifies and reports licence state. Never writes business data."""

    def __init__(self, *, license_dir: Path | str, settings_repo=None, audit=None,
                 db=None, public_key: bytes | None = None,
                 demo_policy: DemoPolicy = DEFAULT_DEMO_POLICY,
                 machine_overrides: dict[str, str | None] | None = None) -> None:
        self._dir = Path(license_dir)
        self._settings = settings_repo
        self._audit = audit
        self._db = db
        self._explicit_key = public_key
        self._policy = demo_policy
        self._machine_overrides = machine_overrides
        self._machine: machine.MachineIdentity | None = None

    # ---- machine ---------------------------------------------------------

    @property
    def machine(self) -> machine.MachineIdentity:
        if self._machine is None:
            self._machine = machine.collect(PRODUCT_ID,
                                            overrides=self._machine_overrides)
        return self._machine

    def forget_machine(self) -> None:
        """Drop the cached fingerprint (tests simulating a different PC)."""
        self._machine = None

    # ---- key -------------------------------------------------------------

    def _public_key(self) -> bytes | None:
        return self._explicit_key if self._explicit_key is not None else vendor_key.public_key()

    @property
    def license_path(self) -> Path:
        return self._dir / LICENSE_FILENAME

    # ---- the single evaluation ------------------------------------------

    def evaluate(self) -> LicenseEvaluation:
        """Re-read and re-check the licence. The only place this is decided."""
        me = self.machine
        base = {"machine_id": me.fingerprint, "machine_short": me.short}

        key = self._public_key()
        if key is None:
            return LicenseEvaluation(
                status=LicenseStatus.NO_VENDOR_KEY,
                reason=LicenseReason.NO_VENDOR_KEY,
                detail="This build has no vendor verification key configured.",
                **base)

        path = self.license_path
        if not path.is_file():
            return self._demo_evaluation(LicenseReason.NO_LICENSE_FILE, base)

        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            return LicenseEvaluation(status=LicenseStatus.INVALID,
                                     reason=LicenseReason.MALFORMED,
                                     detail=f"License file unreadable: {exc}", **base)

        try:
            lic = parse_license(text)
        except LicenseFormatError as exc:
            return LicenseEvaluation(status=LicenseStatus.INVALID,
                                     reason=LicenseReason.MALFORMED,
                                     detail=str(exc), **base)

        # The signature is checked BEFORE any payload value is trusted.
        if not verify(key, lic.signed_bytes, lic.signature):
            return LicenseEvaluation(
                status=LicenseStatus.INVALID, reason=LicenseReason.BAD_SIGNATURE,
                detail="The license signature does not match its contents.", **base)

        if lic.product_id != PRODUCT_ID:
            return LicenseEvaluation(
                status=LicenseStatus.INVALID, reason=LicenseReason.WRONG_PRODUCT,
                license_id=lic.license_id,
                detail=f"This license is for {lic.product_id!r}.", **base)

        if lic.license_type not in (TYPE_FULL, TYPE_DEMO):
            return LicenseEvaluation(
                status=LicenseStatus.INVALID, reason=LicenseReason.UNKNOWN_TYPE,
                license_id=lic.license_id,
                detail=f"Unknown license type {lic.license_type!r}.", **base)

        if not machine.is_same_machine(lic.machine_fingerprint, lic.machine_traits, me):
            return LicenseEvaluation(
                status=LicenseStatus.INVALID, reason=LicenseReason.WRONG_MACHINE,
                license_id=lic.license_id, license_type=lic.license_type,
                detail="This license was issued for a different computer.", **base)

        if lic.expires_at and self._past(lic.expires_at):
            return LicenseEvaluation(
                status=LicenseStatus.INVALID, reason=LicenseReason.EXPIRED,
                license_id=lic.license_id, license_type=lic.license_type,
                issued_at=lic.issued_at, issued_to=lic.issued_to,
                expires_at=lic.expires_at,
                detail="This license has expired.", **base)

        if lic.license_type == TYPE_DEMO:
            return self._demo_evaluation(LicenseReason.OK, base, lic=lic)

        return LicenseEvaluation(
            status=LicenseStatus.FULL, reason=LicenseReason.OK,
            license_id=lic.license_id, license_type=TYPE_FULL,
            issued_at=lic.issued_at, issued_to=lic.issued_to,
            expires_at=lic.expires_at, **base)

    # ---- demo ------------------------------------------------------------

    def _demo_started_on(self) -> date:
        """The day this installation first ran without a full licence."""
        today = date.today()
        if self._settings is None:
            return today
        stored = self._settings.get(DEMO_START_KEY)
        if stored:
            try:
                return date.fromisoformat(stored[:10])
            except ValueError:
                pass
        # First sighting: remember it, so the demo period cannot be reset by
        # restarting the application.
        try:
            if self._db is not None:
                with self._db.transaction():
                    self._settings.set(DEMO_START_KEY, today.isoformat())
            else:
                self._settings.set(DEMO_START_KEY, today.isoformat())
        except Exception:                       # never block startup over this
            _logger.warning("Could not record the demo start date.")
        return today

    def _demo_evaluation(self, reason: str, base: dict,
                         lic: LicenseFile | None = None) -> LicenseEvaluation:
        started = self._demo_started_on()
        expires = self._policy.expiry_date(started)
        days_left = (expires - date.today()).days
        expired = days_left < 0
        return LicenseEvaluation(
            status=LicenseStatus.DEMO_EXPIRED if expired else LicenseStatus.DEMO,
            reason=LicenseReason.DEMO_PERIOD_OVER if expired else reason,
            license_id=lic.license_id if lic else "",
            license_type=TYPE_DEMO,
            issued_at=lic.issued_at if lic else "",
            issued_to=lic.issued_to if lic else "",
            demo_expires_on=expires.isoformat(),
            demo_days_left=max(days_left, 0),
            detail=("The demo period has ended. Activate to continue."
                    if expired else f"Demo — {max(days_left, 0)} day(s) remaining."),
            **base)

    @staticmethod
    def _past(iso_date: str) -> bool:
        try:
            return date.fromisoformat(iso_date[:10]) < date.today()
        except ValueError:
            return True        # an unreadable expiry is treated as expired

    # ---- convenience reads (each one re-evaluates) -----------------------

    def state(self) -> LicenseEvaluation:
        return self.evaluate()

    def is_full(self) -> bool:
        return self.evaluate().is_full

    def allows_workspace(self) -> bool:
        return self.evaluate().allows_workspace

    def require_full(self, feature: str) -> None:
        """Raise unless this installation is fully licensed."""
        evaluation = self.evaluate()
        if not evaluation.is_full:
            raise LicenseError(
                f"{feature} requires a full license ({evaluation.status}).",
                user_message="This feature requires an activated license.")

    def summary(self) -> str:
        """One line for the status bar."""
        e = self.evaluate()
        if e.status == LicenseStatus.FULL:
            return f"Licensed · {e.license_id}" if e.license_id else "Licensed"
        if e.status == LicenseStatus.DEMO:
            return f"{self._policy.label} · {e.demo_days_left} day(s) left"
        if e.status == LicenseStatus.DEMO_EXPIRED:
            return "Demo expired — activation required"
        if e.status == LicenseStatus.NO_VENDOR_KEY:
            return "Unlicensed build"
        return "License invalid — activation required"

    # ---- activation ------------------------------------------------------

    def create_activation_request(self, target: Path | str, *,
                                  business_name: str | None = None) -> Path:
        """Write a ``.zreq`` for the vendor. Contains no secrets and no business data."""
        me = self.machine
        path = Path(target)
        # A directory — existing or not — means "put the request in here under its
        # own name". Without the suffix test, a caller passing a folder that does
        # not exist yet would silently produce an extension-less file that the
        # vendor tool would not recognise as an activation request.
        if path.is_dir() or path.suffix == "":
            path = path / f"zenith-activation-{me.fingerprint[:12]}{REQUEST_SUFFIX}"
        elif path.suffix.lower() != REQUEST_SUFFIX:
            path = path.with_suffix(REQUEST_SUFFIX)
        text = build_request(
            machine_fingerprint=me.fingerprint, machine_traits=me.traits,
            app_version=APP_VERSION,
            requested_at=datetime.now().replace(microsecond=0).isoformat(),
            request_id=uuid.uuid4().hex, business_name=business_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self._record("license.request_created", f"file={path.name}")
        _logger.info("Activation request written: %s", path)
        return path

    def import_license(self, source: Path | str) -> LicenseEvaluation:
        """Validate a candidate ``.zlic`` and install it **only if it is good**.

        The existing licence is replaced only after the candidate has passed the
        full evaluation, so importing a bad file can never take a working
        installation down. Nothing here touches the business database.
        """
        source = Path(source)
        try:
            text = source.read_text(encoding="utf-8")
        except OSError as exc:
            self._record("license.import_failed", f"unreadable: {source.name}")
            raise LicenseError(f"Cannot read {source}: {exc}",
                               user_message="That license file could not be read.")

        evaluation = self._evaluate_text(text)
        if evaluation.status not in (LicenseStatus.FULL, LicenseStatus.DEMO):
            self._record("license.import_failed",
                         f"file={source.name} reason={evaluation.reason}")
            raise LicenseError(
                f"License rejected: {evaluation.reason}",
                user_message=evaluation.detail or "This license file was rejected.")

        self._dir.mkdir(parents=True, exist_ok=True)
        # Write beside the target and move into place, so a failure part-way
        # through cannot leave a half-written licence behind.
        temporary = self.license_path.with_suffix(".tmp")
        temporary.write_text(text, encoding="utf-8")
        os.replace(temporary, self.license_path)
        self._record("license.activated",
                     f"id={evaluation.license_id} type={evaluation.license_type}")
        _logger.info("License imported: %s (%s)", evaluation.license_id,
                     evaluation.license_type)
        return self.evaluate()

    def _evaluate_text(self, text: str) -> LicenseEvaluation:
        """Evaluate candidate text without installing it — same rules as :meth:`evaluate`."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            probe = LicenseService(
                license_dir=tmp, settings_repo=self._settings, db=self._db,
                public_key=self._explicit_key, demo_policy=self._policy,
                machine_overrides=self._machine_overrides)
            probe._machine = self._machine
            (Path(tmp) / LICENSE_FILENAME).write_text(text, encoding="utf-8")
            return probe.evaluate()

    # ---- audit -----------------------------------------------------------

    def _record(self, action: str, details: str) -> None:
        """Audit a licensing event. Failure here must never break licensing."""
        if self._audit is None:
            return
        try:
            if self._db is not None:
                with self._db.transaction():
                    self._audit.record(action=action, details=details)
            else:
                self._audit.record(action=action, details=details)
        except Exception:
            _logger.warning("Could not write the %s audit entry.", action)
