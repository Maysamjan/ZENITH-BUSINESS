"""Login page (Stage 02 §11).

A focused credentials form built from the design system. It does no
authentication itself — it collects input and delegates to a callback, then
displays the outcome (error message or a busy state). Pressing Enter submits.
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtWidgets import QLineEdit, QVBoxLayout, QWidget

from zenith_business.core.i18n import Translator
from zenith_business.ui.auth.widgets import PasswordField
from zenith_business.ui.components import (
    error_label,
    field_label,
    page_title,
    page_subtitle,
    primary_button,
)
from zenith_business.ui.design.tokens import FieldWidth, Spacing


class LoginPage(QWidget):
    def __init__(
        self,
        translator: Translator,
        on_submit: Callable[[str, str], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._t = translator
        self._on_submit = on_submit
        # Scope the transparent background to THIS widget only (a bare
        # "background: transparent" would cascade onto the primary button and
        # strip its fill). The card behind provides the surface.
        self.setObjectName("LoginPageRoot")
        self.setStyleSheet("QWidget#LoginPageRoot { background: transparent; }")

        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(Spacing.SM)

        self._title = page_title(self._t.gettext("login.title"))
        self._subtitle = page_subtitle(self._t.gettext("login.subtitle"))
        col.addWidget(self._title)
        col.addWidget(self._subtitle)
        col.addSpacing(Spacing.SM)

        self._username_label = field_label(self._t.gettext("login.username"))
        self.username = QLineEdit()
        self.username.setPlaceholderText(self._t.gettext("login.username_ph"))
        self.username.setMinimumWidth(int(FieldWidth.LG))
        col.addWidget(self._username_label)
        col.addWidget(self.username)

        col.addSpacing(Spacing.XS)
        self._password_label = field_label(self._t.gettext("login.password"))
        self.password = PasswordField(self._t, "login.password_ph")
        col.addWidget(self._password_label)
        col.addWidget(self.password)

        self._error = error_label("")
        self._error.setVisible(False)
        col.addSpacing(Spacing.XS)
        col.addWidget(self._error)

        col.addSpacing(Spacing.SM)
        self.submit = primary_button(self._t.gettext("login.signin"))
        self.submit.setMinimumHeight(36)
        self.submit.clicked.connect(self._submit)
        col.addWidget(self.submit)
        col.addStretch(1)  # pack fields to the top; absorb extra card height

        # Enter submits from either field.
        self.username.returnPressed.connect(self._submit)
        self.password.edit.returnPressed.connect(self._submit)

    # ---- behavior --------------------------------------------------------

    def _submit(self) -> None:
        self.clear_error()
        self._on_submit(self.username.text().strip(), self.password.text())

    def set_error(self, message: str) -> None:
        self._error.setText(message)
        self._error.setVisible(True)
        self.username.setProperty("state", "error")
        self.password.edit.setProperty("state", "error")
        self._repolish(self.username)
        self._repolish(self.password.edit)

    def clear_error(self) -> None:
        self._error.setVisible(False)
        self.username.setProperty("state", "")
        self.password.edit.setProperty("state", "")
        self._repolish(self.username)
        self._repolish(self.password.edit)

    def set_busy(self, busy: bool) -> None:
        self.submit.setEnabled(not busy)
        self.submit.setText(
            self._t.gettext("login.signing_in" if busy else "login.signin"))

    def focus_first(self) -> None:
        (self.password.edit if self.username.text().strip() else self.username).setFocus()

    @staticmethod
    def _repolish(widget: QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def retranslate(self, translator: Translator) -> None:
        self._t = translator
        self._title.setText(translator.gettext("login.title"))
        self._subtitle.setText(translator.gettext("login.subtitle"))
        self._username_label.setText(translator.gettext("login.username"))
        self._password_label.setText(translator.gettext("login.password"))
        self.username.setPlaceholderText(translator.gettext("login.username_ph"))
        self.password.retranslate(translator)
        self.submit.setText(translator.gettext("login.signin"))
