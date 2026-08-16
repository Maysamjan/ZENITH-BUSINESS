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
    "items.sec_inventory": {LANG_ENGLISH: "Inventory", LANG_DARI: "موجودی"},
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
    "s4.filter_status": {LANG_ENGLISH: "Status", LANG_DARI: "وضعیت"},
    "s4.filter_all": {LANG_ENGLISH: "All", LANG_DARI: "همه"},
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
