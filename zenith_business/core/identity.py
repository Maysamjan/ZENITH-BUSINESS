"""Application identity — the single source of truth for brand/product/version.

Master Spec §6 and Prompt 01 §6 require identity strings to be defined centrally
and never duplicated across UI files. Import from here everywhere.
"""

from __future__ import annotations

from dataclasses import dataclass

# Brand / product identity.
COMPANY_NAME: str = "Zenith Soft"
PRODUCT_NAME: str = "Zenith Business"
PRODUCT_TAGLINE: str = "Business Management System"

# Semantic version. 0.x during development (Prompt 01 §6).
APP_VERSION: str = "0.1.0"

# A short, filesystem/registry-safe slug used for data directory names.
APP_SLUG: str = "ZenithBusiness"

# Development lifecycle marker. Never treat "development" state as licensed
# production; the future Licensing Engine owns that decision.
BUILD_CHANNEL: str = "development"


@dataclass(frozen=True)
class AppIdentity:
    """Immutable snapshot of the application's identity."""

    company: str = COMPANY_NAME
    product: str = PRODUCT_NAME
    tagline: str = PRODUCT_TAGLINE
    version: str = APP_VERSION
    slug: str = APP_SLUG
    channel: str = BUILD_CHANNEL

    @property
    def title(self) -> str:
        """Window/title-bar friendly string, e.g. 'Zenith Business 0.1.0'."""
        return f"{self.product} {self.version}"

    @property
    def full_title(self) -> str:
        """Fully qualified title, e.g. 'Zenith Business 0.1.0 — Zenith Soft'."""
        return f"{self.product} {self.version} — {self.company}"


#: Shared, ready-to-use identity instance.
IDENTITY = AppIdentity()
