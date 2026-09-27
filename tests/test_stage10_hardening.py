"""Stage 10 hardening: encrypted backups, audit chain, licence state, packaging.

Each test states an outcome a customer or an attacker would see.
"""

from __future__ import annotations

import base64
import json
import platform
import sqlite3
import uuid
from pathlib import Path

import pytest

from zenith_business.database.connection import Database
from zenith_business.security import backup_crypto, signatures
from zenith_business.services.context import open_application_context
from zenith_business.services.exceptions import ValidationError
from zenith_business.services.safe_restore import inspect_backup

pytest.importorskip("cryptography", reason="the vetted verification backend")
from tests.tooling.license_signing import generate_keypair, make_license  # noqa: E402

PASSWORD = "Str0ngPass!"


@pytest.fixture
def shop(tmp_path, monkeypatch):
    private, public = generate_keypair()
    monkeypatch.setenv("ZENITH_LICENSE_PUBLIC_KEY",
                       base64.b64encode(public).decode("ascii"))
    database_file = tmp_path / "data" / "zenith.db"
    database_file.parent.mkdir(parents=True)
    db = Database(str(database_file))
    ctx = open_application_context(db, backups_dir=str(tmp_path / "backups"),
                                   license_dir=str(tmp_path / "license"))
    ctx.setup.create_administrator(username="owner", password=PASSWORD,
                                   full_name="Owner", company_name="Kabul Traders")
    ctx.auth.login("owner", PASSWORD)
    ctx.database_file = database_file
    ctx.backups_dir = tmp_path / "backups"
    ctx.license_dir = tmp_path / "license"
    ctx.signing_key = private
    yield ctx
    db.close()


# ---- §4 crypto review ----------------------------------------------------

def test_verification_uses_a_vetted_library_not_hand_written_curve_code():
    assert signatures.backend_available() is True
    assert signatures.backend_name().startswith("cryptography")


def test_the_hand_written_verifier_is_gone():
    import zenith_business

    root = Path(zenith_business.__file__).parent
    assert not (root / "security" / "ed25519_verify.py").exists()


def test_verification_fails_closed_when_the_backend_is_missing(monkeypatch):
    """No backend must mean 'not licensed', never 'assume licensed'."""
    import builtins

    real_import = builtins.__import__

    def no_crypto(name, *args, **kwargs):
        if name.startswith("cryptography"):
            raise ImportError("simulated missing backend")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_crypto)
    assert signatures.backend_available() is False
    assert signatures.verify(b"\x00" * 32, b"message", b"\x00" * 64) is False


def test_a_build_without_a_backend_reports_itself_rather_than_activating(
        shop, monkeypatch):
    monkeypatch.setattr(signatures, "backend_available", lambda: False)
    monkeypatch.setattr(
        "zenith_business.services.licensing_service.backend_available", lambda: False)
    state = shop.licensing.evaluate()
    assert state.is_full is False
    assert state.reason == "no_crypto_backend"


def test_the_vendor_tool_signs_exactly_what_the_reference_produces():
    """Both signing paths audited: the offline tool must not diverge."""
    import importlib.util
    import os

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    spec = importlib.util.spec_from_file_location(
        "vendor_tool", Path(__file__).resolve().parents[1] / "tools"
        / "zenith_license_tool.py")
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)

    for _ in range(5):
        seed = os.urandom(32)
        message = os.urandom(64)
        reference = Ed25519PrivateKey.from_private_bytes(seed)
        assert tool.public_key_from_seed(seed) == reference.public_key().public_bytes(
            __import__("cryptography.hazmat.primitives.serialization",
                       fromlist=["Encoding"]).Encoding.Raw,
            __import__("cryptography.hazmat.primitives.serialization",
                       fromlist=["PublicFormat"]).PublicFormat.Raw)
        assert tool.sign(seed, message) == reference.sign(message)
        # and the application accepts what the tool produced
        assert signatures.verify(tool.public_key_from_seed(seed), message,
                                 tool.sign(seed, message)) is True


