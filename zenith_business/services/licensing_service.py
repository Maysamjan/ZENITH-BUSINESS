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
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from zenith_business.core.identity import APP_VERSION
from zenith_business.core.logging_setup import get_logger
from zenith_business.security import machine_id as machine
from zenith_business.security import vendor_key
from zenith_business.security.signatures import backend_available, verify
from zenith_business.security.trusted_clock import TrustedClock
from zenith_business.security.license_format import (
    LICENSE_SUFFIX,
    PRODUCT_ID,
    REQUEST_SUFFIX,
    TYPE_DEMO,
    TYPE_FULL,
    LicenseFormatError,
    build_request,
    parse_license,
)

_logger = get_logger("services.licensing")


def parse_any_license(text: str):
    """Read a licence in either shape it may arrive in.

    A ``.zlic`` file and a pasted Product Key carry the same facts and the same
    Ed25519 signature; only the packaging differs. Both are parsed into an
    object exposing the same fields, so :meth:`LicenseService.evaluate` verifies
    and judges them through **one** code path. Two judgement routines for two
    shapes is exactly how a second one ends up missing a check.
    """
    from zenith_business.security import product_key

    if product_key.looks_like_product_key(text):
        return product_key.decode_license(text)
    return parse_license(text)

#: Canonical licence file name inside the licence directory.
LICENSE_FILENAME = f"license{LICENSE_SUFFIX}"

#: Settings key that USED to hold the day an unlicensed installation started its
#: demo. A demo is now a signed licence with its own expiry, so nothing reads
#: this any more; the name is kept so an existing row is recognisable rather
#: than mysterious, and so the audited-settings list keeps working.
DEMO_START_KEY = "license.demo_started_at"


class LicenseStatus(str):
    """Coarse states the application reacts to (string-valued for storage)."""

    FULL = "FULL"
    DEMO = "DEMO"
    DEMO_EXPIRED = "DEMO_EXPIRED"
    INVALID = "INVALID"
    #: No licence file at all. Distinct from INVALID because the customer has
    #: done nothing wrong — they simply have not activated yet.
    UNLICENSED = "UNLICENSED"
    NO_VENDOR_KEY = "NO_VENDOR_KEY"


class LicenseReason(str):
    """Why an evaluation came out the way it did — shown to the customer."""

    OK = "ok"
    NO_LICENSE_FILE = "no_license_file"
    CLOCK_ROLLBACK = "clock_rollback"
    MALFORMED = "malformed"
    BAD_SIGNATURE = "bad_signature"
    WRONG_PRODUCT = "wrong_product"
    WRONG_MACHINE = "wrong_machine"
    EXPIRED = "expired"
    UNKNOWN_TYPE = "unknown_type"
    DEMO_PERIOD_OVER = "demo_period_over"
    NO_VENDOR_KEY = "no_vendor_key"
    NO_BACKEND = "no_crypto_backend"


