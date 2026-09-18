"""Stage 10 licensing: what must be refused, and what must keep working.

Every case here is stated as an outcome a customer or an attacker would see,
not as a call into an internal function, because the contract is "this licence
activates / this one does not".
"""

from __future__ import annotations

import shutil

import pytest

from zenith_business.security import machine_id as machine
from zenith_business.security.license_format import (
    PRODUCT_ID,
    TYPE_DEMO,
    TYPE_FULL,
    LicenseFormatError,
    canonical_bytes,
    parse_license,
    parse_request,
)
from zenith_business.services.licensing_service import (
    DemoPolicy,
    LicenseError,
    LicenseReason,
    LicenseService,
    LicenseStatus,
)

pytest.importorskip("cryptography", reason="test signing tooling only")
from tests.tooling.license_signing import (            # noqa: E402
    generate_keypair,
    make_license,
    tamper,
)

THIS_PC = {"machine_guid": "guid-this", "volume_serial": "VOL-1111",
           "mac": "aabbccddeeff", "cpu": "x86_64|Intel|8", "hostname": "shop-pc"}
OTHER_PC = {"machine_guid": "guid-other", "volume_serial": "VOL-9999",
            "mac": "112233445566", "cpu": "x86_64|Intel|8", "hostname": "other-pc"}


@pytest.fixture
def keys():
    return generate_keypair()


@pytest.fixture
def service(tmp_path, keys):
    _private, public = keys
    return LicenseService(license_dir=tmp_path / "license", public_key=public,
                          machine_overrides=THIS_PC)


@pytest.fixture
def this_machine():
    return machine.collect(PRODUCT_ID, overrides=THIS_PC)


def _licence(keys, this_machine, **kw) -> str:
    private, _public = keys
    return make_license(private, machine_fingerprint=this_machine.fingerprint,
                        machine_traits=this_machine.traits, **kw)


# ---- the happy path ------------------------------------------------------

def test_no_licence_file_is_demo_not_an_error(service):
    state = service.evaluate()
    assert state.status == LicenseStatus.DEMO
    assert state.allows_workspace is True


def test_a_licence_for_this_machine_activates(service, keys, this_machine, tmp_path):
    path = tmp_path / "good.zlic"
    path.write_text(_licence(keys, this_machine, license_id="ZB-FULL-000042",
                             issued_to="Kabul Traders Ltd"))
    state = service.import_license(path)
    assert state.status == LicenseStatus.FULL
    assert state.license_id == "ZB-FULL-000042"
    assert state.issued_to == "Kabul Traders Ltd"
    assert service.is_full() is True


def test_activation_survives_a_restart(service, keys, this_machine, tmp_path):
    path = tmp_path / "good.zlic"
    path.write_text(_licence(keys, this_machine))
    service.import_license(path)
    fresh = LicenseService(license_dir=service.license_path.parent,
                           public_key=keys[1], machine_overrides=THIS_PC)
    assert fresh.is_full() is True


# ---- tampering -----------------------------------------------------------

@pytest.mark.parametrize("field, value", [
    ("license_type", TYPE_DEMO),
    ("license_id", "ZB-FULL-999999"),
    ("product_id", "ZENITH-PAYROLL"),
    ("issued_to", "Someone Else"),
    ("issued_at", "2000-01-01"),
    ("expires_at", "2099-12-31"),
    ("machine.fingerprint", "00000000000000000000000000000000"),
])
def test_altering_any_signed_field_invalidates_the_licence(
        service, keys, this_machine, tmp_path, field, value):
    text = _licence(keys, this_machine)
    path = tmp_path / "bad.zlic"
    path.write_text(tamper(text, field, value))
    with pytest.raises(LicenseError):
        service.import_license(path)
    assert service._evaluate_text(path.read_text()).reason == LicenseReason.BAD_SIGNATURE


def test_reformatting_a_licence_does_NOT_invalidate_it(service, keys, this_machine):
    """Canonicalisation cuts both ways: a harmless re-indent must still verify."""
    import json
    text = _licence(keys, this_machine)
    document = json.loads(text)
    reformatted = json.dumps(document, indent=8, sort_keys=False)
    assert service._evaluate_text(reformatted).status == LicenseStatus.FULL


def test_a_licence_signed_by_another_key_is_rejected(service, this_machine):
    other_private, _ = generate_keypair()
    text = make_license(other_private, machine_fingerprint=this_machine.fingerprint,
                        machine_traits=this_machine.traits)
    assert service._evaluate_text(text).reason == LicenseReason.BAD_SIGNATURE


