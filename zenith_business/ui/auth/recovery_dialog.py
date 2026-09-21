"""Forgot-password recovery, reachable from the login screen (final §4).

The recovery service was built in Stage 10 and then had no way in. Manual
testing on Windows found exactly that: a working `recover_with_code` behind no
button, on either the login screen or My Account. A recovery path that a locked
-out owner cannot reach is not a recovery path — it is a unit test.

On a single-owner installation there is no administrator to ask, so this is the
only way back in when a password is forgotten. It deliberately does **not**
weaken the lock it opens:

* the code is generated with :mod:`secrets`, stored only as a PBKDF2 hash, and
  shown exactly once when it is issued — there is no screen anywhere that can
  display an existing code again, because nothing has it to display;
* using it is a password change: the code is consumed, the old password stops
  working, the lockout is cleared and every step is audited;
* a wrong code and a missing code give the same answer, so this cannot be used
  to find out whether an installation has a code at all.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from zenith_business.core.exceptions import ZenithError
from zenith_business.core.i18n import Translator
from zenith_business.ui.auth.widgets import PasswordField
from zenith_business.ui.components import (
    error_label,
    page_subtitle,
    page_title,
    primary_button,
    secondary_button,
)
from zenith_business.ui.design.tokens import FieldWidth, Spacing


class RecoveryDialog(QDialog):
    """Username + recovery code + a new password. Nothing else gets you in."""

    def __init__(self, context, translator: Translator, *, username: str = "",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctx = context
        self._t = translator
        self.recovered_username: str | None = None

        self.setWindowTitle(translator.gettext("rec.title"))
        self.setModal(True)
        self.setMinimumWidth(520)

        root = QVBoxLayout(self)
        root.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        root.setSpacing(Spacing.SM)

        root.addWidget(page_title(translator.gettext("rec.title")))
        root.addWidget(page_subtitle(translator.gettext("rec.subtitle")))

        form = QFormLayout()
        form.setHorizontalSpacing(Spacing.LG)
        self._username = QLineEdit(username)
        self._username.setFixedWidth(int(FieldWidth.LG))
        self._code = QLineEdit()
        self._code.setFixedWidth(int(FieldWidth.LG))
        self._code.setPlaceholderText(translator.gettext("rec.code_ph"))
        self._password = PasswordField(translator, "rec.new_password_ph")
        self._confirm = PasswordField(translator, "rec.confirm_ph")
        form.addRow(QLabel(translator.gettext("login.username")), self._username)
        form.addRow(QLabel(translator.gettext("rec.code")), self._code)
        form.addRow(QLabel(translator.gettext("rec.new_password")), self._password)
        form.addRow(QLabel(translator.gettext("rec.confirm")), self._confirm)
        root.addLayout(form)

        self._error = error_label("")
        self._error.setVisible(False)
        root.addWidget(self._error)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = secondary_button(translator.gettext("sec.cancel"))
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        self._ok = primary_button(translator.gettext("rec.reset"))
        self._ok.clicked.connect(self._submit)
        buttons.addWidget(self._ok)
        root.addLayout(buttons)

        (self._code if username else self._username).setFocus()

    def _fail(self, message: str) -> None:
        self._error.setText(message)
        self._error.setVisible(True)

    def _submit(self) -> None:
        username = self._username.text().strip()
        code = self._code.text().strip()
        new_password = self._password.text()
        if not username or not code or not new_password:
            self._fail(self._t.gettext("rec.error_required"))
            return
        if new_password != self._confirm.text():
            self._fail(self._t.gettext("setup.error_mismatch"))
            return
        try:
            self._ctx.security.recover_with_code(
                username=username, recovery_code=code, new_password=new_password)
        except ZenithError as exc:
            self._fail(getattr(exc, "user_message", str(exc)))
            return
        except Exception as exc:                       # pragma: no cover - defensive
            self._fail(str(exc))
            return
        self.recovered_username = username
        self.accept()
