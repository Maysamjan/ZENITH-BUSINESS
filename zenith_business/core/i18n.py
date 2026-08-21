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
    # ---- home dashboard (Stage 01F) -----------------------------------
    "dash.title": {LANG_ENGLISH: "Dashboard", LANG_DARI: "داشبورد"},
    "dash.demo": {LANG_ENGLISH: "Demonstration data", LANG_DARI: "داده‌های نمایشی"},
    "dash.today_sales": {LANG_ENGLISH: "Today's Sales", LANG_DARI: "فروش امروز"},
    "dash.today_purchases": {LANG_ENGLISH: "Today's Purchases", LANG_DARI: "خرید امروز"},
    "dash.cash": {LANG_ENGLISH: "Cash Balance", LANG_DARI: "موجودی نقد"},
    "dash.receivables": {LANG_ENGLISH: "Receivables", LANG_DARI: "طلبات"},
    "dash.payables": {LANG_ENGLISH: "Payables", LANG_DARI: "بدهی‌ها"},
    "dash.profit": {LANG_ENGLISH: "Today's Profit", LANG_DARI: "مفاد امروز"},
    "dash.low_stock": {LANG_ENGLISH: "Low Stock", LANG_DARI: "موجودی کم"},
    "dash.quick": {LANG_ENGLISH: "Quick Actions", LANG_DARI: "اقدامات سریع"},
    "dash.new_sale": {LANG_ENGLISH: "New Sale", LANG_DARI: "فروش جدید"},
    "dash.new_purchase": {LANG_ENGLISH: "New Purchase", LANG_DARI: "خرید جدید"},
    "dash.receive": {LANG_ENGLISH: "Receive Payment", LANG_DARI: "دریافت پول"},
    "dash.pay": {LANG_ENGLISH: "Make Payment", LANG_DARI: "پرداخت پول"},
    "dash.new_expense": {LANG_ENGLISH: "New Expense", LANG_DARI: "مصرف جدید"},
    "dash.recent": {LANG_ENGLISH: "Recent Transactions", LANG_DARI: "معاملات اخیر"},
    "dash.col_time": {LANG_ENGLISH: "Time", LANG_DARI: "زمان"},
    "dash.col_type": {LANG_ENGLISH: "Type", LANG_DARI: "نوع"},
    "dash.col_party": {LANG_ENGLISH: "Party", LANG_DARI: "طرف حساب"},
    "dash.col_amount": {LANG_ENGLISH: "Amount", LANG_DARI: "مبلغ"},
    "dash.col_status": {LANG_ENGLISH: "Status", LANG_DARI: "وضعیت"},
    "dash.col_item": {LANG_ENGLISH: "Item", LANG_DARI: "جنس"},
    "dash.col_stock": {LANG_ENGLISH: "Stock", LANG_DARI: "موجودی"},
    "dash.t_sale": {LANG_ENGLISH: "Sale", LANG_DARI: "فروش"},
    "dash.t_purchase": {LANG_ENGLISH: "Purchase", LANG_DARI: "خرید"},
    "dash.t_receipt": {LANG_ENGLISH: "Receipt", LANG_DARI: "رسید"},
    "dash.t_expense": {LANG_ENGLISH: "Expense", LANG_DARI: "مصرف"},
    "dash.st_paid": {LANG_ENGLISH: "Paid", LANG_DARI: "پرداخت‌شده"},
    "dash.st_credit": {LANG_ENGLISH: "Credit", LANG_DARI: "نسیه"},
    "dash.st_out": {LANG_ENGLISH: "Out", LANG_DARI: "تمام‌شده"},
    "dash.st_low": {LANG_ENGLISH: "Low", LANG_DARI: "کم"},
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
    "si.updated_balance": {LANG_ENGLISH: "Updated Balance", LANG_DARI: "مانده جدید"},
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
    "print.paper": {LANG_ENGLISH: "Paper", LANG_DARI: "کاغذ"},
    "print.orientation": {LANG_ENGLISH: "Portrait", LANG_DARI: "عمودی"},
    "print.language": {LANG_ENGLISH: "Language", LANG_DARI: "زبان"},
    "print.zoom": {LANG_ENGLISH: "Zoom", LANG_DARI: "بزرگ‌نمایی"},
    "print.fit_width": {LANG_ENGLISH: "Fit Width", LANG_DARI: "عرض صفحه"},
    "print.fit_page": {LANG_ENGLISH: "Fit Page", LANG_DARI: "کل صفحه"},
    "print.title": {LANG_ENGLISH: "SALES INVOICE", LANG_DARI: "بل فروش"},
    "print.bill_to": {LANG_ENGLISH: "Bill To", LANG_DARI: "صورت‌حساب برای"},
    "print.tax_id": {LANG_ENGLISH: "Tax ID", LANG_DARI: "شماره مالیه"},
    "print.email": {LANG_ENGLISH: "Email", LANG_DARI: "ایمیل"},
    "print.col_item": {LANG_ENGLISH: "Item", LANG_DARI: "جنس"},
    "print.paid": {LANG_ENGLISH: "Amount Paid", LANG_DARI: "مبلغ پرداخت‌شده"},
    "print.amount_words": {LANG_ENGLISH: "AMOUNT IN WORDS", LANG_DARI: "مبلغ به حروف"},
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
    # ---- authentication: login & initial setup (Stage 02) -------------
    "auth.brand_tagline": {
        LANG_ENGLISH: "Business Management & Accounting System",
        LANG_DARI: "سیستم مدیریت تجارت و حسابداری",
    },
    "auth.lang_en": {LANG_ENGLISH: "EN", LANG_DARI: "EN"},
    "auth.lang_fa": {LANG_ENGLISH: "دری", LANG_DARI: "دری"},
    "login.title": {LANG_ENGLISH: "Sign In", LANG_DARI: "ورود به سیستم"},
    "login.subtitle": {
        LANG_ENGLISH: "Enter your credentials to continue.",
        LANG_DARI: "برای ادامه، اطلاعات کاربری خود را وارد کنید.",
    },
    "login.username": {LANG_ENGLISH: "Username", LANG_DARI: "نام کاربری"},
    "login.password": {LANG_ENGLISH: "Password", LANG_DARI: "رمز عبور"},
    "login.username_ph": {
        LANG_ENGLISH: "Enter your username", LANG_DARI: "نام کاربری خود را وارد کنید",
    },
    "login.password_ph": {
        LANG_ENGLISH: "Enter your password", LANG_DARI: "رمز عبور خود را وارد کنید",
    },
    "login.show": {LANG_ENGLISH: "Show", LANG_DARI: "نمایش"},
    "login.hide": {LANG_ENGLISH: "Hide", LANG_DARI: "پنهان"},
    "login.signin": {LANG_ENGLISH: "Sign In", LANG_DARI: "ورود"},
    "login.signing_in": {LANG_ENGLISH: "Signing in…", LANG_DARI: "در حال ورود…"},
    "login.error_invalid": {
        LANG_ENGLISH: "Incorrect username or password.",
        LANG_DARI: "نام کاربری یا رمز عبور نادرست است.",
    },
    "login.error_required": {
        LANG_ENGLISH: "Please enter your username and password.",
        LANG_DARI: "لطفاً نام کاربری و رمز عبور را وارد کنید.",
    },
    "login.footer": {
        LANG_ENGLISH: "Zenith Soft · Secure offline access",
        LANG_DARI: "زینت سافت · دسترسی امن آفلاین",
    },
    # ---- developer (Zenith Soft) brand panel on the login screen ----------
    "brand.company": {LANG_ENGLISH: "ZENITH SOFT", LANG_DARI: "زینیت سافت"},
    "brand.kind": {
        LANG_ENGLISH: "Software Development Company",
        LANG_DARI: "شرکت توسعه نرم‌افزار",
    },
    "brand.phone_label": {LANG_ENGLISH: "Phone", LANG_DARI: "شماره تماس"},
    "brand.email_label": {LANG_ENGLISH: "Email", LANG_DARI: "ایمیل"},
    "brand.address_label": {LANG_ENGLISH: "Address", LANG_DARI: "آدرس"},
    "brand.address_value": {
        LANG_ENGLISH: "Qala-e-Fatullah, 3rd Street, Kabul, Afghanistan",
        LANG_DARI: "کابل، قلعه فتح‌الله، سرک سوم",
    },
    "brand.product_lead": {
        LANG_ENGLISH: "The complete desktop solution for your business.",
        LANG_DARI: "راه‌حل کامل دسکتاپ برای کسب‌وکار شما.",
    },
    "login.version": {LANG_ENGLISH: "Version", LANG_DARI: "نسخه"},
    "login.licence": {LANG_ENGLISH: "Licence", LANG_DARI: "جواز"},
    "login.licence_dev": {
        LANG_ENGLISH: "Offline desktop edition",
        LANG_DARI: "نسخه دسکتاپ آفلاین",
    },
    # initial administrator setup
    "setup.title": {LANG_ENGLISH: "Welcome — Create Administrator",
                    LANG_DARI: "خوش آمدید — ایجاد مدیر سیستم"},
    "setup.subtitle": {
        LANG_ENGLISH: "This is the first run. Create the administrator account to secure the system.",
        LANG_DARI: "این نخستین اجرا است. برای ایمن‌سازی سیستم، حساب مدیر را بسازید.",
    },
    "setup.company": {LANG_ENGLISH: "Business Name", LANG_DARI: "نام تجارت"},
    "setup.company_ph": {LANG_ENGLISH: "e.g. Zenith Trading Co.", LANG_DARI: "مثال: شرکت تجارتی زینت"},
    "setup.fullname": {LANG_ENGLISH: "Your Full Name", LANG_DARI: "نام کامل شما"},
    "setup.fullname_ph": {LANG_ENGLISH: "e.g. Ahmad Zahir", LANG_DARI: "مثال: احمد ظاهر"},
    "setup.username": {LANG_ENGLISH: "Administrator Username", LANG_DARI: "نام کاربری مدیر"},
    "setup.password": {LANG_ENGLISH: "Password", LANG_DARI: "رمز عبور"},
    "setup.confirm": {LANG_ENGLISH: "Confirm Password", LANG_DARI: "تکرار رمز عبور"},
    "setup.password_hint": {
        LANG_ENGLISH: "At least 8 characters. Avoid common words.",
        LANG_DARI: "حداقل ۸ حرف. از کلمات عمومی خودداری کنید.",
    },
    "setup.create": {LANG_ENGLISH: "Create Administrator", LANG_DARI: "ایجاد مدیر"},
    "setup.created": {
        LANG_ENGLISH: "Administrator created. Please sign in.",
        LANG_DARI: "مدیر ساخته شد. لطفاً وارد شوید.",
    },
    "setup.error_mismatch": {
        LANG_ENGLISH: "The two passwords do not match.",
        LANG_DARI: "دو رمز عبور یکسان نیستند.",
    },
    # main window identity / logout (Stage 02)
    "app.logout": {LANG_ENGLISH: "Sign Out", LANG_DARI: "خروج از حساب"},
    "app.role": {LANG_ENGLISH: "Role", LANG_DARI: "نقش"},
    # ---- Stage 03 master-data framework -------------------------------
    "md.new": {LANG_ENGLISH: "New", LANG_DARI: "جدید"},
    "md.search": {LANG_ENGLISH: "Search…", LANG_DARI: "جستجو…"},
    "md.refresh": {LANG_ENGLISH: "Refresh", LANG_DARI: "تازه‌سازی"},
    "md.actions": {LANG_ENGLISH: "Actions", LANG_DARI: "اقدامات"},
    "md.edit": {LANG_ENGLISH: "Edit", LANG_DARI: "ویرایش"},
    "md.view": {LANG_ENGLISH: "View Account", LANG_DARI: "دفتر حساب"},
    # -- account settings (round 2 §12) --
    "acct.title": {LANG_ENGLISH: "Account Settings", LANG_DARI: "تنظیمات حساب"},
    "acct.nav": {LANG_ENGLISH: "My Account", LANG_DARI: "حساب من"},
    "acct.change_password": {LANG_ENGLISH: "Change Password", LANG_DARI: "تغییر رمز عبور"},
    "acct.change_username": {LANG_ENGLISH: "Change Username", LANG_DARI: "تغییر نام کاربری"},
    "acct.current_password": {LANG_ENGLISH: "Current Password", LANG_DARI: "رمز عبور فعلی"},
    "acct.new_password": {LANG_ENGLISH: "New Password", LANG_DARI: "رمز عبور جدید"},
    "acct.confirm_password": {LANG_ENGLISH: "Confirm New Password", LANG_DARI: "تکرار رمز عبور جدید"},
    "acct.new_username": {LANG_ENGLISH: "New Username", LANG_DARI: "نام کاربری جدید"},
    "acct.update_password": {LANG_ENGLISH: "Update Password", LANG_DARI: "بروزرسانی رمز"},
    "acct.update_username": {LANG_ENGLISH: "Update Username", LANG_DARI: "بروزرسانی نام کاربری"},
    "acct.err_mismatch": {LANG_ENGLISH: "New passwords do not match.",
                          LANG_DARI: "رمزهای عبور جدید مطابقت ندارند."},
    "acct.ok_password": {LANG_ENGLISH: "Password updated.", LANG_DARI: "رمز عبور بروزرسانی شد."},
    "acct.ok_username": {LANG_ENGLISH: "Username updated.", LANG_DARI: "نام کاربری بروزرسانی شد."},
    "md.activate": {LANG_ENGLISH: "Activate", LANG_DARI: "فعال‌سازی"},
    "md.deactivate": {LANG_ENGLISH: "Deactivate", LANG_DARI: "غیرفعال"},
    "md.active": {LANG_ENGLISH: "Active", LANG_DARI: "فعال"},
    "md.inactive": {LANG_ENGLISH: "Inactive", LANG_DARI: "غیرفعال"},
    "md.count": {LANG_ENGLISH: "{n} records", LANG_DARI: "{n} رکورد"},
    "md.all": {LANG_ENGLISH: "All", LANG_DARI: "همه"},
    "md.saved": {LANG_ENGLISH: "Saved.", LANG_DARI: "ذخیره شد."},
    # ---- items --------------------------------------------------------
    "items.title": {LANG_ENGLISH: "Items", LANG_DARI: "اجناس"},
    "items.new": {LANG_ENGLISH: "New Item", LANG_DARI: "جنس جدید"},
    "items.edit_title": {LANG_ENGLISH: "Edit Item", LANG_DARI: "ویرایش جنس"},
    "items.col_code": {LANG_ENGLISH: "Code", LANG_DARI: "کود"},
    "items.col_name": {LANG_ENGLISH: "Name", LANG_DARI: "نام"},
    "items.col_altname": {LANG_ENGLISH: "Alternate Name", LANG_DARI: "نام دوم"},
    "items.col_barcode": {LANG_ENGLISH: "Barcode", LANG_DARI: "بارکد"},
    "items.col_category": {LANG_ENGLISH: "Category", LANG_DARI: "دسته"},
    "items.col_unit": {LANG_ENGLISH: "Unit", LANG_DARI: "واحد"},
    "items.col_purchase": {LANG_ENGLISH: "Purchase", LANG_DARI: "خرید"},
    "items.col_sale": {LANG_ENGLISH: "Sale", LANG_DARI: "فروش"},
    "items.col_min": {LANG_ENGLISH: "Min Stock", LANG_DARI: "حداقل موجودی"},
    "items.col_status": {LANG_ENGLISH: "Status", LANG_DARI: "وضعیت"},
    "items.sec_general": {LANG_ENGLISH: "General", LANG_DARI: "عمومی"},
    "items.sec_classification": {LANG_ENGLISH: "Classification", LANG_DARI: "دسته‌بندی"},
    "items.sec_pricing": {LANG_ENGLISH: "Pricing", LANG_DARI: "قیمت‌گذاری"},
    "items.sec_inventory": {LANG_ENGLISH: "Inventory & Opening Stock",
                            LANG_DARI: "موجودی و موجودی اولیه"},
    "items.f_opening_qty": {LANG_ENGLISH: "Opening Quantity",
                            LANG_DARI: "موجودی اولیه"},
    "items.f_opening_wh": {LANG_ENGLISH: "Opening Warehouse",
                           LANG_DARI: "انبار موجودی اولیه"},
    "items.opening_hint": {
        LANG_ENGLISH: "Starting stock on hand now. Records one opening inventory "
                      "movement to the chosen warehouse. Leave 0 if none.",
        LANG_DARI: "موجودی فعلی این جنس. یک حرکت موجودی اولیه در انبار انتخاب‌شده "
                   "ثبت می‌کند. اگر موجودی ندارید ۰ بگذارید.",
    },
    "items.f_stockable": {LANG_ENGLISH: "Track inventory (stockable)",
                          LANG_DARI: "کنترل موجودی (قابل انبار)"},
    "items.filter_category": {LANG_ENGLISH: "Category", LANG_DARI: "دسته"},
    "items.filter_status": {LANG_ENGLISH: "Status", LANG_DARI: "وضعیت"},
    # ---- persons ------------------------------------------------------
    "persons.title": {LANG_ENGLISH: "Persons", LANG_DARI: "اشخاص"},
    "persons.new": {LANG_ENGLISH: "New Person", LANG_DARI: "شخص جدید"},
    "persons.edit_title": {LANG_ENGLISH: "Edit Person", LANG_DARI: "ویرایش شخص"},
    "persons.col_code": {LANG_ENGLISH: "Code", LANG_DARI: "کود"},
    "persons.col_name": {LANG_ENGLISH: "Name", LANG_DARI: "نام"},
    "persons.col_company": {LANG_ENGLISH: "Business Name", LANG_DARI: "نام تجارت"},
    "persons.col_phone": {LANG_ENGLISH: "Phone", LANG_DARI: "تیلیفون"},
    "persons.col_roles": {LANG_ENGLISH: "Roles", LANG_DARI: "نقش‌ها"},
    "persons.col_status": {LANG_ENGLISH: "Status", LANG_DARI: "وضعیت"},
    "persons.f_customer": {LANG_ENGLISH: "Customer", LANG_DARI: "مشتری"},
    "persons.f_supplier": {LANG_ENGLISH: "Supplier", LANG_DARI: "تأمین‌کننده"},
    "persons.sec_identity": {LANG_ENGLISH: "Identity & Roles", LANG_DARI: "هویت و نقش‌ها"},
    "persons.sec_contact": {LANG_ENGLISH: "Contact", LANG_DARI: "تماس"},
    "persons.sec_financial": {LANG_ENGLISH: "Financial", LANG_DARI: "مالی"},
    "persons.filter_role": {LANG_ENGLISH: "Role", LANG_DARI: "نقش"},
    "persons.role_customer": {LANG_ENGLISH: "Customers", LANG_DARI: "مشتریان"},
    "persons.role_supplier": {LANG_ENGLISH: "Suppliers", LANG_DARI: "تأمین‌کننده‌ها"},
    "persons.role_both": {LANG_ENGLISH: "Customer + Supplier", LANG_DARI: "مشتری + تأمین‌کننده"},
    # ---- warehouses ---------------------------------------------------
    "wh.title": {LANG_ENGLISH: "Warehouses", LANG_DARI: "انبارها"},
    "wh.new": {LANG_ENGLISH: "New Warehouse", LANG_DARI: "انبار جدید"},
    "wh.edit_title": {LANG_ENGLISH: "Edit Warehouse", LANG_DARI: "ویرایش انبار"},
    "wh.col_code": {LANG_ENGLISH: "Code", LANG_DARI: "کود"},
    "wh.col_name": {LANG_ENGLISH: "Name", LANG_DARI: "نام"},
    "wh.col_address": {LANG_ENGLISH: "Address", LANG_DARI: "آدرس"},
    "wh.col_phone": {LANG_ENGLISH: "Phone", LANG_DARI: "تیلیفون"},
    "wh.col_default": {LANG_ENGLISH: "Default", LANG_DARI: "پیش‌فرض"},
    "wh.col_status": {LANG_ENGLISH: "Status", LANG_DARI: "وضعیت"},
    "wh.f_default": {LANG_ENGLISH: "Default warehouse", LANG_DARI: "انبار پیش‌فرض"},
    "wh.f_notes": {LANG_ENGLISH: "Notes", LANG_DARI: "یادداشت"},
    # ---- company ------------------------------------------------------
    "co.title": {LANG_ENGLISH: "Company Profile", LANG_DARI: "مشخصات شرکت"},
    "co.subtitle": {LANG_ENGLISH: "Business identity used on invoices and reports.",
                    LANG_DARI: "هویت تجاری که در بل‌ها و گزارش‌ها استفاده می‌شود."},
    "co.sec_identity": {LANG_ENGLISH: "Identity", LANG_DARI: "هویت"},
    "co.sec_contact": {LANG_ENGLISH: "Contact", LANG_DARI: "تماس"},
    "co.sec_defaults": {LANG_ENGLISH: "Defaults", LANG_DARI: "پیش‌فرض‌ها"},
    "co.legal_name": {LANG_ENGLISH: "Legal / Business Name", LANG_DARI: "نام قانونی / تجاری"},
    "co.display_name": {LANG_ENGLISH: "Display Name", LANG_DARI: "نام نمایشی"},
    "co.tax_id": {LANG_ENGLISH: "Tax Number (TIN)", LANG_DARI: "شماره مالیه (TIN)"},
    "co.reg_no": {LANG_ENGLISH: "Registration Number", LANG_DARI: "شماره ثبت"},
    "co.address": {LANG_ENGLISH: "Address", LANG_DARI: "آدرس"},
    "co.city": {LANG_ENGLISH: "City", LANG_DARI: "شهر"},
    "co.phone": {LANG_ENGLISH: "Phone", LANG_DARI: "تیلیفون"},
    "co.email": {LANG_ENGLISH: "Email", LANG_DARI: "ایمیل"},
    "co.website": {LANG_ENGLISH: "Website", LANG_DARI: "ویب‌سایت"},
    "co.currency": {LANG_ENGLISH: "Base Currency", LANG_DARI: "اسعار پایه"},
    "co.language": {LANG_ENGLISH: "Default Language", LANG_DARI: "زبان پیش‌فرض"},
    "co.footer": {LANG_ENGLISH: "Invoice Footer", LANG_DARI: "پاورقی بل"},
    "co.sec_logo": {LANG_ENGLISH: "Business Logo", LANG_DARI: "لوگوی تجارت"},
    "co.choose_logo": {LANG_ENGLISH: "Choose Logo…", LANG_DARI: "انتخاب لوگو…"},
    "co.remove_logo": {LANG_ENGLISH: "Remove", LANG_DARI: "حذف"},
    "co.no_logo": {LANG_ENGLISH: "No logo selected", LANG_DARI: "لوگویی انتخاب نشده"},
    "co.logo_hint": {
        LANG_ENGLISH: "PNG or JPG. Used on invoices and reports.",
        LANG_DARI: "PNG یا JPG. در بل‌ها و گزارش‌ها استفاده می‌شود.",
    },
    "co.logo_invalid": {
        LANG_ENGLISH: "Please choose a valid PNG or JPG image.",
        LANG_DARI: "لطفاً یک تصویر معتبر PNG یا JPG انتخاب کنید.",
    },
    # ---- financial years ----------------------------------------------
    "fy.title": {LANG_ENGLISH: "Financial Years", LANG_DARI: "سال‌های مالی"},
    "fy.new": {LANG_ENGLISH: "New Financial Year", LANG_DARI: "سال مالی جدید"},
    "fy.col_name": {LANG_ENGLISH: "Name", LANG_DARI: "نام"},
    "fy.col_start": {LANG_ENGLISH: "Start Date", LANG_DARI: "تاریخ آغاز"},
    "fy.col_end": {LANG_ENGLISH: "End Date", LANG_DARI: "تاریخ پایان"},
    "fy.col_status": {LANG_ENGLISH: "Status", LANG_DARI: "وضعیت"},
    "fy.col_active": {LANG_ENGLISH: "Active", LANG_DARI: "فعال"},
    "fy.f_name": {LANG_ENGLISH: "Name", LANG_DARI: "نام"},
    "fy.f_start": {LANG_ENGLISH: "Start Date (YYYY-MM-DD)", LANG_DARI: "تاریخ آغاز (YYYY-MM-DD)"},
    "fy.f_end": {LANG_ENGLISH: "End Date (YYYY-MM-DD)", LANG_DARI: "تاریخ پایان (YYYY-MM-DD)"},
    "fy.f_make_active": {LANG_ENGLISH: "Make this the active year",
                         LANG_DARI: "این سال مالی فعال شود"},
    "fy.set_active": {LANG_ENGLISH: "Set Active", LANG_DARI: "فعال کردن"},
    "fy.close": {LANG_ENGLISH: "Close", LANG_DARI: "بستن"},
    "fy.status_open": {LANG_ENGLISH: "Open", LANG_DARI: "باز"},
    "fy.status_closed": {LANG_ENGLISH: "Closed", LANG_DARI: "بسته"},
    # ---- users --------------------------------------------------------
    "usr.title": {LANG_ENGLISH: "Users", LANG_DARI: "کاربران"},
    "usr.new": {LANG_ENGLISH: "New User", LANG_DARI: "کاربر جدید"},
    "usr.edit_title": {LANG_ENGLISH: "Edit User", LANG_DARI: "ویرایش کاربر"},
    "usr.col_username": {LANG_ENGLISH: "Username", LANG_DARI: "نام کاربری"},
    "usr.col_fullname": {LANG_ENGLISH: "Full Name", LANG_DARI: "نام کامل"},
    "usr.col_roles": {LANG_ENGLISH: "Roles", LANG_DARI: "نقش‌ها"},
    "usr.col_status": {LANG_ENGLISH: "Status", LANG_DARI: "وضعیت"},
    "usr.f_username": {LANG_ENGLISH: "Username", LANG_DARI: "نام کاربری"},
    "usr.f_fullname": {LANG_ENGLISH: "Full Name", LANG_DARI: "نام کامل"},
    "usr.f_password": {LANG_ENGLISH: "Password", LANG_DARI: "رمز عبور"},
    "usr.f_role": {LANG_ENGLISH: "Role", LANG_DARI: "نقش"},
    "usr.reset_pw": {LANG_ENGLISH: "Reset Password", LANG_DARI: "بازنشانی رمز"},
    "usr.sec_account": {LANG_ENGLISH: "Account", LANG_DARI: "حساب"},
    "usr.sec_access": {LANG_ENGLISH: "Access", LANG_DARI: "دسترسی"},
    # ---- units / categories / roles -----------------------------------
    "unit.title": {LANG_ENGLISH: "Units", LANG_DARI: "واحدها"},
    "unit.new": {LANG_ENGLISH: "New Unit", LANG_DARI: "واحد جدید"},
    "unit.col_code": {LANG_ENGLISH: "Code", LANG_DARI: "کود"},
    "unit.col_en": {LANG_ENGLISH: "Name (EN)", LANG_DARI: "نام (انگلیسی)"},
    "unit.col_fa": {LANG_ENGLISH: "Name (Dari)", LANG_DARI: "نام (دری)"},
    "unit.col_symbol": {LANG_ENGLISH: "Symbol", LANG_DARI: "نماد"},
    "unit.col_decimal": {LANG_ENGLISH: "Decimals", LANG_DARI: "اعشار"},
    "unit.f_decimal": {LANG_ENGLISH: "Allow decimal quantities",
                       LANG_DARI: "اجازه مقدار اعشاری"},
    "cat.title": {LANG_ENGLISH: "Categories", LANG_DARI: "دسته‌ها"},
    "cat.new": {LANG_ENGLISH: "New Category", LANG_DARI: "دسته جدید"},
    "cat.col_code": {LANG_ENGLISH: "Code", LANG_DARI: "کود"},
    "cat.col_en": {LANG_ENGLISH: "Name (EN)", LANG_DARI: "نام (انگلیسی)"},
    "cat.col_fa": {LANG_ENGLISH: "Name (Dari)", LANG_DARI: "نام (دری)"},
    "cat.col_parent": {LANG_ENGLISH: "Parent", LANG_DARI: "دسته والد"},
    "cat.parent_none": {LANG_ENGLISH: "(Top level)", LANG_DARI: "(سطح اول)"},
    "role.title": {LANG_ENGLISH: "Roles & Permissions", LANG_DARI: "نقش‌ها و مجوزها"},
    "role.col_name": {LANG_ENGLISH: "Role", LANG_DARI: "نقش"},
    "role.col_code": {LANG_ENGLISH: "Code", LANG_DARI: "کود"},
    "role.col_perms": {LANG_ENGLISH: "Permissions", LANG_DARI: "مجوزها"},
    "role.edit_perms": {LANG_ENGLISH: "Edit Permissions", LANG_DARI: "ویرایش مجوزها"},
    "field.code": {LANG_ENGLISH: "Code", LANG_DARI: "کود"},
    "field.name": {LANG_ENGLISH: "Name", LANG_DARI: "نام"},
    "field.symbol": {LANG_ENGLISH: "Symbol", LANG_DARI: "نماد"},
    # ==== Stage 04 — Sales, Purchases & Returns =========================
    # -- navigation commands (Buy & Sell) --
    "s4.sale_new": {LANG_ENGLISH: "Sales Invoice", LANG_DARI: "فاکتور فروش"},
    "s4.sale_list": {LANG_ENGLISH: "Sales List", LANG_DARI: "لیست فروش‌ها"},
    "s4.purchase_new": {LANG_ENGLISH: "Purchase Invoice", LANG_DARI: "فاکتور خرید"},
    "s4.purchase_list": {LANG_ENGLISH: "Purchases List", LANG_DARI: "لیست خریدها"},
    "s4.sale_return": {LANG_ENGLISH: "Sales Return", LANG_DARI: "برگشت فروش"},
    "s4.purchase_return": {LANG_ENGLISH: "Purchase Return", LANG_DARI: "برگشت خرید"},
    # -- entry page --
    "s4.sale_title": {LANG_ENGLISH: "Sales Invoice", LANG_DARI: "فاکتور فروش"},
    "s4.purchase_title": {LANG_ENGLISH: "Purchase Invoice", LANG_DARI: "فاکتور خرید"},
    "s4.customer": {LANG_ENGLISH: "Customer", LANG_DARI: "مشتری"},
    "s4.supplier": {LANG_ENGLISH: "Supplier", LANG_DARI: "تأمین‌کننده"},
    "s4.customer_search_ph": {LANG_ENGLISH: "Search customer by name, code or phone…",
                              LANG_DARI: "جستجوی مشتری با نام، کود یا تلیفون…"},
    "s4.supplier_search_ph": {LANG_ENGLISH: "Search supplier by name, code or phone…",
                              LANG_DARI: "جستجوی تأمین‌کننده با نام، کود یا تلیفون…"},
    "s4.item_search_ph": {LANG_ENGLISH: "Search item by name, code or barcode…",
                          LANG_DARI: "جستجوی جنس با نام، کود یا بارکد…"},
    "s4.walkin": {LANG_ENGLISH: "Walk-in Customer", LANG_DARI: "مشتری نقدی"},
    "s4.cash_supplier": {LANG_ENGLISH: "Cash Supplier", LANG_DARI: "تأمین‌کننده نقدی"},
    "s4.auto": {LANG_ENGLISH: "Auto", LANG_DARI: "خودکار"},
    "s4.supplier_ref": {LANG_ENGLISH: "Supplier Ref.", LANG_DARI: "مرجع تأمین‌کننده"},
    "s4.notes": {LANG_ENGLISH: "Notes", LANG_DARI: "یادداشت"},
    "s4.amount_paid": {LANG_ENGLISH: "Amount Paid", LANG_DARI: "مبلغ پرداختی"},
    "s4.keyboard_hint": {
        LANG_ENGLISH: "Item ↵ → Qty ↵ → Price ↵ → Discount ↵ commits the line",
        LANG_DARI: "جنس ↵ ← مقدار ↵ ← قیمت ↵ ← تخفیف ↵ قلم را ثبت می‌کند"},
    "s4.add_item": {LANG_ENGLISH: "Add Item", LANG_DARI: "افزودن جنس"},
    "s4.add_line": {LANG_ENGLISH: "Add", LANG_DARI: "افزودن"},
    "s4.summary": {LANG_ENGLISH: "Summary", LANG_DARI: "خلاصه"},
    "s4.items": {LANG_ENGLISH: "Items", LANG_DARI: "اقلام"},
    "s4.col_item": {LANG_ENGLISH: "Item", LANG_DARI: "جنس"},
    # -- actions --
    "s4.act_post": {LANG_ENGLISH: "Save", LANG_DARI: "ذخیره"},
    "s4.act_post_print": {LANG_ENGLISH: "Save & Print", LANG_DARI: "ذخیره و چاپ"},
    "s4.act_new": {LANG_ENGLISH: "New", LANG_DARI: "جدید"},
    "s4.act_print": {LANG_ENGLISH: "Print", LANG_DARI: "چاپ"},
    "s4.act_close": {LANG_ENGLISH: "Close", LANG_DARI: "بستن"},
    "s4.delete_line": {LANG_ENGLISH: "Delete Line", LANG_DARI: "حذف قلم"},
    "s4.edit_line": {LANG_ENGLISH: "Edit Line", LANG_DARI: "ویرایش قلم"},
    "s4.edit_hint": {
        LANG_ENGLISH: "Double-click Qty/Price/Discount to edit · double-click the item to replace",
        LANG_DARI: "برای ویرایش روی مقدار/قیمت/تخفیف دوکلیک کنید · برای تعویض جنس روی نام جنس دوکلیک کنید"},
    # -- customer type (registered vs walk-in) --
    "s4.step_customer": {LANG_ENGLISH: "Customer", LANG_DARI: "مشتری"},
    "s4.step_supplier": {LANG_ENGLISH: "Supplier", LANG_DARI: "تأمین‌کننده"},
    "s4.mode_registered": {LANG_ENGLISH: "Registered", LANG_DARI: "ثبت‌شده"},
    "s4.mode_walkin": {LANG_ENGLISH: "Walk-in", LANG_DARI: "مشتری آزاد"},
    "s4.walkin_name": {LANG_ENGLISH: "Customer Name", LANG_DARI: "نام مشتری"},
    "s4.walkin_head": {
        LANG_ENGLISH: "Walk-in customer — enter the details of a customer who is NOT registered",
        LANG_DARI: "مشتری آزاد — مشخصات مشتری‌ای را که در سیستم ثبت نشده وارد کنید"},
    "s4.walkin_name_ph": {LANG_ENGLISH: "Type the customer's name…",
                          LANG_DARI: "نام مشتری را بنویسید…"},
    "s4.correcting": {LANG_ENGLISH: "Correcting invoice {no}",
                      LANG_DARI: "در حال اصلاح بل {no}"},
    "s4.msg_corrected": {LANG_ENGLISH: "Corrected — new invoice {no}",
                         LANG_DARI: "اصلاح شد — بل جدید {no}"},
    "s4.msg_correct_only_posted": {
        LANG_ENGLISH: "Only a posted invoice can be corrected.",
        LANG_DARI: "فقط یک بل ثبت‌شده را می‌توان اصلاح کرد."},
    "s4.act_correct": {LANG_ENGLISH: "Correct", LANG_DARI: "اصلاح"},
    "s4.walkin_phone": {LANG_ENGLISH: "Phone (optional)", LANG_DARI: "تلیفون (اختیاری)"},
    "s4.walkin_address": {LANG_ENGLISH: "Address / Note (optional)",
                          LANG_DARI: "آدرس / یادداشت (اختیاری)"},
    # -- messages --
    "s4.msg_posted": {LANG_ENGLISH: "Saved — {no}", LANG_DARI: "ذخیره شد — {no}"},
    "s4.msg_returned": {LANG_ENGLISH: "Return saved — {no}", LANG_DARI: "برگشت ثبت شد — {no}"},
    "s4.msg_add_line": {LANG_ENGLISH: "Add at least one item first.",
                        LANG_DARI: "ابتدا حداقل یک قلم اضافه کنید."},
    "s4.msg_no_currency": {LANG_ENGLISH: "No currency is configured.",
                           LANG_DARI: "هیچ اسعاری تنظیم نشده است."},
    "s4.msg_no_source": {LANG_ENGLISH: "Load a source document first.",
                         LANG_DARI: "ابتدا سند مبنا را بارگیری کنید."},
    "s4.msg_no_return_lines": {LANG_ENGLISH: "Enter a return quantity for at least one line.",
                               LANG_DARI: "برای حداقل یک قلم مقدار برگشت وارد کنید."},
    "s4.msg_source_not_found": {LANG_ENGLISH: "Document not found.",
                                LANG_DARI: "سند یافت نشد."},
    "s4.msg_source_ambiguous": {
        LANG_ENGLISH: "Several invoices match — enter the full document number.",
        LANG_DARI: "چند فاکتور مطابقت دارد — شماره کامل سند را وارد کنید."},
    # -- list screens --
    "s4.sales_list_title": {LANG_ENGLISH: "Sales", LANG_DARI: "فروش‌ها"},
    "s4.purchases_list_title": {LANG_ENGLISH: "Purchases", LANG_DARI: "خریدها"},
    "s4.col_docno": {LANG_ENGLISH: "Document #", LANG_DARI: "شماره سند"},
    "s4.col_date": {LANG_ENGLISH: "Date", LANG_DARI: "تاریخ"},
    "s4.col_party": {LANG_ENGLISH: "Party", LANG_DARI: "طرف حساب"},
    "s4.col_warehouse": {LANG_ENGLISH: "Warehouse", LANG_DARI: "انبار"},
    "s4.col_total": {LANG_ENGLISH: "Total", LANG_DARI: "مجموع"},
    "s4.col_paid": {LANG_ENGLISH: "Paid", LANG_DARI: "پرداخت‌شده"},
    "s4.col_remaining": {LANG_ENGLISH: "Remaining", LANG_DARI: "باقی‌مانده"},
    "s4.col_status": {LANG_ENGLISH: "Status", LANG_DARI: "وضعیت"},
    "s4.col_source": {LANG_ENGLISH: "Source Doc", LANG_DARI: "سند مبنا"},
    "s4.status_posted": {LANG_ENGLISH: "Posted", LANG_DARI: "ثبت‌شده"},
    "s4.status_draft": {LANG_ENGLISH: "Draft", LANG_DARI: "پیش‌نویس"},
    "s4.status_void": {LANG_ENGLISH: "Cancelled", LANG_DARI: "لغوشده"},
    "s4.act_return": {LANG_ENGLISH: "Return", LANG_DARI: "برگشت"},
    "s4.act_void": {LANG_ENGLISH: "Void", LANG_DARI: "ابطال"},
    "s4.void_confirm_title": {LANG_ENGLISH: "Void this sale?", LANG_DARI: "این فروش ابطال شود؟"},
    "s4.void_confirm_body": {
        LANG_ENGLISH: "Voiding {no} reverses its stock, the customer balance and the"
                      " accounting entry. The original document is kept for audit.",
        LANG_DARI: "ابطال {no} موجودی، حساب مشتری و ثبت حسابداری آن را برمی‌گرداند."
                   " سند اصلی برای بازرسی نگهداری می‌شود."},
    "s4.msg_voided": {LANG_ENGLISH: "Sale voided — {no}", LANG_DARI: "فروش ابطال شد — {no}"},
    "s4.filter_status": {LANG_ENGLISH: "Status", LANG_DARI: "وضعیت"},
    "s4.filter_all": {LANG_ENGLISH: "All", LANG_DARI: "همه"},
    # -- customer / supplier account ledger (owner-fix defect #4) --
    "led.customer_title": {LANG_ENGLISH: "Customer Ledger", LANG_DARI: "دفتر حساب مشتری"},
    "led.supplier_title": {LANG_ENGLISH: "Supplier Ledger", LANG_DARI: "دفتر حساب تأمین‌کننده"},
    "led.nav_customer": {LANG_ENGLISH: "Customer Ledger", LANG_DARI: "دفتر حساب مشتری"},
    "led.nav_supplier": {LANG_ENGLISH: "Supplier Ledger", LANG_DARI: "دفتر حساب تأمین‌کننده"},
    "led.pick_hint": {LANG_ENGLISH: "Choose a person to view their account history.",
                      LANG_DARI: "برای دیدن سابقهٔ حساب، یک شخص را انتخاب کنید."},
    "led.total_sales": {LANG_ENGLISH: "Total Sales", LANG_DARI: "مجموع فروش"},
    "led.total_received": {LANG_ENGLISH: "Total Received", LANG_DARI: "مجموع دریافت"},
    "led.receivable": {LANG_ENGLISH: "Current Receivable", LANG_DARI: "قابل دریافت فعلی"},
    "led.total_purchases": {LANG_ENGLISH: "Total Purchases", LANG_DARI: "مجموع خرید"},
    "led.total_paid": {LANG_ENGLISH: "Total Paid", LANG_DARI: "مجموع پرداخت"},
    "led.payable": {LANG_ENGLISH: "Current Payable", LANG_DARI: "قابل پرداخت فعلی"},
    "led.col_date": {LANG_ENGLISH: "Date", LANG_DARI: "تاریخ"},
    "led.col_docno": {LANG_ENGLISH: "Document No.", LANG_DARI: "شماره سند"},
    "led.col_type": {LANG_ENGLISH: "Type", LANG_DARI: "نوع"},
    "led.col_desc": {LANG_ENGLISH: "Description", LANG_DARI: "شرح"},
    "led.col_debit": {LANG_ENGLISH: "Debit", LANG_DARI: "بدهکار"},
    "led.col_credit": {LANG_ENGLISH: "Credit", LANG_DARI: "بستانکار"},
    "led.col_running": {LANG_ENGLISH: "Balance", LANG_DARI: "مانده"},
    "led.t_sale": {LANG_ENGLISH: "Sale", LANG_DARI: "فروش"},
    "led.t_void": {LANG_ENGLISH: "Sale Void", LANG_DARI: "ابطال فروش"},
    "led.t_sales_return": {LANG_ENGLISH: "Sales Return", LANG_DARI: "برگشت فروش"},
    "led.t_purchase": {LANG_ENGLISH: "Purchase", LANG_DARI: "خرید"},
    "led.t_purchase_return": {LANG_ENGLISH: "Purchase Return", LANG_DARI: "برگشت خرید"},
    "led.t_receipt": {LANG_ENGLISH: "Receipt", LANG_DARI: "دریافت"},
    "led.t_payment": {LANG_ENGLISH: "Payment", LANG_DARI: "پرداخت"},
    "s4.empty_list": {LANG_ENGLISH: "No documents yet.", LANG_DARI: "هنوز سندی وجود ندارد."},
    # -- returns --
    "s4.return_sale_title": {LANG_ENGLISH: "Sales Return", LANG_DARI: "برگشت فروش"},
    "s4.return_purchase_title": {LANG_ENGLISH: "Purchase Return", LANG_DARI: "برگشت خرید"},
    "s4.source_doc": {LANG_ENGLISH: "Source Document #", LANG_DARI: "شماره سند مبنا"},
    "s4.source_ph": {LANG_ENGLISH: "Enter document number…", LANG_DARI: "شماره سند را وارد کنید…"},
    "s4.load": {LANG_ENGLISH: "Load", LANG_DARI: "بارگیری"},
    "s4.col_returnable": {LANG_ENGLISH: "Returnable", LANG_DARI: "قابل برگشت"},
    "s4.col_return_qty": {LANG_ENGLISH: "Return Qty", LANG_DARI: "مقدار برگشت"},
    "s4.reason": {LANG_ENGLISH: "Reason", LANG_DARI: "دلیل"},
    "s4.source_summary": {LANG_ENGLISH: "Source: {no} · {party}",
                          LANG_DARI: "مبنا: {no} · {party}"},
    # -- print titles --
    "s4.print.purchase_title": {LANG_ENGLISH: "PURCHASE INVOICE", LANG_DARI: "فاکتور خرید"},
    "s4.print.sales_return_title": {LANG_ENGLISH: "SALES RETURN", LANG_DARI: "برگشت فروش"},
    "s4.print.purchase_return_title": {LANG_ENGLISH: "PURCHASE RETURN", LANG_DARI: "برگشت خرید"},
    # -- dashboard (real) --
    "s4.dash_live": {LANG_ENGLISH: "Live", LANG_DARI: "زنده"},
    "s4.dash_recent": {LANG_ENGLISH: "Recent Sales", LANG_DARI: "فروش‌های اخیر"},
    "s4.t_sale": {LANG_ENGLISH: "Sale", LANG_DARI: "فروش"},
    "s4.dash_no_data": {LANG_ENGLISH: "No transactions yet today.",
                        LANG_DARI: "امروز هنوز معامله‌ای ثبت نشده."},
    "s4.dash_all_stocked": {LANG_ENGLISH: "All items are in stock.",
                            LANG_DARI: "همه اجناس موجود است."},
    # ==== Stage 05 — Receipts, Payments, Expenses =======================
    "s5.receipt_title": {LANG_ENGLISH: "Receive Payment", LANG_DARI: "دریافت پول"},
    "s5.payment_title": {LANG_ENGLISH: "Make Payment", LANG_DARI: "پرداخت پول"},
    "s5.expense_title": {LANG_ENGLISH: "Expense", LANG_DARI: "مصرف"},
    "s5.details": {LANG_ENGLISH: "Details", LANG_DARI: "جزئیات"},
    "s5.category": {LANG_ENGLISH: "Expense Category", LANG_DARI: "دسته مصرف"},
    "s5.expense_of": {LANG_ENGLISH: "Expense", LANG_DARI: "مصرف"},
    "s5.payee": {LANG_ENGLISH: "Paid To", LANG_DARI: "پرداخت به"},
    "s5.fund": {LANG_ENGLISH: "Cash / Bank Account", LANG_DARI: "حساب صندوق/بانک"},
    "s5.method": {LANG_ENGLISH: "Payment Method", LANG_DARI: "روش پرداخت"},
    "s5.reference": {LANG_ENGLISH: "Reference", LANG_DARI: "مرجع"},
    "s5.doc_no": {LANG_ENGLISH: "Document No.", LANG_DARI: "شماره سند"},
    "s5.amount": {LANG_ENGLISH: "Amount", LANG_DARI: "مبلغ"},
    "s5.amount_received": {LANG_ENGLISH: "Amount Received", LANG_DARI: "مبلغ دریافتی"},
    "s5.amount_paid": {LANG_ENGLISH: "Amount Paid", LANG_DARI: "مبلغ پرداختی"},
    "s5.remaining": {LANG_ENGLISH: "Remaining Balance", LANG_DARI: "باقی‌مانده"},
    "s5.prev_payable": {LANG_ENGLISH: "Previous Payable", LANG_DARI: "قابل پرداخت قبلی"},
    "s5.remaining_payable": {LANG_ENGLISH: "Remaining Payable", LANG_DARI: "باقی‌ماندهٔ پرداخت"},
    # payment methods
    "s5.m_cash": {LANG_ENGLISH: "Cash", LANG_DARI: "نقد"},
    "s5.m_bank": {LANG_ENGLISH: "Bank", LANG_DARI: "بانک"},
    "s5.m_transfer": {LANG_ENGLISH: "Transfer", LANG_DARI: "حواله"},
    "s5.m_cheque": {LANG_ENGLISH: "Cheque", LANG_DARI: "چک"},
    "s5.m_other": {LANG_ENGLISH: "Other", LANG_DARI: "سایر"},
    # lists
    "s5.receipts_title": {LANG_ENGLISH: "Receipts", LANG_DARI: "دریافت‌ها"},
    "s5.payments_title": {LANG_ENGLISH: "Payments", LANG_DARI: "پرداخت‌ها"},
    "s5.expenses_title": {LANG_ENGLISH: "Expenses", LANG_DARI: "مصارف"},
    "s5.col_account": {LANG_ENGLISH: "Account", LANG_DARI: "حساب"},
    "s5.col_amount": {LANG_ENGLISH: "Amount", LANG_DARI: "مبلغ"},
    "s5.col_method": {LANG_ENGLISH: "Method", LANG_DARI: "روش"},
    "s5.col_payee": {LANG_ENGLISH: "Payee", LANG_DARI: "پرداخت به"},
    "s5.col_category": {LANG_ENGLISH: "Category", LANG_DARI: "دسته"},
    "s5.all_funds": {LANG_ENGLISH: "All Accounts", LANG_DARI: "همه حساب‌ها"},
    # navigation commands (Receipts & Payments / Funds)
    "s5.nav_receipt": {LANG_ENGLISH: "Receive Payment", LANG_DARI: "دریافت پول"},
    "s5.nav_receipt_list": {LANG_ENGLISH: "Receipts List", LANG_DARI: "لیست دریافت‌ها"},
    "s5.nav_payment": {LANG_ENGLISH: "Make Payment", LANG_DARI: "پرداخت پول"},
    "s5.nav_payment_list": {LANG_ENGLISH: "Payments List", LANG_DARI: "لیست پرداخت‌ها"},
    "s5.nav_expense": {LANG_ENGLISH: "New Expense", LANG_DARI: "مصرف جدید"},
    "s5.nav_expense_list": {LANG_ENGLISH: "Expenses List", LANG_DARI: "لیست مصارف"},
    # printed vouchers
    "s5.print.receipt_title": {LANG_ENGLISH: "RECEIPT VOUCHER", LANG_DARI: "رسید دریافت"},
    "s5.print.payment_title": {LANG_ENGLISH: "PAYMENT VOUCHER", LANG_DARI: "سند پرداخت"},
    "s5.print.expense_title": {LANG_ENGLISH: "EXPENSE VOUCHER", LANG_DARI: "سند مصرف"},
    "s5.v_amount": {LANG_ENGLISH: "Amount", LANG_DARI: "مبلغ"},
    "s5.v_received_from": {LANG_ENGLISH: "Received From", LANG_DARI: "دریافت از"},
    "s5.v_paid_to": {LANG_ENGLISH: "Paid To", LANG_DARI: "پرداخت به"},
    "s5.v_being": {LANG_ENGLISH: "Being / For", LANG_DARI: "بابت"},
    "s5.v_amount_words": {LANG_ENGLISH: "AMOUNT IN WORDS", LANG_DARI: "مبلغ به حروف"},
    "s5.v_method": {LANG_ENGLISH: "Payment Method", LANG_DARI: "روش پرداخت"},
    "s5.v_account": {LANG_ENGLISH: "Account", LANG_DARI: "حساب"},
    "s5.v_reference": {LANG_ENGLISH: "Reference", LANG_DARI: "مرجع"},
    "s5.v_category": {LANG_ENGLISH: "Expense Category", LANG_DARI: "دسته مصرف"},
    "s5.v_received_by": {LANG_ENGLISH: "Received By", LANG_DARI: "دریافت‌کننده"},
    "s5.v_paid_by": {LANG_ENGLISH: "Paid By", LANG_DARI: "پرداخت‌کننده"},
    "s5.v_authorized": {LANG_ENGLISH: "Authorized Signature", LANG_DARI: "امضای مجاز"},
    "s5.v_counterparty": {LANG_ENGLISH: "Signature", LANG_DARI: "امضاء"},
    "s5.msg_amount": {LANG_ENGLISH: "Enter an amount above zero.",
                      LANG_DARI: "مبلغی بیشتر از صفر وارد کنید."},
    # -- Sales Reporting (Stage 05 final) --
    "rep.title": {LANG_ENGLISH: "Sales Report", LANG_DARI: "گزارش فروش"},
    "rep.nav_sales": {LANG_ENGLISH: "Sales Report", LANG_DARI: "گزارش فروش"},
    "rep.period": {LANG_ENGLISH: "Period", LANG_DARI: "دوره"},
    "rep.preset_today": {LANG_ENGLISH: "Today", LANG_DARI: "امروز"},
    "rep.preset_week": {LANG_ENGLISH: "This Week", LANG_DARI: "این هفته"},
    "rep.preset_month": {LANG_ENGLISH: "This Month", LANG_DARI: "این ماه"},
    "rep.preset_year": {LANG_ENGLISH: "This Year", LANG_DARI: "امسال"},
    "rep.preset_custom": {LANG_ENGLISH: "Custom", LANG_DARI: "دلخواه"},
    "rep.from": {LANG_ENGLISH: "From", LANG_DARI: "از تاریخ"},
    "rep.to": {LANG_ENGLISH: "To", LANG_DARI: "تا تاریخ"},
    "rep.warehouse": {LANG_ENGLISH: "Warehouse", LANG_DARI: "انبار"},
    "rep.customer": {LANG_ENGLISH: "Customer", LANG_DARI: "مشتری"},
    "rep.customer_ph": {LANG_ENGLISH: "All customers…", LANG_DARI: "همه مشتریان…"},
    "rep.payment_status": {LANG_ENGLISH: "Payment", LANG_DARI: "پرداخت"},
    "rep.kind": {LANG_ENGLISH: "Customer Type", LANG_DARI: "نوع مشتری"},
    "rep.all": {LANG_ENGLISH: "All", LANG_DARI: "همه"},
    "rep.ps_paid": {LANG_ENGLISH: "Paid", LANG_DARI: "نقده"},
    "rep.ps_credit": {LANG_ENGLISH: "Credit", LANG_DARI: "نسیه"},
    "rep.ps_partial": {LANG_ENGLISH: "Partial", LANG_DARI: "قسمی"},
    "rep.kind_registered": {LANG_ENGLISH: "Registered", LANG_DARI: "ثبت‌شده"},
    "rep.kind_walkin": {LANG_ENGLISH: "Walk-in", LANG_DARI: "مشتری گذری"},
    "rep.run": {LANG_ENGLISH: "Run Report", LANG_DARI: "اجرای گزارش"},
    "rep.m_gross": {LANG_ENGLISH: "Gross Sales", LANG_DARI: "فروش ناخالص"},
    "rep.m_paid": {LANG_ENGLISH: "Paid / Cash", LANG_DARI: "دریافت‌شده / نقد"},
    "rep.m_credit": {LANG_ENGLISH: "Credit", LANG_DARI: "نسیه"},
    "rep.m_returns": {LANG_ENGLISH: "Returns", LANG_DARI: "برگشتی"},
    "rep.m_net": {LANG_ENGLISH: "Net Sales", LANG_DARI: "فروش خالص"},
    "rep.tab_detail": {LANG_ENGLISH: "Transactions", LANG_DARI: "معاملات"},
    "rep.tab_daily": {LANG_ENGLISH: "Daily", LANG_DARI: "روزانه"},
    "rep.tab_monthly": {LANG_ENGLISH: "Monthly", LANG_DARI: "ماهانه"},
    "rep.col_date": {LANG_ENGLISH: "Date", LANG_DARI: "تاریخ"},
    "rep.col_docno": {LANG_ENGLISH: "Invoice #", LANG_DARI: "شماره فاکتور"},
    "rep.col_customer": {LANG_ENGLISH: "Customer", LANG_DARI: "مشتری"},
    "rep.col_type": {LANG_ENGLISH: "Type", LANG_DARI: "نوع"},
    "rep.col_gross": {LANG_ENGLISH: "Gross", LANG_DARI: "ناخالص"},
    "rep.col_paid": {LANG_ENGLISH: "Paid", LANG_DARI: "دریافت"},
    "rep.col_credit": {LANG_ENGLISH: "Credit", LANG_DARI: "نسیه"},
    "rep.col_returned": {LANG_ENGLISH: "Returned", LANG_DARI: "برگشت"},
    "rep.col_net": {LANG_ENGLISH: "Net", LANG_DARI: "خالص"},
    "rep.col_period": {LANG_ENGLISH: "Period", LANG_DARI: "دوره"},
    "rep.col_invoices": {LANG_ENGLISH: "Invoices", LANG_DARI: "فاکتورها"},
    "rep.row_registered": {LANG_ENGLISH: "Registered", LANG_DARI: "ثبت‌شده"},
    "rep.row_walkin": {LANG_ENGLISH: "Walk-in", LANG_DARI: "گذری"},
    "rep.empty": {LANG_ENGLISH: "No sales in the selected period.",
                  LANG_DARI: "در دوره انتخاب‌شده فروشی وجود ندارد."},
    "rep.hint": {LANG_ENGLISH: "Choose a period and run the report.",
                 LANG_DARI: "یک دوره را انتخاب کنید و گزارش را اجرا کنید."},
    "rep.summary_line": {LANG_ENGLISH: "{count} invoice(s) · {df} to {dt}",
                         LANG_DARI: "{count} فاکتور · {df} تا {dt}"},
    "rep.print": {LANG_ENGLISH: "Print", LANG_DARI: "چاپ"},
    "rep.print_title": {LANG_ENGLISH: "Sales Report", LANG_DARI: "گزارش فروش"},
    "rep.print_period": {LANG_ENGLISH: "Period: {df} — {dt}",
                         LANG_DARI: "دوره: {df} — {dt}"},
    "rep.walkin_customer": {LANG_ENGLISH: "Walk-in Customer",
                            LANG_DARI: "مشتری گذری"},
    "rep.total": {LANG_ENGLISH: "Total", LANG_DARI: "مجموع"},
    "rep.msg_bad_dates": {LANG_ENGLISH: "Enter valid From/To dates (YYYY-MM-DD).",
                          LANG_DARI: "تاریخ‌های از/تا را درست وارد کنید (YYYY-MM-DD)."},
    "rep.msg_range": {LANG_ENGLISH: "‘From’ must not be after ‘To’.",
                      LANG_DARI: "«از تاریخ» نباید بعد از «تا تاریخ» باشد."},
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
