"""User management service (Stage 02 §9, §12, §16)."""

from __future__ import annotations

import pytest

from zenith_business.services.exceptions import ValidationError


def test_create_user_with_role(admin_context) -> None:
    uid = admin_context.users.create_user(
        username="cashier1", password="C@shier99", full_name="Cashier One",
        role_codes=["CASHIER"])
    assert uid > 0
    roles = admin_context.users_repo.roles_for_user(uid)
    assert [r["code"] for r in roles] == ["CASHIER"]
    perms = admin_context.users_repo.permissions_for_user(uid)
    assert "sales.create" in perms
    assert "users.manage" not in perms


def test_duplicate_username_rejected(admin_context) -> None:
    admin_context.users.create_user(
        username="dup", password="Dup12345!", full_name="Dup", role_codes=["VIEWER"])
    with pytest.raises(ValidationError):
        admin_context.users.create_user(
            username="DUP", password="Dup12345!", full_name="Dup2", role_codes=["VIEWER"])


def test_weak_password_rejected(admin_context) -> None:
    with pytest.raises(ValidationError):
        admin_context.users.create_user(
            username="weak", password="123", full_name="Weak", role_codes=["VIEWER"])


def test_unknown_role_rejected(admin_context) -> None:
    with pytest.raises(ValidationError):
        admin_context.users.create_user(
            username="norole", password="Str0ngPass!", full_name="No Role",
            role_codes=["NOPE"])


def test_username_normalized(admin_context) -> None:
    admin_context.users.create_user(
        username="  MixedCase  ", password="Str0ngPass!", full_name="Mixed",
        role_codes=["VIEWER"])
    assert admin_context.users_repo.get_by_username("mixedcase") is not None
