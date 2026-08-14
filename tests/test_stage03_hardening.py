"""Stage 03 acceptance hardening (§8, §11) — defects found & fixed in acceptance."""

from __future__ import annotations

import pytest

from zenith_business.services.document_math import parse_money_input
from zenith_business.services.exceptions import ValidationError


def _unit(ctx):
    return ctx.units_repo.id_by_code("BAG")


# ---- non-finite numeric input (NaN / Infinity) is rejected cleanly (§11) ----

@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity", "1e999", "inf", "nan"])
def test_non_finite_price_rejected_as_validation_error(admin_context, bad) -> None:
    u = _unit(admin_context)
    before = admin_context.db.connection().execute("SELECT COUNT(*) FROM items").fetchone()[0]
    with pytest.raises(ValidationError):  # not a raw InvalidOperation
        admin_context.items.create(item_code=f"NF-{bad}", name="X", base_unit_id=u,
                                   default_sale_price=bad)
    assert admin_context.db.connection().execute(
        "SELECT COUNT(*) FROM items").fetchone()[0] == before


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity"])
def test_parse_money_input_rejects_non_finite(bad) -> None:
    with pytest.raises(ValidationError):
        parse_money_input(bad, field="price")


def test_non_finite_credit_limit_rejected(admin_context) -> None:
    with pytest.raises(ValidationError):
        admin_context.parties.create(party_code="P1", name="X", is_customer=True,
                                     credit_limit="Infinity")


# ---- company default warehouse must reference a real warehouse (§8) ----

def test_company_bogus_default_warehouse_rejected(admin_context) -> None:
    with pytest.raises(ValidationError):
        admin_context.company.save(legal_name="Co", default_warehouse_id=999999)


def test_company_valid_default_warehouse_accepted(admin_context) -> None:
    wh = admin_context.warehouses.create(code="MAIN", name="Main", is_default=True)
    admin_context.company.save(legal_name="Co", default_warehouse_id=wh)
    assert admin_context.company_repo.get()["default_warehouse_id"] == wh


# ---- company logo management (§5, §6) ----

def test_logo_import_and_persist(admin_context, tmp_path) -> None:
    from pathlib import Path
    # give the CompanyService a logo dir (fixture context has none by default)
    admin_context.company._logo_dir = tmp_path / "logo"
    src = tmp_path / "src.png"
    src.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 32)  # minimal PNG-ish bytes
    stored = admin_context.company.import_logo(str(src))
    assert Path(stored).exists()
    admin_context.company.save(legal_name="Co", logo_path=stored)
    assert admin_context.company_repo.get()["logo_path"] == stored


def test_logo_rejects_non_image(admin_context, tmp_path) -> None:
    from zenith_business.services.exceptions import ValidationError
    admin_context.company._logo_dir = tmp_path / "logo"
    bad = tmp_path / "notimage.txt"
    bad.write_text("nope")
    import pytest
    with pytest.raises(ValidationError):
        admin_context.company.import_logo(str(bad))


# ---- category parent (§10) ----

def test_category_parent_assignment(admin_context) -> None:
    parent = admin_context.categories.create(code="FOOD", name_en="Food", name_fa="غذا")
    child = admin_context.categories.create(code="DAIRY", name_en="Dairy", name_fa="لبنیات",
                                            parent_id=parent)
    assert admin_context.categories_repo.get(child)["parent_id"] == parent


def test_category_cannot_be_own_parent(admin_context) -> None:
    from zenith_business.services.exceptions import ValidationError
    import pytest
    c = admin_context.categories.create(code="X", name_en="X", name_fa="X")
    with pytest.raises(ValidationError):
        admin_context.categories.update(c, name_en="X", name_fa="X", parent_id=c)
