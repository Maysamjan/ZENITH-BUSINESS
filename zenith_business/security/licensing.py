"""Licensing architecture boundary (Prompt 01 §26-§28).

Stage 01 does NOT implement licensing. It only reserves a clean extension point
so the future **Licensing, Activation & Application Security Engine** can plug in
without touching UI or business code.

Permanent requirements recorded here for the future engine (do not implement now):
    * Machine-bound, lifetime license. Purchased once; permanent for the approved
      machine. No SaaS/subscription requirement.
    * Copying the installer or the business database must NOT transfer activation.
    * Offline activation flow:
          Customer PC -> Activation Request  ->  Zenith Soft vendor tool
          -> signed Activation Code  ->  import  ->  verify signature +
          device fingerprint  ->  activate.
    * Verification uses ASYMMETRIC signatures. The customer app may embed a
      PUBLIC verification key only. The vendor PRIVATE signing key never ships.
    * Business data and license state are logically separate (see core.paths:
      license lives under the roaming license dir, data under the local data dir).
    * Tolerate reasonable hardware changes; machine transfer controlled by vendor.

This module contains NO cryptographic keys and NO secrets. It provides a Protocol
and a development-only null provider that always reports an unlicensed dev build.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable


class LicenseStatus(str, Enum):
    """Coarse license states the shell can react to."""

    DEVELOPMENT = "development"  # unlicensed dev build (Stage 01)
    UNLICENSED = "unlicensed"
    ACTIVE = "active"
    EXPIRED = "expired"  # reserved; lifetime licenses normally never expire
    INVALID = "invalid"


@dataclass(frozen=True)
class LicenseState:
    """Immutable snapshot of the current license situation."""

    status: LicenseStatus
    #: True only when the app should grant full production access.
    is_activated: bool
    #: Human-readable summary for the status bar (no secrets).
    summary: str


@runtime_checkable
class LicenseProvider(Protocol):
    """Contract the future Licensing Engine will implement.

    Kept intentionally tiny at the boundary. The real engine will add activation
    request/import methods; the shell only needs to *read* current state.
    """

    def current_state(self) -> LicenseState: ...


class DevelopmentLicenseProvider:
    """Development-only provider. Always reports an unlicensed dev build.

    DEVELOPMENT-ONLY: this must never be wired into a production build. It exists
    so the shell can display a truthful status during Stage 01 without faking an
    "activated" state.
    """

    def current_state(self) -> LicenseState:
        return LicenseState(
            status=LicenseStatus.DEVELOPMENT,
            is_activated=False,
            summary="Development build (unlicensed)",
        )
