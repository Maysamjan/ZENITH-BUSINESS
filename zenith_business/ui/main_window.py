"""Application main window — shell assembly (Prompt 01B §3-§8, §22).

Composition (Chortkeh-style concept, original Zenith identity):

    +---------------------------------------------------------------+
    | HeaderBar      ZENITH BUSINESS            Guest · EN | دری     |
    +---------------------------------------------------------------+
    | PrimaryNav     Home | Base | Sales | Payments | ... | Tools   |
    +---------------------------------------------------------------+
    | ContextBar     COMMANDS | <contextual command buttons>        |
    +---------------------------------------------------------------+
    |                                                               |
    |   Content stack: Home / Unavailable / Form demo / Table demo  |
    |                                                               |
    +---------------------------------------------------------------+
    | StatusBar   company · database · license                      |
    +---------------------------------------------------------------+

Business functionality is NOT implemented. Business categories expose disabled
placeholder commands and a truthful "unavailable" state; the enabled commands
(Tools → Form/Table preview) exist only to validate the design system.
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QLabel,
    QMainWindow,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from zenith_business.core.config import AppConfig, LANG_DARI, LANG_ENGLISH
from zenith_business.core.i18n import Direction, Translator, resolve_direction
from zenith_business.core.identity import IDENTITY
from zenith_business.core.logging_setup import get_logger
from zenith_business.database import Database, check_health
from zenith_business.security.licensing import DevelopmentLicenseProvider, LicenseProvider
from zenith_business.ui.components import EmptyState, vertical_line
from zenith_business.ui.design.tokens import ControlSize
from zenith_business.ui.pages.dashboard import DashboardPage
from zenith_business.ui.pages.form_demo import FormDemoPage
from zenith_business.ui.pages.print_preview import PrintPreviewPage
from zenith_business.ui.pages.sales_invoice_demo import SalesInvoiceDemoPage
from zenith_business.ui.pages.table_demo import TableDemoPage
from zenith_business.ui.shell import ContextBar, HeaderBar, PrimaryNav

_logger = get_logger("ui.main_window")

# Primary categories (top navigation). Business commands are placeholders.
_CATEGORIES = (
    "menu.base_data",
    "menu.buy_sell",
    "menu.receipts_payments",
    "menu.funds",
    "menu.account_reports",
    "menu.item_reports",
    "menu.tools",
)

# Contextual commands per category. Tuple: (text_key, enabled, action_name).
# action_name is only used for enabled Tools commands.
_COMMANDS: dict[str, list[tuple[str, bool, str | None]]] = {
    "menu.base_data": [
        ("cmd.base.persons", False, None),
        ("cmd.base.products", False, None),
        ("cmd.base.warehouses", False, None),
        ("cmd.base.currencies", False, None),
    ],
    "menu.buy_sell": [
        ("cmd.sales.sale_invoice", False, None),
        ("cmd.sales.sale_return", False, None),
        ("cmd.sales.purchase_invoice", False, None),
        ("cmd.sales.purchase_return", False, None),
        ("cmd.sales.quotation", False, None),
    ],
    "menu.receipts_payments": [
        ("cmd.pay.receipt", False, None),
        ("cmd.pay.payment", False, None),
        ("cmd.pay.transfer", False, None),
    ],
    "menu.funds": [
        ("cmd.funds.cash", False, None),
        ("cmd.funds.bank", False, None),
        ("cmd.funds.exchange", False, None),
    ],
    "menu.account_reports": [
        ("cmd.acct.ledger", False, None),
        ("cmd.acct.trial", False, None),
        ("cmd.acct.statement", False, None),
    ],
    "menu.item_reports": [
        ("cmd.item.kardex", False, None),
        ("cmd.item.stock", False, None),
        ("cmd.item.movement", False, None),
    ],
    "menu.tools": [
        ("cmd.tools.sales_invoice", True, "sales_invoice"),
        ("cmd.tools.print_preview", True, "print_preview"),
        ("cmd.tools.form_demo", True, "form"),
        ("cmd.tools.table_demo", True, "table"),
        ("cmd.tools.settings", False, None),
    ],
}


class MainWindow(QMainWindow):
    """Top-level application window (the shell)."""

    def __init__(
        self,
        config: AppConfig,
        *,
        database: Database | None = None,
        license_provider: LicenseProvider | None = None,
        current_user=None,
        on_logout: Callable[[], None] | None = None,
        context=None,
    ) -> None:
        super().__init__()
        self._config = config
        self._database = database
        self._license = license_provider or DevelopmentLicenseProvider()
        self._translator = Translator(config.ui.language)
        self._current_category: str | None = None
        # Optional authenticated identity (Stage 02). When None, the shell keeps
        # its Stage 01 guest behavior unchanged.
        self._current_user = current_user
        self._on_logout = on_logout
        # Optional Stage 03 application context enabling real master-data screens.
        self._context = context
        self._stage03_pages: dict[str, QWidget] = {}
        self._stage03_commands: dict[str, list[tuple[str, bool, str | None]]] = {}
        self._stage03_actions: dict[str, Callable[[], None]] = {}

        self.setWindowTitle(IDENTITY.title)
        self.setMinimumSize(1024, 640)  # usable on 1366×768 and up (§16)

        self._build_shell()
        self._build_status_bar()
        self._apply_direction()
        self.show_home()
        self._refresh_status()
        self._apply_identity()

    # ---- shell assembly --------------------------------------------------

    def _build_shell(self) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header = HeaderBar(
            self._translator,
            on_language=self._switch_language,
            on_home=self.show_home,
            on_logout=self._on_logout,
        )
        self.primary_nav = PrimaryNav(
            self._translator,
            list(_CATEGORIES),
            on_home=self.show_home,
            on_select=self.select_category,
        )
        self.context_bar = ContextBar(self._translator)

        layout.addWidget(self.header)
        layout.addWidget(self.primary_nav)
        layout.addWidget(self.context_bar)

        # Central content stack.
        self.content = QStackedWidget()
        self.home_page = DashboardPage(
            self._translator, on_new_sale=self.show_sales_invoice
        )
        self.unavailable_page = EmptyState(
            self._translator.gettext("empty.unavailable_title"),
            self._translator.gettext("empty.unavailable_sub"),
        )
        self.form_page = FormDemoPage(self._translator)
        self.table_page = TableDemoPage(self._translator)
        self.print_preview_page = PrintPreviewPage(
            self._translator, on_back=self.show_sales_invoice
        )
        self.sales_invoice_page = SalesInvoiceDemoPage(
            self._translator, on_print=self._open_print_preview
        )
        for page in (self.home_page, self.unavailable_page, self.form_page,
                     self.table_page, self.sales_invoice_page, self.print_preview_page):
            self.content.addWidget(page)

        if self._context is not None:
            self._build_stage03_pages()
            self._build_stage04_pages()
            self._build_stage05_pages()
            self._build_owner_fix_pages()

        layout.addWidget(self.content, stretch=1)

        self.setCentralWidget(container)

    def _build_stage03_pages(self) -> None:
        """Register real Stage 03 master-data screens + enable their nav commands."""
        from zenith_business.ui.master.pages import (
            CategoriesPage,
            CompanyPage,
            FinancialYearsPage,
            ItemsPage,
            PersonsPage,
            RolesPage,
            UnitsPage,
            UsersPage,
            WarehousesPage,
        )

        specs = [
            ("items", ItemsPage, "items.title"),
            ("persons", PersonsPage, "persons.title"),
            ("warehouses", WarehousesPage, "wh.title"),
            ("categories", CategoriesPage, "cat.title"),
            ("units", UnitsPage, "unit.title"),
            ("company", CompanyPage, "co.title"),
            ("financial_years", FinancialYearsPage, "fy.title"),
            ("users", UsersPage, "usr.title"),
            ("roles", RolesPage, "role.title"),
        ]
        for name, page_cls, _label in specs:
            page = page_cls(self._context, self._translator)
            self._stage03_pages[name] = page
            self.content.addWidget(page)
            self._stage03_actions[name] = lambda n=name: self._show_stage03(n)

        # Enabled contextual commands for the master-data and system categories.
        self._stage03_commands["menu.base_data"] = [
            ("items.title", True, "items"),
            ("persons.title", True, "persons"),
            ("wh.title", True, "warehouses"),
            ("cat.title", True, "categories"),
            ("unit.title", True, "units"),
        ]
        self._stage03_commands["menu.tools"] = [
            ("co.title", True, "company"),
            ("fy.title", True, "financial_years"),
            ("usr.title", True, "users"),
            ("role.title", True, "roles"),
        ] + _COMMANDS["menu.tools"]

    def _show_stage03(self, name: str) -> None:
        page = self._stage03_pages.get(name)
        if page is None:
            return
        if hasattr(page, "reload"):
            page.reload()
        self.content.setCurrentWidget(page)

    # ---- Stage 04: real Sales / Purchases / Returns ----------------------

    def _build_stage04_pages(self) -> None:
        """Register the real Stage 04 document screens under Buy & Sell."""
        from zenith_business.ui.documents.entry_page import DocumentEntryPage
        from zenith_business.ui.documents.list_page import DocumentListPage
        from zenith_business.ui.documents.return_page import ReturnEntryPage
        from zenith_business.ui.pages.print_preview import PrintPreviewPage

        ctx, t = self._context, self._translator

        # Shared document print preview (real persisted data, overridable title).
        self._doc_preview = PrintPreviewPage(t, on_back=lambda: self._doc_print_back())
        self._doc_print_back = self.show_home  # reassigned per navigation

        self._s4_sales_entry = DocumentEntryPage(
            ctx, t, mode="sale", on_close=self.show_home,
            on_print=self._doc_printer("sale"))
        self._s4_purchase_entry = DocumentEntryPage(
            ctx, t, mode="purchase", on_close=self.show_home,
            on_print=self._doc_printer("purchase"))
        self._s4_sales_return = ReturnEntryPage(
            ctx, t, mode="sales_return", on_close=self.show_home,
            on_print=self._doc_printer("sales_return"))
        self._s4_purchase_return = ReturnEntryPage(
            ctx, t, mode="purchase_return", on_close=self.show_home,
            on_print=self._doc_printer("purchase_return"))
        self._s4_sales_list = DocumentListPage(
            ctx, t, mode="sale", on_new=lambda: self._show_s4("s4_sale_new"),
            on_print=self._doc_printer("sale"),
            on_return=lambda i: self._open_return("sales_return", i),
            on_void=lambda i: self._void_sale(i))
        self._s4_purchase_list = DocumentListPage(
            ctx, t, mode="purchase", on_new=lambda: self._show_s4("s4_purchase_new"),
            on_print=self._doc_printer("purchase"),
            on_return=lambda i: self._open_return("purchase_return", i))

        self._stage04_pages = {
            "s4_sale_new": self._s4_sales_entry,
            "s4_purchase_new": self._s4_purchase_entry,
            "s4_sale_list": self._s4_sales_list,
            "s4_purchase_list": self._s4_purchase_list,
            "s4_sale_return": self._s4_sales_return,
            "s4_purchase_return": self._s4_purchase_return,
        }
        for page in list(self._stage04_pages.values()) + [self._doc_preview]:
            self.content.addWidget(page)
        for name in self._stage04_pages:
            self._stage03_actions[name] = lambda n=name: self._show_s4(n)

        # Real enabled Buy & Sell commands replace the Stage 01 placeholders.
        self._stage03_commands["menu.buy_sell"] = [
            ("s4.sale_new", True, "s4_sale_new"),
            ("s4.sale_list", True, "s4_sale_list"),
            ("s4.purchase_new", True, "s4_purchase_new"),
            ("s4.purchase_list", True, "s4_purchase_list"),
            ("s4.sale_return", True, "s4_sale_return"),
            ("s4.purchase_return", True, "s4_purchase_return"),
        ]

        # The dashboard's "New Sale" quick action now opens the real invoice.
        self.home_page._on_new_sale = lambda: self._show_s4("s4_sale_new")
        if hasattr(self.home_page, "bind_context"):
            self.home_page.bind_context(ctx)

    def _show_s4(self, name: str) -> None:
        page = self._stage04_pages.get(name)
        if page is None:
            return
        if hasattr(page, "reload"):
            page.reload()
        self.content.setCurrentWidget(page)

    def _doc_printer(self, kind: str):
        """Return an ``on_print(doc_id)`` handler for a document kind."""
        return lambda doc_id: self._open_doc_print(kind, doc_id)

    def _open_doc_print(self, kind: str, doc_id: int) -> None:
        from zenith_business.ui.documents import print_builder as pb
        builders = {
            "sale": pb.build_sale_invoice, "purchase": pb.build_purchase_invoice,
            "sales_return": pb.build_sales_return, "purchase_return": pb.build_purchase_return,
        }
        back_pages = {
            "sale": self._s4_sales_list, "purchase": self._s4_purchase_list,
            "sales_return": self._s4_sales_return, "purchase_return": self._s4_purchase_return,
        }
        data, title_key = builders[kind](self._context, doc_id)
        back = back_pages[kind]
        self._doc_print_back = lambda w=back: self.content.setCurrentWidget(w)
        self._doc_preview.show_invoice(data, title_key=title_key)
        self.content.setCurrentWidget(self._doc_preview)

    def _open_return(self, mode: str, source_id: int) -> None:
        page = (self._s4_sales_return if mode == "sales_return"
                else self._s4_purchase_return)
        page.open_source(source_id)
        self.content.setCurrentWidget(page)

    def _void_sale(self, sale_id: int) -> None:
        """Confirm and safely void a posted sale (defect #3), then refresh the list."""
        from PyQt6.QtWidgets import QMessageBox
        from zenith_business.core.exceptions import ZenithError
        sale = self._context.sales_repo.get(sale_id)
        if sale is None:
            return
        t = self._translator
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(t.gettext("s4.void_confirm_title"))
        box.setText(t.gettext("s4.void_confirm_title"))
        box.setInformativeText(
            t.gettext("s4.void_confirm_body").replace("{no}", sale["document_no"]))
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        if box.exec() != QMessageBox.StandardButton.Yes:
            return
        try:
            self._context.sales_documents.void_sale(
                sale_id=sale_id, reason="Owner void from sales list")
        except ZenithError as exc:
            QMessageBox.warning(self, t.gettext("s4.act_void"),
                                getattr(exc, "user_message", None) or str(exc))
            return
        self._s4_sales_list.reload()

    # ---- owner-fix: customer / supplier account ledgers ------------------

    def _build_owner_fix_pages(self) -> None:
        """Register the customer / supplier ledger screens under Account Reports."""
        from zenith_business.ui.documents.party_ledger_page import PartyLedgerPage
        ctx, t = self._context, self._translator
        self._customer_ledger = PartyLedgerPage(ctx, t, mode="customer", on_close=self.show_home)
        self._supplier_ledger = PartyLedgerPage(ctx, t, mode="supplier", on_close=self.show_home)
        self._ledger_pages = {"customer_ledger": self._customer_ledger,
                              "supplier_ledger": self._supplier_ledger}
        for page in self._ledger_pages.values():
            self.content.addWidget(page)
        for name in self._ledger_pages:
            self._stage03_actions[name] = lambda n=name: self._show_ledger(n)
        self._stage03_commands["menu.account_reports"] = [
            ("led.nav_customer", True, "customer_ledger"),
            ("led.nav_supplier", True, "supplier_ledger"),
        ]

    def _show_ledger(self, name: str) -> None:
        page = self._ledger_pages.get(name)
        if page is None:
            return
        self.content.setCurrentWidget(page)

    # ---- Stage 05: real Receipts / Payments / Expenses -------------------

    def _build_stage05_pages(self) -> None:
        """Register the real Stage 05 money-movement screens under Receipts & Payments."""
        from zenith_business.ui.documents.money_list_page import MoneyListPage
        from zenith_business.ui.documents.money_page import MoneyEntryPage
        from zenith_business.ui.documents.voucher_preview import VoucherPreviewPage

        ctx, t = self._context, self._translator
        self._voucher_preview = VoucherPreviewPage(t, on_back=lambda: self._voucher_back())
        self._voucher_back = self.show_home

        self._s5_receipt_new = MoneyEntryPage(ctx, t, mode="receipt", on_close=self.show_home,
                                              on_print=self._voucher_printer("receipt"))
        self._s5_payment_new = MoneyEntryPage(ctx, t, mode="payment", on_close=self.show_home,
                                              on_print=self._voucher_printer("payment"))
        self._s5_expense_new = MoneyEntryPage(ctx, t, mode="expense", on_close=self.show_home,
                                              on_print=self._voucher_printer("expense"))
        self._s5_receipt_list = MoneyListPage(
            ctx, t, mode="receipt", on_new=lambda: self._show_s5("s5_receipt_new"),
            on_print=self._voucher_printer("receipt"))
        self._s5_payment_list = MoneyListPage(
            ctx, t, mode="payment", on_new=lambda: self._show_s5("s5_payment_new"),
            on_print=self._voucher_printer("payment"))
        self._s5_expense_list = MoneyListPage(
            ctx, t, mode="expense", on_new=lambda: self._show_s5("s5_expense_new"),
            on_print=self._voucher_printer("expense"))

        self._stage05_pages = {
            "s5_receipt_new": self._s5_receipt_new, "s5_receipt_list": self._s5_receipt_list,
            "s5_payment_new": self._s5_payment_new, "s5_payment_list": self._s5_payment_list,
            "s5_expense_new": self._s5_expense_new, "s5_expense_list": self._s5_expense_list,
        }
        for page in list(self._stage05_pages.values()) + [self._voucher_preview]:
            self.content.addWidget(page)
        for name in self._stage05_pages:
            self._stage03_actions[name] = lambda n=name: self._show_s5(n)

        self._stage03_commands["menu.receipts_payments"] = [
            ("s5.nav_receipt", True, "s5_receipt_new"),
            ("s5.nav_receipt_list", True, "s5_receipt_list"),
            ("s5.nav_payment", True, "s5_payment_new"),
            ("s5.nav_payment_list", True, "s5_payment_list"),
            ("s5.nav_expense", True, "s5_expense_new"),
            ("s5.nav_expense_list", True, "s5_expense_list"),
        ]

    def _show_s5(self, name: str) -> None:
        page = self._stage05_pages.get(name)
        if page is None:
            return
        if hasattr(page, "reload"):
            page.reload()
        self.content.setCurrentWidget(page)

    def _voucher_printer(self, kind: str):
        return lambda doc_id: self._open_voucher_print(kind, doc_id)

    def _open_voucher_print(self, kind: str, doc_id: int) -> None:
        from zenith_business.ui.documents import voucher_builder as vb
        builders = {"receipt": vb.build_receipt_voucher, "payment": vb.build_payment_voucher,
                    "expense": vb.build_expense_voucher}
        back_pages = {"receipt": self._s5_receipt_list, "payment": self._s5_payment_list,
                      "expense": self._s5_expense_list}
        data = builders[kind](self._context, self._translator, doc_id)
        back = back_pages[kind]
        self._voucher_back = lambda w=back: self.content.setCurrentWidget(w)
        self._voucher_preview.show_voucher(data)
        self.content.setCurrentWidget(self._voucher_preview)

    def _build_status_bar(self) -> None:
        bar = QStatusBar()
        bar.setSizeGripEnabled(True)
        bar.setFixedHeight(ControlSize.STATUSBAR_HEIGHT)
        self.setStatusBar(bar)

        self._status_company = QLabel()
        self._status_db = QLabel()
        self._status_license = QLabel()
        self._status_license.setProperty("role", "status-strong")

        bar.addWidget(self._status_company, 1)
        bar.addPermanentWidget(self._status_db)
        bar.addPermanentWidget(vertical_line())
        bar.addPermanentWidget(self._status_license)

    # ---- navigation ------------------------------------------------------

    def show_home(self) -> None:
        self._current_category = None
        self.primary_nav.set_selected(None)
        self.context_bar.show_hint()
        # Refresh live dashboard figures each time Home is shown (Stage 04).
        if self._context is not None and hasattr(self.home_page, "bind_context"):
            self.home_page.bind_context(self._context)
        self.content.setCurrentWidget(self.home_page)

    def select_category(self, key: str) -> None:
        self._current_category = key
        self.primary_nav.set_selected(key)

        # Stage 03 (when a context is wired) overrides placeholder commands with
        # real enabled master-data screens; otherwise the Stage 01 specs are used.
        specs = self._stage03_commands.get(key) or _COMMANDS.get(key, [])
        actions: dict[str, Callable[[], None]] = {
            "form": self.show_form_demo,
            "table": self.show_table_demo,
            "sales_invoice": self.show_sales_invoice,
            "print_preview": self.show_print_preview,
            **self._stage03_actions,
        }
        commands = [
            (
                self._translator.gettext(text_key),
                enabled,
                actions.get(action) if action else None,
            )
            for text_key, enabled, action in specs
        ]
        self.context_bar.set_commands(commands)

        # Stage 03: a category with real screens opens its first screen directly
        # instead of the "unavailable" placeholder.
        stage03 = self._stage03_commands.get(key)
        if stage03:
            first_action = next((a for _k, en, a in stage03 if en and a), None)
            if first_action and first_action in self._stage03_actions:
                self._stage03_actions[first_action]()
            return

        if key == "menu.tools":
            # Tools keeps the current content; user picks a preview command.
            return

        # Business category → truthful "unavailable" state naming the section.
        category_name = self._translator.gettext(key)
        self.unavailable_page.set_text(
            self._translator.gettext("empty.unavailable_title"),
            f"{category_name} — {self._translator.gettext('empty.unavailable_sub')}",
        )
        self.content.setCurrentWidget(self.unavailable_page)

    def show_form_demo(self) -> None:
        self.content.setCurrentWidget(self.form_page)

    def show_table_demo(self) -> None:
        self.content.setCurrentWidget(self.table_page)

    def show_sales_invoice(self) -> None:
        self.content.setCurrentWidget(self.sales_invoice_page)

    def show_print_preview(self) -> None:
        self.print_preview_page.show_invoice(self.sales_invoice_page.demo_invoice)
        self.content.setCurrentWidget(self.print_preview_page)

    def _open_print_preview(self, data) -> None:
        self.print_preview_page.show_invoice(data)
        self.content.setCurrentWidget(self.print_preview_page)

    # ---- status ----------------------------------------------------------

    def _refresh_status(self) -> None:
        t = self._translator
        self._status_company.setText(t.gettext("status.no_company"))
        if self._database is not None and check_health(self._database).ok:
            self._status_db.setText(t.gettext("status.db_ok"))
        else:
            self._status_db.setText(t.gettext("status.db_unavailable"))
        state = self._license.current_state()
        self._status_license.setText(state.summary or t.gettext("status.unlicensed"))

    def _apply_identity(self) -> None:
        """Reflect the signed-in user in the header + status bar (Stage 02)."""
        if self._current_user is None:
            return
        self.header.set_identity(self._current_user.full_name, self._role_label())
        company = None
        if self._database is not None:
            import sqlite3

            try:
                from zenith_business.repositories.system import AppSettingsRepository
                company = AppSettingsRepository(self._database).get("company.name")
            except sqlite3.Error as exc:  # non-critical status text only
                _logger.warning("Could not read company name for header: %s", exc)
                company = None
        if company:
            self._status_company.setText(company)

    def _role_label(self) -> str:
        codes = getattr(self._current_user, "role_codes", ())
        if not codes:
            return self._translator.gettext("app.role")
        return codes[0].replace("_", " ").title()

    # ---- language / direction --------------------------------------------

    def _switch_language(self, code: str) -> None:
        if code not in (LANG_DARI, LANG_ENGLISH):
            return
        self._translator.set_language(code)
        self._config.ui.language = code
        _logger.info("Language switched to %s", code)

        self._apply_direction()
        # Retranslate every component (no rebuild of the whole window).
        self.header.retranslate(self._translator)
        self.primary_nav.retranslate(self._translator)
        self.home_page.retranslate(self._translator)
        self.form_page.retranslate(self._translator)
        self.table_page.retranslate(self._translator)
        self.sales_invoice_page.retranslate(self._translator)
        self.print_preview_page.retranslate(self._translator)
        self.unavailable_page.set_text(
            self._translator.gettext("empty.unavailable_title"),
            self._translator.gettext("empty.unavailable_sub"),
        )
        for page in self._stage03_pages.values():
            if hasattr(page, "retranslate"):
                page.retranslate(self._translator)
        for page in getattr(self, "_stage04_pages", {}).values():
            if hasattr(page, "retranslate"):
                page.retranslate(self._translator)
        for page in getattr(self, "_stage05_pages", {}).values():
            if hasattr(page, "retranslate"):
                page.retranslate(self._translator)
        for page in getattr(self, "_ledger_pages", {}).values():
            if hasattr(page, "retranslate"):
                page.retranslate(self._translator)
        if hasattr(self, "_doc_preview"):
            self._doc_preview.retranslate(self._translator)
        if hasattr(self, "_voucher_preview"):
            self._voucher_preview.retranslate(self._translator)
        self._refresh_status()
        self._apply_identity()
        # Restore the contextual command state for the active view.
        if self._current_category is None:
            self.context_bar.show_hint()
        else:
            self.select_category(self._current_category)

    def _apply_direction(self) -> None:
        direction = resolve_direction(
            self._translator.language, self._config.ui.direction
        )
        qt_dir = (
            Qt.LayoutDirection.RightToLeft
            if direction == Direction.RTL
            else Qt.LayoutDirection.LeftToRight
        )
        self.setLayoutDirection(qt_dir)

    # ---- public helpers (tests / bootstrap) ------------------------------

    @property
    def translator(self) -> Translator:
        return self._translator

    def current_direction(self) -> Direction:
        return resolve_direction(self._translator.language, self._config.ui.direction)