@dataclass(frozen=True)
class DemoPolicy:
    """What DEMO mode allows. Defined once, here, and read everywhere (§10).

    Expiry restricts **access**, never data: nothing in demo mode deletes a row,
    trims history or rewrites the database. An expired demo shows an activation
    requirement and keeps backup and licence import available, so the customer
    can always take their data with them.

    ``days`` is no longer what *decides* a demo — a DEMO licence carries its own
    signed expiry, so the length is the vendor's to set per customer. It remains
    here as the suggested default for the vendor tool and for wording.
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
    #: True when the system clock was found behind a time already seen.
    clock_rolled_back: bool = False

    @property
    def is_full(self) -> bool:
        return self.status == LicenseStatus.FULL

    @property
    def is_demo(self) -> bool:
        return self.status == LicenseStatus.DEMO

    @property
    def allows_login(self) -> bool:
        """Whether the application may go past the activation screen at all.

        This is the pre-login gate's single question. Everything that is not a
        live FULL or DEMO licence lands on the activation screen — including a
        fresh install that has never been activated, which is not an error and
        is worded as such.
        """
        return self.status in (LicenseStatus.FULL, LicenseStatus.DEMO)

    @property
    def allows_workspace(self) -> bool:
        """Whether the business screens may be opened. Same question as login."""
        return self.allows_login


class LicenseError(Exception):
    """Raised when an action needs an entitlement the installation does not have.

    ``key`` names a catalogue entry so the screen can say this in the language
    the customer is reading. The service deliberately does not translate: it
    would need a translator injected into a layer that has no business holding
    one, and the English ``user_message`` remains as the fallback for callers
    with no catalogue — the log, the self-test and the vendor tool.
    """

    def __init__(self, message: str, *, user_message: str | None = None,
                 key: str | None = None) -> None:
        super().__init__(message)
        self.user_message = user_message or message
        self.key = key


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
        self._clock: TrustedClock | None = None

    # ---- time ------------------------------------------------------------

    @property
    def clock(self) -> TrustedClock:
        """The clock every expiry is judged against — never ``datetime.now``."""
        if self._clock is None:
            self._clock = TrustedClock(
                license_dir=self._dir, settings_repo=self._settings, db=self._db,
                machine_fingerprint=self.machine.fingerprint)
        return self._clock

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

        if not backend_available():
            # No verification backend in this build: refuse rather than assume.
            return LicenseEvaluation(
                status=LicenseStatus.NO_VENDOR_KEY,
                reason=LicenseReason.NO_BACKEND,
                detail="This build cannot verify licences (no crypto backend).",
                **base)

        key = self._public_key()
        if key is None:
            return LicenseEvaluation(
                status=LicenseStatus.NO_VENDOR_KEY,
                reason=LicenseReason.NO_VENDOR_KEY,
                detail="This build has no vendor verification key configured.",
                **base)

        path = self.license_path
        if not path.is_file():
            # NOT demo. A demo is something the vendor issues and signs, like any
            # other licence; the absence of a file is simply an installation that
            # has not been activated, and it stops at the activation screen.
            return LicenseEvaluation(
                status=LicenseStatus.UNLICENSED,
                reason=LicenseReason.NO_LICENSE_FILE,
                detail="This installation has not been activated yet.", **base)

        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            return LicenseEvaluation(status=LicenseStatus.INVALID,
                                     reason=LicenseReason.MALFORMED,
                                     detail=f"License file unreadable: {exc}", **base)

        try:
            lic = parse_any_license(text)
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

        # From here the licence is genuine, so its issue date is a value the
        # vendor signed: it becomes the floor below which no clock is believed.
        clock = self.clock
        clock.set_floor(lic.issued_at)
        reading = clock.read()
        clock.observe(reading.system_now)
        common = dict(
            license_id=lic.license_id, license_type=lic.license_type,
            issued_at=lic.issued_at, issued_to=lic.issued_to,
            expires_at=lic.expires_at, clock_rolled_back=reading.rolled_back, **base)

        expired = bool(lic.expires_at) and self._past(lic.expires_at, reading.now)
        if expired:
            if lic.license_type == TYPE_DEMO:
                # A finished demo is its own state: the customer is not at fault
                # and the screen says "activate", not "invalid".
                return LicenseEvaluation(
                    status=LicenseStatus.DEMO_EXPIRED,
                    reason=LicenseReason.DEMO_PERIOD_OVER,
                    demo_expires_on=lic.expires_at, demo_days_left=0,
                    detail="The demo period has ended. Activate to continue.",
                    **common)
            return LicenseEvaluation(
                status=LicenseStatus.INVALID, reason=LicenseReason.EXPIRED,
                detail="This license has expired.", **common)

        if lic.license_type == TYPE_DEMO:
            left = self._days_left(lic.expires_at, reading.now)
            return LicenseEvaluation(
                status=LicenseStatus.DEMO, reason=LicenseReason.OK,
                demo_expires_on=lic.expires_at, demo_days_left=left,
                detail=(f"Demo — {left} day(s) remaining." if left is not None
                        else "Demo license."),
                **common)

        return LicenseEvaluation(status=LicenseStatus.FULL,
                                 reason=LicenseReason.OK, **common)

    # ---- time ------------------------------------------------------------

    @staticmethod
    def _expiry_moment(value: str) -> datetime | None:
        """Read an expiry that may be a date or a full timestamp.

        A bare date means the **end** of that day: a licence that says it expires
        on the 30th is good all through the 30th, which is what a customer reads
        it to mean.
        """
        raw = (value or "").strip()
        if not raw:
            return None
        # A bare date is handled FIRST. ``datetime.fromisoformat`` happily parses
        # "2026-09-20" as midnight, which would expire the licence at the START
        # of its last day — the opposite of what the date says.
        if len(raw) == 10 and "T" not in raw and " " not in raw:
            try:
                day = date.fromisoformat(raw)
            except ValueError:
                return None
            return datetime.combine(day, time(23, 59, 59), tzinfo=timezone.utc)
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

    @classmethod
    def _past(cls, value: str, now: datetime) -> bool:
        moment = cls._expiry_moment(value)
        if moment is None:
            return True        # an unreadable expiry is treated as expired
        return now > moment

    @classmethod
    def _days_left(cls, value: str | None, now: datetime) -> int | None:
        moment = cls._expiry_moment(value or "")
        if moment is None:
            return None
        return max(0, int((moment - now).total_seconds() // 86400))

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
            left = e.demo_days_left
            return (f"{self._policy.label} · {left} day(s) left" if left is not None
                    else self._policy.label)
        if e.status == LicenseStatus.DEMO_EXPIRED:
            return "Demo expired — activation required"
        if e.status == LicenseStatus.UNLICENSED:
            return "Not activated — activation required"
        if e.status == LicenseStatus.NO_VENDOR_KEY:
            return "Unlicensed build"
        return "License invalid — activation required"

    # ---- activation ------------------------------------------------------

    def business_name(self) -> str:
        """The customer's OWN business name, or an empty string.

        Resolved in one place so the activation screen and the License page can
        never disagree. There is deliberately **no** fallback: printing falls
        back to the product name when a report has no letterhead, which is
        reasonable on paper and wrong here — an activation request that says
        "Zenith Business", or carries a name from the sample data, tells the
        vendor something untrue about who is asking. Unset stays unset.
        """
        for reader in (self._company_row_name, self._company_setting_name):
            try:
                value = (reader() or "").strip()
            except Exception:
                value = ""
            if value:
                return value
        return ""

    def _company_row_name(self) -> str:
        if self._db is None:
            return ""
        row = self._db.connection().execute(
            "SELECT display_name, legal_name FROM companies ORDER BY id LIMIT 1"
        ).fetchone()
        if row is None:
            return ""
        return str(row["display_name"] or row["legal_name"] or "")

    def _company_setting_name(self) -> str:
        if self._settings is None:
            return ""
        return str(self._settings.get("company.name") or "")

    def create_activation_request(self, target: Path | str, *,
                                  business_name: str | None = None) -> Path:
        """Write a ``.zreq`` for the vendor. Contains no secrets and no business data."""
        me = self.machine
        if business_name is None:
            business_name = self.business_name()
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

    def request_code(self) -> str:
        """The code the customer copies and sends to the vendor.

        Same content as a ``.zreq`` — this machine's fingerprint and hashed
        traits, no secrets and no business data — in one pasteable line.
        """
        from zenith_business.security import product_key

        me = self.machine
        return product_key.encode_request(fingerprint=me.fingerprint,
                                          traits=me.traits)

    def import_product_key(self, text: str) -> LicenseEvaluation:
        """Activate from a pasted Product Key.

        Held to exactly the same bar as a licence file: decoded, then put
        through the full evaluation — signature, product, type, machine, expiry
        — and stored only if it comes back FULL or DEMO. A key that fails leaves
        the installation on whatever licence it already had.
        """
        from zenith_business.security import product_key
        from zenith_business.security.product_key import ProductKeyError

        candidate = " ".join((text or "").split())
        if not candidate:
            raise LicenseError("No product key was entered.",
                               user_message="Please paste your product key.",
                               key="act.err_key_empty")
        # Say what is actually wrong with the paste before treating it as a
        # licence. Falling through to the file parser produced "License file is
        # not valid JSON", which tells a customer who pasted their own request
        # code back nothing they can act on.
        if not product_key.looks_like_product_key(candidate):
            squashed = "".join(candidate.split()).upper()
            if squashed.startswith(product_key.REQUEST_PREFIX + "-"):
                raise LicenseError(
                    "A request code was pasted where a product key belongs.",
                    user_message="That is your request code — the code you send "
                                 "to Zenith Soft. Paste the product key they "
                                 "send back, which starts with ZB1-.",
                    key="act.err_request_pasted")
            raise LicenseError(
                "Text pasted is not a product key.",
                user_message="That does not look like a product key. A product "
                             "key starts with ZB1- and is one long line.",
                key="act.err_not_a_key")
        try:
            evaluation = self._evaluate_text(candidate)
        except ProductKeyError as exc:
            self._record("license.import_failed", "bad product key")
            raise LicenseError(f"Product key rejected: {exc}",
                               user_message=str(exc), key="act.err_key_damaged")
        if evaluation.status not in (LicenseStatus.FULL, LicenseStatus.DEMO):
            self._record("license.import_failed", f"reason={evaluation.reason}")
            # The reason already has its own sentence on the activation screen,
            # so name it rather than duplicating the wording here.
            raise LicenseError(
                f"Product key rejected: {evaluation.reason}",
                user_message=evaluation.detail or "This product key was rejected.",
                key=f"act.reason_{evaluation.reason}")

        self._dir.mkdir(parents=True, exist_ok=True)
        temporary = self.license_path.with_suffix(".tmp")
        temporary.write_text(candidate, encoding="utf-8")
        os.replace(temporary, self.license_path)
        self._record("license.activated",
                     f"id={evaluation.license_id} type={evaluation.license_type}"
                     " via=product_key")
        _logger.info("Activated by product key: %s (%s)", evaluation.license_id,
                     evaluation.license_type)
        return self.evaluate()

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
            # The candidate is judged against the REAL clock, not a fresh one in
            # the temporary folder. Otherwise an expired licence could be walked
            # in past a rolled-back system clock simply because the probe could
            # not see the high-water mark.
            probe._clock = self.clock
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
