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
    # ---- header --------------------------------------------------------
    "header.user_guest": {LANG_ENGLISH: "Guest", LANG_DARI: "کاربر مهمان"},
    "header.channel_dev": {LANG_ENGLISH: "Development", LANG_DARI: "توسعه"},
    "action.home": {LANG_ENGLISH: "Home", LANG_DARI: "خانه"},
    # ---- contextual command bar ---------------------------------------
    "context.commands": {LANG_ENGLISH: "COMMANDS", LANG_DARI: "اوامر"},
    "context.select_hint": {
        LANG_ENGLISH: "Select a section above to see its commands.",
        LANG_DARI: "برای دیدن اوامر، یک بخش را از بالا انتخاب کنید.",
    },
    # Base data commands
    "cmd.base.persons": {LANG_ENGLISH: "Persons / Accounts", LANG_DARI: "اشخاص / حساب‌ها"},
    "cmd.base.products": {LANG_ENGLISH: "Products", LANG_DARI: "اجناس"},
    "cmd.base.warehouses": {LANG_ENGLISH: "Warehouses", LANG_DARI: "انبارها"},
    "cmd.base.currencies": {LANG_ENGLISH: "Currencies", LANG_DARI: "اسعار"},
    # Sales & purchase commands
    "cmd.sales.sale_invoice": {LANG_ENGLISH: "Sales Invoice", LANG_DARI: "بل فروش"},
    "cmd.sales.sale_return": {LANG_ENGLISH: "Sales Return", LANG_DARI: "برگشت فروش"},
    "cmd.sales.purchase_invoice": {LANG_ENGLISH: "Purchase Invoice", LANG_DARI: "بل خرید"},
    "cmd.sales.purchase_return": {LANG_ENGLISH: "Purchase Return", LANG_DARI: "برگشت خرید"},
    "cmd.sales.quotation": {LANG_ENGLISH: "Quotation", LANG_DARI: "نرخ‌دهی"},
    # Receipts & payments
    "cmd.pay.receipt": {LANG_ENGLISH: "Receipt", LANG_DARI: "رسید"},
    "cmd.pay.payment": {LANG_ENGLISH: "Payment", LANG_DARI: "پرداخت"},
    "cmd.pay.transfer": {LANG_ENGLISH: "Transfer", LANG_DARI: "انتقال"},
    # Funds
    "cmd.funds.cash": {LANG_ENGLISH: "Cash Accounts", LANG_DARI: "صندوق‌ها"},
    "cmd.funds.bank": {LANG_ENGLISH: "Bank Accounts", LANG_DARI: "حساب‌های بانکی"},
    "cmd.funds.exchange": {LANG_ENGLISH: "Currency Exchange", LANG_DARI: "تبادله اسعار"},
    # Account reports
    "cmd.acct.ledger": {LANG_ENGLISH: "General Ledger", LANG_DARI: "دفتر کل"},
    "cmd.acct.trial": {LANG_ENGLISH: "Trial Balance", LANG_DARI: "بیلانس آزمایشی"},
    "cmd.acct.statement": {LANG_ENGLISH: "Account Statement", LANG_DARI: "صورت‌حساب"},
    # Item reports
    "cmd.item.kardex": {LANG_ENGLISH: "Kardex", LANG_DARI: "کاردکس"},
    "cmd.item.stock": {LANG_ENGLISH: "Stock Report", LANG_DARI: "گزارش موجودی"},
    "cmd.item.movement": {LANG_ENGLISH: "Movements", LANG_DARI: "حرکات جنس"},
    # Tools (enabled dev/preview commands)
    "cmd.tools.form_demo": {LANG_ENGLISH: "Form Preview", LANG_DARI: "پیش‌نمایش فورم"},
    "cmd.tools.table_demo": {LANG_ENGLISH: "Table Preview", LANG_DARI: "پیش‌نمایش جدول"},
    "cmd.tools.settings": {LANG_ENGLISH: "Settings", LANG_DARI: "تنظیمات"},
    # ---- home screen ---------------------------------------------------
    "home.system_full": {
        LANG_ENGLISH: "Business Management & Accounting System",
        LANG_DARI: "سیستم مدیریت تجارت و حسابداری",
    },
    "home.readiness": {LANG_ENGLISH: "System Readiness", LANG_DARI: "آمادگی سیستم"},
    "home.ready.database": {LANG_ENGLISH: "Database", LANG_DARI: "دیتابیس"},
    "home.ready.language": {LANG_ENGLISH: "Language", LANG_DARI: "زبان"},
    "home.ready.license": {LANG_ENGLISH: "License", LANG_DARI: "مجوز"},
    "home.ready.version": {LANG_ENGLISH: "Version", LANG_DARI: "نسخه"},
    "home.quick_access": {LANG_ENGLISH: "Quick Access", LANG_DARI: "دسترسی سریع"},
    "home.quick_reserved": {
        LANG_ENGLISH: "Reserved for future modules",
        LANG_DARI: "برای ماژول‌های آینده محفوظ است",
    },
    "home.get_started": {
        LANG_ENGLISH: "Select a section from the top navigation to begin.",
        LANG_DARI: "برای شروع، یک بخش را از نوار بالا انتخاب کنید.",
    },
    # ---- empty / unavailable state ------------------------------------
    "empty.unavailable_title": {
        LANG_ENGLISH: "This module is not available yet",
        LANG_DARI: "این ماژول هنوز در دسترس نیست",
    },
    "empty.unavailable_sub": {
        LANG_ENGLISH: "It will be enabled in a future version of Zenith Business.",
        LANG_DARI: "در نسخه‌ آینده زینت بیزنس فعال خواهد شد.",
    },
    # ---- form demonstration -------------------------------------------
    "formdemo.title": {
        LANG_ENGLISH: "Form Layout — Design Preview",
        LANG_DARI: "چیدمان فورم — پیش‌نمایش دیزاین",
    },
    "formdemo.subtitle": {
        LANG_ENGLISH: "Demonstrates the shared form design language. Not a business form; no data is saved.",
        LANG_DARI: "زبان مشترک دیزاین فورم‌ها را نشان می‌دهد. فورم تجارتی نیست و داده‌ای ذخیره نمی‌شود.",
    },
    "formdemo.section_general": {LANG_ENGLISH: "General", LANG_DARI: "عمومی"},
    "formdemo.section_details": {LANG_ENGLISH: "Details", LANG_DARI: "جزئیات"},
    "formdemo.code": {LANG_ENGLISH: "Code", LANG_DARI: "کود"},
    "formdemo.date": {LANG_ENGLISH: "Date", LANG_DARI: "تاریخ"},
    "formdemo.name": {LANG_ENGLISH: "Name", LANG_DARI: "نام"},
    "formdemo.category": {LANG_ENGLISH: "Category", LANG_DARI: "دسته‌بندی"},
    "formdemo.amount": {LANG_ENGLISH: "Amount", LANG_DARI: "مبلغ"},
    "formdemo.quantity": {LANG_ENGLISH: "Quantity", LANG_DARI: "مقدار"},
    "formdemo.description": {LANG_ENGLISH: "Description", LANG_DARI: "تفصیلات"},
    "formdemo.combo_placeholder": {LANG_ENGLISH: "Select…", LANG_DARI: "انتخاب…"},
    "formdemo.validation": {
        LANG_ENGLISH: "Example: “Name” is required — this is how a field-level error appears.",
        LANG_DARI: "مثال: «نام» الزامی است — خطای سطح فیلد این‌گونه نمایش می‌یابد.",
    },
    "action.save": {LANG_ENGLISH: "Save", LANG_DARI: "ذخیره"},
    "action.cancel": {LANG_ENGLISH: "Cancel", LANG_DARI: "لغو"},
    # ---- table demonstration ------------------------------------------
    "tabledemo.title": {
        LANG_ENGLISH: "Data Table — Design Preview",
        LANG_DARI: "جدول داده‌ها — پیش‌نمایش دیزاین",
    },
    "tabledemo.subtitle": {
        LANG_ENGLISH: "Demonstrates the shared table style with placeholder rows. No business data.",
        LANG_DARI: "سبک مشترک جدول‌ها را با سطرهای نمونه نشان می‌دهد. بدون داده‌ تجارتی.",
    },
    "table.col_code": {LANG_ENGLISH: "Code", LANG_DARI: "کود"},
    "table.col_name": {LANG_ENGLISH: "Name", LANG_DARI: "نام"},
    "table.col_category": {LANG_ENGLISH: "Category", LANG_DARI: "دسته‌بندی"},
    "table.col_date": {LANG_ENGLISH: "Date", LANG_DARI: "تاریخ"},
    "table.col_qty": {LANG_ENGLISH: "Qty", LANG_DARI: "مقدار"},
    "table.col_amount": {LANG_ENGLISH: "Amount", LANG_DARI: "مبلغ"},
    "table.col_status": {LANG_ENGLISH: "Status", LANG_DARI: "وضعیت"},
    "table.status_active": {LANG_ENGLISH: "Active", LANG_DARI: "فعال"},
    "table.status_pending": {LANG_ENGLISH: "Pending", LANG_DARI: "معلق"},
    "table.footer": {
        LANG_ENGLISH: "Sample rows for design illustration only.",
        LANG_DARI: "سطرهای نمونه فقط برای نمایش دیزاین.",
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
