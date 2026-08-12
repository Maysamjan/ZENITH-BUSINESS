"""Application identity (Prompt 01 §6, §32)."""

from __future__ import annotations

from zenith_business.core.identity import IDENTITY, AppIdentity


def test_identity_values() -> None:
    assert IDENTITY.company == "Zenith Soft"
    assert IDENTITY.product == "Zenith Business"
    assert IDENTITY.channel == "development"
    assert IDENTITY.version  # non-empty


def test_identity_titles() -> None:
    ident = AppIdentity(version="1.2.3")
    assert ident.title == "Zenith Business 1.2.3"
    assert ident.full_title == "Zenith Business 1.2.3 — Zenith Soft"


def test_identity_is_frozen() -> None:
    import dataclasses

    import pytest

    with pytest.raises(dataclasses.FrozenInstanceError):
        IDENTITY.version = "9.9.9"  # type: ignore[misc]