# ---- §2 backup security --------------------------------------------------

def test_an_encrypted_backup_does_not_leak_business_data(shop):
    shop.parties.create(party_code="C1", name="SECRET CUSTOMER", is_customer=True)
    path = shop.backup.create_backup(passphrase=PASSWORD)
    assert path.suffix == ".zbak"
    assert b"SECRET CUSTOMER" not in path.read_bytes()


def test_the_plain_intermediate_is_not_left_behind(shop):
    shop.backup.create_backup(passphrase=PASSWORD)
    assert list(shop.backups_dir.glob("*.db")) == []


def test_a_backup_can_be_identified_without_the_passphrase(shop):
    path = shop.backup.create_backup(passphrase=PASSWORD)
    header = backup_crypto.read_header(path)
    assert header is not None and header.schema_version
    assert inspect_backup(path).reason == "encrypted"


def test_the_right_passphrase_opens_it_and_a_wrong_one_does_not(shop):
    path = shop.backup.create_backup(passphrase=PASSWORD)
    assert inspect_backup(path, passphrase=PASSWORD).ok is True
    assert inspect_backup(path, passphrase="wrong").reason == "bad_passphrase"


@pytest.mark.parametrize("where", ["body", "header"])
def test_a_single_altered_byte_is_refused(shop, tmp_path, where):
    path = shop.backup.create_backup(passphrase=PASSWORD)
    raw = bytearray(path.read_bytes())
    if where == "body":
        raw[-40] ^= 0x01
    else:
        raw[raw.index(b'"product"') + 2] ^= 0x01
    altered = tmp_path / "altered.zbak"
    altered.write_bytes(bytes(raw))
    assert inspect_backup(altered, passphrase=PASSWORD).ok is False


def test_restore_of_an_encrypted_backup_needs_its_passphrase(shop):
    path = shop.backup.create_backup(passphrase=PASSWORD)
    with pytest.raises(ValidationError):
        shop.safe_restore.restore(path, shop.database_file, confirmed=True)


def test_an_encrypted_backup_restores_correctly(shop):
    shop.parties.create(party_code="C1", name="IN THE BACKUP", is_customer=True)
    path = shop.backup.create_backup(passphrase=PASSWORD)
    shop.parties.create(party_code="C2", name="ADDED LATER", is_customer=True)

    result = shop.safe_restore.restore(path, shop.database_file, confirmed=True,
                                       passphrase=PASSWORD)
    assert result.integrity_ok is True
    restored = Database(str(shop.database_file))
    try:
        names = {r["name"] for r in
                 restored.connection().execute("SELECT name FROM parties")}
    finally:
        restored.close()
    assert names == {"IN THE BACKUP"}


def test_legacy_plain_backups_still_restore(shop):
    """Encrypting must not orphan the backups a customer already has."""
    shop.parties.create(party_code="C1", name="OLD BACKUP DATA", is_customer=True)
    plain = shop.backup.create_backup()          # no passphrase — the old shape
    assert plain.suffix == ".db"
    assert inspect_backup(plain).ok is True
    shop.parties.create(party_code="C2", name="LATER", is_customer=True)
    shop.safe_restore.restore(plain, shop.database_file, confirmed=True)
    restored = Database(str(shop.database_file))
    try:
        names = {r["name"] for r in
                 restored.connection().execute("SELECT name FROM parties")}
    finally:
        restored.close()
    assert names == {"OLD BACKUP DATA"}


# ---- §5 audit integrity --------------------------------------------------

def test_the_audit_chain_verifies_on_a_healthy_log(shop):
    shop.audit_chain.seal()
    report = shop.audit_chain.verify()
    assert report.ok is True and report.sealed > 0


