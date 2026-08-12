"""Sales Invoice — RAPID-ENTRY WORKSPACE PROTOTYPE (Prompt 01D).

The reference screen for the whole application, redesigned around *speed of
invoice entry*: searchable item + customer selectors (type-ahead), a keyboard-
first line-entry flow, an unobtrusive quick-item-info strip, and an always-
visible totals/payment area. The line grid is the operational centre.

IMPORTANT: pure UI/interaction prototype. It does NOT save data, performs NO
accounting/inventory logic, and creates NO database tables. All figures come
from clearly-separated mock providers (``ui.mock.demo_search``). Real, repository
-backed providers arrive in their authorized stages with no change to this UI.

Keyboard model (Prompt 01D §3)
------------------------------
    Item field : type to search · ↑/↓ choose · Enter select → focus Quantity
    Quantity   : Enter → Unit Price
    Unit Price : Enter → Discount
    Discount   : Enter → commit line, open a fresh line, focus its item search
    Esc        : close an open suggestion popup
    Delete     : remove the selected committed line
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from zenith_business.core.i18n import Translator
from zenith_business.ui.components import (
    Card,
    LabeledField,
    StatTile,
    apply_field_width,
    apply_shadow,
    chip,
    escape_amp,
    eyebrow,
    field_label,
    horizontal_divider,
    muted,
    primary_button,
    secondary_button,
    standard_icon,
)
from zenith_business.ui.design.tokens import Color, ControlSize, FieldWidth, Spacing
from zenith_business.ui.mock.demo_invoice import build_demo_invoice
from zenith_business.ui.mock.demo_search import DemoCustomerProvider, DemoItemProvider
from zenith_business.ui.widgets.search_selector import SearchRow, SearchSelector

# Columns: # | Code | Item Name | Unit | Qty | Unit Price | Discount | Total | Warehouse
COL_NO, COL_CODE, COL_NAME, COL_UNIT, COL_QTY, COL_PRICE, COL_DISC, COL_TOTAL, COL_WH = range(9)

def _num(text: str) -> float:
    try:
        return float(str(text).replace(",", "").strip() or 0)
    except ValueError:
        return 0.0


def _money(value: float) -> str:
    return f"{value:,.2f}"


class SalesInvoiceDemoPage(QWidget):
    """Full-workspace, keyboard-first Sales Invoice — one screen at 1366×768.

    Non-scrolling: the line grid stretches to fill remaining height while the
    header, totals/payment and action bar stay compact and always visible
    (Prompt 01F §2).
    """

    def __init__(
        self,
        translator: Translator,
        *,
        on_print=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._t = translator
        self._items = DemoItemProvider()
        self._customers = DemoCustomerProvider()
        self._on_print = on_print
        self._demo = build_demo_invoice()
        self._received = self._demo.paid

        self.setProperty("role", "workspace")  # subtle tinted depth behind cards
        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.MD, Spacing.SM, Spacing.MD, Spacing.SM,
        )
        root.setSpacing(Spacing.SM)

        root.addLayout(self._build_titlebar())
        root.addWidget(self._build_header())
        root.addWidget(self._build_grid_card(), stretch=1)
        root.addLayout(self._build_bottom_band())
        root.addWidget(self._build_action_bar())

        self._reload_demo_lines()
        self._add_active_row()
        self._prefill_customer()
        self._recompute_totals()

    def _prefill_customer(self) -> None:
        """Show the shared demo customer so the screen matches the print."""
        d = self._demo
        self._customer_selector.set_text(d.customer_name)
        self._set_info_chip(self._chip_phone, d.customer_phone, "neutral")
        self._set_info_chip(self._chip_balance, _money(12500.0) + " AFN", "danger")
        self._set_info_chip(self._chip_credit, _money(50000.0) + " AFN", "info")

    # ---- small helpers ---------------------------------------------------

    def _combo(self, items: list[str]) -> QComboBox:
        box = QComboBox(); box.addItems(items); return box

    def _numeric_edit(self, value: str = "", ph: str = "") -> QLineEdit:
        edit = QLineEdit(value)
        if ph:
            edit.setPlaceholderText(ph)
        edit.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return edit

    def _card_title(self, key: str) -> QLabel:
        lbl = QLabel(self._t.gettext(key)); lbl.setProperty("role", "card-title")
        return lbl

    # ---- title bar -------------------------------------------------------

    def _build_titlebar(self) -> QHBoxLayout:
        row = QHBoxLayout(); row.setSpacing(Spacing.MD)
        self._title = QLabel(self._t.gettext("si.title"))
        self._title.setProperty("role", "page-title")
        row.addWidget(self._title)
        self._badge = chip(self._t.gettext("si.prototype_badge"), "warning")
        row.addWidget(self._badge)
        row.addStretch(1)
        self._kbd_hint = muted(self._t.gettext("si.keyboard_hint"))
        row.addWidget(self._kbd_hint)
        return row

    # ---- header (invoice meta + customer autocomplete) -------------------

    def _build_header(self) -> QWidget:
        card = Card(role="section"); card.setProperty("accent", "navy"); apply_shadow(card)
        card.body.setSpacing(Spacing.SM)
        t = self._t
        d = self._demo

        # PRIMARY — Customer: promoted to the top and visually prominent (§8).
        cust_row = QHBoxLayout(); cust_row.setSpacing(Spacing.LG)
        self._customer_selector = SearchSelector(
            self._customers, placeholder=t.gettext("si.customer_search_ph"),
            display_index=0, panel_width=460,
        )
        self._customer_selector.rowSelected.connect(self._on_customer_selected)
        cust_col = QVBoxLayout(); cust_col.setContentsMargins(0, 0, 0, 0); cust_col.setSpacing(Spacing.XXS)
        self._cust_eyebrow = eyebrow(t.gettext("si.customer"))
        cust_col.addWidget(self._cust_eyebrow)
        cust_col.addWidget(self._customer_selector)
        cust_wrap = QWidget(); cust_wrap.setLayout(cust_col)
        cust_wrap.setStyleSheet("background: transparent;")
        cust_wrap.setMinimumWidth(int(FieldWidth.LG))
        cust_row.addWidget(cust_wrap, 2)

        self._chip_phone = self._info_chip("si.phone", "—", "neutral")
        self._chip_balance = self._info_chip("si.prev_balance", "—", "neutral")
        self._chip_credit = self._info_chip("si.credit_limit", "—", "info")
        cust_row.addWidget(self._chip_phone)
        cust_row.addWidget(self._chip_balance)
        cust_row.addWidget(self._chip_credit)
        cust_row.addStretch(1)
        card.body.addLayout(cust_row)

        card.body.addWidget(horizontal_divider())

        # SECONDARY — compact metadata strip (quieter than the primary row).
        meta = QHBoxLayout(); meta.setSpacing(Spacing.LG)
        inv_no = QLineEdit(d.number)      # bound to the shared transaction (§11)
        date = QLineEdit(d.date)
        warehouse = self._combo(["Main", "Store-2", "Transit"])
        salesperson = self._combo([d.salesperson, "Sara", "—"])
        currency = self._combo([d.currency, "USD", "PKR", "EUR"])
        rate = QLineEdit("1.00")
        self._meta_fields: list[tuple[str, LabeledField]] = []
        specs = [
            ("si.invoice_no", inv_no, FieldWidth.SM, False),
            ("si.date", date, FieldWidth.SM, False),
            ("si.warehouse", warehouse, FieldWidth.MD, True),
            ("si.salesperson", salesperson, FieldWidth.MD, True),
            ("si.currency", currency, FieldWidth.SM, True),
            ("si.rate", rate, FieldWidth.SM, True),
        ]
        for key, ctrl, width, compact in specs:
            lf = LabeledField(t.gettext(key), ctrl, width=width, compact=compact)
            self._meta_fields.append((key, lf))
            meta.addWidget(lf)
        meta.addStretch(1)
        card.body.addLayout(meta)
        return card

    def _info_chip(self, label_key: str, value: str, accent: str) -> QWidget:
        wrap = QWidget(); wrap.setStyleSheet("background: transparent;")
        row = QHBoxLayout(wrap); row.setContentsMargins(0, 0, 0, 0); row.setSpacing(Spacing.XS)
        lab = field_label(self._t.gettext(label_key))
        val = chip(value, accent)
        row.addWidget(lab); row.addWidget(val)
        wrap._label = lab  # type: ignore[attr-defined]
        wrap._value = val  # type: ignore[attr-defined]
        wrap._label_key = label_key  # type: ignore[attr-defined]
        return wrap

    # ---- grid ------------------------------------------------------------

    def _grid_headers(self) -> list[str]:
        return ["si.col_row", "si.col_item_code", "si.col_item_name", "si.col_unit",
                "si.col_qty", "si.col_price", "si.col_discount", "si.col_total",
                "si.col_warehouse"]

    def _build_grid_card(self) -> QWidget:
        card = Card(role="section"); card.setProperty("accent", "brand"); apply_shadow(card)
        bar = QHBoxLayout(); bar.setSpacing(Spacing.SM)
        bar.addWidget(self._card_title("si.lines"))
        bar.addStretch(1)
        self._btn_delete = secondary_button(self._t.gettext("si.delete_line"))
        self._btn_delete.setProperty("variant", "danger")
        self._btn_delete.setIcon(standard_icon("delete"))
        self._btn_delete.clicked.connect(self._delete_selected_line)
        bar.addWidget(self._btn_delete)
        card.body.addLayout(bar)

        self._table = QTableWidget(0, 9)
        self._table.setHorizontalHeaderLabels([self._t.gettext(k) for k in self._grid_headers()])
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setDefaultSectionSize(ControlSize.TABLE_ROW_HEIGHT + 2)
        self._table.setMinimumHeight(150)

        header = self._table.horizontalHeader()
        header.setHighlightSections(False)
        header.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)
        widths = {COL_NO: 40, COL_CODE: 100, COL_UNIT: 60, COL_QTY: 74,
                  COL_PRICE: 104, COL_DISC: 84, COL_TOTAL: 116, COL_WH: 92}
        for col, w in widths.items():
            self._table.setColumnWidth(col, w)
        card.body.addWidget(self._table)
        return card

    def _reload_demo_lines(self) -> None:
        self._table.setRowCount(0)
        for line in self._demo.lines:
            self._append_committed_row(
                line.code, line.name, line.unit, line.qty, line.price, line.discount, "Main"
            )

    def _append_committed_row(self, code, name, unit, qty, price, disc, wh) -> None:
        r = self._table.rowCount()
        self._table.insertRow(r)
        total = qty * price - disc
        cells = [str(r + 1), code, name, unit, f"{qty:,.0f}", _money(price),
                 _money(disc), _money(total), wh]
        numeric = {COL_QTY, COL_PRICE, COL_DISC, COL_TOTAL}
        for col, text in enumerate(cells):
            item = QTableWidgetItem(text)
            align = Qt.AlignmentFlag.AlignRight if col in numeric else Qt.AlignmentFlag.AlignLeft
            item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(r, col, item)

    def _add_active_row(self) -> None:
        r = self._table.rowCount()
        self._table.insertRow(r)
        self._active_row = r
        self._table.setItem(r, COL_NO, self._ro_item(str(r + 1)))
        self._table.setItem(r, COL_CODE, self._ro_item(""))
        self._table.setItem(r, COL_UNIT, self._ro_item(""))
        self._table.setItem(r, COL_TOTAL, self._ro_item(""))
        self._table.setItem(r, COL_WH, self._ro_item("Main"))
        # Differentiate the active editing row from committed rows (§14).
        tint = QColor(Color.ACTIVE_ROW_BG)
        for col in (COL_NO, COL_CODE, COL_UNIT, COL_TOTAL, COL_WH):
            self._table.item(r, col).setBackground(tint)
        no_item = self._table.item(r, COL_NO)
        no_item.setBackground(QColor(Color.ACTIVE_ROW_ACCENT))
        no_item.setForeground(QColor("#FFFFFF"))

        self._item_selector = SearchSelector(
            self._items, placeholder=self._t.gettext("si.item_search_ph"),
            display_index=1, panel_width=520,
        )
        self._item_selector.rowSelected.connect(self._on_item_selected)
        self._table.setCellWidget(r, COL_NAME, self._item_selector)

        self._qty_edit = self._numeric_edit(ph="0")
        self._price_edit = self._numeric_edit(ph="0.00")
        self._disc_edit = self._numeric_edit("0.00")
        self._table.setCellWidget(r, COL_QTY, self._qty_edit)
        self._table.setCellWidget(r, COL_PRICE, self._price_edit)
        self._table.setCellWidget(r, COL_DISC, self._disc_edit)

        self._qty_edit.returnPressed.connect(self._price_edit.setFocus)
        self._price_edit.returnPressed.connect(self._disc_edit.setFocus)
        self._disc_edit.returnPressed.connect(self._commit_active_row)
        for e in (self._qty_edit, self._price_edit, self._disc_edit):
            e.textEdited.connect(self._recompute_active_total)
        self._table.selectRow(r)

    def _ro_item(self, text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        return item

    def _on_item_selected(self, row: SearchRow) -> None:
        p = row.payload
        self._table.item(self._active_row, COL_CODE).setText(p["code"])
        self._table.item(self._active_row, COL_UNIT).setText(p["unit"])
        self._price_edit.setText(_money(p["price"]))
        if not self._qty_edit.text():
            self._qty_edit.setText("1")
        self._update_quick_info(p)
        self._recompute_active_total()
        self._qty_edit.setFocus()
        self._qty_edit.selectAll()

    def _recompute_active_total(self, *_a) -> None:
        total = _num(self._qty_edit.text()) * _num(self._price_edit.text()) - _num(self._disc_edit.text())
        self._table.item(self._active_row, COL_TOTAL).setText(_money(total) if self._table.item(self._active_row, COL_CODE).text() else "")

    def _commit_active_row(self) -> None:
        code = self._table.item(self._active_row, COL_CODE).text()
        if not code:
            return
        r = self._active_row
        name = self._item_selector.text()
        unit = self._table.item(r, COL_UNIT).text()
        qty, price, disc = _num(self._qty_edit.text()), _num(self._price_edit.text()), _num(self._disc_edit.text())
        wh = self._table.item(r, COL_WH).text()
        for col in (COL_NAME, COL_QTY, COL_PRICE, COL_DISC):
            self._table.removeCellWidget(r, col)
        total = qty * price - disc
        for col, text, num in (
            (COL_NAME, name, False), (COL_QTY, f"{qty:,.0f}", True),
            (COL_PRICE, _money(price), True), (COL_DISC, _money(disc), True),
            (COL_TOTAL, _money(total), True),
        ):
            item = QTableWidgetItem(text)
            align = Qt.AlignmentFlag.AlignRight if num else Qt.AlignmentFlag.AlignLeft
            item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(r, col, item)
        # Clear the active-row tint now that this line is committed.
        from PyQt6.QtGui import QBrush
        for col in range(9):
            cell = self._table.item(r, col)
            if cell is not None:
                cell.setBackground(QBrush())
                cell.setForeground(QBrush())
        self._add_active_row()
        self._recompute_totals()
        self._item_selector.focus()

    def _delete_selected_line(self) -> None:
        r = self._table.currentRow()
        if r < 0 or r == getattr(self, "_active_row", -1):
            return
        self._table.removeRow(r)
        self._renumber()
        self._active_row = self._table.rowCount() - 1
        self._recompute_totals()

    def _renumber(self) -> None:
        for r in range(self._table.rowCount()):
            if self._table.item(r, COL_NO):
                self._table.item(r, COL_NO).setText(str(r + 1))

    # ---- quick item info (permission-aware) ------------------------------

    def _update_quick_info(self, payload: dict) -> None:
        stock = payload["stock"]
        stock_val = self._q_stock._val  # type: ignore[attr-defined]
        stock_val.setText(f"{stock:,.0f} {payload['unit']}")
        # Stock level colour (Prompt 01E §14): out / low / in.
        accent = "danger" if stock <= 0 else "warning" if stock < 30 else "success"
        stock_val.setProperty("accent", accent)
        stock_val.style().unpolish(stock_val); stock_val.style().polish(stock_val)
        self._q_last._val.setText(_money(payload["last_sale"]) + " AFN")  # type: ignore[attr-defined]
        self._q_default._val.setText(_money(payload["price"]) + " AFN")  # type: ignore[attr-defined]

    # ---- bottom band -----------------------------------------------------

    def _build_bottom_band(self) -> QHBoxLayout:
        band = QHBoxLayout(); band.setSpacing(Spacing.SECTION_GAP)
        band.addWidget(self._build_quick_info(), stretch=3)
        band.addWidget(self._build_payment(), stretch=2)
        return band

    def _build_quick_info(self) -> QWidget:
        # Compact contextual strip (Prompt 01G §9) — not a major form section.
        card = Card(role="section"); card.setProperty("accent", "teal"); apply_shadow(card)
        card.body.setSpacing(Spacing.XS)
        title = self._card_title("si.operational"); title.setProperty("accent", "teal")
        card.body.addWidget(title)

        strip = QHBoxLayout(); strip.setSpacing(Spacing.LG)
        self._q_stock = self._info_pair("si.op_stock")
        self._q_last = self._info_pair("si.op_last_sale")
        self._q_default = self._info_pair("si.default_price")
        for pair in (self._q_stock, self._q_last, self._q_default):
            strip.addWidget(pair)
        strip.addStretch(1)
        card.body.addLayout(strip)

        # Cost/profit is permission-gated (Prompt 01D §8) — not shown by default.
        self._cost_note = muted(self._t.gettext("si.cost_hidden"))
        card.body.addWidget(self._cost_note)
        card.body.addStretch(1)
        return card

    def _info_pair(self, label_key: str) -> QWidget:
        wrap = QWidget(); wrap.setStyleSheet("background: transparent;")
        row = QVBoxLayout(wrap); row.setContentsMargins(0, 0, 0, 0); row.setSpacing(0)
        lab = field_label(self._t.gettext(label_key))
        val = QLabel("—"); val.setProperty("role", "stat-value")
        row.addWidget(lab); row.addWidget(val)
        wrap._val = val  # type: ignore[attr-defined]
        wrap._key = label_key  # type: ignore[attr-defined]
        return wrap

    def _build_payment(self) -> QWidget:
        card = Card(role="section"); card.setProperty("accent", "brand"); apply_shadow(card)
        t = self._t

        # Cash / Credit segmented indicator.
        seg = QHBoxLayout(); seg.setSpacing(Spacing.XS)
        title = self._card_title("si.payment"); title.setProperty("accent", "brand")
        seg.addWidget(title)
        seg.addStretch(1)
        self._seg_cash = chip(t.gettext("si.pay_cash"), "success")
        self._seg_credit = chip(t.gettext("si.pay_credit"), "neutral")
        seg.addWidget(self._seg_cash); seg.addWidget(self._seg_credit)
        card.body.addLayout(seg)

        # Grand total — strong filled brand bar (max emphasis, §14).
        gt = QFrame(); gt.setProperty("role", "grand-total-strong")
        gtl = QHBoxLayout(gt); gtl.setContentsMargins(Spacing.LG, Spacing.SM, Spacing.LG, Spacing.SM)
        self._grand_label = QLabel(t.gettext("si.grand_total"))
        self._grand_label.setProperty("role", "gts-label")
        self._grand_value = QLabel("—")
        self._grand_value.setProperty("role", "gts-value")
        self._grand_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        gtl.addWidget(self._grand_label); gtl.addStretch(1); gtl.addWidget(self._grand_value)
        card.body.addWidget(gt)

        # Amount received (editable) + remaining (computed).
        pay = QGridLayout(); pay.setHorizontalSpacing(Spacing.LG); pay.setVerticalSpacing(Spacing.XS)
        self._recv_label = QLabel(t.gettext("si.cash_received")); self._recv_label.setProperty("role", "total-label")
        self._recv_edit = self._numeric_edit(_money(self._received))
        apply_field_width(self._recv_edit, FieldWidth.SM)
        self._recv_edit.textEdited.connect(self._on_received_changed)
        self._rem_label = QLabel(t.gettext("si.remaining")); self._rem_label.setProperty("role", "total-label")
        self._rem_value = QLabel("—"); self._rem_value.setProperty("role", "total-value")
        self._rem_value.setProperty("accent", "danger")
        self._rem_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        pay.addWidget(self._recv_label, 0, 0); pay.addWidget(self._recv_edit, 0, 1)
        pay.addWidget(self._rem_label, 1, 0); pay.addWidget(self._rem_value, 1, 1)
        pay.setColumnStretch(1, 1)
        card.body.addLayout(pay)
        return card

    def _on_received_changed(self, *_a) -> None:
        self._received = _num(self._recv_edit.text())
        self._recompute_totals()

    # ---- totals ----------------------------------------------------------

    def _committed_subtotal(self) -> float:
        total = 0.0
        for r in range(self._table.rowCount()):
            if r == getattr(self, "_active_row", -1):
                continue
            cell = self._table.item(r, COL_TOTAL)
            if cell:
                total += _num(cell.text())
        return total

    def _recompute_totals(self) -> None:
        grand = self._committed_subtotal()
        self._grand_value.setText(_money(grand) + " AFN")
        remaining = grand - self._received
        self._rem_value.setText(_money(remaining) + " AFN")
        # Remaining is debt (red) when unpaid, positive (green) when settled.
        self._rem_value.setProperty("money", "negative" if remaining > 0.001 else "positive")
        self._rem_value.style().unpolish(self._rem_value); self._rem_value.style().polish(self._rem_value)
        # Cash when fully paid, otherwise credit (§14).
        cash = remaining <= 0.001
        self._seg_cash.setProperty("chip", "success" if cash else "neutral")
        self._seg_credit.setProperty("chip", "neutral" if cash else "warning")
        for c in (self._seg_cash, self._seg_credit):
            c.style().unpolish(c); c.style().polish(c)

    # ---- action bar ------------------------------------------------------

    def _build_action_bar(self) -> QWidget:
        bar = QFrame(); bar.setProperty("role", "actionbar")
        apply_shadow(bar, blur=18, y=3, alpha=30)
        row = QHBoxLayout(bar)
        row.setContentsMargins(Spacing.MD, Spacing.SM, Spacing.MD, Spacing.SM)
        row.setSpacing(Spacing.SM)
        specs = [
            ("si.act_new", "new", "F2", False),
            ("si.act_save", "save", "Ctrl+S", True),
            ("si.act_save_print", "save", "Ctrl+P", False),
            ("si.act_print", "print", "F9", False),
            ("si.act_receive", "receive", "F6", False),
        ]
        self._action_buttons: list[tuple[str, QWidget]] = []
        for key, icon, shortcut, primary in specs:
            btn = primary_button(self._t.gettext(key)) if primary else secondary_button(self._t.gettext(key))
            btn.setIcon(standard_icon(icon)); btn.setToolTip(shortcut)
            if key in ("si.act_save_print", "si.act_print"):
                btn.clicked.connect(self._trigger_print)
            self._action_buttons.append((key, btn))
            row.addWidget(btn)
            hint = QLabel(shortcut); hint.setProperty("role", "shortcut")
            row.addWidget(hint)
        row.addStretch(1)
        self._close_btn = secondary_button(self._t.gettext("si.act_close"))
        self._close_btn.setIcon(standard_icon("close"))
        row.addWidget(self._close_btn)
        return bar

    def _trigger_print(self) -> None:
        """Save & Print / Print → open the A4 print preview (same transaction)."""
        if self._on_print is not None:
            self._on_print(self._demo)

    @property
    def demo_invoice(self):
        return self._demo

    # ---- demo drivers (for screenshots / tests) --------------------------

    def open_item_search(self, text: str = "bas") -> None:
        self._item_selector.open_with(text)

    def select_item(self, index: int = 0, qty: str = "12") -> None:
        rows = self._item_selector.current_rows() or self._items.search(self._item_selector.text() or "bas")
        if rows:
            row = rows[index]
            self._qty_edit.setText(qty)
            # Mirror the real accept path: show the item name, close the popup.
            self._item_selector.set_text(row.values[1])
            self._item_selector._hide_panel()
            self._on_item_selected(row)

    def open_customer_search(self, text: str = "ka") -> None:
        self._customer_selector.open_with(text)

    def select_customer(self, index: int = 0) -> None:
        rows = self._customers.search("ka")
        if rows:
            self._on_customer_selected(rows[index])

    def _on_customer_selected(self, row: SearchRow) -> None:
        p = row.payload
        self._set_info_chip(self._chip_phone, p["phone"], "neutral")
        bal = p["balance"]
        self._set_info_chip(self._chip_balance, _money(bal) + " AFN",
                            "danger" if bal > 0 else "success")
        self._set_info_chip(self._chip_credit, _money(p["credit_limit"]) + " AFN", "info")

    def _set_info_chip(self, wrap: QWidget, value: str, accent: str) -> None:
        val = wrap._value  # type: ignore[attr-defined]
        val.setText(value); val.setProperty("chip", accent)
        val.style().unpolish(val); val.style().polish(val)

    # ---- i18n ------------------------------------------------------------

    def retranslate(self, translator: Translator) -> None:
        self._t = translator
        self._title.setText(translator.gettext("si.title"))
        self._badge.setText(translator.gettext("si.prototype_badge"))
        self._kbd_hint.setText(translator.gettext("si.keyboard_hint"))
        self._table.setHorizontalHeaderLabels([translator.gettext(k) for k in self._grid_headers()])
        self._grand_label.setText(translator.gettext("si.grand_total"))
        self._recv_label.setText(translator.gettext("si.cash_received"))
        self._rem_label.setText(translator.gettext("si.remaining"))
        self._btn_delete.setText(escape_amp(translator.gettext("si.delete_line")))
        self._customer_selector.line_edit.setPlaceholderText(translator.gettext("si.customer_search_ph"))
        self._item_selector.line_edit.setPlaceholderText(translator.gettext("si.item_search_ph"))
        self._cust_eyebrow.setText(translator.gettext("si.customer"))
        for key, lf in self._meta_fields:
            lf.set_label(translator.gettext(key))
        self._cost_note.setText(translator.gettext("si.cost_hidden"))
        for wrap in (self._chip_phone, self._chip_balance, self._chip_credit):
            wrap._label.setText(translator.gettext(wrap._label_key))  # type: ignore[attr-defined]
        for key, btn in self._action_buttons:
            btn.setText(escape_amp(translator.gettext(key)))
        self._close_btn.setText(escape_amp(translator.gettext("si.act_close")))
        self._seg_cash.setText(translator.gettext("si.pay_cash"))
        self._seg_credit.setText(translator.gettext("si.pay_credit"))