# ---- machine binding -----------------------------------------------------

def test_a_licence_for_another_machine_is_rejected(service, keys, tmp_path):
    private, _ = keys
    other = machine.collect(PRODUCT_ID, overrides=OTHER_PC)
    path = tmp_path / "foreign.zlic"
    path.write_text(make_license(private, machine_fingerprint=other.fingerprint,
                                 machine_traits=other.traits))
    with pytest.raises(LicenseError):
        service.import_license(path)
    assert service._evaluate_text(path.read_text()).reason == LicenseReason.WRONG_MACHINE


def test_copying_an_activated_install_to_another_pc_does_not_activate_it(
        service, keys, this_machine, tmp_path):
    path = tmp_path / "good.zlic"
    path.write_text(_licence(keys, this_machine))
    service.import_license(path)
    assert service.is_full() is True

    copied = tmp_path / "copied"
    shutil.copytree(service.license_path.parent, copied)
    on_other_pc = LicenseService(license_dir=copied, public_key=keys[1],
                                 machine_overrides=OTHER_PC)
    state = on_other_pc.evaluate()
    assert state.is_full is False
    assert state.reason == LicenseReason.WRONG_MACHINE


@pytest.mark.parametrize("changed, still_works", [
    ({"volume_serial": "NEW-DISK"}, True),                    # disk replaced
    ({"mac": "ffffffffffff"}, True),                          # new network card
    ({"hostname": "renamed"}, True),                          # PC renamed
    ({"mac": "ffffffffffff", "hostname": "renamed", "cpu": "other"}, True),
    ({"machine_guid": "new-guid"}, True),                     # OS reinstalled
    ({"machine_guid": "new", "volume_serial": "new"}, False),  # a different PC
])
def test_machine_binding_tolerates_change_but_not_a_different_pc(
        service, keys, this_machine, tmp_path, changed, still_works):
    path = tmp_path / "good.zlic"
    path.write_text(_licence(keys, this_machine))
    service.import_license(path)
    moved = LicenseService(license_dir=service.license_path.parent,
                           public_key=keys[1],
                           machine_overrides=dict(THIS_PC, **changed))
    assert moved.evaluate().is_full is still_works


def test_a_pc_that_merely_resembles_the_licensed_one_is_refused(
        service, keys, this_machine, tmp_path):
    """Weak traits alone can never reach the threshold — that is the design."""
    path = tmp_path / "good.zlic"
    path.write_text(_licence(keys, this_machine))
    service.import_license(path)
    lookalike = dict(THIS_PC, machine_guid="different", volume_serial="different")
    impostor = LicenseService(license_dir=service.license_path.parent,
                              public_key=keys[1], machine_overrides=lookalike)
    assert impostor.evaluate().is_full is False


def test_the_fingerprint_contains_no_raw_hardware_identifier(this_machine):
    blob = this_machine.fingerprint + "".join(this_machine.traits.values())
    for raw in THIS_PC.values():
        assert raw not in blob


# ---- product, type, expiry, malformed ------------------------------------

def test_a_licence_for_another_product_is_rejected(service, keys, this_machine):
    assert service._evaluate_text(
        _licence(keys, this_machine, product_id="ZENITH-PAYROLL")
    ).reason == LicenseReason.WRONG_PRODUCT


def test_an_unknown_licence_type_is_rejected(service, keys, this_machine):
    assert service._evaluate_text(
        _licence(keys, this_machine, license_type="ENTERPRISE")
    ).reason == LicenseReason.UNKNOWN_TYPE


def test_an_expired_licence_is_rejected(service, keys, this_machine):
    assert service._evaluate_text(
        _licence(keys, this_machine, expires_at="2000-01-01")
    ).reason == LicenseReason.EXPIRED


def test_a_licence_with_a_future_expiry_still_works(service, keys, this_machine):
    assert service._evaluate_text(
        _licence(keys, this_machine, expires_at="2099-01-01")
    ).status == LicenseStatus.FULL


@pytest.mark.parametrize("text", ["", "hello", "{}", '{"hello": 1}',
                                  '{"format": "zenith-license-1"}'])
def test_malformed_files_are_invalid_not_accepted(service, text):
    assert service._evaluate_text(text).status == LicenseStatus.INVALID


def test_parse_license_refuses_junk_rather_than_returning_it():
    for text in ("", "not json", "{}", '{"format": "other"}'):
        with pytest.raises(LicenseFormatError):
            parse_license(text)


