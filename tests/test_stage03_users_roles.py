"""Stage 03 — user management, roles/permissions, admin protection (§18-§21, §36)."""

from __future__ import annotations

import pytest

from zenith_business.services.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ValidationError,
)


def test_create_user_assign_role_and_login(admin_context) -> None:
    uid = admin_context.users.create_user(
        username="cashier1", password="C@shier99", full_name="Cashier One",
        role_codes=["CASHIER"])
    assert uid > 0
    admin_context.auth.logout()
    user = admin_context.auth.login("cashier1", "C@shier99")
    assert "CASHIER" in user.role_codes


def test_password_reset_old_rejected_new_accepted(admin_context) -> None:
    uid = admin_context.users.create_user(
        username="bob", password="B0bOldPass!", full_name="Bob", role_codes=["CASHIER"])
    admin_context.users.reset_password(uid, "B0bNewPass!")
    # Old password no longer works…
    with pytest.raises(AuthenticationError):
        admin_context.auth.authenticate("bob", "B0bOldPass!")
    # …new password does.
    assert admin_context.auth.authenticate("bob", "B0bNewPass!") is not None


def test_deactivate_then_login_rejected(admin_context) -> None:
    uid = admin_context.users.create_user(
        username="tmp", password="Tmp12345!", full_name="Tmp", role_codes=["CASHIER"])
    admin_context.users.set_active(uid, False)
    with pytest.raises(AuthenticationError):
        admin_context.auth.authenticate("tmp", "Tmp12345!")


def test_search_users(admin_context) -> None:
    admin_context.users.create_user(username="ahmad", password="Ahmad123!",
                                    full_name="Ahmad Zahir", role_codes=["CASHIER"])
    rows = admin_context.users.search_users("ahmad")
    assert any(r["username"] == "ahmad" for r in rows)


def test_set_roles_replaces(admin_context) -> None:
    uid = admin_context.users.create_user(username="u1", password="U1pass!!", full_name="U1",
                                          role_codes=["CASHIER"])
    admin_context.users.set_roles(uid, ["SALESPERSON", "WAREHOUSE"])
    codes = {r["code"] for r in admin_context.users.roles_for(uid)}
    assert codes == {"SALESPERSON", "WAREHOUSE"}


# ---- administrator protection (§21) ------------------------------------

def test_cannot_deactivate_last_admin(admin_context) -> None:
    admin = admin_context.users_repo.get_by_username("admin")
    with pytest.raises(ValidationError):
        admin_context.users.set_active(admin["id"], False)


def test_cannot_strip_admin_role_from_last_admin(admin_context) -> None:
    admin = admin_context.users_repo.get_by_username("admin")
    with pytest.raises(ValidationError):
        admin_context.users.set_roles(admin["id"], ["CASHIER"])


def test_second_admin_allows_deactivating_first(admin_context) -> None:
    admin_context.users.create_user(username="admin2", password="Adm1nTwo!",
                                    full_name="Admin Two", role_codes=["ADMINISTRATOR"])
    admin = admin_context.users_repo.get_by_username("admin")
    # Now there are two active admins → deactivating one is allowed.
    admin_context.users.set_active(admin["id"], False)
    assert admin_context.users_repo.get_by_id(admin["id"])["is_active"] == 0


# ---- role / permission management (§19, §20) ---------------------------

def test_permission_groups_are_labeled(admin_context) -> None:
    groups = dict(admin_context.roles.permission_groups())
    assert "items" in groups and "persons" in groups
    codes = {c for _g, pairs in admin_context.roles.permission_groups() for c, _lbl in pairs}
    assert "persons.create" in codes
    # Human-readable labels, not just raw codes.
    persons = dict(groups["persons"])
    assert persons["persons.create"] == "Create persons"


def test_create_role_and_set_permissions(admin_context) -> None:
    rid = admin_context.roles.create_role(code="STOCKKEEPER", name="Stock Keeper")
    admin_context.roles.set_permissions(rid, ["items.view", "inventory.view", "warehouses.view"])
    assert admin_context.roles.permissions_for_role(rid) == {
        "items.view", "inventory.view", "warehouses.view"}


def test_administrator_role_cannot_lose_permissions(admin_context) -> None:
    admin_role = admin_context.roles_repo.get_by_code("ADMINISTRATOR")
    with pytest.raises(ValidationError):
        admin_context.roles.set_permissions(admin_role["id"], ["items.view"])


def test_roles_management_requires_permission(admin_context) -> None:
    admin_context.users.create_user(username="m", password="M4nager!!", full_name="M",
                                    role_codes=["CASHIER"])
    admin_context.auth.logout(); admin_context.auth.login("m", "M4nager!!")
    with pytest.raises(AuthorizationError):
        admin_context.roles.list_roles()


# ---- audit (§24) --------------------------------------------------------

def test_master_data_changes_audited_without_secrets(admin_context) -> None:
    admin_context.company.save(legal_name="Zenith Co.")
    uid = admin_context.users.create_user(username="au", password="Aud1tPass!",
                                          full_name="Au", role_codes=["CASHIER"])
    admin_context.users.reset_password(uid, "N3wAud1tPass!")
    actions = {a["action"] for a in admin_context.audit.recent(500)}
    assert "company.update" in actions
    assert "users.create" in actions
    assert "users.password_reset" in actions
    # No password/hash ever recorded.
    for a in admin_context.audit.recent(500):
        details = a.get("details") or ""
        assert "Aud1tPass" not in details and "pbkdf2_sha256" not in details
