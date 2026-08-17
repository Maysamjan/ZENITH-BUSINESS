"""Stage 05 money-movement entry — Receipts, Payments, Expenses.

ONE reusable, real, service-backed workspace (``mode`` = ``"receipt"`` |
``"payment"`` | ``"expense"``) built on the LOCKED Stage 01–04 design system:
the same cards, LabeledField metadata, SearchSelector autocomplete, strong
total pill, action bar and RTL behaviour as the Stage 04 invoice screens — no
new visual style. Compact (no line grid): a party/category card, a details
card, and a single totals/amount strip that fits 1366×768.

Posting calls the atomic Stage 05 services (ledger + party balance + document
number + audit) in one transaction. Money is Decimal end to end.
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from zenith_business.core.exceptions import ZenithError
from zenith_business.core.money import D, format_money, money
from zenith_business.services.money_documents import PAYMENT_METHODS
from zenith_business.ui.components import (
    Card,
    LabeledField,
    apply_shadow,
    chip,
    escape_amp,
    eyebrow,
    field_label,
    horizontal_divider,
    primary_button,
    secondary_button,
    standard_icon,
)
from zenith_business.ui.design.tokens import FieldWidth, Spacing
from zenith_business.ui.widgets.search_selector import SearchRow, SearchSelector

_METHOD_KEYS = {"CASH": "s5.m_cash", "BANK": "s5.m_bank", "TRANSFER": "s5.m_transfer",
                "CHEQUE": "s5.m_cheque", "OTHER": "s5.m_other"}


class MoneyEntryPage(QWidget):
    """Real keyboard-first Receipt / Payment / Expense entry."""

    def __init__(
        self,
        context,
        translator,
        *,
        mode: str = "receipt",
        on_print: Callable[[int], None] | None = None,
        on_close: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._ctx = context
        self._t = translator
        self._mode = mode  # 'receipt' | 'payment' | 'expense'
        self._on_print = on_print
        self._on_close = on_close
        self._party_id: int | None = None
        self._prev_balance = D(0)
        self._last_saved_id: int | None = None

        self.setProperty("role", "workspace")
        root = QVBoxLayout(self)
        root.setContentsMargins(Spacing.MD, Spacing.SM, Spacing.MD, Spacing.SM)
        root.setSpacing(Spacing.SM)
        root.addLayout(self._build_titlebar())
        root.addWidget(self._build_header())
        root.addWidget(self._build_details())
        root.addWidget(self._build_amount_strip())
        root.addStretch(1)
        root.addWidget(self._build_action_bar())

        self._reload_sources()
        self._recompute()

    # ---- title -----------------------------------------------------------

    def _title_key(self) -> str:
        return {"receipt": "s5.receipt_title", "payment": "s5.payment_title",
                "expense": "s5.expense_title"}[self._mode]

    def _build_titlebar(self) -> QHBoxLayout:
        row = QHBoxLayout(); row.setSpacing(Spacing.MD)
        self._title = QLabel(self._t.gettext(self._title_key()))
        self._title.setProperty("role", "page-title")
        row.addWidget(self._title); row.addStretch(1)
        self._status_msg = QLabel(""); self._status_msg.setProperty("role", "secondary")
        row.addWidget(self._status_msg)
        return row

    # ---- header (party or category + payee) -----------------------------

    def _build_header(self) -> QWidget:
        card = Card(role="section"); card.setProperty("accent", "navy"); apply_shadow(card)
        card.body.setContentsMargins(Spacing.CARD_PAD_H, Spacing.SM, Spacing.CARD_PAD_H, Spacing.SM)
        card.body.setSpacing(Spacing.XS)
        t = self._t
        row = QHBoxLayout(); row.setSpacing(Spacing.LG)

        if self._mode in ("receipt", "payment"):
            party_key = "s4.customer" if self._mode == "receipt" else "s4.supplier"
            ph_key = "s4.customer_search_ph" if self._mode == "receipt" else "s4.supplier_search_ph"
            provider = (self._ctx.customer_search if self._mode == "receipt"
                        else self._ctx.supplier_search)
            self._party_selector = SearchSelector(
                provider, placeholder=t.gettext(ph_key), display_index=1, panel_width=460)
            self._party_selector.rowSelected.connect(self._on_party_selected)
            self._party_selector.line_edit.textEdited.connect(self._on_party_text_edited)
            col = QVBoxLayout(); col.setContentsMargins(0, 0, 0, 0); col.setSpacing(Spacing.XXS)
            self._party_eyebrow = eyebrow(t.gettext(party_key))
            col.addWidget(self._party_eyebrow); col.addWidget(self._party_selector)
            wrap = QWidget(); wrap.setLayout(col); wrap.setStyleSheet("background: transparent;")
            wrap.setMinimumWidth(int(FieldWidth.LG))
            row.addWidget(wrap, 2)
            self._chip_phone = self._info_chip("si.phone", "—", "neutral")
            bal_key = "si.prev_balance" if self._mode == "receipt" else "s5.prev_payable"
            self._chip_balance = self._info_chip(bal_key, "—", "neutral")
            row.addWidget(self._chip_phone); row.addWidget(self._chip_balance)
        else:
            # expense: category + payee
            self._category_combo = QComboBox()
            self._payee_edit = QLineEdit()
            self._cat_field = LabeledField(t.gettext("s5.category"), self._category_combo,
                                           width=FieldWidth.MD)
            self._payee_field = LabeledField(t.gettext("s5.payee"), self._payee_edit,
                                             width=FieldWidth.LG)
            self._party_eyebrow = eyebrow(t.gettext("s5.expense_of"))
            col = QVBoxLayout(); col.setContentsMargins(0, 0, 0, 0); col.setSpacing(Spacing.XXS)
            col.addWidget(self._party_eyebrow)
            inner = QHBoxLayout(); inner.setSpacing(Spacing.LG)
            inner.addWidget(self._cat_field); inner.addWidget(self._payee_field)
            inner.addStretch(1)
            col.addLayout(inner)
            wrap = QWidget(); wrap.setLayout(col); wrap.setStyleSheet("background: transparent;")
            row.addWidget(wrap, 1)
        row.addStretch(1)
        card.body.addLayout(row)
        return card

    def _info_chip(self, label_key: str, value: str, accent: str) -> QWidget:
        wrap = QWidget(); wrap.setStyleSheet("background: transparent;")
        r = QHBoxLayout(wrap); r.setContentsMargins(0, 0, 0, 0); r.setSpacing(Spacing.XS)
        lab = field_label(self._t.gettext(label_key)); val = chip(value, accent)
        r.addWidget(lab); r.addWidget(val)
        wrap._label = lab; wrap._value = val; wrap._label_key = label_key  # type: ignore[attr-defined]
        return wrap

    def _set_chip(self, wrap: QWidget, value: str, accent: str) -> None:
        val = wrap._value  # type: ignore[attr-defined]
        val.setText(value); val.setProperty("chip", accent)
        val.style().unpolish(val); val.style().polish(val)

    # ---- details ---------------------------------------------------------

    def _build_details(self) -> QWidget:
        card = Card(role="section"); card.setProperty("accent", "brand"); apply_shadow(card)
        card.body.setContentsMargins(Spacing.CARD_PAD_H, Spacing.SM, Spacing.CARD_PAD_H, Spacing.SM)
        card.body.setSpacing(Spacing.SM)
        t = self._t
        self._details_title = QLabel(t.gettext("s5.details"))
        self._details_title.setProperty("role", "card-title"); self._details_title.setProperty("accent", "brand")
        card.body.addWidget(self._details_title)

        self._doc_no = QLineEdit(t.gettext("s4.auto")); self._doc_no.setReadOnly(True)
        self._date_edit = QLineEdit(self._today())
        self._fund_combo = QComboBox()
        self._method_combo = QComboBox()
        for m in PAYMENT_METHODS:
            self._method_combo.addItem(t.gettext(_METHOD_KEYS[m]), m)
        self._currency_combo = QComboBox()
        self._rate_edit = QLineEdit("1")
        self._rate_edit.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._reference_edit = QLineEdit()

        self._meta_fields: list[tuple[str, LabeledField]] = []
        specs = [
            ("s5.doc_no", self._doc_no, FieldWidth.SM),
            ("si.date", self._date_edit, FieldWidth.SM),
            ("s5.fund", self._fund_combo, FieldWidth.MD),
            ("s5.method", self._method_combo, FieldWidth.SM),
            ("si.currency", self._currency_combo, FieldWidth.SM),
            ("si.rate", self._rate_edit, FieldWidth.XS),
        ]
        r1 = QHBoxLayout(); r1.setSpacing(Spacing.LG)
        for key, ctrl, width in specs:
            lf = LabeledField(t.gettext(key), ctrl, width=width, compact=True)
            self._meta_fields.append((key, lf)); r1.addWidget(lf)
        r1.addStretch(1)
        card.body.addLayout(r1)

        card.body.addWidget(horizontal_divider())
        r2 = QHBoxLayout(); r2.setSpacing(Spacing.LG)
        self._ref_field = LabeledField(t.gettext("s5.reference"), self._reference_edit,
                                       width=FieldWidth.MD)
        self._notes_edit = QLineEdit()
        self._notes_field = LabeledField(t.gettext("s4.notes"), self._notes_edit,
                                         width=FieldWidth.LG)
        r2.addWidget(self._ref_field); r2.addWidget(self._notes_field); r2.addStretch(1)
        card.body.addLayout(r2)
        return card

    def _today(self) -> str:
        from zenith_business.core.clock import today_iso
        return today_iso()

    # ---- amount strip ----------------------------------------------------

    def _build_amount_strip(self) -> QWidget:
        card = Card(role="section"); card.setProperty("accent", "brand"); apply_shadow(card)
        card.body.setContentsMargins(Spacing.CARD_PAD_H, Spacing.SM, Spacing.CARD_PAD_H, Spacing.SM)
        t = self._t
        row = QHBoxLayout(); row.setSpacing(Spacing.XL)

        if self._mode in ("receipt", "payment"):
            self._prev_label, self._prev_value, prev_w = self._inline(
                "si.prev_balance" if self._mode == "receipt" else "s5.prev_payable")
            row.addWidget(prev_w)
        row.addStretch(1)

        # strong Amount pill with the editable amount input.
        pill = QFrame(); pill.setProperty("role", "grand-total-strong")
        pl = QHBoxLayout(pill); pl.setContentsMargins(Spacing.LG, Spacing.XS, Spacing.LG, Spacing.XS)
        pl.setSpacing(Spacing.MD)
        amt_key = {"receipt": "s5.amount_received", "payment": "s5.amount_paid",
                   "expense": "s5.amount"}[self._mode]
        self._amount_label = QLabel(t.gettext(amt_key)); self._amount_label.setProperty("role", "gts-label")
        self._amount_edit = QLineEdit("0.00")
        self._amount_edit.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._amount_edit.setFixedWidth(int(FieldWidth.MD))
        self._amount_edit.setProperty("role", "amount-strong")
        self._amount_edit.textEdited.connect(self._recompute)
        pl.addWidget(self._amount_label); pl.addWidget(self._amount_edit)
        row.addWidget(pill)

        if self._mode in ("receipt", "payment"):
            rem_key = "s5.remaining" if self._mode == "receipt" else "s5.remaining_payable"
            self._rem_label, self._rem_value, rem_w = self._inline(rem_key)
            row.addWidget(rem_w)
        else:
            self._fund_note_label, self._fund_note_value, fw = self._inline("s5.fund")
            row.addWidget(fw)
        card.body.addLayout(row)
        return card

    def _inline(self, key: str) -> tuple[QLabel, QLabel, QWidget]:
        lab = field_label(self._t.gettext(key))
        val = QLabel("—"); val.setProperty("role", "total-value")
        h = QHBoxLayout(); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(Spacing.XS)
        h.addWidget(lab); h.addWidget(val)
        holder = QWidget(); holder.setLayout(h); holder.setStyleSheet("background: transparent;")
        return lab, val, holder

    # ---- action bar ------------------------------------------------------

    def _build_action_bar(self) -> QWidget:
        bar = QFrame(); bar.setProperty("role", "actionbar")
        apply_shadow(bar, blur=18, y=3, alpha=30)
        row = QHBoxLayout(bar)
        row.setContentsMargins(Spacing.LG, Spacing.SM, Spacing.LG, Spacing.SM)
        row.setSpacing(Spacing.SM)
        self._btn_new = secondary_button(self._t.gettext("s4.act_new"))
        self._btn_new.setIcon(standard_icon("new")); self._btn_new.clicked.connect(self.reset_form)
        self._btn_post = primary_button(self._t.gettext("s4.act_post"))
        self._btn_post.setIcon(standard_icon("save"))
        self._btn_post.clicked.connect(lambda: self._post(print_after=False))
        self._btn_post_print = secondary_button(self._t.gettext("s4.act_post_print"))
        self._btn_post_print.setIcon(standard_icon("print"))
        self._btn_post_print.clicked.connect(lambda: self._post(print_after=True))
        self._error = QLabel(""); self._error.setProperty("role", "error"); self._error.setVisible(False)
        for b in (self._btn_new, self._btn_post, self._btn_post_print):
            row.addWidget(b)
        row.addSpacing(Spacing.MD); row.addWidget(self._error); row.addStretch(1)
        self._btn_close = secondary_button(self._t.gettext("s4.act_close"))
        self._btn_close.setIcon(standard_icon("close"))
        if self._on_close is not None:
            self._btn_close.clicked.connect(lambda: self._on_close())
        row.addWidget(self._btn_close)
        return bar

    # ---- sources ---------------------------------------------------------

    def reload(self) -> None:
        self._reload_sources()

    def _reload_sources(self) -> None:
        cur_fund = self._fund_combo.currentData()
        self._fund_combo.clear()
        for f in self._ctx.funds_repo.list_funds():
            self._fund_combo.addItem(f["name"], f["id"])
        if cur_fund is not None:
            i = self._fund_combo.findData(cur_fund)
            if i >= 0:
                self._fund_combo.setCurrentIndex(i)
        cur_cur = self._currency_combo.currentData()
        self._currency_combo.clear()
        base = self._ctx.currencies_repo.base_currency()
        for c in self._ctx.currencies_repo.list_active():
            self._currency_combo.addItem(c["code"], c["code"])
        target = cur_cur or (base["code"] if base else None)
        if target is not None:
            i = self._currency_combo.findData(target)
            if i >= 0:
                self._currency_combo.setCurrentIndex(i)
        if self._mode == "expense":
            cur_cat = self._category_combo.currentData()
            self._category_combo.clear()
            for cat in self._ctx.expense_categories_repo.list_active():
                self._category_combo.addItem(cat["name"], cat["id"])
            if cur_cat is not None:
                i = self._category_combo.findData(cur_cat)
                if i >= 0:
                    self._category_combo.setCurrentIndex(i)

    # ---- party -----------------------------------------------------------

    def _on_party_text_edited(self, _text: str) -> None:
        self._party_id = None; self._prev_balance = D(0); self._recompute()

    def _on_party_selected(self, row: SearchRow) -> None:
        p = row.payload
        self._party_id = p["party_id"]
        self._set_chip(self._chip_phone, p.get("phone") or "—", "neutral")
        if self._mode == "receipt":
            bal = self._ctx.receipts.receivable(self._party_id)
        else:
            bal = self._ctx.payments.payable(self._party_id)
        self._prev_balance = D(bal)
        positive = self._prev_balance > 0
        self._set_chip(self._chip_balance, format_money(bal),
                       "danger" if (self._mode == "receipt" and positive)
                       else "warning" if positive else "success")
        self._recompute()

    # ---- totals ----------------------------------------------------------

    def _amount(self) -> D:
        try:
            return money(self._amount_edit.text() or "0")
        except Exception:
            return D(0)

    def _recompute(self, *_a) -> None:
        if self._mode == "expense":
            self._fund_note_value.setText(self._fund_combo.currentText() or "—")
            return
        amt = self._amount()
        self._prev_value.setText(format_money(self._prev_balance))
        remaining = money(self._prev_balance - amt)
        self._rem_value.setText(format_money(remaining))
        self._rem_value.setProperty("money", "negative" if remaining > 0 else "positive")
        self._rem_value.style().unpolish(self._rem_value); self._rem_value.style().polish(self._rem_value)

    # ---- posting ---------------------------------------------------------

    def _post(self, *, print_after: bool) -> None:
        self.clear_error()
        currency_code = self._currency_combo.currentData()
        fund_id = self._fund_combo.currentData()
        method = self._method_combo.currentData()
        date = (self._date_edit.text() or "").strip() or None
        rate = self._rate_edit.text() or "1"
        amount = self._amount_edit.text() or "0"
        ref = (self._reference_edit.text() or "").strip() or None
        notes = (self._notes_edit.text() or "").strip() or None
        try:
            if self._mode == "receipt":
                posted = self._ctx.receipts.post_receipt(
                    party_id=self._party_id, account_id=fund_id, amount=amount,
                    currency_code=currency_code, exchange_rate=rate, payment_method=method,
                    reference=ref, notes=notes, receipt_date=date)
            elif self._mode == "payment":
                posted = self._ctx.payments.post_payment(
                    party_id=self._party_id, account_id=fund_id, amount=amount,
                    currency_code=currency_code, exchange_rate=rate, payment_method=method,
                    reference=ref, notes=notes, payment_date=date)
            else:
                payee = (self._payee_edit.text() or "").strip() or None
                posted = self._ctx.expenses.post_expense(
                    category_id=self._category_combo.currentData(), account_id=fund_id,
                    amount=amount, currency_code=currency_code, exchange_rate=rate,
                    payment_method=method, payee=payee, reference=ref, notes=notes,
                    expense_date=date)
        except ZenithError as exc:
            self._show_error(getattr(exc, "user_message", None) or str(exc))
            return
        self._last_saved_id = posted.id
        self._status_msg.setText(
            self._t.gettext("s4.msg_posted").replace("{no}", posted.document_no))
        self.reset_form()
        if print_after and self._on_print is not None:
            self._on_print(posted.id)

    def reset_form(self) -> None:
        self._party_id = None; self._prev_balance = D(0)
        if self._mode in ("receipt", "payment"):
            self._party_selector.clear()
            self._set_chip(self._chip_phone, "—", "neutral")
            self._set_chip(self._chip_balance, "—", "neutral")
        else:
            self._payee_edit.clear()
        self._amount_edit.setText("0.00"); self._reference_edit.clear(); self._notes_edit.clear()
        self._rate_edit.setText("1"); self._date_edit.setText(self._today())
        self._recompute()

    # ---- errors / drivers ------------------------------------------------

    def _show_error(self, message: str) -> None:
        self._error.setText(message); self._error.setVisible(True)

    def clear_error(self) -> None:
        self._error.setVisible(False)

    def set_party(self, row: SearchRow) -> None:
        self._party_selector.set_text(row.values[1] if len(row.values) > 1 else row.values[0])
        self._on_party_selected(row)

    def set_amount(self, value: str) -> None:
        self._amount_edit.setText(value); self._recompute()

    @property
    def last_saved_id(self) -> int | None:
        return self._last_saved_id

    # ---- i18n ------------------------------------------------------------

    def retranslate(self, translator) -> None:
        self._t = translator
        self._title.setText(translator.gettext(self._title_key()))
        self._details_title.setText(translator.gettext("s5.details"))
        for key, lf in self._meta_fields:
            lf.set_label(translator.gettext(key))
        self._ref_field.set_label(translator.gettext("s5.reference"))
        self._notes_field.set_label(translator.gettext("s4.notes"))
        self._doc_no.setText(translator.gettext("s4.auto"))
        for i, m in enumerate(PAYMENT_METHODS):
            self._method_combo.setItemText(i, translator.gettext(_METHOD_KEYS[m]))
        amt_key = {"receipt": "s5.amount_received", "payment": "s5.amount_paid",
                   "expense": "s5.amount"}[self._mode]
        self._amount_label.setText(translator.gettext(amt_key))
        if self._mode in ("receipt", "payment"):
            self._party_eyebrow.setText(
                translator.gettext("s4.customer" if self._mode == "receipt" else "s4.supplier"))
            self._party_selector.line_edit.setPlaceholderText(translator.gettext(
                "s4.customer_search_ph" if self._mode == "receipt" else "s4.supplier_search_ph"))
            self._prev_label.setText(translator.gettext(
                "si.prev_balance" if self._mode == "receipt" else "s5.prev_payable"))
            self._rem_label.setText(translator.gettext(
                "s5.remaining" if self._mode == "receipt" else "s5.remaining_payable"))
            for wrap in (self._chip_phone, self._chip_balance):
                wrap._label.setText(translator.gettext(wrap._label_key))  # type: ignore[attr-defined]
        else:
            self._party_eyebrow.setText(translator.gettext("s5.expense_of"))
            self._cat_field.set_label(translator.gettext("s5.category"))
            self._payee_field.set_label(translator.gettext("s5.payee"))
            self._fund_note_label.setText(translator.gettext("s5.fund"))
        for btn, key in ((self._btn_new, "s4.act_new"), (self._btn_post, "s4.act_post"),
                         (self._btn_post_print, "s4.act_post_print"),
                         (self._btn_close, "s4.act_close")):
            btn.setText(escape_amp(translator.gettext(key)))
