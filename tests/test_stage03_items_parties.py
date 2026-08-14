"""Stage 03 — item master, party model, search providers (§10-§17, §36)."""

from __future__ import annotations

import pytest

from zenith_business.services.exceptions import AuthorizationError, ValidationError


def _unit(ctx):
    return ctx.units_repo.id_by_code("BAG")


# ---- items --------------------------------------------------------------

def test_item_create_and_fields(admin_context) -> None:
    u = _unit(admin_context)
    iid = admin_context.items.create(
        item_code="RICE25", name="Basmati Rice 25kg", base_unit_id=u, barcode="600123",
        alternate_name="Premium Rice", purchase_price="1500", default_sale_price="1980",
        reorder_level="10")
    row = admin_context.items.get(iid)
    assert row["item_code"] == "RICE25"
    assert row["alternate_name"] == "Premium Rice"
    assert row["default_sale_price"] == "1980.00"  # canonical Decimal text
    assert row["reorder_level"] == "10.000"


def test_item_duplicate_code(admin_context) -> None:
    u = _unit(admin_context)
    admin_context.items.create(item_code="I1", name="A", base_unit_id=u)
    with pytest.raises(ValidationError):
        admin_context.items.create(item_code="I1", name="B", base_unit_id=u)


def test_item_duplicate_barcode(admin_context) -> None:
    u = _unit(admin_context)
    admin_context.items.create(item_code="I1", name="A", base_unit_id=u, barcode="B1")
    with pytest.raises(ValidationError):
        admin_context.items.create(item_code="I2", name="B", base_unit_id=u, barcode="B1")


def test_item_blank_barcode_allowed_and_multiple(admin_context) -> None:
    u = _unit(admin_context)
    a = admin_context.items.create(item_code="I1", name="A", base_unit_id=u)  # no barcode
    b = admin_context.items.create(item_code="I2", name="B", base_unit_id=u, barcode="")
    assert admin_context.items.get(a)["barcode"] is None
    assert admin_context.items.get(b)["barcode"] is None


def test_item_negative_and_malformed_price_rejected(admin_context) -> None:
    u = _unit(admin_context)
    with pytest.raises(ValidationError):
        admin_context.items.create(item_code="N1", name="N", base_unit_id=u,
                                   default_sale_price="-5")
    with pytest.raises(ValidationError):
        admin_context.items.create(item_code="N2", name="N", base_unit_id=u,
                                   default_sale_price="12x3")


def test_item_negative_min_stock_rejected(admin_context) -> None:
    u = _unit(admin_context)
    with pytest.raises(ValidationError):
        admin_context.items.create(item_code="N3", name="N", base_unit_id=u,
                                   reorder_level="-1")


def test_item_search_by_all_fields(admin_context) -> None:
    u = _unit(admin_context)
    admin_context.items.create(item_code="RICE25", name="Basmati Rice", base_unit_id=u,
                               barcode="600123", alternate_name="Premium")
    assert admin_context.items.search("RICE25")       # code
    assert admin_context.items.search("basmati")      # name (case-insensitive)
    assert admin_context.items.search("premium")      # alternate name
    assert admin_context.items.search("600123")       # barcode


def test_item_edit_and_deactivate(admin_context) -> None:
    u = _unit(admin_context)
    iid = admin_context.items.create(item_code="I1", name="Old", base_unit_id=u)
    admin_context.items.update(iid, name="New", base_unit_id=u, default_sale_price="99")
    assert admin_context.items.get(iid)["name"] == "New"
    admin_context.items.set_active(iid, False)
    assert admin_context.items.get(iid)["is_active"] == 0


def test_item_requires_permission(admin_context) -> None:
    u = _unit(admin_context)
    admin_context.users.create_user(username="v", password="V1ewerPass", full_name="V",
                                    role_codes=["VIEWER"])
    admin_context.auth.logout(); admin_context.auth.login("v", "V1ewerPass")
    with pytest.raises(AuthorizationError):
        admin_context.items.create(item_code="Z", name="Z", base_unit_id=u)


# ---- parties (unified customer/supplier) --------------------------------

def test_party_customer_only(admin_context) -> None:
    p = admin_context.parties.create(party_code="C1", name="Cust", is_customer=True)
    row = admin_context.parties.get(p)
    assert row["is_customer"] == 1 and row["is_supplier"] == 0


def test_party_supplier_only(admin_context) -> None:
    p = admin_context.parties.create(party_code="S1", name="Sup", is_supplier=True)
    row = admin_context.parties.get(p)
    assert row["is_customer"] == 0 and row["is_supplier"] == 1


def test_party_both_roles_single_record(admin_context) -> None:
    p = admin_context.parties.create(party_code="B1", name="Both Co", is_customer=True,
                                     is_supplier=True, phone="0700123456")
    row = admin_context.parties.get(p)
    assert row["is_customer"] == 1 and row["is_supplier"] == 1
    # One record serves both roles.
    assert len(admin_context.parties.list(role="customer")) == 1
    assert len(admin_context.parties.list(role="supplier")) == 1
    assert len(admin_context.parties.list(role="both")) == 1


def test_party_requires_a_role(admin_context) -> None:
    with pytest.raises(ValidationError):
        admin_context.parties.create(party_code="X1", name="No role")


def test_party_duplicate_code(admin_context) -> None:
    admin_context.parties.create(party_code="P1", name="A", is_customer=True)
    with pytest.raises(ValidationError):
        admin_context.parties.create(party_code="P1", name="B", is_customer=True)


def test_party_search_by_name_code_phone(admin_context) -> None:
    admin_context.parties.create(party_code="KGS", name="Kabul General Store",
                                 is_customer=True, phone="0700999888", company_name="KGS Ltd")
    assert admin_context.parties.search("kabul")     # name
    assert admin_context.parties.search("KGS")       # code / company
    assert admin_context.parties.search("0700999")   # phone


def test_party_deactivate(admin_context) -> None:
    p = admin_context.parties.create(party_code="P1", name="A", is_customer=True)
    admin_context.parties.set_active(p, False)
    assert admin_context.parties.get(p)["is_active"] == 0


# ---- search providers ---------------------------------------------------

def test_item_search_provider_payload(admin_context) -> None:
    u = _unit(admin_context)
    admin_context.items.create(item_code="RICE25", name="Rice", base_unit_id=u,
                               default_sale_price="1980")
    rows = admin_context.item_search.search("rice")
    assert rows and rows[0].payload["item_code"] == "RICE25"
    assert rows[0].payload["sale_price"] == "1980.00"
    assert "base_unit_id" in rows[0].payload
    assert admin_context.item_search.search("") == []  # empty query → no rows


def test_party_search_provider_role_filter(admin_context) -> None:
    admin_context.parties.create(party_code="C1", name="Customer One", is_customer=True)
    admin_context.parties.create(party_code="S1", name="Supplier One", is_supplier=True)
    cust_rows = admin_context.customer_search.search("one")
    sup_rows = admin_context.supplier_search.search("one")
    assert [r.payload["party_code"] for r in cust_rows] == ["C1"]
    assert [r.payload["party_code"] for r in sup_rows] == ["S1"]
