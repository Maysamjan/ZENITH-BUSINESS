"""Application shell: top navigation, central workspace, status bar.

Prompt 01 §12-§14, §24, §33. The primary navigation is a **top** menu bar (no
permanent left sidebar). Business modules are NOT implemented — top menus exist
as clearly-disabled placeholders to demonstrate the navigation architecture
without appearing functional (§33).

The shell wires only real, existing information into the status bar (§24): the
database health, the license state (development), and the active language. No
business values are faked.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QActionGroup
from PyQt6.QtWidgets import QLabel, QMainWindow, QMenu, QStatusBar, QWidget

from zenith_business.core.config import AppConfig, LANG_DARI, LANG_ENGLISH
from zenith_business.core.i18n import Direction, Translator, resolve_direction
from zenith_business.core.identity import IDENTITY
from zenith_business.core.logging_setup import get_logger
from zenith_business.database import Database, check_health
from zenith_business.security.licensing import DevelopmentLicenseProvider, LicenseProvider
from zenith_business.ui.design.tokens import ControlSize
from zenith_business.ui.home_screen import HomeScreen

_logger = get_logger("ui.main_window")

# Placeholder top-level menu keys (order matters; RTL flips visually via layout
# direction, not by reordering). Business commands are intentionally absent.
_PLACEHOLDER_MENUS = (
    "menu.base_data",
    "menu.buy_sell",
    "menu.receipts_payments",
    "menu.funds",
    "menu.account_reports",
    "menu.item_reports",
    "menu.tools",
)


class MainWindow(QMainWindow):
    """Top-level application window (the shell)."""

    def __init__(
        self,
        config: AppConfig,
        *,
        database: Database | None = None,
        license_provider: LicenseProvider | None = None,
    ) -> None:
        super().__init__()
        self._config = config
        self._database = database
        self._license = license_provider or DevelopmentLicenseProvider()
        self._translator = Translator(config.ui.language)

        self.setWindowTitle(IDENTITY.title)
        self.setMinimumSize(900, 600)  # usable on smaller supported screens (§17)

        self._home = HomeScreen(self._translator)
        self.setCentralWidget(self._home)

        self._build_menus()
        self._build_status_bar()
        self._apply_direction()
        self._refresh_status()

    # ---- menus (TOP navigation) ------------------------------------------

    def _build_menus(self) -> None:
        menubar = self.menuBar()
        menubar.setNativeMenuBar(False)  # keep menus in-window on all platforms
        menubar.clear()
        self._menu_actions: dict[str, QMenu] = {}

        note = self._translator.gettext("menu.placeholder_note")
        for key in _PLACEHOLDER_MENUS:
            menu = menubar.addMenu(_display(self._translator.gettext(key)))
            # A single disabled item makes clear the module is not yet available.
            placeholder = QAction(note, self)
            placeholder.setEnabled(False)
            menu.addAction(placeholder)
            self._menu_actions[key] = menu

        # Tools menu carries the only *real* shell commands: language + exit.
        tools_menu = self._menu_actions["menu.tools"]
        tools_menu.addSeparator()
        self._add_language_menu(tools_menu)
        tools_menu.addSeparator()
        exit_action = QAction(_display(self._translator.gettext("menu.exit")), self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        tools_menu.addAction(exit_action)

    def _add_language_menu(self, parent: QMenu) -> None:
        lang_menu = parent.addMenu(_display(self._translator.gettext("menu.language")))
        group = QActionGroup(self)
        group.setExclusive(True)

        for key, code in (
            ("menu.language.english", LANG_ENGLISH),
            ("menu.language.dari", LANG_DARI),
        ):
            action = QAction(_display(self._translator.gettext(key)), self, checkable=True)
            action.setChecked(self._translator.language == code)
            action.triggered.connect(lambda _checked, c=code: self._switch_language(c))
            group.addAction(action)
            lang_menu.addAction(action)

    # ---- status bar ------------------------------------------------------

    def _build_status_bar(self) -> None:
        bar = QStatusBar()
        bar.setSizeGripEnabled(True)
        bar.setFixedHeight(ControlSize.STATUSBAR_HEIGHT)
        self.setStatusBar(bar)

        self._status_company = QLabel()
        self._status_db = QLabel()
        self._status_license = QLabel()

        # Permanent widgets sit on the trailing edge; direction-aware by Qt.
        bar.addWidget(self._status_company, 1)
        bar.addPermanentWidget(self._status_db)
        bar.addPermanentWidget(_separator())
        bar.addPermanentWidget(self._status_license)

    def _refresh_status(self) -> None:
        t = self._translator
        self._status_company.setText(t.gettext("status.no_company"))

        if self._database is not None:
            health = check_health(self._database)
            self._status_db.setText(
                t.gettext("status.db_ok") if health.ok
                else t.gettext("status.db_unavailable")
            )
        else:
            self._status_db.setText(t.gettext("status.db_unavailable"))

        state = self._license.current_state()
        # Show truthful development/unlicensed state (never fake "activated").
        self._status_license.setText(
            state.summary if state.summary else t.gettext("status.unlicensed")
        )

    # ---- language / direction --------------------------------------------

    def _switch_language(self, code: str) -> None:
        self._translator.set_language(code)
        self._config.ui.language = code
        _logger.info("Language switched to %s", code)
        self._apply_direction()
        self._build_menus()          # rebuild localized menus
        self._home.retranslate(self._translator)
        self._refresh_status()

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

    # ---- public helpers (used by tests / bootstrap) ----------------------

    @property
    def translator(self) -> Translator:
        return self._translator

    def current_direction(self) -> Direction:
        return resolve_direction(self._translator.language, self._config.ui.direction)


def _display(text: str) -> str:
    """Escape ``&`` for Qt menu/action labels so it renders literally.

    Qt treats a single ``&`` as a keyboard-mnemonic marker. Until deliberate
    mnemonics are assigned per module, escape ampersands (e.g. 'Buy & Sell')
    so labels display correctly instead of underlining the next character.
    """
    return text.replace("&", "&&")


def _separator() -> QWidget:
    sep = QLabel("·")
    sep.setProperty("class", "muted")
    return sep
