"""Localization & text-direction foundation (Prompt 01 §19, §20).

Goals for Stage 01:
    * Prove that both RTL (Dari) and LTR (English) layouts are supported.
    * Avoid scattering hard-coded user-facing strings through business logic —
      screens ask the translator for keys instead of embedding literals.

This is intentionally lightweight (no external i18n framework). A small
in-memory catalog demonstrates language switching for the shell. Future stages
may migrate to Qt's ``.ts``/``.qm`` tooling behind this same interface without
changing call sites.
"""

from __future__ import annotations

from enum import Enum

from zenith_business.core.config import LANG_DARI, LANG_ENGLISH, SUPPORTED_LANGUAGES


class Direction(str, Enum):
    """UI layout direction."""

    RTL = "rtl"
    LTR = "ltr"


# Languages that read right-to-left.
_RTL_LANGUAGES = {LANG_DARI}


def direction_for_language(language: str) -> Direction:
    """Return the natural text direction for a language code."""
    return Direction.RTL if language in _RTL_LANGUAGES else Direction.LTR


def resolve_direction(language: str, configured: str = "auto") -> Direction:
    """Resolve effective direction from language and a config override.

    ``configured`` may be 'auto' (derive from language), 'rtl', or 'ltr'.
    """
    value = (configured or "auto").lower()
    if value == "rtl":
        return Direction.RTL
    if value == "ltr":
        return Direction.LTR
    return direction_for_language(language)


# Minimal shell catalog. Keys are stable identifiers; values are per-language.
# Only foundation/shell strings live here — no business terminology.
_CATALOG: dict[str, dict[str, str]] = {
    "app.tagline": {
        LANG_ENGLISH: "Business Management System",
        LANG_DARI: "سیستم مدیریت تجارت",
    },
    "menu.base_data": {LANG_ENGLISH: "Base Data", LANG_DARI: "اطلاعات پایه"},
    "menu.buy_sell": {LANG_ENGLISH: "Buy & Sell", LANG_DARI: "خرید و فروش"},
    "menu.receipts_payments": {
        LANG_ENGLISH: "Receipts & Payments",
        LANG_DARI: "دریافت و پرداخت",
    },
    "menu.funds": {LANG_ENGLISH: "Funds", LANG_DARI: "وجوه"},
    "menu.account_reports": {
        LANG_ENGLISH: "Account Reports",
        LANG_DARI: "گزارش حساب‌ها",
    },
    "menu.item_reports": {LANG_ENGLISH: "Item Reports", LANG_DARI: "گزارش اجناس"},
    "menu.tools": {LANG_ENGLISH: "Tools", LANG_DARI: "امکانات برنامه"},
    "menu.language": {LANG_ENGLISH: "Language", LANG_DARI: "زبان"},
    "menu.language.english": {LANG_ENGLISH: "English", LANG_DARI: "انگلیسی"},
    "menu.language.dari": {LANG_ENGLISH: "Dari", LANG_DARI: "دری"},
    "menu.exit": {LANG_ENGLISH: "Exit", LANG_DARI: "خروج"},
    "status.ready": {LANG_ENGLISH: "Ready", LANG_DARI: "آماده"},
    "status.no_company": {
        LANG_ENGLISH: "No company configured",
        LANG_DARI: "هیچ شرکتی تنظیم نشده",
    },
    "status.db_ok": {LANG_ENGLISH: "Database: OK", LANG_DARI: "دیتابیس: سالم"},
    "status.db_unavailable": {
        LANG_ENGLISH: "Database: unavailable",
        LANG_DARI: "دیتابیس: در دسترس نیست",
    },
    "status.unlicensed": {
        LANG_ENGLISH: "Development build (unlicensed)",
        LANG_DARI: "نسخه توسعه (بدون مجوز)",
    },
    "home.placeholder_hint": {
        LANG_ENGLISH: "Modules will appear here as they are enabled.",
        LANG_DARI: "ماژول‌ها با فعال‌سازی در اینجا نمایش داده می‌شوند.",
    },
    "menu.placeholder_note": {
        LANG_ENGLISH: "(not available in this build)",
        LANG_DARI: "(در این نسخه در دسترس نیست)",
    },
}


class Translator:
    """Resolves text keys for the active language.

    Missing keys return the key itself (a visible signal during development),
    never a crash.
    """

    def __init__(self, language: str = LANG_DARI) -> None:
        self._language = language if language in SUPPORTED_LANGUAGES else LANG_DARI

    @property
    def language(self) -> str:
        return self._language

    @property
    def direction(self) -> Direction:
        return direction_for_language(self._language)

    def set_language(self, language: str) -> None:
        if language in SUPPORTED_LANGUAGES:
            self._language = language

    def gettext(self, key: str) -> str:
        entry = _CATALOG.get(key)
        if not entry:
            return key
        return entry.get(self._language) or entry.get(LANG_ENGLISH) or key

    # Short alias mirroring common i18n conventions.
    def t(self, key: str) -> str:  # noqa: D401 - simple alias
        """Alias for :meth:`gettext`."""
        return self.gettext(key)
