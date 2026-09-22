"""The Zenith Soft License Manager, and the customer side it feeds.

The pair is the point: this application can **issue** because it holds a private
key, and Zenith Business can **verify** because it holds only the public half.
So these tests are written end to end — a licence signed here is activated there,
through the real windows, and the things that must fail are made to fail the same
way.

The Manager is vendor-only and never ships. That is asserted here too, because
"we would never package that" is not a guarantee, and the package auditor cannot
see a directory it was never pointed at.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

pytest.importorskip("cryptography", reason="signing needs a crypto backend")

from vendor.zenith_license_manager import (                            # noqa: E402
    issuing,
    keystore,
    preflight,
    products,
)
from zenith_business.security import vendor_key                        # noqa: E402
from vendor.zenith_license_manager.history import History              # noqa: E402
from zenith_business.core.config import AppConfig, LANG_ENGLISH        # noqa: E402
from zenith_business.database.connection import Database               # noqa: E402
from zenith_business.services.context import open_application_context  # noqa: E402
from zenith_business.services.licensing_service import (               # noqa: E402
    LicenseError,
    LicenseStatus,
)

PASSPHRASE = "vendor-passphrase-not-in-the-repo"
OWNER_PASSWORD = "Str0ngPass!"


@pytest.fixture(autouse=True)
def no_modal_dialogs(monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    for name in ("information", "warning", "critical"):
        monkeypatch.setattr(QMessageBox, name,
                            staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok))
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))


@pytest.fixture
def vendor(tmp_path, monkeypatch):
    """A vendor installation: an encrypted signing key and an empty history.

    The throwaway key is also installed as the key THIS BUILD verifies with, via
    the documented environment override. That is not a convenience: the Manager
    now refuses to issue under a key the application would not accept, so a test
    whose signing key differed from the application's would be testing the
    refusal rather than the licence. Making them the same here is what the real
    pairing looks like.
    """
    import base64

    key_dir = tmp_path / "vendor" / "keys"
    seed, public = keystore.generate_seed()
    monkeypatch.setenv(vendor_key.PUBLIC_KEY_ENV,
                       base64.b64encode(public).decode("ascii"))
    key_dir.mkdir(parents=True)
    keystore.write_key(key_dir / products.ZENITH_BUSINESS.key_filename, seed,
                       PASSPHRASE, product_id="ZENITH-BUSINESS",
                       label="Zenith Business")
    return {"key_dir": key_dir, "seed": seed, "public": public,
            "history": tmp_path / "vendor" / "history.json",
            "licenses": tmp_path / "vendor" / "licenses"}


@pytest.fixture
def customer(tmp_path, vendor):
    """A Zenith Business installation that trusts THIS vendor's public key."""
    database_file = tmp_path / "customer" / "zenith.db"
    database_file.parent.mkdir(parents=True)
    db = Database(str(database_file))
    ctx = open_application_context(db, backups_dir=str(tmp_path / "c-backups"),
                                   license_dir=str(tmp_path / "c-license"))
    ctx.licensing._explicit_key = vendor["public"]
    ctx.database_file = database_file
    ctx.setup.create_administrator(username="owner", password=OWNER_PASSWORD,
                                   full_name="Owner", company_name="Kabul Traders Ltd")
    yield ctx
    db.close()


def _issue(vendor, customer, *, license_type="FULL", days=None, serial=1,
           issued_to="Kabul Traders Ltd", request=None):
    return issuing.issue(
        product=products.ZENITH_BUSINESS, seed=vendor["seed"],
        request_code=request or customer.licensing.request_code(),
        license_type=license_type, serial=serial, issued_to=issued_to,
        phone="0785228719", city="Kabul", demo_days=days)


# ==========================================================================
# 1. the key never leaves the vendor side
# ==========================================================================

def test_a_signing_key_is_encrypted_at_rest(vendor):
    path = vendor["key_dir"] / products.ZENITH_BUSINESS.key_filename
    raw = path.read_bytes()
    assert raw.startswith(keystore.MAGIC)
    # The seed is not sitting in the file for anyone who opens it in an editor.
    assert vendor["seed"] not in raw
    assert vendor["seed"].hex().encode() not in raw


def test_the_wrong_passphrase_does_not_open_a_key(vendor):
    path = vendor["key_dir"] / products.ZENITH_BUSINESS.key_filename
    with pytest.raises(keystore.WrongPassphrase):
        keystore.load_seed(path, "not the passphrase")
    assert keystore.load_seed(path, PASSPHRASE) == vendor["seed"]


