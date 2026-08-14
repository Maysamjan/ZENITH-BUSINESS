"""Stage 03 — company, financial year, warehouse, unit, category (§5-§9, §36)."""

from __future__ import annotations

import pytest

from zenith_business.services.exceptions import AuthorizationError, ValidationError


# ---- company ------------------------------------------------------------

def test_company_save_and_persist(admin_context) -> None:
    cid = admin_context.company.save(
        legal_name="Zenith Trading Co.", display_name="Zenith", tax_id="TIN-1")
    assert cid > 0
    row = admin_context.company.get()
    assert row["legal_name"] == "Zenith Trading Co."
    assert row["display_name"] == "Zenith"


def test_company_requires_name(admin_context) -> None:
    with pytest.raises(ValidationError):
        admin_context.company.save(legal_name="   ")


def test_company_requires_permission(context) -> None:
    context.setup.create_administrator(username="a", password="Str0ngPass!", full_name="A")
    context.users_repo  # noqa
    # cashier lacks company.manage
    context.auth.login("a", "Str0ngPass!")
    uid = context.users.create_user(username="c", password="C@sh1234", full_name="C",
                                    role_codes=["CASHIER"])
    context.auth.logout(); context.auth.login("c", "C@sh1234")
    with pytest.raises(AuthorizationError):
        context.company.save(legal_name="X")


# ---- financial year -----------------------------------------------------

def test_financial_year_valid_and_active(admin_context) -> None:
    fy = admin_context.financial_years.create(
        name="FY 2026", start_date="2026-01-01", end_date="2026-12-31", make_active=True)
    assert fy > 0
    assert admin_context.financial_years.active()["name"] == "FY 2026"
    assert admin_context.financial_years.is_postable("2026-06-15") is True
    assert admin_context.financial_years.is_postable("2027-01-01") is False


def test_financial_year_invalid_dates(admin_context) -> None:
    with pytest.raises(ValidationError):
        admin_context.financial_years.create(
            name="Bad", start_date="2026-12-31", end_date="2026-01-01")


def test_financial_year_single_active(admin_context) -> None:
    a = admin_context.financial_years.create(
        name="FY A", start_date="2025-01-01", end_date="2025-12-31", make_active=True)
    b = admin_context.financial_years.create(
        name="FY B", start_date="2026-01-01", end_date="2026-12-31", make_active=True)
    active = admin_context.financial_years.active()
    assert active["id"] == b
    assert active["name"] == "FY B"


def test_financial_year_overlap_rejected(admin_context) -> None:
    admin_context.financial_years.create(
        name="FY 2026", start_date="2026-01-01", end_date="2026-12-31")
    with pytest.raises(ValidationError):
        admin_context.financial_years.create(
            name="Overlap", start_date="2026-06-01", end_date="2027-06-01")


def test_financial_year_close_blocks_posting(admin_context) -> None:
    fy = admin_context.financial_years.create(
        name="FY 2026", start_date="2026-01-01", end_date="2026-12-31", make_active=True)
    assert admin_context.financial_years.is_postable("2026-06-15") is True
    admin_context.financial_years.close(fy)
    # Closed year is no longer active/open → not postable.
    assert admin_context.financial_years.is_postable("2026-06-15") is False


# ---- warehouse ----------------------------------------------------------

def test_warehouse_create_and_default(admin_context) -> None:
    w1 = admin_context.warehouses.create(code="MAIN", name="Main", is_default=True)
    w2 = admin_context.warehouses.create(code="SHOW", name="Showroom")
    admin_context.warehouses.set_default(w2)
    rows = {w["id"]: w for w in admin_context.warehouses.list()}
    assert rows[w2]["is_default"] == 1
    assert rows[w1]["is_default"] == 0


def test_warehouse_duplicate_code(admin_context) -> None:
    admin_context.warehouses.create(code="MAIN", name="Main")
    with pytest.raises(ValidationError):
        admin_context.warehouses.create(code="MAIN", name="Another")


def test_warehouse_referenced_history_not_deletable(admin_context) -> None:
    """FK RESTRICT protects a warehouse referenced by a stock movement (§22)."""
    unit = admin_context.units_repo.id_by_code("PCS")
    wh = admin_context.warehouses.create(code="MAIN", name="Main", is_default=True)
    item = admin_context.items_repo.create(item_code="I1", name="I", base_unit_id=unit)
    admin_context.inventory.record_opening(item_id=item, warehouse_id=wh,
                                           quantity_on_hand="5", unit_id=unit)
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        admin_context.db.connection().execute("DELETE FROM warehouses WHERE id = ?", (wh,))
    # Deactivation is the supported path instead.
    admin_context.warehouses.set_active(wh, False)
    assert admin_context.warehouses_repo.get(wh)["is_active"] == 0


# ---- unit / category ----------------------------------------------------

def test_unit_create_duplicate_and_decimal_flag(admin_context) -> None:
    u = admin_context.units.create(code="CTN2", name_en="Carton", name_fa="کارتن",
                                   decimal_allowed=False)
    assert admin_context.units_repo.get(u)["decimal_allowed"] == 0
    with pytest.raises(ValidationError):
        admin_context.units.create(code="CTN2", name_en="Dup", name_fa="x")


def test_category_create_edit_search(admin_context) -> None:
    c = admin_context.categories.create(code="FOOD", name_en="Food", name_fa="غذا")
    admin_context.categories.update(c, name_en="Foodstuff", name_fa="مواد غذایی")
    rows = {r["id"]: r for r in admin_context.categories.list()}
    assert rows[c]["name_en"] == "Foodstuff"
    with pytest.raises(ValidationError):
        admin_context.categories.create(code="FOOD", name_en="Dup", name_fa="x")