# ---- failure never damages a working installation ------------------------

def test_a_rejected_import_leaves_the_working_licence_in_place(
        service, keys, this_machine, tmp_path):
    good = tmp_path / "good.zlic"
    good.write_text(_licence(keys, this_machine))
    service.import_license(good)
    before = service.license_path.read_text()

    bad = tmp_path / "bad.zlic"
    bad.write_text(tamper(good.read_text(), "license_id", "ZB-HACK"))
    with pytest.raises(LicenseError):
        service.import_license(bad)

    assert service.license_path.read_text() == before
    assert service.is_full() is True


def test_an_unconfigured_build_reports_itself_rather_than_letting_anything_through(
        tmp_path):
    service = LicenseService(license_dir=tmp_path, public_key=None,
                             machine_overrides=THIS_PC)
    assert service.evaluate().status == LicenseStatus.NO_VENDOR_KEY
    assert service.is_full() is False


def test_the_shipped_package_embeds_no_private_key():
    """The application may verify. It must not be able to sign."""
    import zenith_business.security.vendor_key as vendor_key

    key = vendor_key.public_key()
    assert key is None or len(key) == 32          # a public key, or none at all
    source = open(vendor_key.__file__, encoding="utf-8").read()
    for marker in ("PRIVATE KEY", "private_bytes", "sign("):
        assert marker not in source


def test_no_module_in_the_application_package_can_sign():
    """A grep-level guarantee, so a future change cannot quietly add signing."""
    from pathlib import Path

    import zenith_business

    root = Path(zenith_business.__file__).parent
    offenders = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "Ed25519PrivateKey" in text or "private_bytes" in text:
            offenders.append(str(path.relative_to(root)))
    assert offenders == []


# ---- demo ----------------------------------------------------------------

class _Settings:
    def __init__(self, started=None):
        self._v = {"license.demo_started_at": started} if started else {}

    def get(self, key, default=None):
        return self._v.get(key, default)

    def set(self, key, value):
        self._v[key] = value


def test_demo_reports_its_remaining_days(tmp_path, keys):
    from datetime import date, timedelta

    started = (date.today() - timedelta(days=10)).isoformat()
    service = LicenseService(license_dir=tmp_path, public_key=keys[1],
                             settings_repo=_Settings(started),
                             demo_policy=DemoPolicy(days=30),
                             machine_overrides=THIS_PC)
    state = service.evaluate()
    assert state.status == LicenseStatus.DEMO
    assert state.demo_days_left == 20


def test_an_expired_demo_blocks_the_workspace_but_destroys_nothing(tmp_path, keys):
    service = LicenseService(license_dir=tmp_path, public_key=keys[1],
                             settings_repo=_Settings("2000-01-01"),
                             demo_policy=DemoPolicy(days=30),
                             machine_overrides=THIS_PC)
    state = service.evaluate()
    assert state.status == LicenseStatus.DEMO_EXPIRED
    assert state.allows_workspace is False
    # the machine id is still shown, so the customer can still activate
    assert state.machine_short


def test_the_demo_clock_cannot_be_reset_by_restarting(tmp_path, keys):
    settings = _Settings()
    first = LicenseService(license_dir=tmp_path, public_key=keys[1],
                           settings_repo=settings, machine_overrides=THIS_PC)
    first.evaluate()
    recorded = settings.get("license.demo_started_at")
    assert recorded
    second = LicenseService(license_dir=tmp_path, public_key=keys[1],
                            settings_repo=settings, machine_overrides=THIS_PC)
    second.evaluate()
    assert settings.get("license.demo_started_at") == recorded


# ---- activation request --------------------------------------------------

def test_the_activation_request_carries_this_machine_and_no_secrets(
        service, tmp_path, this_machine):
    path = service.create_activation_request(tmp_path / "out")
    assert path.suffix == ".zreq"
    document = parse_request(path.read_text())
    assert document["product_id"] == PRODUCT_ID
    assert document["machine"]["fingerprint"] == this_machine.fingerprint
    assert "signature" not in document
    text = path.read_text()
    for raw in THIS_PC.values():
        assert raw not in text


def test_an_activation_request_always_gets_its_extension(service, tmp_path):
    assert service.create_activation_request(tmp_path / "req").suffix == ".zreq"
    assert service.create_activation_request(tmp_path / "a.txt").suffix == ".zreq"