def test_an_edited_key_file_is_refused_rather_than_used(vendor):
    path = vendor["key_dir"] / products.ZENITH_BUSINESS.key_filename
    raw = bytearray(path.read_bytes())
    raw[-1] ^= 0xFF
    path.write_bytes(bytes(raw))
    with pytest.raises(keystore.WrongPassphrase):
        keystore.load_seed(path, PASSPHRASE)


def test_a_key_file_describes_itself_without_being_unlocked(vendor):
    info = keystore.read_info(vendor["key_dir"] / products.ZENITH_BUSINESS.key_filename)
    assert info.product_id == "ZENITH-BUSINESS"
    assert info.public_key_b64          # the PUBLIC half is readable, by design
    assert info.created_at


def test_writing_a_key_never_overwrites_an_existing_one(vendor):
    """Overwriting a signing key invalidates every licence issued under it."""
    path = vendor["key_dir"] / products.ZENITH_BUSINESS.key_filename
    before = path.read_bytes()
    seed, _ = keystore.generate_seed()
    with pytest.raises(keystore.KeystoreError):
        keystore.write_key(path, seed, PASSPHRASE, product_id="ZENITH-BUSINESS")
    assert path.read_bytes() == before


def test_keys_live_outside_the_repository():
    """The one accident that matters is a signing key committed to git."""
    import zenith_business

    repo = Path(zenith_business.__file__).resolve().parent.parent
    assert repo not in keystore.default_key_dir().resolve().parents
    assert "ZenithSoft" in str(keystore.default_key_dir())


# ==========================================================================
# 2. issuing, and what the customer does with it
# ==========================================================================

def test_a_full_licence_issued_here_activates_there(vendor, customer):
    issued = _issue(vendor, customer)
    assert issued.product_key.startswith("ZB1-")
    state = customer.licensing.import_product_key(issued.product_key)
    assert state.status == LicenseStatus.FULL
    assert state.license_id == "ZB-FULL-000001"
    assert state.issued_to == "Kabul Traders Ltd"
    assert state.expires_at is None            # FULL does not expire by default
    assert state.allows_login is True


@pytest.mark.parametrize("days", [7, 14, 15, 30, 60])
def test_a_demo_of_any_vendor_chosen_length_activates(vendor, customer, days):
    issued = _issue(vendor, customer, license_type="DEMO", days=days, serial=days)
    assert issued.demo_days == days
    state = customer.licensing.import_product_key(issued.product_key)
    assert state.status == LicenseStatus.DEMO
    assert state.demo_days_left == days
    assert state.expires_at == (date.today() + timedelta(days=days)).isoformat()


def test_the_demo_length_is_the_vendors_alone(vendor, customer):
    """Nothing the customer holds can change how long a demo runs."""
    issued = _issue(vendor, customer, license_type="DEMO", days=7)
    customer.licensing.import_product_key(issued.product_key)
    stored = customer.licensing.license_path.read_text(encoding="utf-8")
    # Editing the stored key to ask for longer breaks the signature.
    longer = stored.replace(stored[-6], "A" if stored[-6] != "A" else "B")
    with pytest.raises(LicenseError):
        customer.licensing.import_product_key(longer)
    assert customer.licensing.evaluate().demo_days_left == 7


def test_an_expired_demo_blocks_login_and_keeps_the_data(vendor, customer):
    issued = issuing.issue(
        product=products.ZENITH_BUSINESS, seed=vendor["seed"],
        request_code=customer.licensing.request_code(), license_type="DEMO",
        serial=9, expires_at=(date.today() - timedelta(days=1)).isoformat())
    with pytest.raises(LicenseError):
        customer.licensing.import_product_key(issued.product_key)
    rows = customer.db.connection().execute("SELECT COUNT(*) FROM users").fetchone()[0]
    assert rows == 1
    assert customer.database_file.is_file()


def test_a_key_for_another_machine_is_refused(vendor, customer):
    from zenith_business.security import machine_id, product_key
    from zenith_business.security.license_format import PRODUCT_ID

    other = machine_id.collect(PRODUCT_ID, overrides={
        "machine_guid": "guid-other", "volume_serial": "VOL-9",
        "mac": "112233445566", "cpu": "x86_64|Intel|8", "hostname": "other-pc"})
    foreign = product_key.encode_request(fingerprint=other.fingerprint,
                                         traits=other.traits)
    issued = _issue(vendor, customer, request=foreign)
    with pytest.raises(LicenseError):
        customer.licensing.import_product_key(issued.product_key)
    assert customer.licensing.evaluate().status == LicenseStatus.UNLICENSED


