"""Login page (Stage 02 §11).

A focused credentials form built from the design system. It does no
authentication itself — it collects input and delegates to a callback, then
displays the outcome (error message or a busy state). Pressing Enter submits.
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QTimer
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
        # Transparency is applied via the APP-level stylesheet (theme.py), not a
        # widget-level stylesheet: a widget-scoped sheet here would suppress the
        # app QSS background on child controls (e.g. blank the primary Sign In
        # button). The object name lets the global rule target this widget only.
        self.setObjectName("LoginPageRoot")

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

        # Lockout countdown. Seconds remaining, ticked once a second so the
        # owner watches the wait shrink instead of guessing at it.
        self._lock_seconds = 0
        self._lock_timer = QTimer(self)
        self._lock_timer.setInterval(1000)
        self._lock_timer.timeout.connect(self._tick_lockout)

    # ---- behavior --------------------------------------------------------

    def _submit(self) -> None:
        self.clear_error()
        self._on_submit(self.username.text().strip(), self.password.text())

    def set_error(self, message: str) -> None:
        # Any other outcome replaces the countdown — it is no longer the truth.
        self.stop_lockout()
        self._set_message_role("error")
        self._error.setText(message)
        self._error.setVisible(True)
        self.username.setProperty("state", "error")
        self.password.edit.setProperty("state", "error")
        self._repolish(self.username)
        self._repolish(self.password.edit)

    def clear_error(self) -> None:
        self.username.setProperty("state", "")
        self.password.edit.setProperty("state", "")
        self._repolish(self.username)
        self._repolish(self.password.edit)
        if self._lock_seconds > 0:
            # A running countdown outlives an ordinary error clear: the wait is
            # still real, and hiding it because the owner pressed Sign In again
            # would be the confusing half-second of nothing we set out to fix.
            self._render_lockout()
            return
        self._error.setVisible(False)

    # ---- lockout countdown ------------------------------------------------

    def show_lockout(self, seconds_remaining: int) -> None:
        """Display 'Try again in 12m 34s.' and count it down to zero."""
        self._lock_seconds = max(0, int(seconds_remaining or 0))
        if self._lock_seconds <= 0:
            self.stop_lockout()
            self.set_error(self._t.gettext("login.error_locked"))
            return
        self._render_lockout()
        self._lock_timer.start()

    def stop_lockout(self) -> None:
        self._lock_seconds = 0
        self._lock_timer.stop()

    @property
    def lockout_seconds(self) -> int:
        """Seconds still on the countdown (0 when no lock is being shown)."""
        return self._lock_seconds

    def lockout_text(self) -> str:
        """The message currently being counted down, in the active language."""
        minutes, seconds = divmod(self._lock_seconds, 60)
        return self._t.gettext("login.error_locked_countdown").format(
            m=minutes, s=f"{seconds:02d}")

    def _render_lockout(self) -> None:
        self._set_message_role("error")
        self._error.setText(self.lockout_text())
        self._error.setVisible(True)
        self.username.setProperty("state", "error")
        self.password.edit.setProperty("state", "error")
        self._repolish(self.username)
        self._repolish(self.password.edit)

    def _tick_lockout(self) -> None:
        self._lock_seconds -= 1
        if self._lock_seconds <= 0:
            self.stop_lockout()
            # Say so rather than going blank — the owner is watching this line.
            # In the neutral colour: the wait ending is good news, not an error.
            self._set_message_role("secondary")
            self._error.setText(self._t.gettext("login.lock_over"))
            self._error.setVisible(True)
            self.username.setProperty("state", "")
            self.password.edit.setProperty("state", "")
            self._repolish(self.username)
            self._repolish(self.password.edit)
            return
        self._render_lockout()

    def _set_message_role(self, role: str) -> None:
        if self._error.property("role") != role:
            self._error.setProperty("role", role)
            self._repolish(self._error)

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
        if self._lock_seconds > 0:
            # Switching language mid-lock must not leave English on a Dari page.
            self._render_lockout()
