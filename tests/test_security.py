"""Security foundation: password hashing + licensing boundary (Prompt 01 §25-§29)."""

from __future__ import annotations

from zenith_business.security.licensing import (
    DevelopmentLicenseProvider,
    LicenseProvider,
    LicenseStatus,
)
from zenith_business.security.passwords import (
    hash_password,
    needs_rehash,
    verify_password,
)


def test_hash_is_not_plaintext() -> None:
    stored = hash_password("s3cret-pass")
    assert "s3cret-pass" not in stored
    assert stored.startswith("pbkdf2_sha256$")


def test_hash_is_salted_unique() -> None:
    assert hash_password("same") != hash_password("same")


def test_verify_correct_and_incorrect() -> None:
    stored = hash_password("correct horse")
    assert verify_password("correct horse", stored) is True
    assert verify_password("wrong", stored) is False


def test_verify_rejects_malformed() -> None:
    assert verify_password("x", "not-a-valid-hash") is False


def test_needs_rehash_detects_weaker_params() -> None:
    strong = hash_password("pw", iterations=240_000)
    assert needs_rehash(strong, iterations=240_000) is False
    assert needs_rehash(strong, iterations=500_000) is True
    assert needs_rehash("garbage") is True


def test_dev_license_provider_is_unlicensed() -> None:
    provider = DevelopmentLicenseProvider()
    assert isinstance(provider, LicenseProvider)  # satisfies the Protocol
    state = provider.current_state()
    assert state.status == LicenseStatus.DEVELOPMENT
    assert state.is_activated is False