def test_a_key_signed_by_a_different_vendor_is_refused(vendor, customer):
    """A second signing key is a different vendor, and is not this one.

    Forged with the codec directly rather than through ``issuing.issue``,
    because the Manager now refuses to sign under a key the application would
    not accept — and someone forging a licence would not be using our Manager
    anyway. This is the customer-side guarantee: a well-formed key signed by
    the wrong hand is refused.
    """
    from zenith_business.security import product_key as pk

    impostor, _public = keystore.generate_seed()
    request = issuing.parse_request(customer.licensing.request_code())
    payload = pk.build_license_payload(
        license_type="FULL", fingerprint=request.fingerprint,
        traits=request.traits, issued_at=date.today().isoformat(),
        expires_at=None, serial=1, issued_to="Kabul Traders Ltd")
    forged = pk.encode_license(payload, keystore.sign(impostor, payload))

    assert forged.startswith("ZB1-")          # well-formed in every other way
    with pytest.raises(LicenseError):
        customer.licensing.import_product_key(forged)


def test_the_manager_refuses_to_sign_with_a_key_the_application_rejects(vendor,
                                                                        customer):
    """The failure the owner actually hit, now caught before a key exists.

    Pressing "Create key…" makes a perfectly valid signing key that the shipped
    application has never heard of. Every licence under it looked right in the
    Manager and was refused at the customer as "not genuine", with nothing on
    either side naming the cause.
    """
    stranger, _public = keystore.generate_seed()
    with pytest.raises(issuing.IssueError) as raised:
        issuing.issue(product=products.ZENITH_BUSINESS, seed=stranger,
                      request_code=customer.licensing.request_code(),
                      license_type="FULL", serial=1)
    assert preflight.WRONG_KEY_MESSAGE in str(raised.value)
    # And it says WHICH key, so the vendor can tell the two apart.
    assert products.fingerprint(keystore.public_key_for(stranger)) in str(raised.value)
    assert products.ZENITH_BUSINESS.expected_fingerprint() in str(raised.value)


def test_activation_survives_a_restart(vendor, customer, tmp_path):
    from zenith_business.services.licensing_service import LicenseService

    issued = _issue(vendor, customer, serial=42)
    customer.licensing.import_product_key(issued.product_key)
    fresh = LicenseService(license_dir=customer.licensing.license_path.parent,
                           public_key=vendor["public"])
    state = fresh.evaluate()
    assert state.status == LicenseStatus.FULL
    assert state.license_id == "ZB-FULL-000042"


def test_a_demo_cannot_be_extended_by_winding_the_clock_back(vendor, customer):
    from datetime import datetime, timezone

    issued = _issue(vendor, customer, license_type="DEMO", days=3)
    customer.licensing.import_product_key(issued.product_key)
    assert customer.licensing.evaluate().status == LicenseStatus.DEMO
    # The installation sees a date ten days on, then the clock is put back.
    customer.licensing.clock.observe(datetime.now(timezone.utc) + timedelta(days=10))
    assert customer.licensing.evaluate().status == LicenseStatus.DEMO_EXPIRED


def test_the_zlic_fallback_carries_the_same_licence(vendor, customer, tmp_path):
    issued = _issue(vendor, customer, serial=5)
    path = issuing.write_zlic(issued, vendor["seed"], tmp_path / "out")
    assert path.suffix == ".zlic"
    state = customer.licensing.import_license(path)
    assert state.status == LicenseStatus.FULL
    assert state.license_id == "ZB-FULL-000005"


def test_a_demo_zlic_also_carries_its_expiry(vendor, customer, tmp_path):
    issued = _issue(vendor, customer, license_type="DEMO", days=21, serial=6)
    path = issuing.write_zlic(issued, vendor["seed"], tmp_path / "out")
    state = customer.licensing.import_license(path)
    assert state.status == LicenseStatus.DEMO
    assert state.demo_days_left == 21


