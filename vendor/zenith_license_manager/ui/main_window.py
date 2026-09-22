"""Zenith Soft License Manager — the vendor application (Vendor Manager §1).

    CONFIDENTIAL. This program holds the private signing key. Never give it,
    its key files or its history to a customer.

The window owns three things the pages deliberately do not: the unlocked signing
key, the history file, and the licence output folder. A page can ask for a
licence to be issued; only this window can sign one, and only while a key is
unlocked. Closing it drops the key.

**Nothing here is a step a customer performs.** The whole point of the pairing
is that issuing needs the private key and verifying needs only the public one,
so a customer can check a licence and never make one.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

_REPO = Path(__file__).resolve().parent.parent.parent.parent
if str(_REPO) not in sys.path:                      # pragma: no cover - path setup
    sys.path.insert(0, str(_REPO))

from vendor.zenith_license_manager import issuing, keystore, products  # noqa: E402
from vendor.zenith_license_manager.history import (                    # noqa: E402
    History,
    default_license_dir,
)
from vendor.zenith_license_manager.ui.generate_page import GeneratePage  # noqa: E402
from vendor.zenith_license_manager.ui.history_page import HistoryPage    # noqa: E402
from vendor.zenith_license_manager.ui.theme import STYLESHEET            # noqa: E402

APP_NAME = "Zenith Soft License Manager"
APP_VERSION = "1.0.0"


class LicenseManagerWindow(QMainWindow):
    """The vendor's one window: issue licences, and look up what was issued."""

    def __init__(self, *, key_dir: Path | None = None,
                 history_path: Path | None = None,
                 license_dir: Path | None = None) -> None:
        super().__init__()
        self._key_dir = Path(key_dir) if key_dir else keystore.default_key_dir()
        self._license_dir = Path(license_dir) if license_dir else default_license_dir()
        self._history = History(history_path)
        #: The unlocked signing key, per product. Held in memory only.
        self._seeds: dict[str, bytes] = {}

        self.setWindowTitle(f"{APP_NAME}  v{APP_VERSION}")
        self.setMinimumSize(1100, 720)
        self.setStyleSheet(STYLESHEET)
        self._build()
        self._refresh_key_state()

    # ---- construction ----------------------------------------------------

    def _build(self) -> None:
        central = QWidget()
        col = QVBoxLayout(central)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)

        header = QWidget()
        header.setObjectName("Header")
        row = QHBoxLayout(header)
        row.setContentsMargins(20, 14, 20, 14)
        title = QLabel(APP_NAME)
        title.setObjectName("HeaderTitle")
        row.addWidget(title)
        row.addStretch(1)
        self.key_state = QLabel("")
        self.key_state.setObjectName("KeyState")
        row.addWidget(self.key_state)
        self.key_button = QPushButton("Unlock signing key…")
        self.key_button.clicked.connect(self._unlock_key)
        row.addWidget(self.key_button)
        self.new_key_button = QPushButton("Create key…")
        self.new_key_button.clicked.connect(self._create_key)
        row.addWidget(self.new_key_button)
        self.import_key_button = QPushButton("Import key…")
        self.import_key_button.clicked.connect(self._import_key)
        row.addWidget(self.import_key_button)
        col.addWidget(header)

        warning = QLabel(
            "⚠  CONFIDENTIAL — This tool is for Zenith Soft only. Never share it, "
            "its license history, or the signing key with customers.")
        warning.setObjectName("Warning")
        warning.setWordWrap(True)
        col.addWidget(warning)

        self.tabs = QTabWidget()
        self.generate_page = GeneratePage(
            on_generate=self._generate, next_serial=self._history.next_serial)
        self.history_page = HistoryPage(
            load=self._history.search, on_reexport=self._reexport)
        self.tabs.addTab(self.generate_page, "Generate License")
        self.tabs.addTab(self.history_page, "License History")
        self.tabs.currentChanged.connect(
            lambda i: self.history_page.reload() if i == 1 else None)
        col.addWidget(self.tabs, 1)
        self.setCentralWidget(central)

        self.generate_page.save_button.clicked.connect(self._save_zlic)
        self.generate_page.open_button.clicked.connect(self._open_folder)

    # ---- the signing key -------------------------------------------------

    def _key_path(self, product: products.Product) -> Path:
        return self._key_dir / product.key_filename

    def _refresh_key_state(self) -> None:
        product = self.generate_page.current_product()
        unlocked = product.product_id in self._seeds
        if unlocked:
            self.key_state.setText("🔓  Private key loaded")
            self.key_state.setProperty("state", "ok")
        elif self._key_path(product).is_file():
            self.key_state.setText("🔒  Signing key locked")
            self.key_state.setProperty("state", "locked")
        else:
            self.key_state.setText("⚠  No signing key for this product")
            self.key_state.setProperty("state", "missing")
        self.key_state.style().unpolish(self.key_state)
        self.key_state.style().polish(self.key_state)

    def _unlock_key(self) -> None:
        product = self.generate_page.current_product()
        path = self._key_path(product)
        if not path.is_file():
            QMessageBox.information(
                self, "No signing key",
                f"There is no signing key for {product.display_name} yet.\n\n"
                f"Expected at:\n{path}\n\nUse “Create key…” to make one.")
            return
        passphrase, ok = QInputDialog.getText(
            self, "Unlock signing key",
            f"Passphrase for {product.display_name}:", QLineEdit.EchoMode.Password)
        if not ok:
            return
        try:
            self._seeds[product.product_id] = keystore.load_seed(path, passphrase)
        except keystore.WrongPassphrase:
            QMessageBox.critical(self, "Wrong passphrase",
                                 "That passphrase did not open the key file.")
            return
        except keystore.KeystoreError as exc:
            QMessageBox.critical(self, "Cannot open key", str(exc))
            return
        self._refresh_key_state()

    def _create_key(self) -> None:
        """Make a NEW signing key. The public half is shown, to send onward."""
        product = self.generate_page.current_product()
        path = self._key_path(product)
        if path.is_file():
            QMessageBox.warning(
                self, "Key already exists",
                f"{product.display_name} already has a signing key at\n{path}\n\n"
                "Replacing it would invalidate every license issued under it. "
                "Move the old file away by hand if you really mean to.")
            return
        passphrase, ok = QInputDialog.getText(
            self, "New signing key",
            "Choose a passphrase to protect the new key.\n"
            "If you lose it, every license must be reissued under a new key.",
            QLineEdit.EchoMode.Password)
        if not ok or not passphrase:
            return
        again, ok = QInputDialog.getText(self, "New signing key",
                                         "Type the passphrase again:",
                                         QLineEdit.EchoMode.Password)
        if not ok:
            return
        if again != passphrase:
            QMessageBox.critical(self, "They do not match",
                                 "The two passphrases are different.")
            return
        seed, _public = keystore.generate_seed()
        try:
            info = keystore.write_key(path, seed, passphrase,
                                      product_id=product.product_id,
                                      label=product.display_name)
        except keystore.KeystoreError as exc:
            QMessageBox.critical(self, "Cannot write key", str(exc))
            return
        self._seeds[product.product_id] = seed
        self._refresh_key_state()
        QMessageBox.information(
            self, "Signing key created",
            f"Saved to:\n{info.path}\n\n"
            "Send ONLY the public key below to whoever builds "
            f"{product.display_name}. Keep the file and the passphrase private, "
            "and back the file up somewhere safe.\n\n"
            f"PUBLIC KEY: {info.public_key_b64}")

    def _import_key(self) -> None:
        """Take custody of an existing signing key, encrypting it on the way in.

        Needed for two ordinary situations and one awkward one: moving the
        Manager to a new PC, restoring from a backup, and taking over a key that
        was generated elsewhere — a key handed over in a message, for instance,
        which should be encrypted here and then deleted from wherever it came.
        """
        import base64

        product = self.generate_page.current_product()
        path = self._key_path(product)
        if path.is_file():
            QMessageBox.warning(
                self, "Key already exists",
                f"{product.display_name} already has a signing key at\n{path}\n\n"
                "Move it away by hand first if you mean to replace it.")
            return
        text, ok = QInputDialog.getText(
            self, "Import signing key",
            f"Paste the private key for {product.display_name} (base64):")
        if not ok or not text.strip():
            return
        try:
            seed = base64.b64decode("".join(text.split()), validate=True)
        except Exception:
            QMessageBox.critical(self, "Not a key",
                                 "That is not valid base64 key material.")
            return
        if len(seed) != keystore.SEED_BYTES:
            QMessageBox.critical(
                self, "Not a key",
                f"An Ed25519 private key is {keystore.SEED_BYTES} bytes; that is "
                f"{len(seed)}.")
            return
        passphrase, ok = QInputDialog.getText(
            self, "Import signing key",
            "Choose a passphrase to protect it on this computer:",
            QLineEdit.EchoMode.Password)
        if not ok or not passphrase:
            return
        try:
            info = keystore.write_key(path, seed, passphrase,
                                      product_id=product.product_id,
                                      label=product.display_name)
        except keystore.KeystoreError as exc:
            QMessageBox.critical(self, "Cannot write key", str(exc))
            return
        self._seeds[product.product_id] = seed
        self._refresh_key_state()
        QMessageBox.information(
            self, "Signing key imported",
            f"Encrypted and saved to:\n{info.path}\n\n"
            "Delete the copy you pasted from — this file and your passphrase "
            "are now the only things needed to issue licenses.\n\n"
            f"PUBLIC KEY: {info.public_key_b64}")

    # ---- issuing ---------------------------------------------------------

    def _generate(self, values: dict) -> None:
        product = products.by_id(values["product_id"]) or products.ZENITH_BUSINESS
        seed = self._seeds.get(product.product_id)
        if seed is None:
            self._unlock_key()
            seed = self._seeds.get(product.product_id)
            if seed is None:
                return

        license_id = values.get("license_id") or ""
        serial = _serial_from(license_id) or self._history.next_serial(
            product.product_id, values["license_type"])
        clash = self._history.serial_in_use(product.product_id,
                                            values["license_type"], serial)
        if clash is not None:
            answer = QMessageBox.question(
                self, "License number already used",
                f"{clash.license_id} was issued on {clash.created_at[:10]} to "
                f"{clash.issued_to or 'an unnamed customer'}.\n\n"
                "Issue another license with the same number?\n"
                "The existing record will be kept either way.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return

        try:
            issued = issuing.issue(
                product=product, seed=seed, request_code=values["request_code"],
                license_type=values["license_type"], serial=serial,
                issued_to=values["issued_to"], phone=values["phone"],
                city=values["city"], notes=values["notes"],
                demo_days=values["demo_days"], expires_at=values["expires_at"],
                license_id=license_id or None)
        except issuing.IssueError as exc:
            QMessageBox.critical(self, "Cannot issue this license", str(exc))
            return

        self._history.append(issued)
        self.generate_page.show_issued(issued)
        self.history_page.reload()

    def _save_zlic(self) -> None:
        issued = self.generate_page.issued
        if issued is None:
            return
        seed = self._seeds.get(issued.product_id)
        if seed is None:
            QMessageBox.warning(self, "Key locked",
                                "Unlock the signing key to write a .zlic file.")
            return
        self._license_dir.mkdir(parents=True, exist_ok=True)
        suggested = str(self._license_dir / f"{issued.license_id}.zlic")
        name, _ = QFileDialog.getSaveFileName(self, "Save license file", suggested,
                                              "Zenith license (*.zlic)")
        if not name:
            return
        try:
            path = issuing.write_zlic(issued, seed, name)
        except OSError as exc:
            QMessageBox.critical(self, "Cannot write file", str(exc))
            return
        self._history.set_zlic_path(issued.license_id, str(path))
        self.history_page.reload()
        QMessageBox.information(self, "License file saved", str(path))

    def _reexport(self, record) -> None:
        """Write a ``.zlic`` again from a history row, without reissuing."""
        seed = self._seeds.get(record.product_id)
        if seed is None:
            QMessageBox.warning(self, "Key locked",
                                "Unlock the signing key to write a .zlic file.")
            return
        rebuilt = issuing.IssuedLicense(
            product_id=record.product_id, license_id=record.license_id,
            license_type=record.license_type, serial=record.serial,
            machine_fingerprint=record.machine_fingerprint,
            machine_short=record.machine_short, issued_to=record.issued_to,
            phone=record.phone, city=record.city, notes=record.notes,
            issued_at=record.issued_at, expires_at=record.expires_at,
            product_key=record.product_key, created_at=record.created_at)
        self._license_dir.mkdir(parents=True, exist_ok=True)
        try:
            path = issuing.write_zlic(rebuilt, seed, self._license_dir)
        except OSError as exc:
            QMessageBox.critical(self, "Cannot write file", str(exc))
            return
        self._history.set_zlic_path(record.license_id, str(path))
        self.history_page.reload()
        QMessageBox.information(self, "License file written", str(path))

    def _open_folder(self) -> None:
        import subprocess

        self._license_dir.mkdir(parents=True, exist_ok=True)
        folder = str(self._license_dir)
        try:
            if sys.platform.startswith("win"):
                subprocess.Popen(["explorer", folder])
            elif sys.platform == "darwin":            # pragma: no cover
                subprocess.Popen(["open", folder])
            else:                                     # pragma: no cover
                subprocess.Popen(["xdg-open", folder])
        except OSError:
            QMessageBox.information(self, "License folder", folder)


def _serial_from(license_id: str) -> int | None:
    """The number a vendor typed into the License ID field, if it has one."""
    tail = (license_id or "").rsplit("-", 1)[-1]
    return int(tail) if tail.isdigit() else None


def main(argv: list[str] | None = None) -> int:
    from PyQt6.QtWidgets import QApplication

    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    window = LicenseManagerWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":                            # pragma: no cover
    raise SystemExit(main())
