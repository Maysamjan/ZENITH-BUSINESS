"""Stage 10 screens: Audit Log, Backup & Restore, License (§3, §4, §5, §11).

Three workspace pages on the locked design system, EN/Dari with RTL, built from
the same components as every other screen so they do not look bolted on.

The rule these pages follow is that a destructive action is never one click
away. Restore and licence import both take the customer through: choose a file →
the file is *inspected and described* → confirm in words → re-enter the owner
password. The password step is not decoration; it is the difference between
"someone is signed in" and "the owner is doing this".
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from zenith_business.core.exceptions import ZenithError
from zenith_business.core.i18n import Translator
from zenith_business.ui.components import (
    Card,
    apply_shadow,
    escape_amp,
    eyebrow,
    page_title,
    primary_button,
    secondary_button,
    standard_icon,
)
from zenith_business.ui.design.tokens import ControlSize, FieldWidth, Spacing

# ---------------------------------------------------------------------------
# shared: the re-authentication gate
# ---------------------------------------------------------------------------


class ConfirmSensitiveDialog(QDialog):
    """Explain the consequence, then ask for the owner password (§2).

    One dialog for every dangerous action, so the protection cannot be
    inconsistent between them.
    """

    def __init__(self, translator: Translator, *, title: str, message: str,
                 confirm_label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._t = translator
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(460)

        root = QVBoxLayout(self)
        root.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        root.setSpacing(Spacing.MD)

        head = QLabel(message)
        head.setWordWrap(True)
        root.addWidget(head)

        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.setFixedWidth(int(FieldWidth.LG))
        form = QFormLayout()
        form.addRow(QLabel(translator.gettext("sec.confirm_password")), self._password)
        root.addLayout(form)

        self._error = QLabel("")
        self._error.setProperty("role", "danger")
        self._error.setWordWrap(True)
        self._error.setVisible(False)
        root.addWidget(self._error)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = secondary_button(translator.gettext("sec.cancel"))
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        self._ok = primary_button(escape_amp(confirm_label))
        self._ok.clicked.connect(self.accept)
        buttons.addWidget(self._ok)
        root.addLayout(buttons)
        self._password.setFocus()
        self._password.returnPressed.connect(self.accept)

    @property
    def password(self) -> str:
        return self._password.text()

    def show_error(self, text: str) -> None:
        self._error.setText(text)
        self._error.setVisible(True)
        self._password.clear()
        self._password.setFocus()


def confirm_sensitive(parent: QWidget, context, translator: Translator, *,
                      title_key: str, message: str, confirm_key: str,
                      action: str) -> bool:
    """Run the confirm-and-re-authenticate gate. True only if the owner proved it."""
    return verified_password(parent, context, translator, title_key=title_key,
                             message=message, confirm_key=confirm_key,
                             action=action) is not None


def verified_password(parent: QWidget, context, translator: Translator, *,
                      title_key: str, message: str, confirm_key: str,
                      action: str) -> str | None:
    """The same gate, returning the password it just proved — or None.

    Handing the verified password back matters for one thing: the safety copy a
    restore takes of the CURRENT database has to be encrypted, and the only
    secret the customer has just proved they know, at exactly the right moment,
    is this one. Asking twice for the same password would be the alternative,
    and a second prompt is how people end up typing something else.
    """
    while True:
        dialog = ConfirmSensitiveDialog(
            translator, title=translator.gettext(title_key), message=message,
            confirm_label=translator.gettext(confirm_key), parent=parent)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        password = dialog.password
        try:
            if context.security.verify_current_password(password, action=action):
                return password
        except ZenithError as exc:
            QMessageBox.warning(parent, translator.gettext("sec.blocked_title"),
                                getattr(exc, "user_message", str(exc)))
            return None
        QMessageBox.warning(parent, translator.gettext("sec.wrong_password_title"),
                            translator.gettext("sec.wrong_password"))


def _table(columns: list[str], stretch: int = 0) -> QTableWidget:
    table = QTableWidget(0, len(columns))
    table.setHorizontalHeaderLabels(columns)
    table.verticalHeader().setVisible(False)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    table.horizontalHeader().setHighlightSections(False)
    table.verticalHeader().setDefaultSectionSize(ControlSize.TABLE_ROW_HEIGHT + 4)
    for i in range(len(columns)):
        table.horizontalHeader().setSectionResizeMode(
            i, QHeaderView.ResizeMode.Stretch if i == stretch
            else QHeaderView.ResizeMode.ResizeToContents)
    return table


class _Page(QWidget):
    """Shared chrome: title, body, action bar with a status line."""

    def __init__(self, context, translator: Translator, title_key: str, *,
                 on_close: Callable[[], None] | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctx = context
        self._t = translator
        self._on_close = on_close
        self._title_key = title_key
        self.setProperty("role", "workspace")
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(Spacing.PAGE_MARGIN, Spacing.SM,
                                      Spacing.PAGE_MARGIN, Spacing.SM)
        self._root.setSpacing(Spacing.SM)
        self._title = page_title(translator.gettext(title_key))
        self._root.addWidget(self._title)

    def _finish(self, extra_buttons: list = ()) -> None:
        bar = QWidget()
        bar.setProperty("role", "actionbar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(Spacing.LG, Spacing.SM, Spacing.LG, Spacing.SM)
        self._status = QLabel("")
        self._status.setProperty("role", "secondary")
        self._status.setWordWrap(True)
        row.addWidget(self._status, stretch=1)
        for button in extra_buttons:
            row.addWidget(button)
        self._close_btn = secondary_button(self._t.gettext("s4.act_close"))
        self._close_btn.setIcon(standard_icon("close"))
        if self._on_close is not None:
            self._close_btn.clicked.connect(lambda: self._on_close())
        row.addWidget(self._close_btn)
        self._root.addWidget(bar)

    def _say(self, text: str, *, bad: bool = False) -> None:
        self._status.setText(text)
        self._status.setProperty("role", "danger" if bad else "secondary")
        self._status.style().unpolish(self._status)
        self._status.style().polish(self._status)


# ---------------------------------------------------------------------------
# 1. Audit log
# ---------------------------------------------------------------------------


class AuditLogPage(_Page):
    """Read-only view of what happened and who did it (§3).

    Read-only is the contract, not the styling: the page offers no edit and no
    delete, and there is no service method behind it that could. The audit trail
    is written inside the transaction of the action it describes, so it commits
    or rolls back with it.
    """

    COLUMNS = ("sec.col_when", "sec.col_action", "sec.col_entity",
               "sec.col_reference", "sec.col_details")

    def __init__(self, context, translator: Translator, *,
                 on_close: Callable[[], None] | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(context, translator, "sec.audit_title",
                         on_close=on_close, parent=parent)
        card = Card(role="section")
        card.setProperty("accent", "navy")
        apply_shadow(card)
        card.body.setContentsMargins(Spacing.CARD_PAD_H, Spacing.SM,
                                     Spacing.CARD_PAD_H, Spacing.SM)
        self._hint = QLabel(translator.gettext("sec.audit_hint"))
        self._hint.setWordWrap(True)
        card.body.addWidget(self._hint)
        self._root.addWidget(card)

        self._table = _table([translator.gettext(k) for k in self.COLUMNS], stretch=4)
        self._root.addWidget(self._table, stretch=1)
        self._refresh_btn = secondary_button(translator.gettext("sec.refresh"))
        self._refresh_btn.clicked.connect(self.reload)
        self._verify_btn = secondary_button(translator.gettext("sec.audit_verify"))
        self._verify_btn.clicked.connect(self._verify_chain)
        self._finish([self._verify_btn, self._refresh_btn])
        self.reload()

    def _verify_chain(self) -> None:
        """Walk the hash chain and report the first entry that disagrees."""
        try:
            self._ctx.audit_chain.seal()
            report = self._ctx.audit_chain.verify()
        except Exception as exc:
            self._say(str(exc), bad=True)
            return
        if report.ok:
            self._say(self._t.gettext("sec.audit_chain_ok")
                      .replace("{n}", str(report.sealed)))
        else:
            self._say(self._t.gettext("sec.audit_chain_bad")
                      .replace("{id}", str(report.first_bad_id))
                      .replace("{detail}", report.detail), bad=True)

    def reload(self) -> None:
        rows = self._ctx.audit_repo.recent(500)
        self._table.setRowCount(0)
        self._table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            values = (row.get("created_at") or "", row.get("action") or "",
                      row.get("entity_type") or "", row.get("document_no") or "",
                      row.get("details") or "")
            for c, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft
                                      | Qt.AlignmentFlag.AlignVCenter)
                self._table.setItem(r, c, item)
        self._say(self._t.gettext("sec.audit_count").replace("{n}", str(len(rows))))

    def retranslate(self, translator: Translator) -> None:
        self._t = translator
        self._title.setText(translator.gettext("sec.audit_title"))
        self._hint.setText(translator.gettext("sec.audit_hint"))
        self._table.setHorizontalHeaderLabels(
            [translator.gettext(k) for k in self.COLUMNS])
        self._refresh_btn.setText(escape_amp(translator.gettext("sec.refresh")))
        self._verify_btn.setText(escape_amp(translator.gettext("sec.audit_verify")))
        self._close_btn.setText(escape_amp(translator.gettext("s4.act_close")))
        self.reload()


# ---------------------------------------------------------------------------
# 2. Backup & restore
# ---------------------------------------------------------------------------


class BackupPage(_Page):
    """Create a backup, check one, and restore one safely (§4, §5)."""

    def __init__(self, context, translator: Translator, *,
                 database_path: str | None = None,
                 on_close: Callable[[], None] | None = None,
                 on_restored: Callable[[], None] | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(context, translator, "sec.backup_title",
                         on_close=on_close, parent=parent)
        self._database_path = database_path
        self._on_restored = on_restored

        self._backup_card = Card(role="section")
        self._backup_card.setProperty("accent", "navy")
        apply_shadow(self._backup_card)
        body = self._backup_card.body
        body.setContentsMargins(Spacing.CARD_PAD_H, Spacing.SM,
                                Spacing.CARD_PAD_H, Spacing.SM)
        self._backup_head = eyebrow(translator.gettext("sec.backup_now"))
        body.addWidget(self._backup_head)
        self._backup_hint = QLabel(translator.gettext("sec.backup_hint"))
        self._backup_hint.setWordWrap(True)
        body.addWidget(self._backup_hint)
        row = QHBoxLayout()
        self._create_btn = primary_button(translator.gettext("sec.create_backup"))
        self._create_btn.clicked.connect(self._create_backup)
        row.addWidget(self._create_btn)
        self._check_btn = secondary_button(translator.gettext("sec.check_backup"))
        self._check_btn.clicked.connect(self._check_backup)
        row.addWidget(self._check_btn)
        row.addStretch(1)
        body.addLayout(row)
        self._root.addWidget(self._backup_card)

        self._restore_card = Card(role="section")
        self._restore_card.setProperty("accent", "amber")
        apply_shadow(self._restore_card)
        rbody = self._restore_card.body
        rbody.setContentsMargins(Spacing.CARD_PAD_H, Spacing.SM,
                                 Spacing.CARD_PAD_H, Spacing.SM)
        self._restore_head = eyebrow(translator.gettext("sec.restore"))
        rbody.addWidget(self._restore_head)
        self._restore_hint = QLabel(translator.gettext("sec.restore_hint"))
        self._restore_hint.setWordWrap(True)
        rbody.addWidget(self._restore_hint)
        rrow = QHBoxLayout()
        self._restore_btn = primary_button(translator.gettext("sec.restore_from_file"))
        self._restore_btn.clicked.connect(self._restore)
        rrow.addWidget(self._restore_btn)
        rrow.addStretch(1)
        rbody.addLayout(rrow)
        self._root.addWidget(self._restore_card)

        self._table = _table([translator.gettext(k) for k in
                              ("sec.col_file", "sec.col_when", "sec.col_size")],
                             stretch=0)
        self._root.addWidget(self._table, stretch=1)
        self._integrity_btn = secondary_button(translator.gettext("sec.check_database"))
        self._integrity_btn.clicked.connect(self._check_database)
        self._finish([self._integrity_btn])
        self.reload()

    # -- data ------------------------------------------------------------

    def reload(self) -> None:
        from pathlib import Path
        directory = getattr(self._ctx.backup, "_backups_dir", None)
        files = []
        if directory is not None and Path(directory).is_dir():
            files = sorted(
                [p for p in Path(directory).iterdir()
                 if p.suffix in (".db", ".zbak") and p.is_file()],
                key=lambda p: p.stat().st_mtime, reverse=True)
        self._table.setRowCount(0)
        self._table.setRowCount(len(files))
        import datetime
        for r, path in enumerate(files):
            stat = path.stat()
            when = datetime.datetime.fromtimestamp(stat.st_mtime).strftime(
                "%Y-%m-%d %H:%M:%S")
            size = f"{stat.st_size / 1024:,.0f} KB"
            for c, value in enumerate((path.name, when, size)):
                self._table.setItem(r, c, QTableWidgetItem(value))
        self._say(self._t.gettext("sec.backup_count").replace("{n}", str(len(files))))

    # -- actions ---------------------------------------------------------

    def _create_backup(self) -> None:
        """Create an encrypted backup, locked with the owner password.

        The owner password is reused as the backup passphrase deliberately: it
        is one secret rather than two, and it is the one the customer already
        has to type to restore. The consequence is stated on screen — a backup
        opens with the password that was current when it was written.

        **The typed text is verified against the account before it is used as a
        key.** It was not, and that was the defect behind the inconsistency
        found on Windows: with a Persian keyboard layout active, the physical
        keys of the English password produce Persian characters, so a backup got
        locked with a string the owner never meant to type. Checking that file
        afterwards with the same physical keys succeeded — it *was* the
        passphrase — while restoring it failed, because restoring also
        re-authenticates against the real account password. Same keys, two
        different answers, and nothing in between to explain why.
        """
        passphrase = self._ask_passphrase("sec.backup_pass_prompt",
                                          note_key="sec.backup_pass_must_match_owner")
        if passphrase is None:
            self._say(self._t.gettext("sec.restore_cancelled"))
            return
        try:
            proved = self._ctx.security.verify_current_password(
                passphrase, action="backup.create")
        except ZenithError as exc:
            self._say(getattr(exc, "user_message", str(exc)), bad=True)
            return
        if not proved:
            # Refused before a file exists: a backup nobody can open is worse
            # than no backup, because it looks like protection.
            self._say(self._t.gettext("sec.backup_pass_rejected"), bad=True)
            return
        try:
            path = self._ctx.backup.create_backup(
                passphrase=passphrase,
                hint=self._t.gettext("sec.backup_hint_owner_password"))
        except ZenithError as exc:
            self._say(getattr(exc, "user_message", str(exc)), bad=True)
            return
        except Exception as exc:
            self._say(str(exc), bad=True)
            return
        check = self._ctx.safe_restore.inspect(path, passphrase=passphrase)
        self.reload()
        if check.ok:
            self._say(self._t.gettext("sec.backup_ok").replace("{file}", path.name))
        else:
            self._say(self._t.gettext("sec.backup_unverified")
                      .replace("{file}", path.name), bad=True)

    def _pick(self, title_key: str) -> str | None:
        from pathlib import Path
        start = getattr(self._ctx.backup, "_backups_dir", None)
        name, _ = QFileDialog.getOpenFileName(
            self, self._t.gettext(title_key), str(start or Path.home()),
            self._t.gettext("sec.backup_filter"))
        return name or None

    def _ask_passphrase(self, prompt_key: str, *, note_key: str | None = None
                        ) -> str | None:
        """Ask for a backup password. Returns EXACTLY what was typed.

        No normalisation of any kind happens here or anywhere below it: the
        characters Qt reports are the characters scrypt sees, so a Persian
        keyboard layout produces a Persian passphrase and an English one
        produces an English passphrase. There is no physical-key translation to
        make the two agree, and there must not be — that would mean two
        different strings opening the same file.
        """
        from PyQt6.QtWidgets import QInputDialog

        prompt = self._t.gettext(prompt_key)
        if note_key is not None:
            prompt = f"{prompt}\n\n{self._t.gettext(note_key)}"
        text, ok = QInputDialog.getText(
            self, self._t.gettext("sec.backup_title"),
            prompt, QLineEdit.EchoMode.Password)
        if not ok:
            return None
        return text

    def _refusal(self, check) -> str:
        """Customer-facing wording for a refused file, in the active language.

        The raw reason token used to reach the screen, so a customer whose
        backup failed its authentication tag was shown ``bad_passphrase`` — which
        is both jargon and, worse, only one of the three things it can mean.
        """
        key = f"sec.refuse_{check.reason}"
        text = self._t.gettext(key)
        return check.detail or check.reason if text == key else text

    def _check_backup(self) -> None:
        name = self._pick("sec.check_backup")
        if not name:
            return
        from zenith_business.security import backup_crypto

        passphrase = None
        if backup_crypto.looks_encrypted(name):
            passphrase = self._ask_passphrase(
                "sec.backup_open_prompt",
                note_key="sec.backup_needs_creation_password")
            if passphrase is None:
                self._say(self._t.gettext("sec.restore_cancelled"))
                return
        check = self._ctx.safe_restore.inspect(name, passphrase=passphrase)
        from pathlib import Path
        label = Path(name).name
        if check.ok:
            self._say(self._t.gettext("sec.check_ok").replace("{file}", label)
                      .replace("{v}", str(check.schema_version)))
        else:
            self._say(self._t.gettext("sec.check_bad").replace("{file}", label)
                      .replace("{reason}", self._refusal(check)), bad=True)

    def _restore(self) -> None:
        name = self._pick("sec.restore_from_file")
        if not name:
            return
        from pathlib import Path

        from zenith_business.security import backup_crypto

        passphrase = None
        if backup_crypto.looks_encrypted(name):
            passphrase = self._ask_passphrase(
                "sec.backup_open_prompt",
                note_key="sec.backup_needs_creation_password")
            if passphrase is None:
                self._say(self._t.gettext("sec.restore_cancelled"))
                return
        check = self._ctx.safe_restore.inspect(name, passphrase=passphrase)
        label = Path(name).name
        if not check.ok:
            # Refused before anything is touched, and the reason is named.
            reason = self._refusal(check)
            self._say(self._t.gettext("sec.check_bad").replace("{file}", label)
                      .replace("{reason}", reason), bad=True)
            QMessageBox.critical(self, self._t.gettext("sec.restore"),
                                 self._t.gettext("sec.restore_refused")
                                 .replace("{file}", label)
                                 .replace("{reason}", reason))
            return
        if self._database_path is None:
            self._say(self._t.gettext("sec.restore_no_target"), bad=True)
            return

        message = (self._t.gettext("sec.restore_confirm")
                   .replace("{file}", label)
                   .replace("{v}", str(check.schema_version)))
        owner_password = verified_password(
            self, self._ctx, self._t, title_key="sec.restore", message=message,
            confirm_key="sec.restore_confirm_button", action="backup.restore")
        if owner_password is None:
            self._say(self._t.gettext("sec.restore_cancelled"))
            return
        try:
            result = self._ctx.safe_restore.restore(
                name, self._database_path, confirmed=True, passphrase=passphrase,
                # The copy taken of the CURRENT database is customer data too,
                # and it used to be written as a plain readable .db. It is now
                # locked with the password the owner has just proved.
                safety_passphrase=owner_password)
        except ZenithError as exc:
            self._say(getattr(exc, "user_message", str(exc)), bad=True)
            QMessageBox.critical(self, self._t.gettext("sec.restore"),
                                 getattr(exc, "user_message", str(exc)))
            return
        safety = result.safety_backup.name if result.safety_backup else "-"
        QMessageBox.information(
            self, self._t.gettext("sec.restore"),
            self._t.gettext("sec.restore_done").replace("{safety}", safety))
        self._say(self._t.gettext("sec.restore_done").replace("{safety}", safety))
        if self._on_restored is not None:
            self._on_restored()

    def _check_database(self) -> None:
        from zenith_business.services.safe_restore import check_database_integrity
        report = check_database_integrity(self._ctx.db)
        if report.ok:
            self._say(self._t.gettext("sec.db_ok")
                      .replace("{v}", str(report.schema_version))
                      .replace("{mode}", report.journal_mode))
        else:
            self._say(self._t.gettext("sec.db_bad").replace("{detail}", report.detail),
                      bad=True)

    def retranslate(self, translator: Translator) -> None:
        self._t = translator
        self._title.setText(translator.gettext("sec.backup_title"))
        self._backup_head.setText(translator.gettext("sec.backup_now"))
        self._backup_hint.setText(translator.gettext("sec.backup_hint"))
        self._restore_head.setText(translator.gettext("sec.restore"))
        self._restore_hint.setText(translator.gettext("sec.restore_hint"))
        for button, key in ((self._create_btn, "sec.create_backup"),
                            (self._check_btn, "sec.check_backup"),
                            (self._restore_btn, "sec.restore_from_file"),
                            (self._integrity_btn, "sec.check_database"),
                            (self._close_btn, "s4.act_close")):
            button.setText(escape_amp(translator.gettext(key)))
        self._table.setHorizontalHeaderLabels(
            [translator.gettext(k) for k in
             ("sec.col_file", "sec.col_when", "sec.col_size")])
        self.reload()


# ---------------------------------------------------------------------------
# 3. License status
# ---------------------------------------------------------------------------


class LicensePage(_Page):
    """Product, licence type, activation status, machine id (§11).

    Shows state and offers exactly two actions: produce an activation request,
    and import a licence the vendor signed. There is deliberately nothing here
    that could issue or alter a licence — the application holds only a public
    verification key.
    """

    FIELDS = (
        ("sec.lic_product", "product"),
        ("sec.lic_type", "license_type"),
        ("sec.lic_status", "status"),
        ("sec.lic_machine", "machine"),
        ("sec.lic_id", "license_id"),
        ("sec.lic_issued_to", "issued_to"),
        ("sec.lic_issued", "issued_at"),
        ("sec.lic_expires", "expires"),
    )

    def __init__(self, context, translator: Translator, *,
                 on_close: Callable[[], None] | None = None,
                 on_changed: Callable[[], None] | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(context, translator, "sec.license_title",
                         on_close=on_close, parent=parent)
        self._on_changed = on_changed

        self._card = Card(role="section")
        self._card.setProperty("accent", "navy")
        apply_shadow(self._card)
        body = self._card.body
        body.setContentsMargins(Spacing.CARD_PAD_H, Spacing.MD,
                                Spacing.CARD_PAD_H, Spacing.MD)
        self._banner = QLabel("")
        self._banner.setWordWrap(True)
        self._banner.setProperty("role", "secondary")
        body.addWidget(self._banner)

        self._form = QFormLayout()
        self._form.setHorizontalSpacing(Spacing.LG)
        self._form.setVerticalSpacing(Spacing.XS)
        self._labels: dict[str, QLabel] = {}
        self._keys: dict[str, QLabel] = {}
        for key, name in self.FIELDS:
            caption = QLabel(translator.gettext(key))
            caption.setProperty("role", "secondary")
            value = QLabel("—")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self._keys[name] = value
            self._labels[key] = caption
            self._form.addRow(caption, value)
        body.addLayout(self._form)
        self._root.addWidget(self._card)
        self._root.addStretch(1)

        self._request_btn = primary_button(translator.gettext("sec.lic_make_request"))
        self._request_btn.clicked.connect(self._make_request)
        self._import_btn = secondary_button(translator.gettext("sec.lic_import"))
        self._import_btn.clicked.connect(self._import_license)
        self._finish([self._request_btn, self._import_btn])
        self.reload()

    def reload(self) -> None:
        from zenith_business.core.identity import PRODUCT_NAME

        state = self._ctx.licensing.evaluate()
        self._keys["product"].setText(PRODUCT_NAME)
        self._keys["license_type"].setText(
            state.license_type or self._t.gettext("sec.lic_none"))
        self._keys["status"].setText(self._t.gettext(f"sec.st_{state.status.lower()}"))
        self._keys["machine"].setText(state.machine_short or "—")
        self._keys["license_id"].setText(state.license_id or "—")
        self._keys["issued_to"].setText(state.issued_to or "—")
        self._keys["issued_at"].setText(state.issued_at or "—")
        # "Never" is a statement about a licence that exists and has no end date.
        # With no licence there is nothing to expire, and "Never" read as a
        # promise of permanent entitlement the installation does not have.
        expiry = state.expires_at or state.demo_expires_on
        self._keys["expires"].setText(
            expiry if expiry else (self._t.gettext("sec.lic_never") if state.license_id
                                   else self._t.gettext("sec.lic_not_applicable")))
        from zenith_business.ui.components import license_summary

        self._banner.setText(state.detail or "")
        self._say(license_summary(self._t, state), bad=not state.allows_login)

    def _make_request(self) -> None:
        from pathlib import Path
        suggested = f"zenith-activation-{self._ctx.licensing.machine.fingerprint[:12]}.zreq"
        name, _ = QFileDialog.getSaveFileName(
            self, self._t.gettext("sec.lic_make_request"),
            str(Path.home() / suggested), self._t.gettext("sec.lic_req_filter"))
        if not name:
            return
        try:
            # The service resolves the customer's OWN business name, or leaves
            # it unset — never a sample name and never the product's.
            path = self._ctx.licensing.create_activation_request(name)
        except OSError as exc:
            self._say(str(exc), bad=True)
            return
        self._say(self._t.gettext("sec.lic_request_saved").replace("{file}", path.name))
        QMessageBox.information(
            self, self._t.gettext("sec.lic_make_request"),
            self._t.gettext("sec.lic_request_next").replace("{file}", str(path)))

    def _import_license(self) -> None:
        from pathlib import Path
        name, _ = QFileDialog.getOpenFileName(
            self, self._t.gettext("sec.lic_import"), str(Path.home()),
            self._t.gettext("sec.lic_filter"))
        if not name:
            return
        # Replacing a licence is a sensitive action (§2), so it is gated too.
        if not confirm_sensitive(self, self._ctx, self._t,
                                 title_key="sec.lic_import",
                                 message=self._t.gettext("sec.lic_import_confirm")
                                 .replace("{file}", Path(name).name),
                                 confirm_key="sec.lic_import_button",
                                 action="license.import"):
            self._say(self._t.gettext("sec.restore_cancelled"))
            return
        try:
            state = self._ctx.licensing.import_license(name)
        except ZenithError as exc:
            message = getattr(exc, "user_message", str(exc))
            self._say(message, bad=True)
            QMessageBox.critical(self, self._t.gettext("sec.lic_import"), message)
            self.reload()
            return
        except Exception as exc:                      # LicenseError is not a ZenithError
            message = getattr(exc, "user_message", str(exc))
            self._say(message, bad=True)
            QMessageBox.critical(self, self._t.gettext("sec.lic_import"), message)
            self.reload()
            return
        self.reload()
        QMessageBox.information(
            self, self._t.gettext("sec.lic_import"),
            self._t.gettext("sec.lic_import_ok").replace("{id}", state.license_id))
        if self._on_changed is not None:
            self._on_changed()

    def retranslate(self, translator: Translator) -> None:
        self._t = translator
        self._title.setText(translator.gettext("sec.license_title"))
        for key, caption in self._labels.items():
            caption.setText(translator.gettext(key))
        for button, key in ((self._request_btn, "sec.lic_make_request"),
                            (self._import_btn, "sec.lic_import"),
                            (self._close_btn, "s4.act_close")):
            button.setText(escape_amp(translator.gettext(key)))
        self.reload()
