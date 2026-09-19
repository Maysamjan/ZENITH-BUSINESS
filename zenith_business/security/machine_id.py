"""Machine fingerprint for license binding (Stage 10 §8).

The requirement pulls in two directions. Copying the application, the database
and the license file to a second PC must **not** activate it — but a customer
who replaces a failed disk or a network card must **not** be locked out of the
software they paid for.

A single identifier cannot do both, so this module reads several independent
traits and scores how many still match:

=================  ======  ==================================================
Trait              Weight  Why
=================  ======  ==================================================
``machine_guid``        3  Per OS installation. Windows ``MachineGuid`` from
                           the registry; ``/etc/machine-id`` elsewhere. Does
                           not travel with a copied folder.
``volume_serial``       2  Per filesystem — the system drive's serial. Changes
                           if the disk is replaced, not if a NIC is.
``mac``                 1  Primary adapter. Easy to change or spoof, so it only
                           ever contributes, never decides.
``cpu``                 1  Model and core count. Weak on its own: two identical
                           PCs share it.
``hostname``            1  Weak: a user can rename a second PC to match.
=================  ======  ==================================================

A license activates when the score reaches :data:`MATCH_THRESHOLD` (5 of 8).
That number is chosen, not guessed: the three weak traits total 3, so a score of
5 is **unreachable without at least one strong trait**. Two identical PCs with
the same model, the same name and a cloned MAC still fail, because neither the
OS install nor the disk is the same one. Meanwhile a legitimate machine survives
a disk swap (3+1+1) or an OS reinstall that keeps the disk (2+1+1+1).

Every trait is hashed with the product id before it is stored, so a fingerprint
taken here is not a reusable hardware identifier and cannot be correlated with
another product's.
"""

from __future__ import annotations

import hashlib
import os
import platform
import subprocess
import uuid
from dataclasses import dataclass, field

#: Trait name -> weight. The scoring rule above depends on these numbers.
TRAIT_WEIGHTS: dict[str, int] = {
    "machine_guid": 3,
    "volume_serial": 2,
    "mac": 1,
    "cpu": 1,
    "hostname": 1,
}

#: Strong traits, for the "never weak-only" rule documented above.
STRONG_TRAITS = frozenset({"machine_guid", "volume_serial"})

#: Score needed for the same machine. Weak traits total 3, so this cannot be
#: reached without a strong trait matching.
MATCH_THRESHOLD = 5

_TRAIT_LENGTH = 16          # hex characters kept per trait hash
_FINGERPRINT_LENGTH = 32


def _digest(product_id: str, trait: str, value: str, length: int) -> str:
    raw = f"{product_id}\x1f{trait}\x1f{value}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:length]


def _windows_machine_guid() -> str | None:
    try:
        import winreg                                      # Windows only
    except ImportError:
        return None
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r"SOFTWARE\Microsoft\Cryptography", 0,
                             winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
        try:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            return str(value) or None
        finally:
            winreg.CloseKey(key)
    except OSError:
        return None


def _posix_machine_id() -> str | None:
    for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            text = open(path, encoding="utf-8").read().strip()
            if text:
                return text
        except OSError:
            continue
    return None


def _machine_guid() -> str | None:
    return _windows_machine_guid() if os.name == "nt" else _posix_machine_id()


def _windows_volume_serial() -> str | None:
    try:
        import ctypes
        drive = os.environ.get("SystemDrive", "C:") + "\\"
        serial = ctypes.c_ulong(0)
        ok = ctypes.windll.kernel32.GetVolumeInformationW(  # type: ignore[attr-defined]
            ctypes.c_wchar_p(drive), None, 0, ctypes.byref(serial), None, None, None, 0)
        return f"{serial.value:08X}" if ok else None
    except Exception:
        return None


def _posix_volume_serial() -> str | None:
    try:
        result = subprocess.run(["findmnt", "-no", "UUID", "/"],
                                capture_output=True, text=True, timeout=3)
        uuid_text = result.stdout.strip()
        if uuid_text:
            return uuid_text
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        info = os.stat("/")
        return f"{info.st_dev:x}"
    except OSError:
        return None


def _volume_serial() -> str | None:
    return _windows_volume_serial() if os.name == "nt" else _posix_volume_serial()


def _mac() -> str | None:
    node = uuid.getnode()
    # getnode() sets the multicast bit when it had to invent a random address;
    # a random value would change every run and is worse than having no trait.
    if (node >> 40) & 0x01:
        return None
    return f"{node:012x}"


def _cpu() -> str | None:
    parts = [platform.machine(), platform.processor() or ""]
    try:
        parts.append(str(os.cpu_count() or ""))
    except Exception:
        pass
    text = "|".join(p for p in parts if p)
    return text or None


def _hostname() -> str | None:
    return platform.node() or None


_COLLECTORS = {
    "machine_guid": _machine_guid,
    "volume_serial": _volume_serial,
    "mac": _mac,
    "cpu": _cpu,
    "hostname": _hostname,
}


@dataclass(frozen=True)
class MachineIdentity:
    """This computer's traits, already hashed. Contains no raw hardware ids."""

    fingerprint: str
    traits: dict[str, str] = field(default_factory=dict)

    @property
    def short(self) -> str:
        """Human-readable machine id for the License screen, e.g. ``A1B2-C3D4-…``."""
        text = self.fingerprint.upper()
        return "-".join(text[i:i + 4] for i in range(0, min(len(text), 16), 4))


def collect(product_id: str, *, overrides: dict[str, str | None] | None = None
            ) -> MachineIdentity:
    """Read this machine's traits and derive its fingerprint.

    ``overrides`` supplies raw trait values instead of reading the real machine —
    used by tests to simulate a different computer, never by the application.
    """
    raw: dict[str, str | None] = {}
    for name, collector in _COLLECTORS.items():
        if overrides is not None and name in overrides:
            raw[name] = overrides[name]
            continue
        try:
            raw[name] = collector()
        except Exception:
            # A trait that cannot be read is simply absent; it must never stop
            # the application from starting.
            raw[name] = None

    traits = {name: _digest(product_id, name, value, _TRAIT_LENGTH)
              for name, value in raw.items() if value}
    # The fingerprint is the strong traits where they exist, so it stays stable
    # across the weak-trait changes the scoring already tolerates.
    core = "|".join(f"{name}={traits[name]}"
                    for name in sorted(STRONG_TRAITS) if name in traits)
    if not core:
        core = "|".join(f"{name}={traits[name]}" for name in sorted(traits))
    fingerprint = _digest(product_id, "fingerprint", core, _FINGERPRINT_LENGTH)
    return MachineIdentity(fingerprint=fingerprint, traits=traits)


def match_score(licensed: dict[str, str], current: MachineIdentity) -> int:
    """Total weight of the traits that still agree with the licensed machine."""
    score = 0
    for name, weight in TRAIT_WEIGHTS.items():
        want = licensed.get(name)
        if want and current.traits.get(name) == want:
            score += weight
    return score


def is_same_machine(licensed_fingerprint: str, licensed_traits: dict[str, str],
                    current: MachineIdentity) -> bool:
    """True when this computer is the one the license was issued for.

    An exact fingerprint match is decisive. Otherwise the trait score has to
    reach :data:`MATCH_THRESHOLD`, which a machine that merely resembles the
    licensed one cannot do — see the module docstring.
    """
    if licensed_fingerprint and licensed_fingerprint == current.fingerprint:
        return True
    return match_score(licensed_traits or {}, current) >= MATCH_THRESHOLD
