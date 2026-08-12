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
    "list.search": {LANG_ENGLISH: "Search…", LANG_DARI: "جستجو…"},
    "list.rows_count": {LANG_ENGLISH: "6 sample records", LANG_DARI: "۶ رکورد نمونه"},
    # ---- Tools command: Sales Invoice prototype -----------------------
    "cmd.tools.sales_invoice": {
        LANG_ENGLISH: "Sales Invoice (Prototype)",
        LANG_DARI: "بل فروش (پیش‌نمونه)",
    },
    # ---- Sales Invoice prototype --------------------------------------
    "si.title": {LANG_ENGLISH: "Sales Invoice", LANG_DARI: "بل فروش"},
    "si.prototype_badge": {
        LANG_ENGLISH: "PROTOTYPE — visual only, no data is saved",
        LANG_DARI: "پیش‌نمونه — فقط نمایشی، داده‌ای ذخیره نمی‌شود",
    },
    "si.demo_data": {LANG_ENGLISH: "Demonstration data", LANG_DARI: "داده‌های نمایشی"},
    "si.operational": {LANG_ENGLISH: "Operational Info", LANG_DARI: "معلومات عملیاتی"},
    # header
    "si.invoice_no": {LANG_ENGLISH: "Invoice No.", LANG_DARI: "شماره بل"},
    "si.date": {LANG_ENGLISH: "Date", LANG_DARI: "تاریخ"},
    "si.reference": {LANG_ENGLISH: "Reference", LANG_DARI: "مرجع"},
    "si.warehouse": {LANG_ENGLISH: "Warehouse", LANG_DARI: "انبار"},
    "si.salesperson": {LANG_ENGLISH: "Salesperson", LANG_DARI: "فروشنده"},
    "si.currency": {LANG_ENGLISH: "Currency", LANG_DARI: "اسعار"},
    "si.rate": {LANG_ENGLISH: "Exchange Rate", LANG_DARI: "نرخ تبادله"},
    "si.description": {LANG_ENGLISH: "Description", LANG_DARI: "تفصیلات"},
    # customer
    "si.customer": {LANG_ENGLISH: "Customer", LANG_DARI: "مشتری"},
    "si.customer_code": {LANG_ENGLISH: "Customer Code", LANG_DARI: "کود مشتری"},
    "si.customer_name": {LANG_ENGLISH: "Customer Name", LANG_DARI: "نام مشتری"},
    "si.phone": {LANG_ENGLISH: "Phone", LANG_DARI: "تیلیفون"},
    "si.address": {LANG_ENGLISH: "Address", LANG_DARI: "آدرس"},
    "si.prev_balance": {LANG_ENGLISH: "Previous Balance", LANG_DARI: "بیلانس قبلی"},
    "si.credit_limit": {LANG_ENGLISH: "Credit Limit", LANG_DARI: "حد اعتبار"},
    # grid columns
    "si.col_row": {LANG_ENGLISH: "#", LANG_DARI: "#"},
    "si.col_item_code": {LANG_ENGLISH: "Item Code", LANG_DARI: "کود جنس"},
    "si.col_item_name": {LANG_ENGLISH: "Item Name", LANG_DARI: "نام جنس"},
    "si.col_unit": {LANG_ENGLISH: "Unit", LANG_DARI: "واحد"},
    "si.col_qty": {LANG_ENGLISH: "Qty", LANG_DARI: "مقدار"},
    "si.col_price": {LANG_ENGLISH: "Unit Price", LANG_DARI: "قیمت فی واحد"},
    "si.col_discount": {LANG_ENGLISH: "Discount", LANG_DARI: "تخفیف"},
    "si.col_tax": {LANG_ENGLISH: "Tax", LANG_DARI: "مالیه"},
    "si.col_total": {LANG_ENGLISH: "Total", LANG_DARI: "مجموع"},
    "si.col_warehouse": {LANG_ENGLISH: "Warehouse", LANG_DARI: "انبار"},
    # summary
    "si.subtotal": {LANG_ENGLISH: "Subtotal", LANG_DARI: "مجموع فرعی"},
    "si.discount": {LANG_ENGLISH: "Discount", LANG_DARI: "تخفیف"},
    "si.additional": {LANG_ENGLISH: "Additional Expense", LANG_DARI: "مصارف اضافی"},
    "si.tax": {LANG_ENGLISH: "Tax", LANG_DARI: "مالیه"},
    "si.grand_total": {LANG_ENGLISH: "Grand Total", LANG_DARI: "مجموع کل"},
    "si.cash_received": {LANG_ENGLISH: "Cash Received", LANG_DARI: "نقد دریافت‌شده"},
    "si.remaining": {LANG_ENGLISH: "Credit / Remaining", LANG_DARI: "باقی / نسیه"},
    # operational info
    "si.op_stock": {LANG_ENGLISH: "Current Stock", LANG_DARI: "موجودی فعلی"},
    "si.op_last_purchase": {LANG_ENGLISH: "Last Purchase", LANG_DARI: "آخرین خرید"},
    "si.op_last_sale": {LANG_ENGLISH: "Last Sale", LANG_DARI: "آخرین فروش"},
    "si.op_avg_cost": {LANG_ENGLISH: "Average Cost", LANG_DARI: "اوسط قیمت"},
    # rapid-entry UX (Stage 01D)
    "si.item_search_ph": {
        LANG_ENGLISH: "Type item name, code or barcode…",
        LANG_DARI: "نام، کود یا بارکد جنس را تایپ کنید…",
    },
    "si.customer_search_ph": {
        LANG_ENGLISH: "Search customer by name, code or phone…",
        LANG_DARI: "جستجوی مشتری با نام، کود یا تیلیفون…",
    },
    "si.keyboard_hint": {
        LANG_ENGLISH: "Enter next line · ↑ ↓ choose · Enter select · Esc close · Del remove line",
        LANG_DARI: "Enter سطر بعدی · ↑ ↓ انتخاب · Enter تایید · Esc بستن · Del حذف سطر",
    },
    "si.payment": {LANG_ENGLISH: "Payment", LANG_DARI: "پرداخت"},
    "si.pay_cash": {LANG_ENGLISH: "Cash", LANG_DARI: "نقد"},
    "si.pay_credit": {LANG_ENGLISH: "Credit", LANG_DARI: "نسیه"},
    "si.delete_line": {LANG_ENGLISH: "Delete Line", LANG_DARI: "حذف سطر"},
    "si.lines": {LANG_ENGLISH: "Invoice Lines", LANG_DARI: "اقلام بل"},
    "si.default_price": {LANG_ENGLISH: "Default Sale Price", LANG_DARI: "قیمت فروش پیش‌فرض"},
    "si.cost_hidden": {
        LANG_ENGLISH: "Average cost & profit are hidden (permission-gated).",
        LANG_DARI: "قیمت تمام‌شد و مفاد پنهان است (وابسته به اجازه دسترسی).",
    },
    # actions
    "si.act_new": {LANG_ENGLISH: "New", LANG_DARI: "جدید"},
    "si.act_save": {LANG_ENGLISH: "Save", LANG_DARI: "ذخیره"},
    "si.act_save_print": {LANG_ENGLISH: "Save & Print", LANG_DARI: "ذخیره و چاپ"},
    "si.act_print": {LANG_ENGLISH: "Print", LANG_DARI: "چاپ"},
    "si.act_receive": {LANG_ENGLISH: "Receive Cash", LANG_DARI: "دریافت نقد"},
    "si.act_close": {LANG_ENGLISH: "Close", LANG_DARI: "بستن"},
    # ---- Tools command: print preview ---------------------------------
    "cmd.tools.print_preview": {
        LANG_ENGLISH: "Invoice Print Preview", LANG_DARI: "پیش‌نمایش چاپ بل",
    },
    # ---- printed A4 invoice -------------------------------------------
    "print.preview_title": {LANG_ENGLISH: "Print Preview", LANG_DARI: "پیش‌نمایش چاپ"},
    "print.back": {LANG_ENGLISH: "Back to Invoice", LANG_DARI: "بازگشت به بل"},
    "print.title": {LANG_ENGLISH: "SALES INVOICE", LANG_DARI: "بل فروش"},
    "print.bill_to": {LANG_ENGLISH: "Bill To", LANG_DARI: "صورت‌حساب برای"},
    "print.tax_id": {LANG_ENGLISH: "Tax ID", LANG_DARI: "شماره مالیه"},
    "print.email": {LANG_ENGLISH: "Email", LANG_DARI: "ایمیل"},
    "print.col_item": {LANG_ENGLISH: "Item", LANG_DARI: "جنس"},
    "print.paid": {LANG_ENGLISH: "Amount Paid", LANG_DARI: "مبلغ پرداخت‌شده"},
    "print.prepared_by": {LANG_ENGLISH: "Prepared By", LANG_DARI: "تهیه‌کننده"},
    "print.customer_sign": {LANG_ENGLISH: "Customer Signature", LANG_DARI: "امضای مشتری"},
    "print.authorized_sign": {LANG_ENGLISH: "Authorized Signature", LANG_DARI: "امضای مجاز"},
    "print.notes": {LANG_ENGLISH: "Notes / Terms", LANG_DARI: "یادداشت / شرایط"},
    "print.terms_text": {
        LANG_ENGLISH: "Payment due on receipt. Goods sold are subject to the store return policy.",
        LANG_DARI: "پرداخت هنگام دریافت. اجناس فروخته‌شده تابع پالیسی برگشت فروشگاه است.",
    },
    "print.thankyou": {
        LANG_ENGLISH: "Thank you for your business!",
        LANG_DARI: "از خرید شما سپاسگزاریم!",
    },
    "print.demo_note": {
        LANG_ENGLISH: "Demonstration document — company details are placeholders and configurable.",
        LANG_DARI: "سند نمایشی — مشخصات شرکت نمونه و قابل تنظیم است.",
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
