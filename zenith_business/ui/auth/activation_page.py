"""The activation screen, shown BEFORE login (Stage 10 final §1).

Real Windows testing found the gate in the wrong place: the application opened
the login screen and the whole workspace while unlicensed, and licensing was
something you went and looked at afterwards, in Tools. A licence checked after
the door is already open is not a gate.

So this page lives in the **same window as login**, as the page in front of it.
It is not a separate dialog that could be skipped, and there is no route from
here to the login form except a licence that evaluates to FULL or DEMO. A fresh
install, a licence for another computer, an edited licence and a finished demo
all land here, each with its own wording — "you have not activated yet" is not
the same message as "this licence has been altered", and telling a customer the
wrong one of those costs a support call.

What it can do is exactly what an unlicensed installation must be able to do:
read this machine's id, write an activation request for the vendor, and import
the licence that comes back. It cannot issue anything — the application holds a
public verification key and nothing else.

**It never touches business data.** Nothing on this page reads, writes, deletes
or encrypts a customer's records. An installation that can never be activated
still has every byte of its data, and the Backup screen behind a valid licence
is not the only way out: the database file itself is untouched on disk.
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from zenith_business.core.i18n import Translator
from zenith_business.ui.components import (
    error_label,
    page_subtitle,
    page_title,
    primary_button,
    secondary_button,
)
from zenith_business.ui.design.tokens import Spacing

#: Field captions, in the order a customer reads them.
_FIELDS = (
    ("act.f_product", "product"),
    ("act.f_machine", "machine"),
    ("act.f_status", "status"),
    ("act.f_type", "license_type"),
    ("act.f_expires", "expires"),
)

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
    """Product, machine id, licence state, and the two things you can do."""

    def __init__(self, translator: Translator, *,
                 on_make_request: Callable[[], None],
                 on_import: Callable[[], None],
                 on_recheck: Callable[[], None],
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._t = translator
        self.setObjectName("LoginPageRoot")     # same transparent-surface rule

        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(Spacing.SM)

        self._title = page_title(translator.gettext("act.title"))
        self._subtitle = page_subtitle(translator.gettext("act.subtitle"))
        col.addWidget(self._title)
        col.addWidget(self._subtitle)
        col.addSpacing(Spacing.SM)

        self._form = QFormLayout()
        self._form.setHorizontalSpacing(Spacing.LG)
        self._form.setVerticalSpacing(Spacing.XS)
        self._captions: dict[str, QLabel] = {}
        self._values: dict[str, QLabel] = {}
        for key, name in _FIELDS:
            caption = QLabel(translator.gettext(key))
            caption.setProperty("role", "secondary")
            value = QLabel("—")
            value.setWordWrap(True)
            # The machine id is what the customer reads out or copies into an
            # email, so it must be selectable.
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self._captions[key] = caption
            self._values[name] = value
            self._form.addRow(caption, value)
        col.addLayout(self._form)

        self._why = error_label("")
        self._why.setWordWrap(True)
        col.addSpacing(Spacing.XS)
        col.addWidget(self._why)

        self._status_line = QLabel("")
        self._status_line.setProperty("role", "secondary")
        self._status_line.setWordWrap(True)
        col.addWidget(self._status_line)

        col.addSpacing(Spacing.SM)
        self._request_btn = primary_button(translator.gettext("act.make_request"))
        self._request_btn.setMinimumHeight(36)
        self._request_btn.clicked.connect(lambda: on_make_request())
        col.addWidget(self._request_btn)

        row = QHBoxLayout()
        self._import_btn = secondary_button(translator.gettext("act.import"))
        self._import_btn.clicked.connect(lambda: on_import())
        row.addWidget(self._import_btn)
        self._recheck_btn = secondary_button(translator.gettext("act.recheck"))
        self._recheck_btn.clicked.connect(lambda: on_recheck())
        row.addWidget(self._recheck_btn)
        row.addStretch(1)
        col.addLayout(row)
        col.addStretch(1)

        self._state = None

    # ---- display ---------------------------------------------------------

    def show_state(self, state) -> None:
        """Render a :class:`LicenseEvaluation`. The only way this page changes."""
        from zenith_business.core.identity import PRODUCT_NAME

        self._state = state
        t = self._t
        self._values["product"].setText(PRODUCT_NAME)
        self._values["machine"].setText(state.machine_short or "—")
        self._values["status"].setText(t.gettext(f"sec.st_{state.status.lower()}"))
        self._values["license_type"].setText(state.license_type or t.gettext("sec.lic_none"))
        # "Never" is only true of a licence that exists and has no end date. With
        # no licence at all there is nothing to expire, and saying "Never" reads
        # as reassurance about an entitlement the customer does not have.
        expiry = state.expires_at or state.demo_expires_on
        self._values["expires"].setText(
            expiry if expiry else (t.gettext("sec.lic_never") if state.license_id
                                   else t.gettext("sec.lic_not_applicable")))

        explanation = self._explain(state)
        self._why.setText(explanation)
        self._why.setVisible(bool(explanation))
        extra = []
        if state.clock_rolled_back:
            extra.append(t.gettext("act.clock_warning"))
        # The evaluation's own detail is the short, internal version of the same
        # sentence. Printing both put "This installation has not been activated
        # yet." on the screen twice, one line under the other.
        if state.detail and not explanation:
            extra.append(state.detail)
        self._status_line.setText(" ".join(extra))
        self._status_line.setVisible(bool(extra))

    def _explain(self, state) -> str:
        key = _REASON_TEXT.get(state.reason) or _EXPLANATION.get(state.status)
        return self._t.gettext(key) if key else ""

    def say(self, message: str, *, bad: bool = False) -> None:
        """Report the outcome of an action without disturbing the state fields."""
        self._status_line.setText(message)
        self._status_line.setProperty("role", "danger" if bad else "secondary")
        self._status_line.style().unpolish(self._status_line)
        self._status_line.style().polish(self._status_line)
        self._status_line.setVisible(bool(message))

    def retranslate(self, translator: Translator) -> None:
        self._t = translator
        self._title.setText(translator.gettext("act.title"))
        self._subtitle.setText(translator.gettext("act.subtitle"))
        for key, caption in self._captions.items():
            caption.setText(translator.gettext(key))
        self._request_btn.setText(translator.gettext("act.make_request"))
        self._import_btn.setText(translator.gettext("act.import"))
        self._recheck_btn.setText(translator.gettext("act.recheck"))
        if self._state is not None:
            self.show_state(self._state)
