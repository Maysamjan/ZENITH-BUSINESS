"""A clock a demo period cannot be cheated out of (Stage 10 final §2).

``datetime.now()`` is whatever the person at the keyboard set it to. On a single
offline PC that is the whole attack: set Windows back three weeks and a 30-day
demo runs forever. Nothing in a licence file can fix that, because a signature
proves what the vendor wrote, not what time it is now.

So the application remembers the **latest moment it has ever seen** and never
believes a time earlier than that:

    trusted_now() = max(system clock, high-water mark)

Moving the clock **forward** advances the high-water mark and cannot be undone —
you can end your own demo early, which nobody wants to do. Moving it **back**
changes nothing: the mark is already ahead, so the demo neither gains days nor
loses them. That is the exact behaviour the brief asks for.

Where the mark is kept, and why in three places
-----------------------------------------------
Each store defeats a different careless attack, and the highest value of the
three wins, so deleting any one of them does not reset anything:

``license/clock.state``  a protected file beside the licence. On Windows it is
                         sealed with **DPAPI** (``CryptProtectData``), so it is
                         bound to this Windows account and cannot be moved to
                         another PC or hand-edited. Elsewhere, and if DPAPI is
                         unavailable, it carries an HMAC keyed by the machine
                         fingerprint — see the honesty note below.
``app_settings`` row     inside the business database, so wiping the licence
                         folder does not reset the mark.
licence ``issued_at``    a floor that is *signed*. Even with both stores gone,
                         time cannot be rolled back before the vendor issued the
                         licence, because that date is covered by the signature.

Honest limits
-------------
This raises the cost of a clock rollback; it does not make one impossible. A
local Administrator can delete both stores, and on a machine where DPAPI is not
available the HMAC key is derived from traits of that same machine, so someone
who reads the code can recompute it. What survives every one of those is the
signed floor: a licence cannot be used before it was issued. Anti-rollback on a
fully offline PC whose owner has Administrator rights is a cost problem, never a
proof, and pretending otherwise would be the dishonest part.

**No customer data is involved.** This module reads and writes its own small
state file and one settings row. A failure anywhere in it is logged and ignored:
a clock that cannot be read must never stop a business from opening its books.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from zenith_business.core.logging_setup import get_logger

_logger = get_logger("security.clock")

#: File holding the protected high-water mark, beside the licence.
STATE_FILENAME = "clock.state"

#: Settings key mirroring the mark inside the database.
HIGH_WATER_KEY = "license.clock_high_water"

#: Slack before a backwards jump is called a rollback rather than clock drift.
#: NTP corrections and a laptop waking up are seconds; this is generous enough
#: to never cry wolf and far too small to matter to a demo measured in days.
TOLERANCE_SECONDS = 120

#: Entropy mixed into DPAPI so the blob is bound to this application's purpose.
_DPAPI_ENTROPY = b"zenith-business-trusted-clock-v1"

_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _parse(text: str | None) -> datetime | None:
    if not text:
        return None
    raw = str(text).strip()
    try:
        return datetime.strptime(raw, _TIME_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _format(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime(_TIME_FORMAT)


# ---------------------------------------------------------------------------
# sealing the state file
# ---------------------------------------------------------------------------


def _dpapi_available() -> bool:
    return os.name == "nt"


def _dpapi(protect: bool, data: bytes) -> bytes | None:
    """Call CryptProtectData / CryptUnprotectData. None if unavailable."""
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class Blob(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD),
                        ("pbData", ctypes.POINTER(ctypes.c_char))]

        def to_blob(raw: bytes) -> Blob:
            buffer = ctypes.create_string_buffer(raw, len(raw))
            return Blob(len(raw), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))

        crypt32 = ctypes.windll.crypt32                    # type: ignore[attr-defined]
        kernel32 = ctypes.windll.kernel32                  # type: ignore[attr-defined]
        source = to_blob(data)
        entropy = to_blob(_DPAPI_ENTROPY)
        result = Blob()
        function = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
        ok = function(ctypes.byref(source), None, ctypes.byref(entropy),
                      None, None, 0, ctypes.byref(result))
        if not ok:
            return None
        try:
            return ctypes.string_at(result.pbData, result.cbData)
        finally:
            kernel32.LocalFree(result.pbData)
    except Exception:                                      # pragma: no cover - Windows
        _logger.warning("DPAPI unavailable; falling back to a keyed digest.")
        return None


def _fallback_key(machine_fingerprint: str) -> bytes:
    return hashlib.sha256(
        (_DPAPI_ENTROPY.decode() + "|" + (machine_fingerprint or "")).encode("utf-8")
    ).digest()


def _seal(payload: bytes, machine_fingerprint: str) -> bytes:
    sealed = _dpapi(True, payload)
    if sealed is not None:
        return b"DPAPI1\x00" + sealed
    tag = hmac.new(_fallback_key(machine_fingerprint), payload, hashlib.sha256).digest()
    return b"HMAC01\x00" + tag + payload


def _unseal(blob: bytes, machine_fingerprint: str) -> bytes | None:
    if blob.startswith(b"DPAPI1\x00"):
        return _dpapi(False, blob[7:])
    if blob.startswith(b"HMAC01\x00"):
        body = blob[7:]
        if len(body) <= 32:
            return None
        tag, payload = body[:32], body[32:]
        expected = hmac.new(_fallback_key(machine_fingerprint), payload,
                            hashlib.sha256).digest()
        return payload if hmac.compare_digest(tag, expected) else None
    return None


# ---------------------------------------------------------------------------
# the clock
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClockReading:
    """What the clock believes, and whether it caught the system lying."""

    now: datetime
    system_now: datetime
    high_water: datetime | None
    rolled_back: bool
    #: Seconds the system clock is behind the high-water mark (0 when it is not).
    behind_seconds: int = 0

    @property
    def detail(self) -> str:
        if not self.rolled_back:
            return "System clock accepted."
        return (f"System clock is {self.behind_seconds // 3600}h behind a time this "
                f"installation has already seen; using the later time.")


class TrustedClock:
    """Monotonic-by-memory time for licence and demo decisions."""

    def __init__(self, *, license_dir: Path | str, settings_repo=None, db=None,
                 machine_fingerprint: str = "") -> None:
        self._dir = Path(license_dir)
        self._settings = settings_repo
        self._db = db
        self._machine = machine_fingerprint
        self._floor: datetime | None = None

    # ---- the signed floor ------------------------------------------------

    def set_floor(self, issued_at: str | None) -> None:
        """Never accept a time before the licence was issued (a signed value)."""
        self._floor = _parse(issued_at)

    # ---- reading ---------------------------------------------------------

    @property
    def state_path(self) -> Path:
        return self._dir / STATE_FILENAME

    def _from_file(self) -> datetime | None:
        try:
            blob = self.state_path.read_bytes()
        except OSError:
            return None
        payload = _unseal(blob, self._machine)
        if payload is None:
            # Present but not ours: someone replaced or edited it. Treated as
            # absent rather than trusted, and said out loud in the log.
            _logger.warning("The clock state file did not authenticate; ignoring it.")
            return None
        try:
            return _parse(json.loads(payload.decode("utf-8")).get("high_water"))
        except Exception:
            return None

    def _from_settings(self) -> datetime | None:
        if self._settings is None:
            return None
        try:
            return _parse(self._settings.get(HIGH_WATER_KEY))
        except Exception:
            return None

    def high_water(self) -> datetime | None:
        """The latest moment any store remembers, floor included."""
        candidates = [c for c in (self._from_file(), self._from_settings(), self._floor)
                      if c is not None]
        return max(candidates) if candidates else None

    def read(self) -> ClockReading:
        """What time it is, as far as this installation is willing to believe."""
        system_now = datetime.now(timezone.utc)
        mark = self.high_water()
        if mark is None:
            return ClockReading(system_now, system_now, None, False)
        behind = int((mark - system_now).total_seconds())
        if behind > TOLERANCE_SECONDS:
            return ClockReading(mark, system_now, mark, True, behind)
        return ClockReading(max(system_now, mark), system_now, mark, False)

    def now(self) -> datetime:
        return self.read().now

    # ---- writing ---------------------------------------------------------

    def observe(self, moment: datetime | None = None) -> datetime | None:
        """Record that this moment has been seen. Returns the new mark.

        Only ever moves forward. Called at startup and whenever the licence is
        re-evaluated, so simply using the program advances the mark.
        """
        seen = (moment or datetime.now(timezone.utc)).astimezone(timezone.utc)
        mark = self.high_water()
        if mark is not None and mark >= seen:
            return mark
        self._write(seen)
        return seen

    def _write(self, moment: datetime) -> None:
        text = _format(moment)
        payload = json.dumps({"high_water": text, "product": "ZENITH-BUSINESS"},
                             separators=(",", ":")).encode("utf-8")
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            staged = self.state_path.with_name(STATE_FILENAME + ".writing")
            staged.write_bytes(_seal(payload, self._machine))
            os.replace(staged, self.state_path)
        except OSError:
            _logger.warning("Could not write the protected clock state.")
        if self._settings is None:
            return
        try:
            if self._db is not None:
                with self._db.transaction():
                    self._settings.set(HIGH_WATER_KEY, text)
            else:
                self._settings.set(HIGH_WATER_KEY, text)
        except Exception:
            _logger.warning("Could not mirror the clock state into settings.")
