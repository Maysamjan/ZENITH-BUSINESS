"""Customer / Supplier account-ledger screen (owner-fix defect #4).

Pick a registered person and see their complete financial history — every sale/
receipt (or purchase/payment), the running balance, and a top summary — all read
from the authoritative ledger via :class:`PartyLedgerService`. Same LOCKED design
system, top navigation, Vazirmatn, EN/Dari RTL and table idiom as the other
screens; nothing here writes or duplicates a balance.
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from zenith_business.core.i18n import Translator
from zenith_business.core.money import D, format_money
from zenith_business.ui.components import (
    Card,
    apply_shadow,
    escape_amp,
    eyebrow,
    field_label,
    page_title,
    secondary_button,
    standard_icon,
)
from zenith_business.ui.design.tokens import ControlSize, FieldWidth, Spacing
from zenith_business.ui.widgets.search_selector import SearchRow, SearchSelector

# source_type -> localized transaction-type label
_TYPE_KEYS = {
    "SALE": "led.t_sale", "SALE_VOID": "led.t_void", "SALES_RETURN": "led.t_sales_return",
    "PURCHASE": "led.t_purchase", "PURCHASE_RETURN": "led.t_purchase_return",
    "RECEIPT": "led.t_receipt", "PAYMENT": "led.t_payment",
}


class PartyLedgerPage(QWidget):
    def __init__(self, context, translator: Translator, *, mode: str,
                 on_close: Callable[[], None] | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctx = context
        self._t = translator
        self._mode = mode  # 'customer' | 'supplier'
        self._on_close = on_close
        self._party_id: int | None = None

        self.setProperty("role", "workspace")
        root = QVBoxLayout(self)
        root.setContentsMargins(Spacing.PAGE_MARGIN, Spacing.SM,
                                Spacing.PAGE_MARGIN, Spacing.SM)
        root.setSpacing(Spacing.SM)
        root.addLayout(self._build_titlebar())
        root.addWidget(self._build_picker())
        root.addWidget(self._build_summary())
        root.addWidget(self._build_table(), stretch=1)
        root.addWidget(self._build_action_bar())

    # ---- title -----------------------------------------------------------

    def _title_key(self) -> str:
        return "led.customer_title" if self._mode == "customer" else "led.supplier_title"

    def _build_titlebar(self) -> QHBoxLayout:
        row = QHBoxLayout(); row.setSpacing(Spacing.MD)
        self._title = page_title(self._t.gettext(self._title_key()))
        row.addWidget(self._title); row.addStretch(1)
        return row

    def _build_picker(self) -> QWidget:
        card = Card(role="section"); card.setProperty("accent", "navy"); apply_shadow(card)
        card.body.setContentsMargins(Spacing.CARD_PAD_H, Spacing.SM, Spacing.CARD_PAD_H, Spacing.SM)
        col = QVBoxLayout(); col.setSpacing(Spacing.XXS)
        key = "s4.customer" if self._mode == "customer" else "s4.supplier"
        self._picker_eyebrow = eyebrow(self._t.gettext(key))
        provider = (self._ctx.customer_search if self._mode == "customer"
                    else self._ctx.supplier_search)
        ph = "s4.customer_search_ph" if self._mode == "customer" else "s4.supplier_search_ph"
        self._selector = SearchSelector(provider, placeholder=self._t.gettext(ph),
                                        display_index=1, panel_width=460)
        self._selector.rowSelected.connect(self._on_party_selected)
        self._selector.setMinimumWidth(int(FieldWidth.LG))
        col.addWidget(self._picker_eyebrow); col.addWidget(self._selector)
        wrap = QWidget(); wrap.setLayout(col); wrap.setStyleSheet("background: transparent;")
        card.body.addWidget(wrap)
        return card

    # ---- summary ---------------------------------------------------------

    def _metric(self, key: str, accent: str) -> tuple[QLabel, QLabel, QWidget]:
        box = QFrame(); box.setProperty("role", "section"); box.setProperty("accent", accent)
        v = QVBoxLayout(box); v.setContentsMargins(Spacing.MD, Spacing.SM, Spacing.MD, Spacing.SM)
        v.setSpacing(Spacing.XXS)
        lab = eyebrow(self._t.gettext(key))
        val = QLabel("—"); val.setProperty("role", "total-value")
        v.addWidget(lab); v.addWidget(val)
        return lab, val, box

    def _build_summary(self) -> QWidget:
        wrap = QWidget(); wrap.setStyleSheet("background: transparent;")
        row = QHBoxLayout(wrap); row.setContentsMargins(0, 0, 0, 0); row.setSpacing(Spacing.MD)
        if self._mode == "customer":
            k1, k2, k3 = "led.total_sales", "led.total_received", "led.receivable"
        else:
            k1, k2, k3 = "led.total_purchases", "led.total_paid", "led.payable"
        self._m1_lab, self._m1, b1 = self._metric(k1, "brand")
        self._m2_lab, self._m2, b2 = self._metric(k2, "teal")
        self._m3_lab, self._m3, b3 = self._metric(k3, "navy")
        for b in (b1, b2, b3):
            row.addWidget(b, 1)
        return wrap

    # ---- table -----------------------------------------------------------

    def _columns(self) -> list[tuple[str, str, str]]:
        return [("led.col_date", "date", "l"), ("led.col_docno", "doc_no", "l"),
                ("led.col_type", "type", "l"), ("led.col_desc", "description", "l"),
                ("led.col_debit", "debit", "r"), ("led.col_credit", "credit", "r"),
                ("led.col_running", "running", "r")]

    def _build_table(self) -> QWidget:
        cols = self._columns()
        self._table = QTableWidget(0, len(cols))
        self._table.setHorizontalHeaderLabels([self._t.gettext(h) for h, _k, _a in cols])
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.setMinimumHeight(160)
        hh = self._table.horizontalHeader(); hh.setHighlightSections(False)
        desc_idx = 3
        for i in range(len(cols)):
            if i == desc_idx:
                hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                hh.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        self._table.verticalHeader().setDefaultSectionSize(ControlSize.TABLE_ROW_HEIGHT + 4)
        return self._table

    def _build_action_bar(self) -> QWidget:
        bar = QFrame(); bar.setProperty("role", "actionbar"); apply_shadow(bar, blur=18, y=3, alpha=30)
        row = QHBoxLayout(bar)
        row.setContentsMargins(Spacing.LG, Spacing.SM, Spacing.LG, Spacing.SM)
        self._empty = QLabel(self._t.gettext("led.pick_hint")); self._empty.setProperty("role", "secondary")
        row.addWidget(self._empty); row.addStretch(1)
        self._btn_close = secondary_button(self._t.gettext("s4.act_close"))
        self._btn_close.setIcon(standard_icon("close"))
        if self._on_close is not None:
            self._btn_close.clicked.connect(lambda: self._on_close())
        row.addWidget(self._btn_close)
        return bar

    # ---- data ------------------------------------------------------------

    def _on_party_selected(self, row: SearchRow) -> None:
        self._party_id = row.payload.get("party_id")
        self.reload()

    def show_party(self, party_id: int) -> None:
        """Open this ledger directly for a given party (contextual access, round 2)."""
        party = self._ctx.parties_repo.get(party_id)
        if party is None:
            return
        self._party_id = party_id
        self._selector.set_text(party.get("name") or "")
        self.reload()

    def reload(self) -> None:
        if self._party_id is None:
            return
        if self._mode == "customer":
            data = self._ctx.party_ledger.customer_ledger(self._party_id)
            totals = data["totals"]
            self._m1.setText(format_money(totals["total_sales"]))
            self._m2.setText(format_money(totals["total_received"]))
            self._m3.setText(format_money(totals["receivable"]))
        else:
            data = self._ctx.party_ledger.supplier_ledger(self._party_id)
            totals = data["totals"]
            self._m1.setText(format_money(totals["total_purchases"]))
            self._m2.setText(format_money(totals["total_paid"]))
            self._m3.setText(format_money(totals["payable"]))
        self._render(data["rows"])
        self._empty.setText("")

    def _render(self, rows: list[dict]) -> None:
        cols = self._columns()
        self._table.setRowCount(0)
        self._table.setRowCount(len(rows))
        money_keys = {"debit", "credit", "running"}
        for r, data in enumerate(rows):
            for c, (_h, key, align) in enumerate(cols):
                if key == "type":
                    text = self._t.gettext(_TYPE_KEYS.get(data.get("source_type", ""), ""))\
                        or data.get("source_type", "")
                else:
                    value = data.get(key)
                    text = (format_money(value) if key in money_keys
                            else ("" if value is None else str(value)))
                item = QTableWidgetItem(text)
                a = (Qt.AlignmentFlag.AlignRight if align == "r" else Qt.AlignmentFlag.AlignLeft)
                item.setTextAlignment(a | Qt.AlignmentFlag.AlignVCenter)
                self._table.setItem(r, c, item)

    # ---- i18n ------------------------------------------------------------

    def retranslate(self, translator: Translator) -> None:
        self._t = translator
        self._title.setText(translator.gettext(self._title_key()))
        key = "s4.customer" if self._mode == "customer" else "s4.supplier"
        self._picker_eyebrow.setText(translator.gettext(key))
        ph = "s4.customer_search_ph" if self._mode == "customer" else "s4.supplier_search_ph"
        self._selector.line_edit.setPlaceholderText(translator.gettext(ph))
        if self._mode == "customer":
            ks = ("led.total_sales", "led.total_received", "led.receivable")
        else:
            ks = ("led.total_purchases", "led.total_paid", "led.payable")
        for lab, k in zip((self._m1_lab, self._m2_lab, self._m3_lab), ks):
            lab.setText(translator.gettext(k))
        self._table.setHorizontalHeaderLabels(
            [translator.gettext(h) for h, _k, _a in self._columns()])
        self._btn_close.setText(escape_amp(translator.gettext("s4.act_close")))
        if self._party_id is not None:
            self.reload()
        else:
            self._empty.setText(translator.gettext("led.pick_hint"))
