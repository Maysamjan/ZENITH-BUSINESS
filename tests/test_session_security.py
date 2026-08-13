"""Session security (Stage 02 §15, §17)."""

from __future__ import annotations

from zenith_business.services.session import CurrentUser


def test_login_populates_then_logout_clears(admin_context) -> None:
    assert admin_context.session.is_authenticated
    assert admin_context.session.username == "admin"
    admin_context.auth.logout()
    assert not admin_context.session.is_authenticated
    assert admin_context.session.user is None
    assert admin_context.session.user_id is None


def test_relogin_creates_correct_identity(admin_context) -> None:
    admin_context.users.create_user(
        username="cash", password="C@shier99", full_name="Cash", role_codes=["CASHIER"])
    admin_context.auth.logout()
    user = admin_context.auth.login("cash", "C@shier99")
    assert user.username == "cash"
    assert "CASHIER" in user.role_codes
    assert "ADMINISTRATOR" not in user.role_codes
    assert not user.has_permission("users.manage")
    assert admin_context.session.user.username == "cash"


def test_session_holds_no_password_material(admin_context) -> None:
    user = admin_context.session.user
    assert isinstance(user, CurrentUser)
    # The snapshot has no password/hash attributes at all.
    for field in vars(user):
        assert "password" not in field.lower()
        assert "hash" not in field.lower()