def test_a_mangled_request_code_is_refused_before_a_licence_is_made(vendor, customer):
    """Issuing against a broken code would bind a licence to no real machine."""
    code = customer.licensing.request_code()
    broken = code[:-4] + ("Q" if code[-4] != "Q" else "R") + code[-3:]
    with pytest.raises(issuing.IssueError):
        _issue(vendor, customer, request=broken)


def test_a_full_licence_may_still_be_given_an_expiry_on_purpose(vendor, customer):
    issued = issuing.issue(
        product=products.ZENITH_BUSINESS, seed=vendor["seed"],
        request_code=customer.licensing.request_code(), license_type="FULL",
        serial=2, expires_at=(date.today() + timedelta(days=365)).isoformat())
    state = customer.licensing.import_product_key(issued.product_key)
    assert state.status == LicenseStatus.FULL
    assert state.expires_at


# ==========================================================================
# 3. history
# ==========================================================================

def test_every_issue_is_written_down(vendor, customer):
    history = History(vendor["history"])
    first = _issue(vendor, customer, license_type="DEMO", days=14, serial=1)
    history.append(first)
    second = _issue(vendor, customer, serial=1)
    history.append(second)

    rows = history.load()
    assert len(rows) == 2
    assert {r.license_type for r in rows} == {"DEMO", "FULL"}
    assert rows[0].demo_days == 14
    assert rows[0].product_key == first.product_key


def test_history_is_never_silently_overwritten(vendor, customer):
    history = History(vendor["history"])
    history.append(_issue(vendor, customer, serial=1, issued_to="First Shop"))
    history.append(_issue(vendor, customer, serial=1, issued_to="Second Shop"))
    rows = history.load()
    assert len(rows) == 2, "a reissue replaced the original record"
    assert {r.issued_to for r in rows} == {"First Shop", "Second Shop"}
    clash = history.serial_in_use("ZENITH-BUSINESS", "FULL", 1)
    assert clash is not None


def test_the_next_licence_number_skips_what_is_used(vendor, customer):
    history = History(vendor["history"])
    assert history.next_serial("ZENITH-BUSINESS", "FULL") == 1
    history.append(_issue(vendor, customer, serial=7))
    assert history.next_serial("ZENITH-BUSINESS", "FULL") == 8
    # Types are numbered separately.
    assert history.next_serial("ZENITH-BUSINESS", "DEMO") == 1


@pytest.mark.parametrize("term", ["kabul", "0785228719", "ZB-FULL-000003",
                                  "Kabul Traders"])
def test_history_is_searchable_by_what_a_vendor_remembers(vendor, customer, term):
    history = History(vendor["history"])
    history.append(_issue(vendor, customer, serial=3))
    assert len(history.search(term)) == 1
    assert history.search("a shop that does not exist") == []


def test_the_history_file_is_not_inside_the_repository(vendor):
    import zenith_business
    from vendor.zenith_license_manager.history import default_history_path

    repo = Path(zenith_business.__file__).resolve().parent.parent
    assert repo not in default_history_path().resolve().parents


# ==========================================================================
# 4. the window
# ==========================================================================

def _manager(vendor, qapp):
    from vendor.zenith_license_manager.ui.main_window import LicenseManagerWindow

    return LicenseManagerWindow(key_dir=vendor["key_dir"],
                                history_path=vendor["history"],
                                license_dir=vendor["licenses"])


def _unlocked(vendor, qapp):
    """A Manager with the signing key loaded, exactly as unlocking leaves it.

    The refresh is the point, not a detail: issuing is enabled by the
    self-test and by nothing else, so a test that only dropped a seed into
    ``_seeds`` would find Generate disabled — which is the behaviour, not a
    bug in the test.
    """
    window = _manager(vendor, qapp)
    window._seeds["ZENITH-BUSINESS"] = vendor["seed"]
    window._refresh_key_state()
    return window


def test_the_manager_opens_and_reports_its_key_state(vendor, qapp):
    window = _manager(vendor, qapp)
    try:
        assert "Zenith Soft License Manager" in window.windowTitle()
        assert [window.tabs.tabText(i) for i in range(window.tabs.count())] == \
            ["Generate License", "License History"]
        # A key exists but has not been unlocked yet.
        assert "locked" in window.key_state.text().lower()
    finally:
        window.deleteLater()


