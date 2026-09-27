"""Initial administrator setup page (Stage 02 §11).

Shown only on first run (empty user table). Collects the first administrator's
details — there is no built-in default account — and delegates creation to a
callback. Built from the same design system and fully bilingual.
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtWidgets import QLineEdit, QVBoxLayout, QWidget

from zenith_business.core.i18n import Translator
from zenith_business.ui.auth.widgets import PasswordField
from zenith_business.ui.components import (
    error_label,
    field_label,
    muted,
    page_subtitle,
    page_title,
    primary_button,
)
from zenith_business.ui.design.tokens import FieldWidth, Spacing


class InitialAdminSetupPage(QWidget):
    def __init__(
        self,
        translator: Translator,
        on_submit: Callable[[dict], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._t = translator
        self._on_submit = on_submit
        # Scope the transparent background to THIS widget only (see LoginPage).
        # Transparency via the app-level stylesheet (theme.py), not a
        # widget-level sheet, so child controls keep their app QSS backgrounds.
        self.setObjectName("SetupPageRoot")

        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(Spacing.XS)

        self._title = page_title(self._t.gettext("setup.title"))
        self._subtitle = page_subtitle(self._t.gettext("setup.subtitle"))
        col.addWidget(self._title)
        col.addWidget(self._subtitle)
        col.addSpacing(Spacing.SM)

        self._company_label = field_label(self._t.gettext("setup.company"))
        self.company = QLineEdit()
        self.company.setPlaceholderText(self._t.gettext("setup.company_ph"))
        self.company.setMinimumWidth(int(FieldWidth.LG))
        col.addWidget(self._company_label)
        col.addWidget(self.company)

        self._fullname_label = field_label(self._t.gettext("setup.fullname"))
        self.full_name = QLineEdit()
        self.full_name.setPlaceholderText(self._t.gettext("setup.fullname_ph"))
        col.addWidget(self._fullname_label)
        col.addWidget(self.full_name)

        self._username_label = field_label(self._t.gettext("setup.username"))
        self.username = QLineEdit()
        col.addWidget(self._username_label)
        col.addWidget(self.username)

        self._password_label = field_label(self._t.gettext("setup.password"))
        self.password = PasswordField(self._t, "login.password_ph")
        col.addWidget(self._password_label)
        col.addWidget(self.password)

        self._confirm_label = field_label(self._t.gettext("setup.confirm"))
        self.confirm = PasswordField(self._t, "login.password_ph")
        col.addWidget(self._confirm_label)
        col.addWidget(self.confirm)

        self._hint = muted(self._t.gettext("setup.password_hint"))
        col.addWidget(self._hint)

        self._error = error_label("")
        self._error.setVisible(False)
        col.addWidget(self._error)

        col.addSpacing(Spacing.SM)
        self.submit = primary_button(self._t.gettext("setup.create"))
        self.submit.setMinimumHeight(36)
        self.submit.clicked.connect(self._submit)
        col.addWidget(self.submit)
        col.addStretch(1)  # pack fields to the top; absorb extra card height

    def _submit(self) -> None:
        self.clear_error()
        self._on_submit({
            "company_name": self.company.text().strip(),
            "full_name": self.full_name.text().strip(),
            "username": self.username.text().strip(),
            "password": self.password.text(),
            "confirm_password": self.confirm.text(),
        })

    def set_error(self, message: str) -> None:
        self._error.setText(message)
        self._error.setVisible(True)

    def clear_error(self) -> None:
        self._error.setVisible(False)

    def retranslate(self, translator: Translator) -> None:
        self._t = translator
        self._title.setText(translator.gettext("setup.title"))
        self._subtitle.setText(translator.gettext("setup.subtitle"))
        self._company_label.setText(translator.gettext("setup.company"))
        self.company.setPlaceholderText(translator.gettext("setup.company_ph"))
        self._fullname_label.setText(translator.gettext("setup.fullname"))
        self.full_name.setPlaceholderText(translator.gettext("setup.fullname_ph"))
        self._username_label.setText(translator.gettext("setup.username"))
        self._password_label.setText(translator.gettext("setup.password"))
        self._confirm_label.setText(translator.gettext("setup.confirm"))
        self.password.retranslate(translator)
        self.confirm.retranslate(translator)
        self._hint.setText(translator.gettext("setup.password_hint"))
        self.submit.setText(translator.gettext("setup.create"))
