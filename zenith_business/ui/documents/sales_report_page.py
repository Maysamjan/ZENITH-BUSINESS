"""Sales Report screen (Stage 05 final — Sales Reporting System).

Answers, for any historical period, how much was sold, paid, left on credit and
returned, and the resulting Net Sales — for registered AND walk-in customers.

Everything shown is read straight from the authoritative POSTED ``sales`` /
``sales_returns`` tables via :class:`SalesReportService`; there is no separate
reporting truth, so:

* a partial payment is split into its paid and credit parts (never classified
  whole),
* a later receipt (debt collection) is NOT counted as sales revenue,
* a corrected invoice counts exactly once (the VOID original is excluded),
* Gross and Returns stay distinguishable and Net = Gross − Returns.

Dates use the app's existing ISO storage (no second date system). Same LOCKED
design system, top navigation, Vazirmatn and EN/Dari RTL as every other screen.
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
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from zenith_business.core.clock import today_iso
from zenith_business.core.i18n import Translator
from zenith_business.core.money import format_money
from zenith_business.ui.components import (
    Card,
    LabeledField,
    apply_shadow,
    escape_amp,
    eyebrow,
    field_label,
    page_title,
    primary_button,
    secondary_button,
    standard_icon,
)
from zenith_business.ui.design.tokens import ControlSize, FieldWidth, Spacing
from zenith_business.services.sales_reports import preset_range

_PRESETS = ("today", "week", "month", "year", "custom")
_PRESET_KEYS = {
    "today": "rep.preset_today", "week": "rep.preset_week", "month": "rep.preset_month",
    "year": "rep.preset_year", "custom": "rep.preset_custom",
}


class SalesReportPage(QWidget):
    def __init__(self, context, translator: Translator, *,
                 on_close: Callable[[], None] | None = None,
                 on_print: Callable[[dict], None] | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctx = context
        self._t = translator
        self._on_close = on_close
        self._on_print = on_print
        self._preset = "month"
        self._view = "detail"           # detail | daily | monthly
        self._last: dict | None = None  # last-run payload (for print)

        self.setProperty("role", "workspace")
        root = QVBoxLayout(self)
        root.setContentsMargins(Spacing.PAGE_MARGIN, Spacing.SM,
                                Spacing.PAGE_MARGIN, Spacing.SM)
        root.setSpacing(Spacing.SM)
        root.addLayout(self._build_titlebar())
        root.addWidget(self._build_filters())
        root.addWidget(self._build_summary())
        root.addWidget(self._build_view_switch())
        root.addWidget(self._build_table(), stretch=1)
        root.addWidget(self._build_action_bar())

        self._apply_preset("month", run=False)

    # ---- title -----------------------------------------------------------

    def _build_titlebar(self) -> QHBoxLayout:
        row = QHBoxLayout(); row.setSpacing(Spacing.MD)
        self._title = page_title(self._t.gettext("rep.title"))
        row.addWidget(self._title); row.addStretch(1)
        return row

    # ---- filters ---------------------------------------------------------

    def _seg_button(self, text: str, cb) -> QPushButton:
        b = QPushButton(text)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setCheckable(True)
        b.clicked.connect(lambda _c=False: cb())
        return b

    def _build_filters(self) -> QWidget:
        card = Card(role="section"); card.setProperty("accent", "navy"); apply_shadow(card)
        card.body.setContentsMargins(Spacing.CARD_PAD_H, Spacing.SM,
                                     Spacing.CARD_PAD_H, Spacing.SM)
        col = QVBoxLayout(); col.setSpacing(Spacing.SM)

        # Row 1 — period presets
        prow = QHBoxLayout(); prow.setSpacing(Spacing.XS)
        self._period_eyebrow = eyebrow(self._t.gettext("rep.period"))
        prow.addWidget(self._period_eyebrow)
        self._preset_buttons: dict[str, QPushButton] = {}
        for key in _PRESETS:
            b = self._seg_button(self._t.gettext(_PRESET_KEYS[key]),
                                 lambda k=key: self._apply_preset(k))
            self._preset_buttons[key] = b
            prow.addWidget(b)
        prow.addStretch(1)
        col.addLayout(prow)

        # Row 2 — dates + filters + run
        frow = QHBoxLayout(); frow.setSpacing(Spacing.MD)
        self._from_edit = QLineEdit(today_iso())
        self._to_edit = QLineEdit(today_iso())
        self._from_edit.textEdited.connect(self._on_date_typed)
        self._to_edit.textEdited.connect(self._on_date_typed)
        self._wh_combo = QComboBox()
        self._cust_combo = QComboBox()
        self._ps_combo = QComboBox()
        self._kind_combo = QComboBox()
        self._populate_filters()

        self._from_field = LabeledField(self._t.gettext("rep.from"), self._from_edit,
                                        width=FieldWidth.SM, compact=True)
        self._to_field = LabeledField(self._t.gettext("rep.to"), self._to_edit,
                                      width=FieldWidth.SM, compact=True)
        self._wh_field = LabeledField(self._t.gettext("rep.warehouse"), self._wh_combo,
                                      width=FieldWidth.MD, compact=True)
        self._cust_field = LabeledField(self._t.gettext("rep.customer"), self._cust_combo,
                                        width=FieldWidth.MD, compact=True)
        self._ps_field = LabeledField(self._t.gettext("rep.payment_status"), self._ps_combo,
                                      width=FieldWidth.SM, compact=True)
        self._kind_field = LabeledField(self._t.gettext("rep.kind"), self._kind_combo,
                                        width=FieldWidth.SM, compact=True)
        for f in (self._from_field, self._to_field, self._wh_field, self._cust_field,
                  self._ps_field, self._kind_field):
            frow.addWidget(f)
        frow.addStretch(1)
        self._run_btn = primary_button(self._t.gettext("rep.run"))
        self._run_btn.setIcon(standard_icon("search"))
        self._run_btn.clicked.connect(self.run)
        frow.addWidget(self._run_btn, alignment=Qt.AlignmentFlag.AlignBottom)
        col.addLayout(frow)

        # Scope the transparent background to THIS wrapper only (objectName selector),
        # otherwise a bare "background: transparent" cascades onto descendant widgets
        # and clobbers the primary Run button's fill.
        wrap = QWidget(); wrap.setLayout(col); wrap.setObjectName("RepFilterWrap")
        wrap.setStyleSheet("#RepFilterWrap { background: transparent; }")
        card.body.addWidget(wrap)
        return card

    def _populate_filters(self) -> None:
        t = self._t
        self._wh_combo.clear()
        self._wh_combo.addItem(t.gettext("rep.all"), None)
        for w in self._ctx.warehouses_repo.list_all():
            self._wh_combo.addItem(w["name"], w["id"])
        self._cust_combo.clear()
        self._cust_combo.addItem(t.gettext("rep.customer_ph"), None)
        for p in self._ctx.parties_repo.list(role="customer"):
            self._cust_combo.addItem(p["name"], p["id"])
        self._ps_combo.clear()
        for label, data in ((t.gettext("rep.all"), None), (t.gettext("rep.ps_paid"), "paid"),
                            (t.gettext("rep.ps_credit"), "credit"),
                            (t.gettext("rep.ps_partial"), "partial")):
            self._ps_combo.addItem(label, data)
        self._kind_combo.clear()
        for label, data in ((t.gettext("rep.all"), None),
                            (t.gettext("rep.kind_registered"), "registered"),
                            (t.gettext("rep.kind_walkin"), "walkin")):
            self._kind_combo.addItem(label, data)

    # ---- summary tiles ---------------------------------------------------

    def _metric(self, key: str, accent: str) -> tuple[QLabel, QLabel, QWidget]:
        box = QFrame(); box.setProperty("role", "stat"); box.setProperty("accent", accent)
        v = QVBoxLayout(box)
        v.setContentsMargins(Spacing.MD, Spacing.SM, Spacing.MD, Spacing.SM)
        v.setSpacing(Spacing.XXS)
        lab = QLabel(self._t.gettext(key)); lab.setProperty("role", "stat-label")
        val = QLabel("—"); val.setProperty("role", "stat-value"); val.setProperty("accent", accent)
        v.addWidget(lab); v.addWidget(val)
        return lab, val, box

    def _build_summary(self) -> QWidget:
        wrap = QWidget(); wrap.setStyleSheet("background: transparent;")
        outer = QVBoxLayout(wrap); outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(Spacing.XXS)
        row = QHBoxLayout(); row.setContentsMargins(0, 0, 0, 0); row.setSpacing(Spacing.MD)
        self._g_lab, self._g_val, b1 = self._metric("rep.m_gross", "info")
        self._p_lab, self._p_val, b2 = self._metric("rep.m_paid", "success")
        self._c_lab, self._c_val, b3 = self._metric("rep.m_credit", "warning")
        self._r_lab, self._r_val, b4 = self._metric("rep.m_returns", "danger")
        self._n_lab, self._n_val, b5 = self._metric("rep.m_net", "neutral")
        for b in (b1, b2, b3, b4, b5):
            row.addWidget(b, 1)
        outer.addLayout(row)
        self._summary_line = QLabel(""); self._summary_line.setProperty("role", "secondary")
        outer.addWidget(self._summary_line)
        return wrap

    # ---- view switch (Transactions / Daily / Monthly) --------------------

    def _build_view_switch(self) -> QWidget:
        wrap = QWidget(); wrap.setStyleSheet("background: transparent;")
        row = QHBoxLayout(wrap); row.setContentsMargins(0, 0, 0, 0); row.setSpacing(Spacing.XS)
        self._view_buttons: dict[str, QPushButton] = {}
        for view, key in (("detail", "rep.tab_detail"), ("daily", "rep.tab_daily"),
                          ("monthly", "rep.tab_monthly")):
            b = self._seg_button(self._t.gettext(key), lambda v=view: self._set_view(v))
            self._view_buttons[view] = b
            row.addWidget(b)
        row.addStretch(1)
        return wrap

    def _set_view(self, view: str) -> None:
        self._view = view
        for v, b in self._view_buttons.items():
            b.setChecked(v == view)
        self._render()

    # ---- table -----------------------------------------------------------

    def _detail_columns(self) -> list[tuple[str, str, str]]:
        return [("rep.col_date", "date", "l"), ("rep.col_docno", "document_no", "l"),
                ("rep.col_customer", "party", "l"), ("rep.col_type", "type", "l"),
                ("rep.col_gross", "gross", "r"), ("rep.col_paid", "paid", "r"),
                ("rep.col_credit", "credit", "r"), ("rep.col_returned", "returned", "r"),
                ("rep.col_net", "net", "r")]

    def _breakdown_columns(self) -> list[tuple[str, str, str]]:
        return [("rep.col_period", "period", "l"), ("rep.col_invoices", "invoices", "r"),
                ("rep.col_gross", "gross", "r"), ("rep.col_paid", "paid", "r"),
                ("rep.col_credit", "credit", "r"), ("rep.col_returned", "returns", "r"),
                ("rep.col_net", "net", "r")]

    def _build_table(self) -> QWidget:
        self._table = QTableWidget(0, 0)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.setMinimumHeight(160)
        self._table.horizontalHeader().setHighlightSections(False)
        self._table.verticalHeader().setDefaultSectionSize(ControlSize.TABLE_ROW_HEIGHT + 4)
        return self._table

    # ---- action bar ------------------------------------------------------

    def _build_action_bar(self) -> QWidget:
        bar = QFrame(); bar.setProperty("role", "actionbar")
        apply_shadow(bar, blur=18, y=3, alpha=30)
        row = QHBoxLayout(bar)
        row.setContentsMargins(Spacing.LG, Spacing.SM, Spacing.LG, Spacing.SM)
        self._status = QLabel(self._t.gettext("rep.hint"))
        self._status.setProperty("role", "secondary")
        row.addWidget(self._status); row.addStretch(1)
        self._print_btn = secondary_button(self._t.gettext("rep.print"))
        self._print_btn.setIcon(standard_icon("print"))
        self._print_btn.clicked.connect(self._print)
        row.addWidget(self._print_btn)
        self._close_btn = secondary_button(self._t.gettext("s4.act_close"))
        self._close_btn.setIcon(standard_icon("close"))
        if self._on_close is not None:
            self._close_btn.clicked.connect(lambda: self._on_close())
        row.addWidget(self._close_btn)
        return bar

    # ---- preset / date handling -----------------------------------------

    def _apply_preset(self, preset: str, *, run: bool = True) -> None:
        self._preset = preset
        for k, b in self._preset_buttons.items():
            b.setChecked(k == preset)
        custom = preset == "custom"
        self._from_edit.setReadOnly(not custom)
        self._to_edit.setReadOnly(not custom)
        if not custom:
            df, dt = preset_range(preset, today_iso())
            self._from_edit.setText(df)
            self._to_edit.setText(dt)
            if run:
                self.run()

    def _on_date_typed(self, _text: str) -> None:
        # Editing a date implies a custom range.
        if self._preset != "custom":
            self._preset = "custom"
            for k, b in self._preset_buttons.items():
                b.setChecked(k == "custom")
            self._from_edit.setReadOnly(False)
            self._to_edit.setReadOnly(False)

    # ---- run -------------------------------------------------------------

    def _valid_dates(self) -> tuple[str, str] | None:
        from datetime import date
        df, dt = self._from_edit.text().strip(), self._to_edit.text().strip()
        try:
            d1, d2 = date.fromisoformat(df), date.fromisoformat(dt)
        except ValueError:
            self._status.setText(self._t.gettext("rep.msg_bad_dates"))
            return None
        if d1 > d2:
            self._status.setText(self._t.gettext("rep.msg_range"))
            return None
        return df, dt

    def run(self) -> None:
        dates = self._valid_dates()
        if dates is None:
            return
        df, dt = dates
        wh = self._wh_combo.currentData()
        party = self._cust_combo.currentData()
        ps = self._ps_combo.currentData()
        kind = self._kind_combo.currentData()
        walkin_label = self._t.gettext("rep.walkin_customer")
        svc = self._ctx.sales_reports
        summary = svc.summary(date_from=df, date_to=dt, warehouse_id=wh, party_id=party)
        detail = svc.transactions(date_from=df, date_to=dt, walkin_label=walkin_label,
                                  warehouse_id=wh, party_id=party,
                                  payment_status=ps, kind=kind)
        daily = svc.daily_breakdown(date_from=df, date_to=dt, warehouse_id=wh, party_id=party)
        monthly = svc.monthly_breakdown(year=int(df[:4]), warehouse_id=wh, party_id=party)
        self._last = {"summary": summary, "detail": detail, "daily": daily,
                      "monthly": monthly, "date_from": df, "date_to": dt}
        self._apply_summary(summary)
        self._render()

    def _apply_summary(self, s: dict) -> None:
        self._g_val.setText(format_money(s["gross"]))
        self._p_val.setText(format_money(s["paid"]))
        self._c_val.setText(format_money(s["credit"]))
        self._r_val.setText(format_money(s["returns"]))
        self._n_val.setText(format_money(s["net"]))
        self._summary_line.setText(self._t.gettext("rep.summary_line").format(
            count=s["invoices"], df=s["date_from"], dt=s["date_to"]))

    # ---- rendering -------------------------------------------------------

    def _render(self) -> None:
        if self._last is None:
            return
        if self._view == "detail":
            self._render_detail(self._last["detail"])
        elif self._view == "daily":
            self._render_breakdown(self._last["daily"])
        else:
            self._render_breakdown([m for m in self._last["monthly"]
                                    if int(m["invoices"]) or m["gross"] != "0.00"
                                    or m["returns"] != "0.00"])

    def _render_detail(self, rows: list[dict]) -> None:
        cols = self._detail_columns()
        self._configure_columns(cols, stretch_key="party")
        money = {"gross", "paid", "credit", "returned", "net"}
        self._table.setRowCount(len(rows))
        for r, data in enumerate(rows):
            for c, (_h, key, align) in enumerate(cols):
                if key == "type":
                    text = self._t.gettext("rep.row_walkin" if data.get("walkin")
                                           else "rep.row_registered")
                else:
                    value = data.get(key)
                    text = format_money(value) if key in money else ("" if value is None
                                                                     else str(value))
                self._set_cell(r, c, text, align)
        self._status.setText(self._t.gettext("rep.empty") if not rows
                             else self._t.gettext("rep.summary_line").format(
                                 count=len(rows), df=self._last["date_from"],
                                 dt=self._last["date_to"]))

    def _render_breakdown(self, rows: list[dict]) -> None:
        cols = self._breakdown_columns()
        self._configure_columns(cols, stretch_key="period")
        money = {"gross", "paid", "credit", "returns", "net"}
        self._table.setRowCount(len(rows))
        for r, data in enumerate(rows):
            for c, (_h, key, align) in enumerate(cols):
                value = data.get(key)
                text = (format_money(value) if key in money
                        else ("" if value is None else str(value)))
                self._set_cell(r, c, text, align)
        if not rows:
            self._status.setText(self._t.gettext("rep.empty"))

    def _configure_columns(self, cols: list[tuple[str, str, str]], *, stretch_key: str) -> None:
        self._table.setColumnCount(len(cols))
        self._table.setHorizontalHeaderLabels([self._t.gettext(h) for h, _k, _a in cols])
        hh = self._table.horizontalHeader()
        for i, (_h, key, _a) in enumerate(cols):
            mode = (QHeaderView.ResizeMode.Stretch if key == stretch_key
                    else QHeaderView.ResizeMode.ResizeToContents)
            hh.setSectionResizeMode(i, mode)

    def _set_cell(self, r: int, c: int, text: str, align: str) -> None:
        item = QTableWidgetItem(text)
        a = Qt.AlignmentFlag.AlignRight if align == "r" else Qt.AlignmentFlag.AlignLeft
        item.setTextAlignment(a | Qt.AlignmentFlag.AlignVCenter)
        self._table.setItem(r, c, item)

    # ---- print -----------------------------------------------------------

    def _print(self) -> None:
        if self._last is None or self._on_print is None:
            return
        self._on_print(self._last)

    # ---- lifecycle -------------------------------------------------------

    def reload(self) -> None:
        """Refresh filter option lists (customers/warehouses may have changed)."""
        wh, cust = self._wh_combo.currentData(), self._cust_combo.currentData()
        self._populate_filters()
        i = self._wh_combo.findData(wh)
        if i >= 0:
            self._wh_combo.setCurrentIndex(i)
        j = self._cust_combo.findData(cust)
        if j >= 0:
            self._cust_combo.setCurrentIndex(j)

    def retranslate(self, translator: Translator) -> None:
        self._t = translator
        self._title.setText(translator.gettext("rep.title"))
        self._period_eyebrow.setText(translator.gettext("rep.period"))
        for k, b in self._preset_buttons.items():
            b.setText(translator.gettext(_PRESET_KEYS[k]))
        self._from_field.set_label(translator.gettext("rep.from"))
        self._to_field.set_label(translator.gettext("rep.to"))
        self._wh_field.set_label(translator.gettext("rep.warehouse"))
        self._cust_field.set_label(translator.gettext("rep.customer"))
        self._ps_field.set_label(translator.gettext("rep.payment_status"))
        self._kind_field.set_label(translator.gettext("rep.kind"))
        self._run_btn.setText(escape_amp(translator.gettext("rep.run")))
        for lab, key in ((self._g_lab, "rep.m_gross"), (self._p_lab, "rep.m_paid"),
                         (self._c_lab, "rep.m_credit"), (self._r_lab, "rep.m_returns"),
                         (self._n_lab, "rep.m_net")):
            lab.setText(translator.gettext(key))
        for view, key in (("detail", "rep.tab_detail"), ("daily", "rep.tab_daily"),
                          ("monthly", "rep.tab_monthly")):
            self._view_buttons[view].setText(translator.gettext(key))
        self._print_btn.setText(escape_amp(translator.gettext("rep.print")))
        self._close_btn.setText(escape_amp(translator.gettext("s4.act_close")))
        cur_wh, cur_cust = self._wh_combo.currentData(), self._cust_combo.currentData()
        cur_ps, cur_kind = self._ps_combo.currentData(), self._kind_combo.currentData()
        self._populate_filters()
        for combo, data in ((self._wh_combo, cur_wh), (self._cust_combo, cur_cust),
                            (self._ps_combo, cur_ps), (self._kind_combo, cur_kind)):
            i = combo.findData(data)
            if i >= 0:
                combo.setCurrentIndex(i)
        if self._last is not None:
            self._apply_summary(self._last["summary"])
            self._render()