def test_the_manager_generates_a_key_the_customer_accepts(vendor, customer, qapp):
    window = _unlocked(vendor, qapp)
    try:
        page = window.generate_page
        page.request.setPlainText(customer.licensing.request_code())
        page.customer_name.setText("Kabul Traders Ltd")
        page.city.setText("Kabul")
        page.type_demo.setChecked(True)
        page.day_buttons[1].setChecked(True)             # 14 days
        page.generate.click()

        key = page.key_box.toPlainText()
        assert key.startswith("ZB1-")
        state = customer.licensing.import_product_key(key)
        assert state.status == LicenseStatus.DEMO
        assert state.demo_days_left == 14
        assert History(vendor["history"]).load()[0].issued_to == "Kabul Traders Ltd"
    finally:
        window.deleteLater()


def test_the_window_shows_the_machine_id_as_the_code_is_pasted(vendor, customer, qapp):
    window = _manager(vendor, qapp)
    try:
        page = window.generate_page
        page.request.setPlainText(customer.licensing.request_code())
        assert page.machine_preview.text() == customer.licensing.machine.short
        page.request.setPlainText("ZBR1-NONSENSE")
        assert "⚠" in page.machine_preview.text()
    finally:
        window.deleteLater()


def test_the_demo_row_only_appears_for_a_demo(vendor, qapp):
    window = _manager(vendor, qapp)
    try:
        page = window.generate_page
        page.type_full.setChecked(True)
        assert page.demo_row.isVisible() is False
        assert page.selected_days() is None
        page.type_demo.setChecked(True)
        assert page.demo_row.isVisibleTo(page) is True
        assert page.selected_days() == 14
    finally:
        window.deleteLater()


def test_choosing_days_fills_in_the_expiry_date(vendor, qapp):
    window = _manager(vendor, qapp)
    try:
        page = window.generate_page
        page.type_demo.setChecked(True)
        page.day_buttons[3].setChecked(True)              # 30 days
        assert page.expiry.text() == (date.today() + timedelta(days=30)).isoformat()
        page.day_custom.setChecked(True)
        page.custom_days.setValue(45)
        assert page.expiry.text() == (date.today() + timedelta(days=45)).isoformat()
    finally:
        window.deleteLater()


def test_the_licence_number_is_suggested_and_editable(vendor, customer, qapp):
    window = _unlocked(vendor, qapp)
    try:
        page = window.generate_page
        assert page.license_id.text() == "ZB-FULL-000001"
        page.license_id.setText("ZB-FULL-000777")
        page.request.setPlainText(customer.licensing.request_code())
        page.generate.click()
        assert page.issued.license_id == "ZB-FULL-000777"
        state = customer.licensing.import_product_key(page.issued.product_key)
        assert state.license_id == "ZB-FULL-000777"
    finally:
        window.deleteLater()


def test_the_history_tab_lists_and_finds_what_was_issued(vendor, customer, qapp):
    window = _unlocked(vendor, qapp)
    try:
        page = window.generate_page
        page.request.setPlainText(customer.licensing.request_code())
        page.customer_name.setText("Herat Traders")
        page.generate.click()

        window.tabs.setCurrentIndex(1)
        history = window.history_page
        assert history.table.rowCount() == 1
        history.search.setText("herat")
        assert history.table.rowCount() == 1
        history.search.setText("nobody")
        assert history.table.rowCount() == 0
    finally:
        window.deleteLater()


def test_an_unsupported_product_cannot_be_issued(vendor, customer, qapp):
    """D-Clinic is registered for later; claiming support would ship dead keys."""
    with pytest.raises(issuing.IssueError):
        issuing.issue(product=products.D_CLINIC, seed=vendor["seed"],
                      request_code=customer.licensing.request_code(),
                      license_type="FULL", serial=1)


# ==========================================================================
# 5. none of this may reach a customer
# ==========================================================================

def test_zenith_business_never_imports_the_vendor_package():
    import zenith_business

    root = Path(zenith_business.__file__).resolve().parent
    for module in root.rglob("*.py"):
        text = module.read_text(encoding="utf-8")
        assert "zenith_license_manager" not in text, f"{module} reaches the Manager"
        assert "from vendor" not in text, f"{module} imports the vendor package"


def test_the_frozen_application_collects_only_the_application_package():
    spec = Path("packaging/zenith_business.spec").read_text(encoding="utf-8")
    assert "vendor" not in spec.replace("vendor_key", "")
    assert 'collect_submodules("zenith_business")' in spec