def test_editing_an_audit_row_directly_is_detected(shop):
    shop.audit_chain.seal()
    shop.db.connection().execute(
        "UPDATE audit_log SET details = 'nothing happened' WHERE id = 1")
    report = shop.audit_chain.verify()
    assert report.ok is False
    assert report.first_bad_id == 1
    assert "altered" in report.detail


def test_deleting_an_audit_row_is_detected(shop):
    shop.backup.create_backup()
    shop.audit_chain.seal()
    rows = shop.db.connection().execute(
        "SELECT id FROM audit_log ORDER BY id").fetchall()
    shop.db.connection().execute("DELETE FROM audit_log WHERE id = ?",
                                 (rows[1]["id"],))
    assert shop.audit_chain.verify().ok is False


def test_a_row_inserted_into_already_sealed_history_is_detected(shop):
    """The hole this closed: an UNSEALED forgery slipped between sealed rows.

    Verification skipped unsealed rows entirely, so a forged entry inserted
    among sealed history chained correctly around it and passed. A legitimate
    unsealed row is always at the TAIL — anything earlier was put there.
    """
    shop.backup.create_backup()
    # spread the ids so there is a gap to insert into, as a file editor would
    shop.db.connection().execute("UPDATE audit_log SET id = id * 10")
    shop.audit_chain.seal()
    assert shop.audit_chain.verify().ok is True

    shop.db.connection().execute(
        "INSERT INTO audit_log (id, user_id, username, action, created_at, details)"
        " VALUES (15, 1, 'owner', 'forged.payment', '2020-01-01T00:00:00Z', 'never')")
    report = shop.audit_chain.verify()
    assert report.ok is False
    assert report.first_bad_id == 15
    assert "inserted" in report.detail


def test_appending_a_row_at_the_end_is_not_reported_as_tampering(shop):
    """Stated honestly: a NEW entry at the tail is indistinguishable from real
    activity, and is not claimed to be detectable."""
    shop.audit_chain.seal()
    shop.audit_repo.record(action="test.appended", details="legitimate new entry")
    assert shop.audit_chain.verify().ok is True


def test_a_row_edited_then_rehashed_by_hand_still_breaks_the_chain(shop):
    """Recomputing ONE hash is not enough: the following entries disagree."""
    shop.backup.create_backup()
    shop.audit_chain.seal()
    from zenith_business.services.audit_chain import compute_hash

    rows = shop.db.connection().execute(
        "SELECT * FROM audit_log ORDER BY id").fetchall()
    victim = rows[0]
    shop.db.connection().execute(
        "UPDATE audit_log SET details = 'rewritten' WHERE id = ?", (victim["id"],))
    changed = shop.db.connection().execute(
        "SELECT * FROM audit_log WHERE id = ?", (victim["id"],)).fetchone()
    shop.db.connection().execute(
        "UPDATE audit_log SET entry_hash = ? WHERE id = ?",
        (compute_hash(changed["prev_hash"] or "", changed), victim["id"]))
    assert shop.audit_chain.verify().ok is False


def test_unsealed_entries_are_not_reported_as_tampering(shop):
    """A row written since the last seal is normal, not evidence of an attack."""
    shop.audit_chain.seal()
    shop.audit_repo.record(action="test.fresh", details="written after sealing")
    report = shop.audit_chain.verify()
    assert report.ok is True
    assert report.unsealed >= 1


def test_sealing_is_idempotent(shop):
    shop.audit_chain.seal()
    assert shop.audit_chain.seal() == 0


def test_the_chain_survives_normal_business_activity(shop):
    for index in range(5):
        shop.parties.create(party_code=f"C{index}", name=f"Customer {index}",
                            is_customer=True)
    shop.audit_chain.seal()
    assert shop.audit_chain.verify().ok is True


# ---- §1 licence state ----------------------------------------------------

def _activate(shop, license_id="ZB-FULL-000001"):
    me = shop.licensing.machine
    path = shop.license_dir / "incoming.zlic"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(make_license(shop.signing_key,
                                 machine_fingerprint=me.fingerprint,
                                 machine_traits=me.traits, license_id=license_id))
    return shop.licensing.import_license(path)


