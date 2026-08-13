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
        layout.addWidget(self.content, stretch=1)

        self.setCentralWidget(container)

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
        self.content.setCurrentWidget(self.home_page)

    def select_category(self, key: str) -> None:
        self._current_category = key
        self.primary_nav.set_selected(key)

        specs = _COMMANDS.get(key, [])
        actions: dict[str, Callable[[], None]] = {
            "form": self.show_form_demo,
            "table": self.show_table_demo,
            "sales_invoice": self.show_sales_invoice,
            "print_preview": self.show_print_preview,
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
            try:
                from zenith_business.repositories.system import AppSettingsRepository
                company = AppSettingsRepository(self._database).get("company.name")
            except Exception:  # pragma: no cover - status text is non-critical
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