def test_the_vendor_package_holds_no_key_material():
    """The Manager makes and encrypts keys; it must not carry one."""
    root = Path(__file__).resolve().parent.parent / "vendor"
    for module in root.rglob("*.py"):
        text = module.read_text(encoding="utf-8")
        assert "BEGIN PRIVATE KEY" not in text
        assert "private_key" not in text or "private_key\"" in text or \
            "public_key" in text          # header field names are not keys


def test_no_signing_key_file_is_committed():
    repo = Path(__file__).resolve().parent.parent
    for pattern in ("*.zkey", "zenith-signing-key.json", "*.zlic"):
        found = [p for p in repo.rglob(pattern)
                 if ".git" not in p.parts and "tmp" not in p.parts]
        assert not found, f"{pattern} committed: {found}"


# ==========================================================================
# 6. keypair consistency — the pass that exists because a real licence was
#    issued under a key the shipped application had never heard of
# ==========================================================================

def test_the_product_reads_its_expected_key_from_the_application(vendor):
    """One source of truth: the Manager asks the application, it does not copy.

    A constant here would be right on the day it was written and wrong the
    first time a build was re-keyed — which is exactly the failure being fixed.
    """
    import base64

    expected = products.ZENITH_BUSINESS.expected_public_key()
    assert expected == vendor_key.public_key()
    assert expected == vendor["public"]
    assert products.ZENITH_BUSINESS.expected_fingerprint() == \
        products.fingerprint(base64.b64encode(vendor["public"]).decode())


def test_a_fingerprint_is_short_enough_for_a_person_to_compare(vendor):
    fp = products.fingerprint(vendor["public"])
    assert len(fp) == 19 and fp.count("-") == 3          # XXXX-XXXX-XXXX-XXXX
    assert products.fingerprint(None) == "—"
    assert products.fingerprint("not base64 at all") == "—"
    # Different keys must not share a fingerprint.
    other, _ = keystore.generate_seed()
    assert products.fingerprint(keystore.public_key_for(other)) != fp


def test_the_self_test_passes_only_for_the_applications_own_key(vendor):
    right = preflight.self_test(products.ZENITH_BUSINESS, vendor["seed"])
    assert right.ok
    assert right.fingerprint == right.expected_fingerprint
    assert [c.name for c in right.checks] == [
        "Signing key loaded", "Crypto backend", "Public key derives",
        "Sign/verify round-trip", "Product", "Matches the application's key"]

    stranger, _ = keystore.generate_seed()
    wrong = preflight.self_test(products.ZENITH_BUSINESS, stranger)
    assert not wrong.ok
    assert [c.name for c in wrong.failures] == ["Matches the application's key"]
    assert preflight.WRONG_KEY_MESSAGE in wrong.summary
    # Everything else about the stranger's key is genuinely fine, and the
    # report says so rather than blaming the key material.
    assert wrong.fingerprint != wrong.expected_fingerprint


def test_the_self_test_reports_no_key_without_raising():
    result = preflight.self_test(products.ZENITH_BUSINESS, None)
    assert not result.ok
    assert result.summary == "No signing key is unlocked."
    assert result.fingerprint == "—"


def test_a_key_filed_under_another_product_is_caught_by_name(vendor):
    result = preflight.self_test(products.ZENITH_BUSINESS, vendor["seed"],
                                 key_product_id="D-CLINIC")
    assert not result.ok
    assert any(c.name == "Product" and not c.ok for c in result.checks)


def test_a_build_with_no_embedded_key_cannot_confirm_any_signing_key(
        vendor, monkeypatch):
    """Honest about the one case where the check cannot be made."""
    monkeypatch.delenv(vendor_key.PUBLIC_KEY_ENV, raising=False)
    monkeypatch.setattr(vendor_key, "EMBEDDED_PUBLIC_KEY_B64", "")
    result = preflight.self_test(products.ZENITH_BUSINESS, vendor["seed"])
    assert not result.ok
    assert "carries no verification key" in result.summary


def test_every_issued_key_is_verified_before_it_is_returned(vendor, customer,
                                                            monkeypatch):
    """A key that fails the read-back must never reach the vendor's screen.

    Corrupted at the point the key is ASSEMBLED, after the signing key has
    already passed its own self-test — otherwise the earlier round-trip check
    catches it and the read-back is never reached. This is the failure no
    amount of checking the inputs would find: good key, good payload, damaged
    output.
    """
    real_encode = issuing.product_key.encode_license

    def damaged(payload, signature):
        return real_encode(payload, bytes([signature[0] ^ 0xFF]) + signature[1:])

    monkeypatch.setattr(issuing.product_key, "encode_license", damaged)
    with pytest.raises(issuing.IssueError) as raised:
        _issue(vendor, customer)
    assert "failed verification" in str(raised.value)
    assert "has not been issued" in str(raised.value)

    monkeypatch.setattr(issuing.product_key, "encode_license", real_encode)
    assert _issue(vendor, customer).product_key.startswith("ZB1-")


