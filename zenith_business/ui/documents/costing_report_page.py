"""Costing Reports screen (Stage 08) — valuation, COGS and gross profit.

Three views of the one costed movement ledger:

* **Inventory Valuation** — quantity, average cost and value, per item and per
  warehouse, with the company total.
* **Cost of Goods Sold**  — what the goods that left on sales actually cost.
* **Gross Profit**        — net sales − COGS, with both halves on the sheet so
  the subtraction can be checked by eye.

Deliberately built on the Stage 06 report screen's shape and its **A4-only**
print document rather than a second print implementation: a costing table is as
wide as an inventory table, and one print standard is easier to keep honest than
two. Net sales is read from the locked Sales Reporting engine — this screen never
recomputes it.
"""

from __future__ import annotations

from datetime import date
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
from zenith_business.core.money import D, format_money
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

#: report key -> (title i18n key, columns[(header_key, row_key, align)])
REPORTS: dict[str, tuple[str, list[tuple[str, str, str]]]] = {
    "valuation": ("cost.rep_valuation", [
        ("cost.col_item_code", "item_code", "l"),
        ("cost.col_item_name", "item_name", "l"),
        ("cost.col_unit", "unit_code", "l"),
        ("cost.col_qty", "quantity", "r"),
        ("cost.col_avg_cost", "average_cost", "r"),
        ("cost.col_value", "value", "r")]),
    "cogs": ("cost.rep_cogs", [
        ("cost.col_item_code", "item_code", "l"),
        ("cost.col_item_name", "item_name", "l"),
        ("cost.col_qty_sold", "quantity_sold", "r"),
        ("cost.col_avg_cost", "average_cost", "r"),
        ("cost.col_cogs", "cogs", "r")]),
    "gross_profit": ("cost.rep_gross_profit", [
        ("cost.col_figure", "label", "l"),
        ("cost.col_amount", "amount", "r")]),
}

#: Keys rendered as money rather than raw text.
_MONEY_KEYS = {"value", "cogs", "amount", "average_cost"}
#: Keys rendered as quantities.
_QTY_KEYS = {"quantity", "quantity_sold"}

#: Period choices, widest-useful first (see the picker for why year leads).
_PERIODS: tuple[tuple[str, str], ...] = (
    ("cost.period_year", "year"),
    ("cost.period_month", "month"),
    ("cost.period_all", "all"),
)