def _activate_demo(shop, days=14):
    """A genuine signed DEMO licence — a demo is issued, never assumed."""
    from datetime import date, timedelta

    me = shop.licensing.machine
    path = shop.license_dir / "demo.zlic"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(make_license(
        shop.signing_key, machine_fingerprint=me.fingerprint,
        machine_traits=me.traits, license_id="ZB-DEMO-000001",
        license_type="DEMO",
        expires_at=(date.today() + timedelta(days=days)).isoformat()))
    return shop.licensing.import_license(path)


def test_a_full_licence_removes_every_demo_indicator(shop):
    # Start from a real demo, not from "unlicensed", which is now its own state.
    _activate_demo(shop)
    assert "DEMO" in shop.licensing.summary()
    _activate(shop)
    summary = shop.licensing.summary()
    assert "DEMO" not in summary.upper().replace("DEMONSTRATION", "")
    assert summary.startswith("Licensed")
    assert shop.licensing.evaluate().status == "FULL"


def test_full_activation_survives_a_restart(shop):
    _activate(shop, "ZB-FULL-000042")
    shop.db.close()

    reopened = Database(str(shop.database_file))
    try:
        fresh = open_application_context(reopened, backups_dir=str(shop.backups_dir),
                                         license_dir=str(shop.license_dir))
        state = fresh.licensing.evaluate()
        assert state.status == "FULL"
        assert state.license_id == "ZB-FULL-000042"
        assert "DEMO" not in fresh.licensing.summary()
    finally:
        reopened.close()


def test_the_login_screen_reads_the_real_licence_state(shop, qapp):
    """It used to print the development text unconditionally."""
    from zenith_business.core.config import AppConfig
    from zenith_business.ui.auth.auth_window import AuthWindow

    _activate(shop, "ZB-FULL-000007")
    window = AuthWindow(shop, AppConfig())
    try:
        assert "ZB-FULL-000007" in window._version_text()
        assert "Development build" not in window._version_text()
    finally:
        window.deleteLater()


# ---- §6 machine data privacy ---------------------------------------------

def test_an_activation_request_exposes_no_raw_hardware_identifier(shop, tmp_path):
    path = shop.licensing.create_activation_request(tmp_path / "out")
    text = path.read_text(encoding="utf-8")
    for raw in (platform.node(), platform.machine(), f"{uuid.getnode():012x}"):
        if raw:
            assert raw not in text, f"{raw!r} leaked into the activation request"


def test_machine_traits_are_fixed_length_hashes(shop, tmp_path):
    path = shop.licensing.create_activation_request(tmp_path / "out")
    document = json.loads(path.read_text(encoding="utf-8"))
    traits = document["machine"]["traits"]
    assert traits
    for value in traits.values():
        assert len(value) == 16
        assert all(c in "0123456789abcdef" for c in value)
    assert len(document["machine"]["fingerprint"]) == 32


def test_a_licence_file_carries_only_hashed_machine_data(shop):
    _activate(shop)
    document = json.loads(shop.licensing.license_path.read_text(encoding="utf-8"))
    blob = json.dumps(document["payload"]["machine"])
    for raw in (platform.node(), f"{uuid.getnode():012x}"):
        if raw:
            assert raw not in blob


# ---- §7 packaging --------------------------------------------------------

def _auditor():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "release_audit", Path(__file__).resolve().parents[1] / "packaging"
        / "audit_release_package.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _package(tmp_path):
    """A realistic package: our exe plus the vendored crypto and Qt binaries.

    The vendored files carry the exact strings that made the first real build
    fail — a general-purpose crypto library naming its own signing classes, and
    Qt's PEM parser holding the header literal it searches for.
    """
    root = tmp_path / "package"
    (root / "app").mkdir(parents=True)
    (root / "app" / "ZenithBusiness.exe").write_bytes(
        b"Ed25519PublicKey EMBEDDED_PUBLIC_KEY_B64 Ed25519PrivateKey private_bytes")
    (root / "app" / "cryptography_rust.pyd").write_bytes(
        b"Ed25519PrivateKey private_bytes")
    (root / "app" / "Qt6Network.dll").write_bytes(b"-----BEGIN RSA PRIVATE KEY-----")
    return root


