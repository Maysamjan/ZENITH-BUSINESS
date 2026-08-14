"""Stage 04 keyboard-first document entry — Sales & Purchase invoices.

ONE reusable, real, service-backed workspace (``mode`` = ``"sale"`` | ``"purchase"``)
optimised for fast daily use. The primary flow is entirely keyboard-driven:

    Party  →  Item search  →  Quantity  →  Unit Price  →  Discount  →  commit line
                                                                       ↳ next item

Everything shown is real: items/parties come from the Stage 03 repositories via
the LOCKED ``SearchSelector`` autocomplete; posting calls the atomic Stage 04
services (inventory + ledger + party balance + numbering + audit) in one
transaction. Money and quantities are Decimal throughout (never float): the
on-screen totals are computed with :func:`compute_line`, the same primitive the
service posts with, so screen and stored truth agree exactly.
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from zenith_business.core.i18n import Translator
from zenith_business.core.exceptions import ZenithError
from zenith_business.core.money import D, format_money, money
from zenith_business.services.document_math import compute_line
from zenith_business.services.purchase_documents import PurchaseLine
from zenith_business.services.sales_documents import SaleLine
from zenith_business.ui.components import (
    Card,
    apply_shadow,
    chip,
    escape_amp,
    eyebrow,
    field_label,
    horizontal_divider,
    muted,
    primary_button,
    secondary_button,
)
from zenith_business.ui.design.tokens import ControlSize, FieldWidth, Spacing
from zenith_business.ui.widgets.search_selector import SearchRow, SearchSelector

# committed-line grid columns
C_NO, C_CODE, C_NAME, C_UNIT, C_QTY, C_PRICE, C_DISC, C_TOTAL, C_WH = range(9)


class DocumentEntryPage(QWidget):
    """Real keyboard-first Sales / Purchase invoice entry."""

    def __init__(
        self,
        context,
        translator: Translator,
        *,
        mode: str = "sale",
        on_print: Callable[[int], None] | None = None,
        on_close: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._ctx = context
        self._t = translator
        self._mode = mode  # 'sale' | 'purchase'
        self._on_print = on_print
        self._on_close = on_close
        self._lines: list[dict] = []
        self._party_id: int | None = None
        self._last_saved_id: int | None = None

        self.setProperty("role", "workspace")
        root = QVBoxLayout(self)
        root.setContentsMargins(Spacing.MD, Spacing.SM, Spacing.MD, Spacing.SM)
        root.setSpacing(Spacing.SM)

        root.addLayout(self._build_titlebar())
        root.addWidget(self._build_header())
        root.addWidget(self._build_entry_strip())
        root.addWidget(self._build_grid_card(), stretch=1)
        root.addLayout(self._build_bottom_band())
        root.addWidget(self._build_action_bar())

        self._reload_meta_sources()
        self._recompute_totals()

    # ---- title -----------------------------------------------------------

    def _title_key(self) -> str:
        return "s4.sale_title" if self._mode == "sale" else "s4.purchase_title"

    def _build_titlebar(self) -> QHBoxLayout:
        row = QHBoxLayout(); row.setSpacing(Spacing.MD)
        self._title = QLabel(self._t.gettext(self._title_key()))
        self._title.setProperty("role", "page-title")
        row.addWidget(self._title)
        row.addStretch(1)
        self._status_msg = muted("")
        row.addWidget(self._status_msg)
        self._kbd_hint = muted(self._t.gettext("s4.keyboard_hint"))
        row.addWidget(self._kbd_hint)
        return row

    # ---- header (party + meta) ------------------------------------------

    def _build_header(self) -> QWidget:
        card = Card(role="section"); card.setProperty("accent", "navy"); apply_shadow(card)
        card.body.setSpacing(Spacing.SM)
        t = self._t

        party_key = "s4.customer" if self._mode == "sale" else "s4.supplier"
        ph_key = "s4.customer_search_ph" if self._mode == "sale" else "s4.supplier_search_ph"
        provider = self._ctx.customer_search if self._mode == "sale" else self._ctx.supplier_search

        prow = QHBoxLayout(); prow.setSpacing(Spacing.LG)
        self._party_selector = SearchSelector(
            provider, placeholder=t.gettext(ph_key), display_index=1, panel_width=460)
        self._party_selector.rowSelected.connect(self._on_party_selected)
        self._party_selector.line_edit.textEdited.connect(self._on_party_text_edited)
        col = QVBoxLayout(); col.setContentsMargins(0, 0, 0, 0); col.setSpacing(Spacing.XXS)
        self._party_eyebrow = eyebrow(t.gettext(party_key))
        col.addWidget(self._party_eyebrow)
        col.addWidget(self._party_selector)
        wrap = QWidget(); wrap.setLayout(col); wrap.setStyleSheet("background: transparent;")
        wrap.setMinimumWidth(int(FieldWidth.LG))
        prow.addWidget(wrap, 2)

        self._chip_phone = self._info_chip("si.phone", "—", "neutral")
        bal_key = "si.prev_balance" if self._mode == "sale" else "s4.supplier_ref"
        self._chip_balance = self._info_chip(bal_key, "—", "neutral")
        prow.addWidget(self._chip_phone)
        prow.addWidget(self._chip_balance)
        prow.addStretch(1)
        card.body.addLayout(prow)

        card.body.addWidget(horizontal_divider())

        meta = QHBoxLayout(); meta.setSpacing(Spacing.LG)
        self._invoice_no = QLabel(t.gettext("s4.auto")); self._invoice_no.setProperty("role", "stat-value")
        self._date_edit = QLineEdit(self._ctx_today())
        self._wh_combo = QComboBox()
        self._currency_combo = QComboBox()
        self._rate_edit = QLineEdit("1")
        self._rate_edit.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._meta_labels: list[tuple[str, QLabel]] = []
        specs = [
            ("si.invoice_no", self._invoice_no, FieldWidth.SM),
            ("si.date", self._date_edit, FieldWidth.SM),
            ("si.warehouse", self._wh_combo, FieldWidth.MD),
            ("si.currency", self._currency_combo, FieldWidth.SM),
            ("si.rate", self._rate_edit, FieldWidth.SM),
        ]
        for key, ctrl, width in specs:
            ctrl.setMinimumWidth(int(width))
            cell = QVBoxLayout(); cell.setSpacing(Spacing.XXS)
            lab = field_label(t.gettext(key)); self._meta_labels.append((key, lab))
            cell.addWidget(lab); cell.addWidget(ctrl)
            holder = QWidget(); holder.setLayout(cell); holder.setStyleSheet("background: transparent;")
            meta.addWidget(holder)
        meta.addStretch(1)
        card.body.addLayout(meta)
        return card

    def _ctx_today(self) -> str:
        from zenith_business.core.clock import today_iso
        return today_iso()

    def _info_chip(self, label_key: str, value: str, accent: str) -> QWidget:
        wrap = QWidget(); wrap.setStyleSheet("background: transparent;")
        row = QHBoxLayout(wrap); row.setContentsMargins(0, 0, 0, 0); row.setSpacing(Spacing.XS)
        lab = field_label(self._t.gettext(label_key)); val = chip(value, accent)
        row.addWidget(lab); row.addWidget(val)
        wrap._label = lab; wrap._value = val; wrap._label_key = label_key  # type: ignore[attr-defined]
        return wrap

    def _set_chip(self, wrap: QWidget, value: str, accent: str) -> None:
        val = wrap._value  # type: ignore[attr-defined]
        val.setText(value); val.setProperty("chip", accent)
        val.style().unpolish(val); val.style().polish(val)

    # ---- entry strip -----------------------------------------------------

    def _build_entry_strip(self) -> QWidget:
        card = Card(role="section"); card.setProperty("accent", "teal")
        card.body.setContentsMargins(Spacing.MD, Spacing.SM, Spacing.MD, Spacing.SM)
        row = QHBoxLayout(); row.setSpacing(Spacing.SM)

        self._item_selector = SearchSelector(
            self._ctx.item_search, placeholder=self._t.gettext("s4.item_search_ph"),
            display_index=1, panel_width=520)
        self._item_selector.rowSelected.connect(self._on_item_selected)
        row.addWidget(self._item_selector, 3)

        self._qty_edit = self._num_edit("0")
        self._price_edit = self._num_edit("0.00")
        self._disc_edit = self._num_edit("0.00")
        for w in (self._qty_edit, self._price_edit, self._disc_edit):
            w.setMaximumWidth(110)
            row.addWidget(w, 1)

        self._add_btn = primary_button(self._t.gettext("s4.act_new"))
        self._add_btn.setText("＋")
        self._add_btn.clicked.connect(self._commit_line)
        row.addWidget(self._add_btn)

        # keyboard chain: item Enter handled in _on_item_selected → qty focus
        self._qty_edit.returnPressed.connect(self._price_edit.setFocus)
        self._price_edit.returnPressed.connect(self._disc_edit.setFocus)
        self._disc_edit.returnPressed.connect(self._commit_line)
        card.body.addLayout(row)
        return card

    def _num_edit(self, ph: str) -> QLineEdit:
        e = QLineEdit(); e.setPlaceholderText(ph)
        e.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return e

    # ---- grid ------------------------------------------------------------

    def _grid_headers(self) -> list[str]:
        return ["si.col_row", "si.col_item_code", "si.col_item_name", "si.col_unit",
                "si.col_qty", "si.col_price", "si.col_discount", "si.col_total",
                "si.col_warehouse"]

    def _build_grid_card(self) -> QWidget:
        card = Card(role="section"); card.setProperty("accent", "brand"); apply_shadow(card)
        bar = QHBoxLayout(); bar.setSpacing(Spacing.SM)
        self._lines_title = QLabel(self._t.gettext("si.lines"))
        self._lines_title.setProperty("role", "card-title")
        bar.addWidget(self._lines_title); bar.addStretch(1)
        self._btn_delete = secondary_button(self._t.gettext("s4.delete_line"))
        self._btn_delete.setProperty("variant", "danger")
        self._btn_delete.clicked.connect(self._delete_selected)
        bar.addWidget(self._btn_delete)
        card.body.addLayout(bar)

        self._table = QTableWidget(0, 9)
        self._table.setHorizontalHeaderLabels([self._t.gettext(k) for k in self._grid_headers()])
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setDefaultSectionSize(ControlSize.TABLE_ROW_HEIGHT + 2)
        from PyQt6.QtWidgets import QHeaderView
        header = self._table.horizontalHeader()
        header.setHighlightSections(False)
        header.setSectionResizeMode(C_NAME, QHeaderView.ResizeMode.Stretch)
        widths = {C_NO: 40, C_CODE: 100, C_UNIT: 60, C_QTY: 80, C_PRICE: 110,
                  C_DISC: 90, C_TOTAL: 120, C_WH: 110}
        for col, w in widths.items():
            self._table.setColumnWidth(col, w)
        card.body.addWidget(self._table)
        return card

    # ---- bottom band (totals + payment) ---------------------------------

    def _build_bottom_band(self) -> QHBoxLayout:
        band = QHBoxLayout(); band.setSpacing(Spacing.SECTION_GAP)
        band.addStretch(1)
        band.addWidget(self._build_payment(), stretch=2)
        return band

    def _build_payment(self) -> QWidget:
        card = Card(role="section"); card.setProperty("accent", "brand"); apply_shadow(card)
        t = self._t

        gt = QFrame(); gt.setProperty("role", "grand-total-strong")
        gtl = QHBoxLayout(gt); gtl.setContentsMargins(Spacing.LG, Spacing.SM, Spacing.LG, Spacing.SM)
        self._grand_label = QLabel(t.gettext("si.grand_total"))
        self._grand_label.setProperty("role", "gts-label")
        self._grand_value = QLabel("—"); self._grand_value.setProperty("role", "gts-value")
        self._grand_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        gtl.addWidget(self._grand_label); gtl.addStretch(1); gtl.addWidget(self._grand_value)
        card.body.addWidget(gt)

        pay = QGridLayout(); pay.setHorizontalSpacing(Spacing.LG); pay.setVerticalSpacing(Spacing.XS)
        self._sub_label = QLabel(t.gettext("si.subtotal")); self._sub_label.setProperty("role", "total-label")
        self._sub_value = QLabel("—"); self._sub_value.setProperty("role", "total-value")
        self._sub_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._disc_label = QLabel(t.gettext("si.discount")); self._disc_label.setProperty("role", "total-label")
        self._disc_value = QLabel("—"); self._disc_value.setProperty("role", "total-value")
        self._disc_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._recv_label = QLabel(t.gettext("s4.amount_paid")); self._recv_label.setProperty("role", "total-label")
        self._recv_edit = self._num_edit("0.00")
        self._recv_edit.setMaximumWidth(140)
        self._recv_edit.textEdited.connect(self._recompute_totals)
        self._rem_label = QLabel(t.gettext("si.remaining")); self._rem_label.setProperty("role", "total-label")
        self._rem_value = QLabel("—"); self._rem_value.setProperty("role", "total-value")
        self._rem_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        pay.addWidget(self._sub_label, 0, 0); pay.addWidget(self._sub_value, 0, 1)
        pay.addWidget(self._disc_label, 1, 0); pay.addWidget(self._disc_value, 1, 1)
        pay.addWidget(self._recv_label, 2, 0); pay.addWidget(self._recv_edit, 2, 1)
        pay.addWidget(self._rem_label, 3, 0); pay.addWidget(self._rem_value, 3, 1)
        pay.setColumnStretch(1, 1)
        card.body.addLayout(pay)
        return card

    # ---- action bar ------------------------------------------------------

    def _build_action_bar(self) -> QWidget:
        bar = QFrame(); bar.setProperty("role", "actionbar")
        apply_shadow(bar, blur=18, y=3, alpha=30)
        row = QHBoxLayout(bar)
        row.setContentsMargins(Spacing.MD, Spacing.SM, Spacing.MD, Spacing.SM)
        row.setSpacing(Spacing.SM)
        self._btn_new = secondary_button(self._t.gettext("s4.act_new"))
        self._btn_new.clicked.connect(self.reset_form)
        self._btn_post = primary_button(self._t.gettext("s4.act_post"))
        self._btn_post.clicked.connect(lambda: self._post(print_after=False))
        self._btn_post_print = secondary_button(self._t.gettext("s4.act_post_print"))
        self._btn_post_print.clicked.connect(lambda: self._post(print_after=True))
        self._error = QLabel(""); self._error.setProperty("role", "error")
        self._error.setVisible(False)
        for b in (self._btn_new, self._btn_post, self._btn_post_print):
            row.addWidget(b)
        row.addWidget(self._error)
        row.addStretch(1)
        self._btn_close = secondary_button(self._t.gettext("s4.act_close"))
        if self._on_close is not None:
            self._btn_close.clicked.connect(lambda: self._on_close())
        row.addWidget(self._btn_close)
        return bar

    # ---- data sources ----------------------------------------------------

    def reload(self) -> None:
        """Refresh meta sources when the page is (re)shown."""
        self._reload_meta_sources()

    def _reload_meta_sources(self) -> None:
        cur_wh = self._wh_combo.currentData()
        self._wh_combo.clear()
        for wh in self._ctx.warehouses_repo.list_active():
            self._wh_combo.addItem(wh["name"], wh["id"])
        if cur_wh is not None:
            idx = self._wh_combo.findData(cur_wh)
            if idx >= 0:
                self._wh_combo.setCurrentIndex(idx)
        cur_cur = self._currency_combo.currentData()
        self._currency_combo.clear()
        base = self._ctx.currencies_repo.base_currency()
        for cur in self._ctx.currencies_repo.list_active():
            self._currency_combo.addItem(cur["code"], cur["code"])
        target = cur_cur or (base["code"] if base else None)
        if target is not None:
            idx = self._currency_combo.findData(target)
            if idx >= 0:
                self._currency_combo.setCurrentIndex(idx)

    # ---- party -----------------------------------------------------------

    def _on_party_text_edited(self, _text: str) -> None:
        # typing a fresh name clears a previously chosen party (walk-in / cash)
        self._party_id = None

    def _on_party_selected(self, row: SearchRow) -> None:
        p = row.payload
        self._party_id = p["party_id"]
        self._set_chip(self._chip_phone, p.get("phone") or "—", "neutral")
        if self._mode == "sale":
            bal = self._ctx.sales_documents.receivable(self._party_id)
            positive = D(bal) > 0
            self._set_chip(self._chip_balance, format_money(bal),
                           "danger" if positive else "success")
        else:
            pay = self._ctx.purchase_documents.payable(self._party_id)
            positive = D(pay) > 0
            self._set_chip(self._chip_balance, format_money(pay),
                           "warning" if positive else "success")

    # ---- item / line entry ----------------------------------------------

    def _on_item_selected(self, row: SearchRow) -> None:
        p = row.payload
        self._pending_item = p
        if self._mode == "sale" and p.get("sale_price") is not None:
            self._price_edit.setText(format_money(p["sale_price"]).replace(",", ""))
        if not self._qty_edit.text():
            self._qty_edit.setText("1")
        self._qty_edit.setFocus(); self._qty_edit.selectAll()

    def _commit_line(self) -> None:
        self.clear_error()
        payload = getattr(self, "_pending_item", None)
        if payload is None:
            self._item_selector.focus()
            return
        try:
            c = compute_line(self._qty_edit.text() or "0", self._price_edit.text() or "0",
                             self._disc_edit.text() or "0")
        except ZenithError as exc:
            self._show_error(getattr(exc, "user_message", None) or str(exc))
            return
        wh_id = self._wh_combo.currentData()
        wh_name = self._wh_combo.currentText()
        self._lines.append({
            "item_id": payload["item_id"], "unit_id": payload.get("base_unit_id"),
            "code": payload.get("item_code", ""), "name": payload.get("name", ""),
            "unit": payload.get("unit_symbol") or "",
            "qty": str(c.quantity), "price": str(c.unit_price), "discount": str(c.discount),
            "total": str(c.line_total), "wh_id": wh_id, "wh_name": wh_name,
        })
        self._render_lines()
        self._recompute_totals()
        # reset the entry strip for the next line
        self._pending_item = None
        self._item_selector.clear()
        self._qty_edit.clear(); self._price_edit.clear(); self._disc_edit.clear()
        self._item_selector.focus()

    def _render_lines(self) -> None:
        self._table.setRowCount(len(self._lines))
        numeric = {C_QTY, C_PRICE, C_DISC, C_TOTAL}
        for r, ln in enumerate(self._lines):
            cells = [str(r + 1), ln["code"], ln["name"], ln["unit"],
                     format_money(ln["qty"]), format_money(ln["price"]),
                     format_money(ln["discount"]), format_money(ln["total"]),
                     ln["wh_name"] or ""]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                align = (Qt.AlignmentFlag.AlignRight if col in numeric
                         else Qt.AlignmentFlag.AlignLeft)
                item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
                self._table.setItem(r, col, item)

    def _delete_selected(self) -> None:
        r = self._table.currentRow()
        if 0 <= r < len(self._lines):
            self._lines.pop(r)
            self._render_lines()
            self._recompute_totals()

    # ---- totals ----------------------------------------------------------

    def _recompute_totals(self, *_a) -> None:
        subtotal = sum((D(ln["qty"]) * D(ln["price"]) for ln in self._lines), D(0))
        discount = sum((D(ln["discount"]) for ln in self._lines), D(0))
        grand = money(subtotal - discount)
        self._sub_value.setText(format_money(subtotal))
        self._disc_value.setText(format_money(discount))
        self._grand_value.setText(format_money(grand))
        try:
            paid = money(self._recv_edit.text() or "0")
        except Exception:
            paid = D(0)
        remaining = money(grand - paid)
        self._rem_value.setText(format_money(remaining))
        self._rem_value.setProperty("accent", "danger" if remaining > 0 else "success")
        self._rem_value.style().unpolish(self._rem_value)
        self._rem_value.style().polish(self._rem_value)

    # ---- posting ---------------------------------------------------------

    def _post(self, *, print_after: bool) -> None:
        self.clear_error()
        if not self._lines:
            self._show_error(self._t.gettext("s4.msg_add_line"))
            return
        currency_code = self._currency_combo.currentData()
        if not currency_code:
            self._show_error(self._t.gettext("s4.msg_no_currency"))
            return
        wh_id = self._wh_combo.currentData()
        date = (self._date_edit.text() or "").strip() or None
        rate = self._rate_edit.text() or "1"
        paid = self._recv_edit.text() or "0"
        try:
            if self._mode == "sale":
                lines = [SaleLine(item_id=ln["item_id"], unit_id=ln["unit_id"],
                                  quantity=ln["qty"], unit_price=ln["price"],
                                  discount=ln["discount"]) for ln in self._lines]
                posted = self._ctx.sales_documents.post_sale(
                    currency_code=currency_code, lines=lines, party_id=self._party_id,
                    warehouse_id=wh_id, amount_paid=paid, exchange_rate=rate, sale_date=date)
            else:
                lines = [PurchaseLine(item_id=ln["item_id"], unit_id=ln["unit_id"],
                                      quantity=ln["qty"], unit_price=ln["price"],
                                      discount=ln["discount"]) for ln in self._lines]
                posted = self._ctx.purchase_documents.post_purchase(
                    currency_code=currency_code, lines=lines, party_id=self._party_id,
                    warehouse_id=wh_id, amount_paid=paid, exchange_rate=rate, purchase_date=date)
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
        self._lines = []
        self._party_id = None
        self._pending_item = None
        self._render_lines()
        self._party_selector.clear()
        self._item_selector.clear()
        self._set_chip(self._chip_phone, "—", "neutral")
        self._set_chip(self._chip_balance, "—", "neutral")
        self._qty_edit.clear(); self._price_edit.clear(); self._disc_edit.clear()
        self._recv_edit.clear()
        self._date_edit.setText(self._ctx_today())
        self._recompute_totals()

    # ---- errors ----------------------------------------------------------

    def _show_error(self, message: str) -> None:
        self._error.setText(message); self._error.setVisible(True)

    def clear_error(self) -> None:
        self._error.setVisible(False)

    # ---- test / screenshot drivers --------------------------------------

    def add_line(self, payload: dict, qty: str, price: str, discount: str = "0") -> None:
        """Programmatically add a committed line (tests / demos)."""
        self._pending_item = payload
        self._qty_edit.setText(qty); self._price_edit.setText(price)
        self._disc_edit.setText(discount)
        self._commit_line()

    def set_party(self, row: SearchRow) -> None:
        self._party_selector.set_text(row.values[1] if len(row.values) > 1 else row.values[0])
        self._on_party_selected(row)

    def set_amount_paid(self, value: str) -> None:
        self._recv_edit.setText(value); self._recompute_totals()

    @property
    def line_count(self) -> int:
        return len(self._lines)

    @property
    def last_saved_id(self) -> int | None:
        return self._last_saved_id

    # ---- i18n ------------------------------------------------------------

    def retranslate(self, translator: Translator) -> None:
        self._t = translator
        self._title.setText(translator.gettext(self._title_key()))
        self._kbd_hint.setText(translator.gettext("s4.keyboard_hint"))
        self._party_eyebrow.setText(
            translator.gettext("s4.customer" if self._mode == "sale" else "s4.supplier"))
        self._party_selector.line_edit.setPlaceholderText(translator.gettext(
            "s4.customer_search_ph" if self._mode == "sale" else "s4.supplier_search_ph"))
        self._item_selector.line_edit.setPlaceholderText(translator.gettext("s4.item_search_ph"))
        self._table.setHorizontalHeaderLabels([translator.gettext(k) for k in self._grid_headers()])
        self._lines_title.setText(translator.gettext("si.lines"))
        self._btn_delete.setText(escape_amp(translator.gettext("s4.delete_line")))
        self._grand_label.setText(translator.gettext("si.grand_total"))
        self._sub_label.setText(translator.gettext("si.subtotal"))
        self._disc_label.setText(translator.gettext("si.discount"))
        self._recv_label.setText(translator.gettext("s4.amount_paid"))
        self._rem_label.setText(translator.gettext("si.remaining"))
        self._btn_new.setText(escape_amp(translator.gettext("s4.act_new")))
        self._btn_post.setText(escape_amp(translator.gettext("s4.act_post")))
        self._btn_post_print.setText(escape_amp(translator.gettext("s4.act_post_print")))
        self._btn_close.setText(escape_amp(translator.gettext("s4.act_close")))
        for key, lab in self._meta_labels:
            lab.setText(translator.gettext(key))
        for wrap in (self._chip_phone, self._chip_balance):
            wrap._label.setText(translator.gettext(wrap._label_key))  # type: ignore[attr-defined]
        self._invoice_no.setText(translator.gettext("s4.auto"))
        self._render_lines()
