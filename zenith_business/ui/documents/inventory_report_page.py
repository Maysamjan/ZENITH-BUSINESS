"""Inventory Reports screen (Stage 06).

Five views of the one movement ledger — Current Stock, Opening vs Current, Stock
by Warehouse, Item Movement and Low Stock. Each reads
:class:`InventoryReportService`, which reads the same service the Inventory
screen and the Sales stock check use, so no two screens can disagree.

Printing reuses the existing preview standard with the CUSTOMER's business
identity, **A4 only** — an inventory report is a wide table and squeezing it onto
A5 hurts readability.
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from zenith_business.core.i18n import Translator
from zenith_business.core.money import format_money
from zenith_business.ui.components import (
    Card,
    LabeledField,
    apply_shadow,
    escape_amp,
    page_title,
    primary_button,
    secondary_button,
    standard_icon,
)
from zenith_business.ui.design.tokens import ControlSize, FieldWidth, Spacing
from zenith_business.ui.documents.inventory_pages import stock_status_key

#: report key -> (title i18n key, columns[(header_key, row_key, align)])
REPORTS: dict[str, tuple[str, list[tuple[str, str, str]]]] = {
    "current": ("inv.rep_current", [
        ("inv.col_item_code", "item_code", "l"), ("inv.col_item_name", "item_name", "l"),
        ("inv.col_unit", "unit", "l"), ("inv.col_current", "current", "r"),
        ("inv.col_minimum", "minimum", "r"), ("inv.col_warehouse", "warehouses", "l"),
        ("inv.col_status", "status_label", "l")]),
    "opening_vs_current": ("inv.rep_opening_vs_current", [
        ("inv.col_item_code", "item_code", "l"), ("inv.col_item_name", "item_name", "l"),
        ("inv.col_unit", "unit", "l"), ("inv.col_opening", "opening", "r"),
        ("inv.col_current", "current", "r"), ("inv.col_difference", "difference", "r")]),
    "by_warehouse": ("inv.rep_by_warehouse", [
        ("inv.col_warehouse", "warehouse_name", "l"),
        ("inv.col_item_code", "item_code", "l"), ("inv.col_item_name", "item_name", "l"),
        ("inv.col_unit", "unit_symbol", "l"), ("inv.col_qty", "quantity", "r")]),
    "movement": ("inv.rep_movement", [
        ("inv.col_date", "movement_date", "l"), ("inv.col_type", "type_label", "l"),
        ("inv.col_warehouse", "warehouse_name", "l"),
        ("inv.col_in", "qty_in", "r"), ("inv.col_out", "qty_out", "r"),
        ("inv.col_balance", "balance", "r"), ("inv.col_document", "document_no", "l"),
        ("inv.col_note", "notes", "l")]),
    "low_stock": ("inv.rep_low_stock", [
        ("inv.col_item_code", "item_code", "l"), ("inv.col_item_name", "item_name", "l"),
        ("inv.col_unit", "unit", "l"), ("inv.col_current", "current", "r"),
        ("inv.col_minimum", "minimum", "r"), ("inv.col_warehouse", "warehouses", "l")]),
}

_MONEY_KEYS = {"opening", "current", "minimum", "difference", "quantity",
               "qty_in", "qty_out", "balance"}


class InventoryReportPage(QWidget):
    def __init__(self, context, translator: Translator, *,
                 on_close: Callable[[], None] | None = None,
                 on_print: Callable[[dict], None] | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctx = context
        self._t = translator
        self._on_close = on_close
        self._on_print = on_print
        self._kind = "current"
        self._last: dict | None = None

        self.setProperty("role", "workspace")
        root = QVBoxLayout(self)
        root.setContentsMargins(Spacing.PAGE_MARGIN, Spacing.SM,
                                Spacing.PAGE_MARGIN, Spacing.SM)
        root.setSpacing(Spacing.SM)
        root.addLayout(self._build_titlebar())
        root.addWidget(self._build_picker())
        self._table = QTableWidget(0, 0)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.setMinimumHeight(160)
        self._table.horizontalHeader().setHighlightSections(False)
        self._table.verticalHeader().setDefaultSectionSize(ControlSize.TABLE_ROW_HEIGHT + 4)
        root.addWidget(self._table, stretch=1)
        root.addWidget(self._build_action_bar())
        self.run()

    def _build_titlebar(self) -> QHBoxLayout:
        row = QHBoxLayout(); row.setSpacing(Spacing.MD)
        self._title = page_title(self._t.gettext("inv.reports_title"))
        row.addWidget(self._title); row.addStretch(1)
        return row

    def _build_picker(self) -> QWidget:
        card = Card(role="section"); card.setProperty("accent", "navy"); apply_shadow(card)
        card.body.setContentsMargins(Spacing.CARD_PAD_H, Spacing.SM,
                                     Spacing.CARD_PAD_H, Spacing.SM)
        col = QVBoxLayout(); col.setSpacing(Spacing.SM)

        seg = QHBoxLayout(); seg.setSpacing(Spacing.XS)
        self._kind_buttons: dict[str, QPushButton] = {}
        for kind, (title_key, _cols) in REPORTS.items():
            b = QPushButton(self._t.gettext(title_key))
            b.setCheckable(True); b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _c=False, k=kind: self._set_kind(k))
            self._kind_buttons[kind] = b
            seg.addWidget(b)
        seg.addStretch(1)
        col.addLayout(seg)

        row = QHBoxLayout(); row.setSpacing(Spacing.MD)
        self._item_combo = QComboBox()
        self._wh_combo = QComboBox()
        for c in (self._item_combo, self._wh_combo):
            c.currentIndexChanged.connect(lambda _i: self.run())
        self._item_field = LabeledField(self._t.gettext("inv.f_item"), self._item_combo,
                                        width=FieldWidth.MD, compact=True)
        self._wh_field = LabeledField(self._t.gettext("inv.f_warehouse"), self._wh_combo,
                                      width=FieldWidth.MD, compact=True)
        row.addWidget(self._item_field); row.addWidget(self._wh_field); row.addStretch(1)
        col.addLayout(row)

        wrap = QWidget(); wrap.setLayout(col); wrap.setObjectName("InvRepFilter")
        wrap.setStyleSheet("#InvRepFilter { background: transparent; }")
        card.body.addWidget(wrap)
        self._populate_filters()
        self._set_kind("current", run=False)
        return card

    def _populate_filters(self) -> None:
        for c in (self._item_combo, self._wh_combo):
            c.blockSignals(True)
        keep = (self._item_combo.currentData(), self._wh_combo.currentData())
        self._item_combo.clear()
        for it in self._ctx.items.list():
            self._item_combo.addItem(f"{it['item_code']} — {it['name']}", it["id"])
        self._wh_combo.clear()
        self._wh_combo.addItem(self._t.gettext("inv.filter_all_wh"), None)
        for w in self._ctx.warehouses_repo.list_active():
            self._wh_combo.addItem(w["name"], w["id"])
        for combo, value in zip((self._item_combo, self._wh_combo), keep):
            i = combo.findData(value)
            if i >= 0:
                combo.setCurrentIndex(i)
        for c in (self._item_combo, self._wh_combo):
            c.blockSignals(False)

    def _build_action_bar(self) -> QWidget:
        bar = QFrame(); bar.setProperty("role", "actionbar")
        apply_shadow(bar, blur=18, y=3, alpha=30)
        row = QHBoxLayout(bar)
        row.setContentsMargins(Spacing.LG, Spacing.SM, Spacing.LG, Spacing.SM)
        self._status = QLabel(""); self._status.setProperty("role", "secondary")
        row.addWidget(self._status); row.addStretch(1)
        self._print_btn = primary_button(self._t.gettext("rep.print"))
        self._print_btn.setIcon(standard_icon("print"))
        self._print_btn.clicked.connect(self._print)
        row.addWidget(self._print_btn)
        self._close_btn = secondary_button(self._t.gettext("s4.act_close"))
        self._close_btn.setIcon(standard_icon("close"))
        if self._on_close is not None:
            self._close_btn.clicked.connect(lambda: self._on_close())
        row.addWidget(self._close_btn)
        return bar

    # ---- running ---------------------------------------------------------

    def _set_kind(self, kind: str, *, run: bool = True) -> None:
        self._kind = kind
        for k, b in self._kind_buttons.items():
            b.setChecked(k == kind)
        # Only the per-item movement report needs an item; the rest span all items.
        self._item_field.setVisible(kind == "movement")
        self._wh_field.setVisible(kind in ("movement", "by_warehouse"))
        if run:
            self.run()

    def run(self) -> None:
        svc = self._ctx.inventory_reports
        wh = self._wh_combo.currentData() if hasattr(self, "_wh_combo") else None
        if self._kind == "current":
            rows = svc.current_stock()
        elif self._kind == "opening_vs_current":
            rows = svc.opening_vs_current()
        elif self._kind == "by_warehouse":
            rows = svc.stock_by_warehouse(warehouse_id=wh)
        elif self._kind == "low_stock":
            rows = svc.low_stock()
        else:
            item_id = self._item_combo.currentData()
            rows = (svc.item_movement(item_id=item_id, warehouse_id=wh)
                    if item_id is not None else [])
            for r in rows:
                r["type_label"] = self._t.gettext(f"inv.mt_{r['movement_type']}")
        for r in rows:
            if "current" in r:
                r["status_label"] = self._t.gettext(
                    stock_status_key(r.get("current"), r.get("minimum")))
        # Carry the already-translated headers so the printed sheet is in the SAME
        # language as the screen, instead of the print builder having to guess.
        self._last = {
            "kind": self._kind, "rows": rows,
            "title": self._t.gettext(REPORTS[self._kind][0]),
            "columns": [(self._t.gettext(h), key, align)
                        for h, key, align in REPORTS[self._kind][1]],
        }
        self._render(rows)

    def _render(self, rows: list[dict]) -> None:
        cols = REPORTS[self._kind][1]
        self._table.setColumnCount(len(cols))
        self._table.setHorizontalHeaderLabels([self._t.gettext(h) for h, _k, _a in cols])
        hh = self._table.horizontalHeader()
        stretch = "item_name"
        for i, (_h, key, _a) in enumerate(cols):
            hh.setSectionResizeMode(
                i, QHeaderView.ResizeMode.Stretch if key == stretch
                else QHeaderView.ResizeMode.ResizeToContents)
        self._table.setRowCount(0)
        self._table.setRowCount(len(rows))
        for r, data in enumerate(rows):
            for c, (_h, key, align) in enumerate(cols):
                value = data.get(key)
                text = (format_money(value) if key in _MONEY_KEYS and str(value or "").strip()
                        else ("" if value is None else str(value)))
                item = QTableWidgetItem(text)
                a = (Qt.AlignmentFlag.AlignRight if align == "r"
                     else Qt.AlignmentFlag.AlignLeft)
                item.setTextAlignment(a | Qt.AlignmentFlag.AlignVCenter)
                self._table.setItem(r, c, item)
        self._status.setText(self._t.gettext("inv.items_count").replace("{n}", str(len(rows)))
                             if rows else self._t.gettext("inv.empty"))

    def _print(self) -> None:
        if self._last is None or self._on_print is None:
            return
        self._on_print(self._last)

    def reload(self) -> None:
        self._populate_filters()
        self.run()

    def retranslate(self, translator: Translator) -> None:
        self._t = translator
        self._title.setText(translator.gettext("inv.reports_title"))
        for kind, b in self._kind_buttons.items():
            b.setText(translator.gettext(REPORTS[kind][0]))
        self._item_field.set_label(translator.gettext("inv.f_item"))
        self._wh_field.set_label(translator.gettext("inv.f_warehouse"))
        self._print_btn.setText(escape_amp(translator.gettext("rep.print")))
        self._close_btn.setText(escape_amp(translator.gettext("s4.act_close")))
        self._populate_filters()
        self.run()
