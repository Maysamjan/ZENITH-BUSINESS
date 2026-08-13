"""Authentication UI: gate flow, RTL, error state (Stage 02 §11)."""

from __future__ import annotations

import pytest

from zenith_business.core.config import AppConfig, LANG_DARI, LANG_ENGLISH
from zenith_business.core.i18n import Direction


@pytest.fixture
def auth_window(qapp, context):
    from zenith_business.ui.auth.auth_window import AuthWindow

    cfg = AppConfig()
    cfg.ui.language = LANG_ENGLISH
    return AuthWindow(context, cfg), context


def test_first_run_shows_setup_page(auth_window) -> None:
    window, _ = auth_window
    assert window._stack.currentWidget() is window._setup_page


def test_setup_password_mismatch_shows_error(auth_window) -> None:
    window, _ = auth_window
    window._handle_setup({
        "company_name": "Co", "full_name": "Owner", "username": "owner",
        "password": "Str0ngPass!", "confirm_password": "different",
    })
    # Error is populated and un-hidden (isVisible() would need a shown window).
    assert window._setup_page._error.text() != ""
    assert window._setup_page._error.isVisibleTo(window._setup_page)
    assert window._stack.currentWidget() is window._setup_page


def test_setup_success_advances_to_login(auth_window) -> None:
    window, ctx = auth_window
    window._handle_setup({
        "company_name": "Co", "full_name": "Owner", "username": "owner",
        "password": "Str0ngPass!", "confirm_password": "Str0ngPass!",
    })
    assert ctx.is_setup_required is False
    assert window._stack.currentWidget() is window._login_page
    assert window._login_page.username.text() == "owner"


def test_login_wrong_password_shows_generic_error(auth_window) -> None:
    window, ctx = auth_window
    ctx.setup.create_administrator(
        username="owner", password="Str0ngPass!", full_name="Owner")
    window._show_page(window._login_page)
    window._handle_login("owner", "nope")
    assert window._login_page._error.text() != ""
    assert window._login_page._error.isVisibleTo(window._login_page)
    assert window.authenticated_user is None


def test_login_success_accepts(auth_window) -> None:
    window, ctx = auth_window
    ctx.setup.create_administrator(
        username="owner", password="Str0ngPass!", full_name="Owner")
    window._show_page(window._login_page)
    window._handle_login("owner", "Str0ngPass!")
    assert window.authenticated_user is not None
    assert window.authenticated_user.username == "owner"


def test_language_switch_sets_rtl(auth_window) -> None:
    window, _ = auth_window
    assert window.current_direction() == Direction.LTR
    window._switch_language(LANG_DARI)
    assert window.current_direction() == Direction.RTL
    assert window.layoutDirection().name == "RightToLeft"


def test_password_field_toggle(qapp, context) -> None:
    from PyQt6.QtWidgets import QLineEdit

    from zenith_business.core.i18n import Translator
    from zenith_business.ui.auth.widgets import PasswordField

    field = PasswordField(Translator(LANG_ENGLISH), "login.password_ph")
    assert field.edit.echoMode() == QLineEdit.EchoMode.Password
    field.toggle.setChecked(True)
    field._on_toggle()
    assert field.edit.echoMode() == QLineEdit.EchoMode.Normal