def test_a_key_that_signs_but_cannot_verify_is_caught_before_issuing(vendor,
                                                                     customer,
                                                                     monkeypatch):
    """The other half: a signing key whose own signatures do not verify."""
    monkeypatch.setattr(issuing.keystore, "sign", lambda seed, msg: bytes(64))
    with pytest.raises(issuing.IssueError) as raised:
        _issue(vendor, customer)
    assert "does not verify" in str(raised.value)


def test_the_read_back_checks_what_was_asked_for_not_just_the_signature(vendor,
                                                                        customer):
    """Type, machine and expiry are re-read from the finished key."""
    issued = _issue(vendor, customer, license_type="DEMO", days=14, serial=7)
    request = issuing.parse_request(customer.licensing.request_code())

    preflight.verify_issued(products.ZENITH_BUSINESS, issued.product_key,
                            expect_fingerprint=request.fingerprint,
                            expect_type="DEMO", expect_expiry=issued.expires_at)

    for kwargs, complaint in (
            (dict(expect_type="FULL"), "licence type"),
            (dict(expect_fingerprint="0" * 32), "wrong machine"),
            (dict(expect_expiry=None), "expiry")):
        args = dict(expect_fingerprint=request.fingerprint, expect_type="DEMO",
                    expect_expiry=issued.expires_at)
        args.update(kwargs)
        with pytest.raises(preflight.PreflightError) as raised:
            preflight.verify_issued(products.ZENITH_BUSINESS,
                                    issued.product_key, **args)
        assert complaint in str(raised.value)


def test_the_window_disables_issuing_until_the_right_key_is_loaded(vendor, qapp):
    """The button is the guarantee, not a label beside it."""
    window = _manager(vendor, qapp)
    try:
        assert window.generate_page.generate.isEnabled() is False
        assert "locked" in window.key_state.text().lower()

        window._seeds["ZENITH-BUSINESS"] = vendor["seed"]
        window._refresh_key_state()
        assert window.generate_page.generate.isEnabled() is True
        assert "verified" in window.key_state.text().lower()

        stranger, _ = keystore.generate_seed()
        window._seeds["ZENITH-BUSINESS"] = stranger
        window._refresh_key_state()
        assert window.generate_page.generate.isEnabled() is False
        assert "wrong signing key" in window.key_state.text().lower()
        assert preflight.WRONG_KEY_MESSAGE in window.diag_verdict.text()
    finally:
        window.deleteLater()


def test_the_window_shows_both_fingerprints_so_they_can_be_compared(vendor, qapp):
    window = _unlocked(vendor, qapp)
    try:
        own = products.fingerprint(vendor["public"])
        assert own in window.diag_fingerprint.text()
        assert own in window.diag_expected.text()      # they match, so both show it
        assert "Zenith Business" in window.diag_product.text()
        assert "unlocked" in window.diag_status.text()

        stranger, _ = keystore.generate_seed()
        window._seeds["ZENITH-BUSINESS"] = stranger
        window._refresh_key_state()
        # Now they differ, and the strip shows BOTH so the vendor can see which.
        assert products.fingerprint(keystore.public_key_for(stranger)) in \
            window.diag_fingerprint.text()
        assert own in window.diag_expected.text()
    finally:
        window.deleteLater()


def test_a_blocked_generate_click_produces_no_key_and_no_history(vendor, customer,
                                                                 qapp):
    """Clicking Generate with the wrong key must leave nothing behind."""
    window = _manager(vendor, qapp)
    try:
        stranger, _ = keystore.generate_seed()
        window._seeds["ZENITH-BUSINESS"] = stranger
        window._refresh_key_state()

        page = window.generate_page
        page.request.setPlainText(customer.licensing.request_code())
        page.generate.click()

        assert page.key_box.toPlainText() == ""
        assert page.copy_button.isEnabled() is False
        assert History(vendor["history"]).load() == []
    finally:
        window.deleteLater()
