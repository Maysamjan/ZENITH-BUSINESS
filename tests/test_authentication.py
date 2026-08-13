"""Authentication, initial setup, lockout (Stage 02 §10, §11)."""

from __future__ import annotations

import pytest

from zenith_business.services.authentication import MAX_FAILED_ATTEMPTS
from zenith_business.services.exceptions import (
    AccountInactiveError,
    AccountLockedError,
    AuthenticationError,
    SetupError,
    ValidationError,
)


def test_initial_setup_required_then_completed(context) -> None:
    assert context.is_setup_required is True
    context.setup.create_administrator(
        username="owner", password="Str0ngPass!", full_name="Owner")
    assert context.is_setup_required is False


def test_no_insecure_default_admin(context) -> None:
    # admin/admin is explicitly forbidden by the password policy.
    with pytest.raises(ValidationError):
        context.setup.create_administrator(
            username="admin", password="admin", full_name="X")


def test_setup_cannot_run_twice(context) -> None:
    context.setup.create_administrator(
        username="owner", password="Str0ngPass!", full_name="Owner")
    with pytest.raises(SetupError):
        context.setup.create_administrator(
            username="owner2", password="Another1!", full_name="Two")


def test_login_success_loads_permissions(context) -> None:
    context.setup.create_administrator(
        username="owner", password="Str0ngPass!", full_name="Owner")
    user = context.auth.login("owner", "Str0ngPass!")
    assert user.username == "owner"
    assert "ADMINISTRATOR" in user.role_codes
    assert user.has_permission("sales.post")
    assert context.session.is_authenticated


def test_login_wrong_password_is_generic(context) -> None:
    context.setup.create_administrator(
        username="owner", password="Str0ngPass!", full_name="Owner")
    with pytest.raises(AuthenticationError):
        context.auth.authenticate("owner", "wrong")


def test_lockout_after_repeated_failures(context) -> None:
    context.setup.create_administrator(
        username="owner", password="Str0ngPass!", full_name="Owner")
    for _ in range(MAX_FAILED_ATTEMPTS):
        with pytest.raises(AuthenticationError):
            context.auth.authenticate("owner", "wrong")
    # Now locked — even the correct password is refused while locked.
    with pytest.raises(AccountLockedError):
        context.auth.authenticate("owner", "Str0ngPass!")


def test_inactive_account_rejected(admin_context) -> None:
    uid = admin_context.users.create_user(
        username="bob", password="B0bStrong!", full_name="Bob", role_codes=["CASHIER"])
    admin_context.users.set_active(uid, False)
    with pytest.raises(AccountInactiveError):
        admin_context.auth.authenticate("bob", "B0bStrong!")


def test_passwords_never_stored_in_plaintext(context) -> None:
    context.setup.create_administrator(
        username="owner", password="Str0ngPass!", full_name="Owner")
    row = context.users_repo.get_by_username("owner")
    assert "Str0ngPass!" not in row["password_hash"]
    assert row["password_hash"].startswith("pbkdf2_sha256$")


def test_audit_never_contains_password(context) -> None:
    context.setup.create_administrator(
        username="owner", password="Str0ngPass!", full_name="Owner")
    context.auth.login("owner", "Str0ngPass!")
    for entry in context.audit.recent(100):
        assert "Str0ngPass!" not in (entry.get("details") or "")


def test_malformed_login_inputs_are_rejected(context) -> None:
    context.setup.create_administrator(
        username="owner", password="Str0ngPass!", full_name="Owner")
    for uname, pwd in [("", "x"), ("   ", "Str0ngPass!"), ("owner", ""),
                       ("owner", "   ")]:
        with pytest.raises(AuthenticationError):
            context.auth.authenticate(uname, pwd)


def test_successful_login_resets_failure_counter(context) -> None:
    context.setup.create_administrator(
        username="owner", password="Str0ngPass!", full_name="Owner")
    for _ in range(3):
        with pytest.raises(AuthenticationError):
            context.auth.authenticate("owner", "wrong")
    context.auth.authenticate("owner", "Str0ngPass!")
    row = context.users_repo.get_by_username("owner")
    assert row["failed_login_attempts"] == 0
    assert not row["is_locked"]
