"""Account Settings — the signed-in user changes their own password / username.

Self-service (round 2 §12): both actions require the current password, are verified
and audited by :class:`UserService`, never store plaintext, and preserve the user
id (so all transaction/audit relationships stay intact). Same LOCKED design system,
EN/Dari and RTL/LTR as the rest of the app.
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

from zenith_business.core.exceptions import ZenithError
from zenith_business.core.i18n import Translator
from zenith_business.ui.components import (
    Card,
    LabeledField,
    apply_shadow,
    escape_amp,
    eyebrow,
    page_title,
    primary_button,
    secondary_button,
    standard_icon,
)
from zenith_business.ui.design.tokens import FieldWidth, Spacing


class AccountSettingsPage(QWidget):
    def __init__(self, context, translator: Translator, *,
                 on_close: Callable[[], None] | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctx = context
        self._t = translator
        self._on_close = on_close
        self.setProperty("role", "workspace")

        root = QVBoxLayout(self)
        root.setContentsMargins(Spacing.PAGE_MARGIN, Spacing.SM,
                                Spacing.PAGE_MARGIN, Spacing.SM)
        root.setSpacing(Spacing.SM)
        self._title = page_title(self._t.gettext("acct.title"))
        root.addWidget(self._title)
        root.addWidget(self._build_password_card())
        root.addWidget(self._build_username_card())
        root.addStretch(1)
        root.addWidget(self._build_action_bar())

    def _pw_edit(self) -> QLineEdit:
        e = QLineEdit(); e.setEchoMode(QLineEdit.EchoMode.Password)
        e.setFixedWidth(int(FieldWidth.LG))
        return e

    def _build_password_card(self) -> QWidget:
        card = Card(role="section"); card.setProperty("accent", "navy"); apply_shadow(card)
        card.body.setContentsMargins(Spacing.CARD_PAD_H, Spacing.SM, Spacing.CARD_PAD_H, Spacing.SM)
        card.body.setSpacing(Spacing.XS)
        self._pw_head = eyebrow(self._t.gettext("acct.change_password"))
        card.body.addWidget(self._pw_head)
        self._pw_current = self._pw_edit(); self._pw_new = self._pw_edit()
        self._pw_confirm = self._pw_edit()
        self._pw_lfs = [
            ("acct.current_password", self._pw_current),
            ("acct.new_password", self._pw_new),
            ("acct.confirm_password", self._pw_confirm),
        ]
        row = QHBoxLayout(); row.setSpacing(Spacing.LG)
        self._pw_lf_widgets = []
        for key, ctrl in self._pw_lfs:
            lf = LabeledField(self._t.gettext(key), ctrl, width=FieldWidth.LG, compact=True)
            self._pw_lf_widgets.append((key, lf)); row.addWidget(lf)
        row.addStretch(1)
        card.body.addLayout(row)
        bar = QHBoxLayout()
        self._pw_msg = QLabel(""); self._pw_msg.setProperty("role", "secondary")
        self._pw_btn = primary_button(self._t.gettext("acct.update_password"))
        self._pw_btn.clicked.connect(self._save_password)
        bar.addWidget(self._pw_msg); bar.addStretch(1); bar.addWidget(self._pw_btn)
        card.body.addLayout(bar)
        return card

    def _build_username_card(self) -> QWidget:
        card = Card(role="section"); card.setProperty("accent", "teal"); apply_shadow(card)
        card.body.setContentsMargins(Spacing.CARD_PAD_H, Spacing.SM, Spacing.CARD_PAD_H, Spacing.SM)
        card.body.setSpacing(Spacing.XS)
        self._un_head = eyebrow(self._t.gettext("acct.change_username"))
        card.body.addWidget(self._un_head)
        self._un_current = self._pw_edit()
        self._un_new = QLineEdit(); self._un_new.setFixedWidth(int(FieldWidth.LG))
        row = QHBoxLayout(); row.setSpacing(Spacing.LG)
        self._un_lfs = [("acct.current_password", self._un_current),
                        ("acct.new_username", self._un_new)]
        self._un_lf_widgets = []
        for key, ctrl in self._un_lfs:
            lf = LabeledField(self._t.gettext(key), ctrl, width=FieldWidth.LG, compact=True)
            self._un_lf_widgets.append((key, lf)); row.addWidget(lf)
        row.addStretch(1)
        card.body.addLayout(row)
        bar = QHBoxLayout()
        self._un_msg = QLabel(""); self._un_msg.setProperty("role", "secondary")
        self._un_btn = primary_button(self._t.gettext("acct.update_username"))
        self._un_btn.clicked.connect(self._save_username)
        bar.addWidget(self._un_msg); bar.addStretch(1); bar.addWidget(self._un_btn)
        card.body.addLayout(bar)
        return card

    def _build_action_bar(self) -> QWidget:
        from PyQt6.QtWidgets import QFrame
        bar = QFrame(); bar.setProperty("role", "actionbar"); apply_shadow(bar, blur=18, y=3, alpha=30)
        row = QHBoxLayout(bar)
        row.setContentsMargins(Spacing.LG, Spacing.SM, Spacing.LG, Spacing.SM)
        row.addStretch(1)
        self._btn_close = secondary_button(self._t.gettext("s4.act_close"))
        self._btn_close.setIcon(standard_icon("close"))
        if self._on_close is not None:
            self._btn_close.clicked.connect(lambda: self._on_close())
        row.addWidget(self._btn_close)
        return bar

    # ---- actions ---------------------------------------------------------

    def _save_password(self) -> None:
        self._pw_msg.setProperty("role", "secondary"); self._pw_msg.setText("")
        if self._pw_new.text() != self._pw_confirm.text():
            self._flash(self._pw_msg, self._t.gettext("acct.err_mismatch"), ok=False)
            return
        try:
            self._ctx.users.change_own_password(
                current_password=self._pw_current.text(), new_password=self._pw_new.text())
        except ZenithError as exc:
            self._flash(self._pw_msg, getattr(exc, "user_message", None) or str(exc), ok=False)
            return
        for e in (self._pw_current, self._pw_new, self._pw_confirm):
            e.clear()
        self._flash(self._pw_msg, self._t.gettext("acct.ok_password"), ok=True)

    def _save_username(self) -> None:
        try:
            self._ctx.users.change_own_username(
                current_password=self._un_current.text(), new_username=self._un_new.text())
        except ZenithError as exc:
            self._flash(self._un_msg, getattr(exc, "user_message", None) or str(exc), ok=False)
            return
        self._un_current.clear(); self._un_new.clear()
        self._flash(self._un_msg, self._t.gettext("acct.ok_username"), ok=True)

    def _flash(self, label: QLabel, text: str, *, ok: bool) -> None:
        label.setText(text)
        label.setProperty("role", "success" if ok else "error")
        label.style().unpolish(label); label.style().polish(label)

    def reload(self) -> None:
        for e in (self._pw_current, self._pw_new, self._pw_confirm,
                  self._un_current, self._un_new):
            e.clear()
        self._pw_msg.setText(""); self._un_msg.setText("")

    def retranslate(self, translator: Translator) -> None:
        self._t = translator
        self._title.setText(translator.gettext("acct.title"))
        self._pw_head.setText(translator.gettext("acct.change_password"))
        self._un_head.setText(translator.gettext("acct.change_username"))
        for key, lf in self._pw_lf_widgets + self._un_lf_widgets:
            lf.set_label(translator.gettext(key))
        self._pw_btn.setText(escape_amp(translator.gettext("acct.update_password")))
        self._un_btn.setText(escape_amp(translator.gettext("acct.update_username")))
        self._btn_close.setText(escape_amp(translator.gettext("s4.act_close")))
