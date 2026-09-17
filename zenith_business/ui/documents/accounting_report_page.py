"""Financial Reports screen (Stage 09) — statements over the double-entry ledger.

Trial Balance, Profit & Loss, Balance Sheet, General Ledger, Cash & Bank and
Receivables / Payables. Built on the Stage 08 report screen's shape and its
A4-only sheet, so there is one report standard in the application rather than
three.

The period is From/To dates, with quick choices for the active financial year,
this year and this month. **There is no period close or year close** — out of
scope by instruction — so a balance sheet folds the period's own result into
equity rather than relying on a closing entry that does not exist.
"""

from __future__ import annotations

from datetime import date
from typing import Callable

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
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
    "trial_balance": ("acc.rep_trial_balance", [
        ("acc.col_code", "code", "l"), ("acc.col_account", "name", "l"),
        ("acc.col_opening", "opening", "r"), ("acc.col_debit", "debit", "r"),
        ("acc.col_credit", "credit", "r"), ("acc.col_closing", "closing", "r")]),
    "profit_loss": ("acc.rep_profit_loss", [
        ("acc.col_figure", "label", "l"), ("acc.col_amount", "amount", "r")]),
    "balance_sheet": ("acc.rep_balance_sheet", [
        ("acc.col_figure", "label", "l"), ("acc.col_amount", "amount", "r")]),
    "general_ledger": ("acc.rep_general_ledger", [
        ("acc.col_date", "date", "l"), ("acc.col_reference", "reference", "l"),
        ("acc.col_description", "description", "l"),
        ("acc.col_debit", "debit", "r"), ("acc.col_credit", "credit", "r"),
        ("acc.col_balance", "balance", "r")]),
    "cash_bank": ("acc.rep_cash_bank", [
        ("acc.col_code", "code", "l"), ("acc.col_account", "name", "l"),
        ("acc.col_opening", "opening", "r"), ("acc.col_in", "money_in", "r"),
        ("acc.col_out", "money_out", "r"), ("acc.col_closing", "closing", "r")]),
    "receivables": ("acc.rep_receivables", [
        ("acc.col_party_code", "party_code", "l"), ("acc.col_party", "name", "l"),
        ("acc.col_current", "current", "r"), ("acc.col_1_30", "d1_30", "r"),
        ("acc.col_31_60", "d31_60", "r"), ("acc.col_61_90", "d61_90", "r"),
        ("acc.col_90_plus", "d90_plus", "r"), ("acc.col_balance", "balance", "r")]),
    "payables": ("acc.rep_payables", [
        ("acc.col_party_code", "party_code", "l"), ("acc.col_party", "name", "l"),
        ("acc.col_current", "current", "r"), ("acc.col_1_30", "d1_30", "r"),
        ("acc.col_31_60", "d31_60", "r"), ("acc.col_61_90", "d61_90", "r"),
        ("acc.col_90_plus", "d90_plus", "r"), ("acc.col_balance", "balance", "r")]),
}

#: Keys rendered as money.
_MONEY_KEYS = {"opening", "debit", "credit", "closing", "amount", "balance",
               "money_in", "money_out", "current", "d1_30", "d31_60", "d61_90",
               "d90_plus"}

#: Quick period choices. The financial year leads: these are its statements.
_PERIODS: tuple[tuple[str, str], ...] = (
    ("acc.period_fy", "fy"),
    ("acc.period_year", "year"),
    ("acc.period_month", "month"),
    ("acc.period_custom", "custom"),
)


