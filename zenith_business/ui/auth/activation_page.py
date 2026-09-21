"""The activation screen, shown BEFORE login (Stage 10 final §1).

Real Windows testing found the gate in the wrong place: the application opened
the login screen and the whole workspace while unlicensed, and licensing was
something you went and looked at afterwards, in Tools. A licence checked after
the door is already open is not a gate.

So this page lives in the **same window as login**, as the page in front of it.
It is not a separate dialog that could be skipped, and there is no route from
here to the login form except a licence that evaluates to FULL or DEMO.

The shape of it: copy, send, paste, activate
--------------------------------------------
The first version asked the customer to save a ``.zreq`` file, email the file,
receive a ``.zlic`` file, find it on disk and import it. Four file operations
for someone who wants to start work. The owner asked for the workflow their
other product uses, and they were right to:

    1. Copy the request code
    2. Send it (WhatsApp, SMS, a phone call, anything)
    3. Receive a product key
    4. Paste it
    5. Activate

Nothing about the security changes. A product key is the same Ed25519-signed,
machine-bound licence a ``.zlic`` holds, packed small enough to paste — see
:mod:`zenith_business.security.product_key`. The file route survives under
**Advanced**, because a long code can be mangled by an email client and a file
cannot.

Each failure gets its own wording — "you have not activated yet" is not the
same message as "this licence has been altered", and telling a customer the
wrong one of those costs a support call.

**It never touches business data.** Nothing here reads, writes, deletes or
encrypts a customer's records. An installation that can never be activated
still has every byte of its data.
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from zenith_business.core.i18n import Translator
from zenith_business.ui.components import (
    error_label,
    link_button,
    page_subtitle,
    page_title,
    primary_button,
    secondary_button,
)
from zenith_business.ui.design.tokens import Spacing

#: Status -> the sentence that explains it. Each one names what to DO next,
#: because "invalid" on its own tells the customer nothing they can act on.
_EXPLANATION = {
    "UNLICENSED": "act.why_unlicensed",
    "DEMO_EXPIRED": "act.why_demo_over",
    "INVALID": "act.why_invalid",
    "NO_VENDOR_KEY": "act.why_no_key",
}

#: Reasons that deserve wording of their own rather than the generic "invalid".
_REASON_TEXT = {
    "wrong_machine": "act.why_wrong_machine",
    "expired": "act.why_expired",
    "bad_signature": "act.why_altered",
    "malformed": "act.why_altered",
    "wrong_product": "act.why_wrong_product",
    "no_crypto_backend": "act.why_no_backend",
}


class ActivationPage(QWidget):
    """Machine ID and request code out; product key in; activate."""

    def __init__(self, translator: Translator, *,
                 on_activate: Callable[[str], None],
                 on_copy_request: Callable[[], None],
                 on_make_request: Callable[[], None],
                 on_import: Callable[[], None],
                 on_recheck: Callable[[], None],
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._t = translator
        self._on_activate = on_activate
        self.setObjectName("LoginPageRoot")     # same transparent-surface rule

        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(Spacing.XS)

        self._title = page_title(translator.gettext("act.title"))
        self._subtitle = page_subtitle(translator.gettext("act.subtitle"))
        col.addWidget(self._title)
        col.addWidget(self._subtitle)

        # ---- what the customer sends ------------------------------------
        self._id_panel = QFrame()
        self._id_panel.setProperty("role", "card")
        panel = QVBoxLayout(self._id_panel)
        panel.setContentsMargins(Spacing.MD, Spacing.SM, Spacing.MD, Spacing.SM)
        panel.setSpacing(Spacing.XS)

        self._machine_caption = QLabel(translator.gettext("act.your_machine_id"))
        self._machine_caption.setProperty("role", "field-label")
        panel.addWidget(self._machine_caption)
        self._machine_id = QLabel("—")
        self._machine_id.setProperty("role", "code")
        self._machine_id.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        panel.addWidget(self._machine_id)

        self._request_hint = QLabel(translator.gettext("act.request_hint"))
        self._request_hint.setProperty("role", "secondary")
        self._request_hint.setWordWrap(True)
        panel.addWidget(self._request_hint)

        self._copy_btn = secondary_button(translator.gettext("act.copy_request"))
        self._copy_btn.clicked.connect(lambda: on_copy_request())
        row = QHBoxLayout()
        row.addWidget(self._copy_btn)
        row.addStretch(1)
        panel.addLayout(row)
        col.addWidget(self._id_panel)

        # ---- what the customer pastes -----------------------------------
        col.addSpacing(Spacing.XS)
        self._key_caption = QLabel(translator.gettext("act.product_key"))
        self._key_caption.setProperty("role", "field-label")
        col.addWidget(self._key_caption)

        self.key_input = QPlainTextEdit()
        self.key_input.setPlaceholderText(translator.gettext("act.product_key_ph"))
        # Three lines: the whole key is visible at once, so a customer can see
        # that all of it arrived rather than discovering a truncated paste from
        # a signature failure.
        self.key_input.setFixedHeight(76)
        self.key_input.setTabChangesFocus(True)
        col.addWidget(self.key_input)

        self._error = error_label("")
        self._error.setVisible(False)
        col.addWidget(self._error)

        self.activate_btn = primary_button(translator.gettext("act.activate"))
        self.activate_btn.setMinimumHeight(36)
        self.activate_btn.clicked.connect(self._submit)
        col.addWidget(self.activate_btn)

        # ---- the file route, kept but out of the way ---------------------
        self._advanced_btn = link_button(translator.gettext("act.advanced_show"))
        self._advanced_btn.clicked.connect(self._toggle_advanced)
        col.addWidget(self._advanced_btn)

        self._advanced = QWidget()
        adv = QHBoxLayout(self._advanced)
        adv.setContentsMargins(0, 0, 0, 0)
        self._request_btn = secondary_button(translator.gettext("act.make_request"))
        self._request_btn.clicked.connect(lambda: on_make_request())
        self._import_btn = secondary_button(translator.gettext("act.import"))
        self._import_btn.clicked.connect(lambda: on_import())
        self._recheck_btn = secondary_button(translator.gettext("act.recheck"))
        self._recheck_btn.clicked.connect(lambda: on_recheck())
        for button in (self._request_btn, self._import_btn, self._recheck_btn):
            adv.addWidget(button)
        adv.addStretch(1)
        self._advanced.setVisible(False)
        col.addWidget(self._advanced)

        # ---- state, reported quietly under everything --------------------
        self._status_line = QLabel("")
        self._status_line.setProperty("role", "secondary")
        self._status_line.setWordWrap(True)
        col.addWidget(self._status_line)
        col.addStretch(1)

        self._state = None

    # ---- behaviour -------------------------------------------------------

    def _toggle_advanced(self) -> None:
        showing = not self._advanced.isVisible()
        self._advanced.setVisible(showing)
        self._advanced_btn.setText(self._t.gettext(
            "act.advanced_hide" if showing else "act.advanced_show"))

    def _submit(self) -> None:
        self.clear_error()
        self._on_activate(self.key_input.toPlainText())

    @property
    def product_key(self) -> str:
        return self.key_input.toPlainText()

    def clear_key(self) -> None:
        self.key_input.clear()

    def set_error(self, message: str) -> None:
        self._show_message(message, bad=True)

    def _show_message(self, message: str, *, bad: bool) -> None:
        self._error.setProperty("role", "error" if bad else "secondary")
        self._error.style().unpolish(self._error)
        self._error.style().polish(self._error)
        self._error.setText(message)
        self._error.setVisible(bool(message))

    def clear_error(self) -> None:
        self._error.setVisible(False)

    # ---- display ---------------------------------------------------------

    def show_state(self, state) -> None:
        """Render a :class:`LicenseEvaluation`. The only way this page changes."""
        self._state = state
        t = self._t
        self._machine_id.setText(state.machine_short or "—")

        explanation = self._explain(state)
        # A fresh install has done nothing wrong, so its instructions are not an
        # error. Red belongs to a licence that was refused; "here is what to do
        # next" in red makes a first run look like a fault.
        self._show_message(explanation, bad=state.status != "UNLICENSED")
        extra = []
        if state.clock_rolled_back:
            extra.append(t.gettext("act.clock_warning"))
        # The evaluation's own detail is the short, internal version of the same
        # sentence. Printing both put the same line on the screen twice.
        if state.detail and not explanation:
            extra.append(state.detail)
        self._status_line.setText(" ".join(extra))
        self._status_line.setVisible(bool(extra))

    def _explain(self, state) -> str:
        key = _REASON_TEXT.get(state.reason) or _EXPLANATION.get(state.status)
        return self._t.gettext(key) if key else ""

    def say(self, message: str, *, bad: bool = False) -> None:
        """Report the outcome of an action without disturbing the state fields."""
        if bad:
            self.set_error(message)
            return
        self._status_line.setText(message)
        self._status_line.setVisible(bool(message))

    def retranslate(self, translator: Translator) -> None:
        self._t = translator
        self._title.setText(translator.gettext("act.title"))
        self._subtitle.setText(translator.gettext("act.subtitle"))
        self._machine_caption.setText(translator.gettext("act.your_machine_id"))
        self._request_hint.setText(translator.gettext("act.request_hint"))
        self._key_caption.setText(translator.gettext("act.product_key"))
        self.key_input.setPlaceholderText(translator.gettext("act.product_key_ph"))
        self._copy_btn.setText(translator.gettext("act.copy_request"))
        self.activate_btn.setText(translator.gettext("act.activate"))
        self._advanced_btn.setText(translator.gettext(
            "act.advanced_hide" if self._advanced.isVisible() else "act.advanced_show"))
        self._request_btn.setText(translator.gettext("act.make_request"))
        self._import_btn.setText(translator.gettext("act.import"))
        self._recheck_btn.setText(translator.gettext("act.recheck"))
        if self._state is not None:
            self.show_state(self._state)