def test_a_clean_package_passes_despite_vendored_signing_capability(tmp_path):
    """The false alarm that failed the first hardened build must not come back."""
    assert _auditor().audit(_package(tmp_path)) == 0


@pytest.mark.parametrize("name, filename, content", [
    ("a real PEM private key", "leak.pem",
     "-----BEGIN PRIVATE KEY-----\n" + "A" * 64),
    ("the vendor signing key", "key.json", '{"kind": "zenith-signing-key"}'),
    ("the vendor tool by filename", "zenith_license_tool.py", "print()"),
    ("test signing tooling", "t.py", "from tests.tooling import license_signing"),
    ("a licence generator", "g.py", "def make_license(seed):\n    pass"),
    ("a packaged licence", "c.zlic", '{"format": "zenith-license-1"}'),
    ("a licence bypass", "b.py", "if os.environ.get('ZENITH_SKIP_LICENSE'): pass"),
    ("a backdoor", "d.py", "MASTER_PASSWORD = 'letmein'"),
    ("a default password", "e.py", "admin_password = 'Admin@123'"),
    ("our own code able to sign", "ours.py", "from x import Ed25519PrivateKey"),
])
def test_the_auditor_fails_the_build_on(tmp_path, name, filename, content):
    root = _package(tmp_path)
    (root / filename).write_text(content)
    assert _auditor().audit(root) == 1, f"the auditor did not catch {name}"


def test_the_auditor_requires_a_verification_path(tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    (root / "readme.txt").write_text("nothing here")
    assert _auditor().audit(root) == 1


# ---- the build's own self-report -----------------------------------------

def test_the_selftest_reports_a_working_security_state(tmp_path, monkeypatch, capsys):
    """CI runs this against the FROZEN exe; here it is checked as a function."""
    from zenith_business.app import selftest

    monkeypatch.setenv("ZENITH_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    assert selftest([]) == 0
    printed = capsys.readouterr().out
    assert "signature verify     : True" in printed
    assert "backup encryption    : True" in printed
    assert "SELFTEST             : OK" in printed


def test_the_selftest_still_reports_when_there_is_no_stdout(tmp_path, monkeypatch):
    """The shipped exe is WINDOWED: sys.stdout is None and print() raises.

    A console-only report was invisible in the one build that matters, and the
    self-test looked like a failure when it had actually run fine.
    """
    import sys as system

    from zenith_business.app import selftest

    monkeypatch.setenv("ZENITH_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    report = tmp_path / "report.txt"
    monkeypatch.setattr(system, "stdout", None)
    assert selftest([f"--selftest-out={report}"]) == 0
    text = report.read_text(encoding="utf-8")
    assert "SELFTEST             : OK" in text
    assert "signature verify     : True" in text


def test_the_selftest_fails_when_the_crypto_backend_is_missing(
        tmp_path, monkeypatch, capsys):
    """A build that cannot verify must not report itself healthy."""
    from zenith_business.app import selftest
    from zenith_business.security import signatures

    monkeypatch.setenv("ZENITH_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setattr(signatures, "backend_available", lambda: False)
    assert selftest([]) == 1
    assert "SELFTEST             : FAILED" in capsys.readouterr().out


def test_the_selftest_cannot_change_any_state(tmp_path, monkeypatch):
    """It prints. It must not activate, unlock or alter anything."""
    import inspect

    from zenith_business import app

    source = inspect.getsource(app.selftest)
    for forbidden in ("import_license", "update", "INSERT", "DELETE", "set("):
        assert forbidden not in source, f"selftest must not {forbidden}"
