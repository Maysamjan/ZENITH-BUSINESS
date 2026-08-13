"""Shared auth-form widgets (Stage 02).

A password input with an inline Show/Hide toggle, built from the design system so
it matches every other input. The toggle never reveals the password to logs — it
only changes the on-screen echo mode.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QWidget

from zenith_business.core.i18n import Translator
from zenith_business.ui.design.tokens import Spacing


class PasswordField(QWidget):
    """A ``QLineEdit`` in password mode with a Show/Hide toggle button."""

    def __init__(self, translator: Translator, placeholder_key: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._t = translator
        self.setObjectName("PasswordFieldRoot")
        self.setStyleSheet("QWidget#PasswordFieldRoot { background: transparent; }")
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(Spacing.SM)

        self.edit = QLineEdit()
        self.edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit.setPlaceholderText(self._t.gettext(placeholder_key))
        self._placeholder_key = placeholder_key

        self.toggle = QPushButton(self._t.gettext("login.show"))
        self.toggle.setCheckable(True)
        self.toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle.setFixedWidth(64)
        self.toggle.clicked.connect(self._on_toggle)

        row.addWidget(self.edit, 1)
        row.addWidget(self.toggle)

    def _on_toggle(self) -> None:
        if self.toggle.isChecked():
            self.edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle.setText(self._t.gettext("login.hide"))
        else:
            self.edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle.setText(self._t.gettext("login.show"))

    def text(self) -> str:
        return self.edit.text()

    def clear(self) -> None:
        self.edit.clear()

    def retranslate(self, translator: Translator) -> None:
        self._t = translator
        self.edit.setPlaceholderText(translator.gettext(self._placeholder_key))
        self.toggle.setText(
            translator.gettext("login.hide" if self.toggle.isChecked() else "login.show"))
