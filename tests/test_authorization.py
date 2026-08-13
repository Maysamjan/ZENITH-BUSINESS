"""Service-layer permission enforcement (Stage 02 §14)."""

from __future__ import annotations

import pytest

from zenith_business.services.exceptions import AuthenticationError, AuthorizationError


def test_require_without_user_raises(context) -> None:
    with pytest.raises(AuthenticationError):
        context.authz.require("sales.view")


def test_admin_can_everything(admin_context) -> None:
    assert admin_context.authz.can("users.manage")
    admin_context.authz.require("backup.create")  # does not raise


def test_cashier_denied_user_management(admin_context) -> None:
    admin_context.users.create_user(
        username="cash", password="C@shier99", full_name="Cash", role_codes=["CASHIER"])
    admin_context.auth.login("cash", "C@shier99")
    assert admin_context.authz.can("sales.create")
    assert not admin_context.authz.can("users.manage")
    with pytest.raises(AuthorizationError):
        admin_context.authz.require("users.manage")


def test_permission_enforced_even_bypassing_ui(admin_context) -> None:
    """Calling the service directly (no UI) still enforces the permission."""
    admin_context.users.create_user(
        username="view", password="V1ewerPass", full_name="Viewer", role_codes=["VIEWER"])
    admin_context.auth.login("view", "V1ewerPass")
    with pytest.raises(AuthorizationError):
        admin_context.users.create_user(
            username="x", password="Xy12345!", full_name="X", role_codes=["VIEWER"])