class CostingReportPage(QWidget):
    def __init__(self, context, translator: Translator, *,
                 on_close: Callable[[], None] | None = None,
                 on_print: Callable[[dict], None] | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctx = context
        self._t = translator
        self._on_close = on_close
        self._on_print = on_print
        self._kind = "valuation"
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

    # ---- chrome ----------------------------------------------------------

    def _build_titlebar(self) -> QHBoxLayout:
        row = QHBoxLayout(); row.setSpacing(Spacing.MD)
        self._title = page_title(self._t.gettext("cost.reports_title"))
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
        self._wh_combo = QComboBox()
        self._wh_combo.currentIndexChanged.connect(lambda _i: self.run())
        self._wh_field = LabeledField(self._t.gettext("cost.f_warehouse"), self._wh_combo,
                                      width=FieldWidth.MD, compact=True)
        self._period_combo = QComboBox()
        # This YEAR leads on purpose. A costing report opened on a month with no
        # trading would otherwise look broken rather than empty, and the owner's
        # financial year is the window these figures actually belong to.
        for key, value in _PERIODS:
            self._period_combo.addItem(self._t.gettext(key), value)
        self._period_combo.currentIndexChanged.connect(lambda _i: self.run())
        self._period_field = LabeledField(self._t.gettext("cost.f_period"),
                                          self._period_combo, width=FieldWidth.MD,
                                          compact=True)
        row.addWidget(self._wh_field); row.addWidget(self._period_field); row.addStretch(1)
        col.addLayout(row)

        wrap = QWidget(); wrap.setLayout(col); wrap.setObjectName("CostRepFilter")
        wrap.setStyleSheet("#CostRepFilter { background: transparent; }")
        card.body.addWidget(wrap)
        self._populate_filters()
        self._set_kind("valuation", run=False)
        return card

    def _populate_filters(self) -> None:
        self._wh_combo.blockSignals(True)
        keep = self._wh_combo.currentData()
        self._wh_combo.clear()
        self._wh_combo.addItem(self._t.gettext("cost.filter_all_wh"), None)
        for w in self._ctx.warehouses_repo.list_active():
            self._wh_combo.addItem(w["name"], w["id"])
        i = self._wh_combo.findData(keep)
        if i >= 0:
            self._wh_combo.setCurrentIndex(i)
        self._wh_combo.blockSignals(False)

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
        # Valuation is a position "right now"; the other two cover a period.
        self._period_field.setVisible(kind != "valuation")
        if run:
            self.run()

    def _period(self) -> tuple[str, str]:
        """The date window the period picker asks for."""
        today = date.today()
        choice = self._period_combo.currentData() if hasattr(self, "_period_combo") else "year"
        if choice == "month":
            first = today.replace(day=1)
            return first.isoformat(), today.isoformat()
        if choice == "all":
            return "0001-01-01", "9999-12-31"
        return today.replace(month=1, day=1).isoformat(), today.isoformat()

    def run(self) -> None:
        svc = self._ctx.costing_reports
        wh = self._wh_combo.currentData() if hasattr(self, "_wh_combo") else None
        date_from, date_to = self._period()
        # (i18n key, value, how to format it, which column it totals). The column
        # matters: a total printed under the money column would be formatted as
        # money, and a quantity total reading 35.00 beside item rows reading
        # 15.000 is exactly the kind of difference nobody can explain.
        summary: list[tuple[str, str, str, str]] = []

        if self._kind == "valuation":
            report = svc.valuation(warehouse_id=wh)
            rows = report["items"]
            total = report["total"]
            summary = [("cost.sum_qty", total["quantity"], "qty", "quantity"),
                       ("cost.sum_value", total["value"], "money", "value")]
        elif self._kind == "cogs":
            report = svc.cogs(date_from=date_from, date_to=date_to, warehouse_id=wh)
            rows = report["items"]
            summary = [("cost.sum_cogs", report["total"], "money", "cogs")]
        else:
            gp = svc.gross_profit(date_from=date_from, date_to=date_to, warehouse_id=wh)
            # Gross profit is one figure built from a few others; showing the
            # workings as rows lets the owner check the subtraction themselves.
            rows = [
                {"label": self._t.gettext("cost.gp_gross_sales"), "amount": gp["gross_sales"]},
                {"label": self._t.gettext("cost.gp_returns"), "amount": gp["returns"]},
                {"label": self._t.gettext("cost.gp_net_sales"), "amount": gp["net_sales"]},
                {"label": self._t.gettext("cost.gp_cogs"), "amount": gp["cogs"]},
                {"label": self._t.gettext("cost.gp_profit"), "amount": gp["gross_profit"]},
            ]
            summary = [("cost.sum_margin",
                        f"{gp['margin_percent']}%" if gp["margin_percent"] else "—",
                        "raw", "amount")]

        # Carry the already-translated headers so the printed sheet is in the
        # SAME language as the screen rather than the builder guessing.
        self._last = {
            "kind": self._kind, "rows": rows,
            "title": self._t.gettext(REPORTS[self._kind][0]),
            "columns": [(self._t.gettext(h), key, align)
                        for h, key, align in REPORTS[self._kind][1]],
            "summary": [(self._t.gettext(k), self._summary_text(v, how), column)
                        for k, v, how, column in summary],
        }
        self._render(rows, self._last["summary"])

    @staticmethod
    def _summary_text(value: str, how: str) -> str:
        if how == "money":
            return format_money(value)
        return str(value)

    def _render(self, rows: list[dict], summary: list[tuple[str, str, str]]) -> None:
        cols = REPORTS[self._kind][1]
        self._table.setColumnCount(len(cols))
        self._table.setHorizontalHeaderLabels([self._t.gettext(h) for h, _k, _a in cols])
        hh = self._table.horizontalHeader()
        stretch = "item_name" if self._kind != "gross_profit" else "label"
        for i, (_h, key, _a) in enumerate(cols):
            hh.setSectionResizeMode(
                i, QHeaderView.ResizeMode.Stretch if key == stretch
                else QHeaderView.ResizeMode.ResizeToContents)
        self._table.setRowCount(0)
        self._table.setRowCount(len(rows))
        for r, data in enumerate(rows):
            for c, (_h, key, align) in enumerate(cols):
                item = QTableWidgetItem(self._text(key, data.get(key)))
                a = (Qt.AlignmentFlag.AlignRight if align == "r"
                     else Qt.AlignmentFlag.AlignLeft)
                item.setTextAlignment(a | Qt.AlignmentFlag.AlignVCenter)
                self._table.setItem(r, c, item)
        # The summary arrives already translated and already formatted, so the
        # status line and the printed sheet show the identical wording.
        parts = [f"{label}: {value}" for label, value, _column in summary]
        self._status.setText("   ·   ".join(parts) if parts
                             else self._t.gettext("inv.empty"))

    @staticmethod
    def _text(key: str, value) -> str:
        if value is None or str(value).strip() == "":
            return ""
        if key == "average_cost":
            # An average is a cost per unit, not a posted amount: trailing
            # costing zeros would only add noise to a table of money.
            return format_money(D(value).quantize(D("0.01")))
        if key in _MONEY_KEYS:
            return format_money(value)
        if key in _QTY_KEYS:
            return str(value)
        return str(value)

    def _print(self) -> None:
        if self._last is None or self._on_print is None:
            return
        self._on_print(self._last)

    def reload(self) -> None:
        self._populate_filters()
        self.run()

    def retranslate(self, translator: Translator) -> None:
        self._t = translator
        self._title.setText(translator.gettext("cost.reports_title"))
        for kind, b in self._kind_buttons.items():
            b.setText(translator.gettext(REPORTS[kind][0]))
        self._wh_field.set_label(translator.gettext("cost.f_warehouse"))
        self._period_field.set_label(translator.gettext("cost.f_period"))
        self._period_combo.blockSignals(True)
        keep = self._period_combo.currentData()
        self._period_combo.clear()
        for key, value in _PERIODS:
            self._period_combo.addItem(translator.gettext(key), value)
        i = self._period_combo.findData(keep)
        if i >= 0:
            self._period_combo.setCurrentIndex(i)
        self._period_combo.blockSignals(False)
        self._print_btn.setText(escape_amp(translator.gettext("rep.print")))
        self._close_btn.setText(escape_amp(translator.gettext("s4.act_close")))
        self._populate_filters()
        self.run()
