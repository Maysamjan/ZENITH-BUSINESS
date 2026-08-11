"""UI shell foundation — redesigned shell (Prompt 01B §3-§8, §26).

Runs headlessly via the offscreen Qt platform (see conftest).
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtCore import Qt  # noqa: E402

from zenith_business.core.config import load_config  # noqa: E402
from zenith_business.core.i18n import Direction  # noqa: E402
from zenith_business.core.paths import resolve_paths  # noqa: E402
from zenith_business.database import Database  # noqa: E402
from zenith_business.database.connection import MEMORY  # noqa: E402
from zenith_business.ui.design.theme import build_stylesheet  # noqa: E402
from zenith_business.ui.main_window import MainWindow, _CATEGORIES  # noqa: E402


@pytest.fixture
def window(qapp, data_home: Path) -> MainWindow:
    paths = resolve_paths().ensure()
    config = load_config(paths)
    db = Database(MEMORY)
    db.connect()
    return MainWindow(config, database=db)


def test_stylesheet_builds() -> None:
    css = build_stylesheet()
    assert "#HeaderBar" in css
    assert "#PrimaryNav" in css
    assert "QStatusBar" in css


def test_window_title(window: MainWindow) -> None:
    assert "Zenith Business" in window.windowTitle()


def test_primary_nav_has_all_categories(window: MainWindow) -> None:
    for key in _CATEGORIES:
        btn = window.primary_nav.button(key)
        assert btn.text()  # localized, non-empty


def test_home_is_default_view(window: MainWindow) -> None:
    assert window.content.currentWidget() is window.home_page


def test_business_category_commands_are_disabled(window: MainWindow) -> None:
    window.select_category("menu.buy_sell")
    buttons = window.context_bar.command_buttons()
    assert buttons  # commands are shown
    assert all(not b.isEnabled() for b in buttons)  # but none functional
    # Selecting a not-yet-built category shows the truthful unavailable state.
    assert window.content.currentWidget() is window.unavailable_page


def test_tools_commands_reach_design_previews(window: MainWindow) -> None:
    window.select_category("menu.tools")
    buttons = window.context_bar.command_buttons()
    enabled = [b for b in buttons if b.isEnabled()]
    assert len(enabled) >= 2  # Form + Table previews are enabled
    window.show_form_demo()
    assert window.content.currentWidget() is window.form_page
    window.show_table_demo()
    assert window.content.currentWidget() is window.table_page


def test_status_bar_shows_real_state_only(window: MainWindow) -> None:
    from PyQt6.QtWidgets import QLabel

    bar = window.statusBar()
    texts = [lbl.text() for lbl in bar.findChildren(QLabel)]
    # Truthful development/unlicensed state — never a faked activation.
    assert any("Development" in t or "توسعه" in t for t in texts)


def test_default_direction_is_rtl_for_dari(window: MainWindow) -> None:
    assert window.current_direction() == Direction.RTL
    assert window.layoutDirection() == Qt.LayoutDirection.RightToLeft


def test_language_switch_flips_direction_and_retranslates(window: MainWindow) -> None:
    window._switch_language("en")
    assert window.current_direction() == Direction.LTR
    assert window.layoutDirection() == Qt.LayoutDirection.LeftToRight
    # Button text is ampersand-escaped for display; it renders as "Buy & Sell".
    assert window.primary_nav.button("menu.buy_sell").text().replace("&&", "&") == "Buy & Sell"
    window._switch_language("fa_AF")
    assert window.layoutDirection() == Qt.LayoutDirection.RightToLeft


def test_home_button_returns_home(window: MainWindow) -> None:
    window.select_category("menu.funds")
    assert window.content.currentWidget() is window.unavailable_page
    window.show_home()
    assert window.content.currentWidget() is window.home_page