class AccountingReportPage(QWidget):
    def __init__(self, context, translator: Translator, *,
                 on_close: Callable[[], None] | None = None,
                 on_print: Callable[[dict], None] | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctx = context
        self._t = translator
        self._on_close = on_close
        self._on_print = on_print
        self._kind = "trial_balance"
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
        self._title = page_title(self._t.gettext("acc.reports_title"))
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
            # escape_amp: "Profit & Loss" would otherwise render as "Profit _Loss",
            # because Qt reads a lone & as a keyboard mnemonic.
            b = QPushButton(escape_amp(self._t.gettext(title_key)))
            b.setCheckable(True); b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _c=False, k=kind: self._set_kind(k))
            self._kind_buttons[kind] = b
            seg.addWidget(b)
        seg.addStretch(1)
        col.addLayout(seg)

        row = QHBoxLayout(); row.setSpacing(Spacing.MD)
        self._period_combo = QComboBox()
        for key, value in _PERIODS:
            self._period_combo.addItem(self._t.gettext(key), value)
        self._period_combo.currentIndexChanged.connect(self._on_period_changed)
        self._period_field = LabeledField(self._t.gettext("acc.f_period"),
                                          self._period_combo, width=FieldWidth.MD,
                                          compact=True)
        self._from_edit = self._date_edit()
        self._to_edit = self._date_edit()
        self._from_field = LabeledField(self._t.gettext("acc.f_from"), self._from_edit,
                                        width=FieldWidth.SM, compact=True)
        self._to_field = LabeledField(self._t.gettext("acc.f_to"), self._to_edit,
                                      width=FieldWidth.SM, compact=True)
        self._account_combo = QComboBox()
        self._account_combo.currentIndexChanged.connect(lambda _i: self.run())
        self._account_field = LabeledField(self._t.gettext("acc.f_account"),
                                           self._account_combo, width=FieldWidth.LG,
                                           compact=True)
        for w in (self._period_field, self._from_field, self._to_field,
                  self._account_field):
            row.addWidget(w)
        row.addStretch(1)
        col.addLayout(row)

        wrap = QWidget(); wrap.setLayout(col); wrap.setObjectName("AccRepFilter")
        wrap.setStyleSheet("#AccRepFilter { background: transparent; }")
        card.body.addWidget(wrap)
        self._populate_filters()
        self._apply_period("fy", run=False)
        self._set_kind("trial_balance", run=False)
        return card

    def _date_edit(self) -> QDateEdit:
        edit = QDateEdit()
        edit.setCalendarPopup(True)
        edit.setDisplayFormat("yyyy-MM-dd")
        edit.dateChanged.connect(lambda _d: self._on_date_typed())
        return edit

    def _populate_filters(self) -> None:
        self._account_combo.blockSignals(True)
        keep = self._account_combo.currentData()
        self._account_combo.clear()
        self._account_combo.addItem(self._t.gettext("acc.filter_all_accounts"), None)
        for a in self._ctx.accounting_repo.accounts():
            self._account_combo.addItem(f"{a['code']} — {a['name']}", a["id"])
        i = self._account_combo.findData(keep)
        if i >= 0:
            self._account_combo.setCurrentIndex(i)
        self._account_combo.blockSignals(False)

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

    # ---- period ----------------------------------------------------------

    def _on_period_changed(self, _index: int) -> None:
        self._apply_period(self._period_combo.currentData())

    def _apply_period(self, choice: str, *, run: bool = True) -> None:
        """Set the dates for a quick choice; 'custom' leaves them to the operator."""
        today = date.today()
        if choice == "fy":
            fy = self._active_financial_year()
            if fy is not None:
                start, end = fy["start_date"], fy["end_date"]
            else:
                start, end = today.replace(month=1, day=1).isoformat(), today.isoformat()
        elif choice == "year":
            start, end = today.replace(month=1, day=1).isoformat(), today.isoformat()
        elif choice == "month":
            start, end = today.replace(day=1).isoformat(), today.isoformat()
        else:
            if run:
                self.run()
            return
        for edit, value in ((self._from_edit, start), (self._to_edit, end)):
            edit.blockSignals(True)
            edit.setDate(QDate.fromString(value, "yyyy-MM-dd"))
            edit.blockSignals(False)
        if run:
            self.run()

    def _active_financial_year(self) -> dict | None:
        try:
            return self._ctx.financial_years.active()
        except Exception:
            return None

    def _on_date_typed(self) -> None:
        """Typing a date means the operator wants their own window."""
        i = self._period_combo.findData("custom")
        if i >= 0 and self._period_combo.currentIndex() != i:
            self._period_combo.blockSignals(True)
            self._period_combo.setCurrentIndex(i)
            self._period_combo.blockSignals(False)
        self.run()

    def _range(self) -> tuple[str, str]:
        return (self._from_edit.date().toString("yyyy-MM-dd"),
                self._to_edit.date().toString("yyyy-MM-dd"))

    # ---- running ---------------------------------------------------------

    def _set_kind(self, kind: str, *, run: bool = True) -> None:
        self._kind = kind
        for k, b in self._kind_buttons.items():
            b.setChecked(k == kind)
        # An account filter only means something for the general ledger; a
        # balance sheet and the ageing reports are a position on one date.
        self._account_field.setVisible(kind == "general_ledger")
        position_only = kind in ("balance_sheet", "receivables", "payables")
        self._from_field.setVisible(not position_only)
        if run:
            self.run()

    def run(self) -> None:
        svc = self._ctx.accounting_reports
        date_from, date_to = self._range()
        # (i18n key, value, column it belongs under, how to format it).
        summary: list[tuple[str, str, str, str]] = []
        rows: list[dict] = []

        if self._kind == "trial_balance":
            report = svc.trial_balance(date_from=date_from, date_to=date_to)
            rows = report["rows"]
            summary = [("acc.sum_debit", report["total_debit"], "debit", "money"),
                       ("acc.sum_credit", report["total_credit"], "credit", "money"),
                       ("acc.sum_balanced",
                        self._t.gettext("acc.yes" if report["balanced"] else "acc.no"),
                        "closing", "text")]
        elif self._kind == "profit_loss":
            report = svc.profit_loss(date_from=date_from, date_to=date_to)
            rows = self._profit_loss_rows(report)
            summary = [("acc.sum_net_profit", report["net_profit"],
                        "amount", "money")]
        elif self._kind == "balance_sheet":
            report = svc.balance_sheet(as_of=date_to)
            rows = self._balance_sheet_rows(report)
            summary = [("acc.sum_assets", report["total_assets"], "amount", "money"),
                       ("acc.sum_liab_equity", report["total_liabilities_equity"],
                        "amount", "money"),
                       ("acc.sum_balanced",
                        self._t.gettext("acc.yes" if report["balanced"] else "acc.no"),
                        "amount", "text")]
        elif self._kind == "general_ledger":
            report = svc.general_ledger(account_id=self._account_combo.currentData(),
                                        date_from=date_from, date_to=date_to)
            rows = report["rows"]
            # Opening and closing only mean something for ONE account; across
            # every account a running balance nets to zero and would read as a
            # figure rather than as "not applicable".
            summary = [("acc.sum_debit", report["total_debit"], "debit", "money"),
                       ("acc.sum_credit", report["total_credit"], "credit", "money")]
            if self._account_combo.currentData() is not None:
                summary = ([("acc.sum_opening", report["opening"], "debit", "money")]
                           + summary
                           + [("acc.sum_closing", report["closing"], "balance", "money")])
        elif self._kind == "cash_bank":
            report = svc.cash_bank(date_from=date_from, date_to=date_to)
            rows = report["accounts"]
            summary = [("acc.sum_in", report["total_in"], "money_in", "money"),
                       ("acc.sum_out", report["total_out"], "money_out", "money"),
                       ("acc.sum_closing", report["total_closing"], "closing", "money")]
        else:
            report = (svc.receivables(as_of=date_to) if self._kind == "receivables"
                      else svc.payables(as_of=date_to))
            rows = report["rows"]
            summary = [("acc.sum_total", report["total"], "balance", "money")]

        self._last = {
            "kind": self._kind, "rows": rows,
            "title": self._t.gettext(REPORTS[self._kind][0]),
            "columns": [(self._t.gettext(h), key, align)
                        for h, key, align in REPORTS[self._kind][1]],
            "period": f"{date_from} — {date_to}",
            "summary": [(self._t.gettext(k), self._summary_text(v, how), column)
                        for k, v, column, how in summary],
        }
        self._render(rows, self._last["summary"])

    @staticmethod
    def _summary_text(value, how: str) -> str:
        """Format by the caller's stated intent.

        Never by inspecting the value: ``D()`` turns anything unparseable into
        zero rather than raising, so a guess printed "Balanced: Yes" as
        "Balanced: 0.00".
        """
        return format_money(value) if how == "money" else str(value)

    def _profit_loss_rows(self, report: dict) -> list[dict]:
        """The statement as the reader checks it, one step per line."""
        t = self._t
        rows = [
            {"label": t.gettext("acc.pl_net_sales"), "amount": report["net_sales"]},
            {"label": t.gettext("acc.pl_cogs"), "amount": report["cogs"]},
            {"label": t.gettext("acc.pl_gross_profit"), "amount": report["gross_profit"]},
        ]
        for row in report["expense_rows"]:
            rows.append({"label": f"   {row['code']} {row['name']}",
                         "amount": row["amount"]})
        rows.append({"label": t.gettext("acc.pl_expenses"),
                     "amount": report["operating_expenses"]})
        if D(report["other_income"]) != 0:
            rows.append({"label": t.gettext("acc.pl_other_income"),
                         "amount": report["other_income"]})
        rows.append({"label": t.gettext("acc.pl_net_profit"),
                     "amount": report["net_profit"]})
        return rows

    def _balance_sheet_rows(self, report: dict) -> list[dict]:
        t = self._t
        rows: list[dict] = [{"label": t.gettext("acc.bs_assets"), "amount": ""}]
        for row in report["assets"]:
            rows.append({"label": f"   {row['code']} {row['name']}",
                         "amount": row["amount"]})
        rows.append({"label": t.gettext("acc.bs_total_assets"),
                     "amount": report["total_assets"]})
        rows.append({"label": t.gettext("acc.bs_liabilities"), "amount": ""})
        for row in report["liabilities"]:
            rows.append({"label": f"   {row['code']} {row['name']}",
                         "amount": row["amount"]})
        rows.append({"label": t.gettext("acc.bs_total_liabilities"),
                     "amount": report["total_liabilities"]})
        rows.append({"label": t.gettext("acc.bs_equity"), "amount": ""})
        for row in report["equity"]:
            # The period's own result has no account of its own until a year
            # close exists, so it is named rather than shown with a blank code.
            label = (t.gettext("acc.bs_result") if row["name"] == "__result__"
                     else f"   {row['code']} {row['name']}")
            rows.append({"label": label, "amount": row["amount"]})
        rows.append({"label": t.gettext("acc.bs_total_equity"),
                     "amount": report["total_equity"]})
        rows.append({"label": t.gettext("acc.bs_total_liab_equity"),
                     "amount": report["total_liabilities_equity"]})
        return rows

    def _render(self, rows: list[dict], summary: list[tuple[str, str, str]]) -> None:
        cols = REPORTS[self._kind][1]
        self._table.setColumnCount(len(cols))
        self._table.setHorizontalHeaderLabels([self._t.gettext(h) for h, _k, _a in cols])
        hh = self._table.horizontalHeader()
        stretch = next((k for _h, k, _a in cols
                        if k in ("name", "label", "description")), None)
        for i, (_h, key, _a) in enumerate(cols):
            hh.setSectionResizeMode(
                i, QHeaderView.ResizeMode.Stretch if key == stretch
                else QHeaderView.ResizeMode.ResizeToContents)
        self._table.setRowCount(0)
        self._table.setRowCount(len(rows))
        for r, data in enumerate(rows):
            for c, (_h, key, align) in enumerate(cols):
                value = data.get(key)
                text = ("" if value is None or str(value) == ""
                        else (format_money(value) if key in _MONEY_KEYS else str(value)))
                item = QTableWidgetItem(text)
                a = (Qt.AlignmentFlag.AlignRight if align == "r"
                     else Qt.AlignmentFlag.AlignLeft)
                item.setTextAlignment(a | Qt.AlignmentFlag.AlignVCenter)
                self._table.setItem(r, c, item)
        parts = [f"{label}: {value}" for label, value, _column in summary]
        self._status.setText("   ·   ".join(parts) if parts
                             else self._t.gettext("inv.empty"))

    def _print(self) -> None:
        if self._last is None or self._on_print is None:
            return
        self._on_print(self._last)

    def reload(self) -> None:
        self._populate_filters()
        self.run()

    def retranslate(self, translator: Translator) -> None:
        self._t = translator
        self._title.setText(translator.gettext("acc.reports_title"))
        for kind, b in self._kind_buttons.items():
            b.setText(escape_amp(translator.gettext(REPORTS[kind][0])))
        self._period_field.set_label(translator.gettext("acc.f_period"))
        self._from_field.set_label(translator.gettext("acc.f_from"))
        self._to_field.set_label(translator.gettext("acc.f_to"))
        self._account_field.set_label(translator.gettext("acc.f_account"))
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
