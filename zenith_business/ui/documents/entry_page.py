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
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
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
    LabeledField,
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
        # Sales support both a registered customer account and an unregistered
        # walk-in/general customer (defect #2). Purchases keep the single party flow.
        self._customer_mode = "registered"  # 'registered' | 'walkin'
        self._rendering = False  # guards itemChanged during programmatic fills
        self._prev_balance = D(0)  # party's balance before this invoice (round 2)
        self._correction_sale_id: int | None = None  # set when correcting a posted sale

        self.setProperty("role", "workspace")
        root = QVBoxLayout(self)
        root.setContentsMargins(Spacing.MD, Spacing.XS, Spacing.MD, Spacing.XS)
        root.setSpacing(Spacing.XXS)  # tight so the items table keeps the space (§5)

        root.addLayout(self._build_titlebar())
        # The line grid (stretch, internal scroll, floored min-height) absorbs any
        # vertical squeeze, so the totals band and the action bar below it stay
        # visible on small windows while the grand total is always in view.
        root.addWidget(self._build_header())
        root.addWidget(self._build_grid_card(), stretch=1)  # entry row + line grid
        root.addLayout(self._build_bottom_band())
        root.addWidget(self._build_action_bar())

        self._reload_meta_sources()
        if self._mode == "sale":
            self._set_customer_mode("registered")  # initial visual + field state
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
        self._status_msg = QLabel("")
        self._status_msg.setProperty("role", "secondary")
        row.addWidget(self._status_msg)
        self._kbd_note = muted(self._t.gettext("s4.keyboard_hint"))
        row.addWidget(self._kbd_note)
        return row

    # ---- header (party + meta) ------------------------------------------

    def _build_header(self) -> QWidget:
        card = Card(role="section"); card.setProperty("accent", "navy"); apply_shadow(card)
        # Compact header so the dominant items table keeps the vertical space (§5).
        card.body.setContentsMargins(Spacing.CARD_PAD_H, Spacing.XS, Spacing.CARD_PAD_H, Spacing.XS)
        card.body.setSpacing(Spacing.XXS)
        # Minimum (not Maximum) vertical policy: the header takes exactly its
        # content height and never grows to steal the table's space — but it must
        # NEVER be compressed below its content either, otherwise the (taller)
        # walk-in panel gets clipped when the Expanding items table is greedy.
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        t = self._t

        # Retained for retranslate but shown inline (no separate row) to save height.
        self._step_customer = eyebrow(t.gettext(
            "s4.step_customer" if self._mode == "sale" else "s4.step_supplier"))
        self._step_customer.setVisible(False)
        # Customer-type toggle (sales only): registered account vs walk-in/general.
        if self._mode == "sale":
            self._seg_registered = secondary_button(t.gettext("s4.mode_registered"))
            self._seg_walkin = secondary_button(t.gettext("s4.mode_walkin"))
            for b in (self._seg_registered, self._seg_walkin):
                b.setProperty("segmented", True)
                b.setCursor(Qt.CursorShape.PointingHandCursor)
            self._seg_registered.clicked.connect(lambda: self._set_customer_mode("registered"))
            self._seg_walkin.clicked.connect(lambda: self._set_customer_mode("walkin"))

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
        self._registered_wrap = QWidget(); self._registered_wrap.setLayout(col)
        self._registered_wrap.setStyleSheet("background: transparent;")
        self._registered_wrap.setMinimumWidth(int(FieldWidth.LG))
        prow.addWidget(self._registered_wrap, 2)

        self._chip_phone = self._info_chip("si.phone", "—", "neutral")
        bal_key = "si.prev_balance" if self._mode == "sale" else "s4.supplier_ref"
        self._chip_balance = self._info_chip(bal_key, "—", "neutral")
        prow.addWidget(self._chip_phone)
        prow.addWidget(self._chip_balance)
        prow.addStretch(1)
        # Customer-type toggle sits inline at the end of the customer row (sales).
        if self._mode == "sale":
            prow.addWidget(self._seg_registered)
            prow.addWidget(self._seg_walkin)
        card.body.addLayout(prow)

        # Walk-in / general customer panel (sales only) — a clearly identifiable,
        # bordered area so the operator immediately knows this is where to type an
        # UNREGISTERED customer's details. Hidden until Walk-in mode is chosen; the
        # entered details are snapshotted onto the sale.
        if self._mode == "sale":
            panel = QFrame()
            panel.setObjectName("WalkinPanel")
            # Scope the tint to the panel itself (object-name selector) so it does
            # not cascade onto the child inputs and strip their white fill.
            panel.setStyleSheet(
                "QFrame#WalkinPanel { background: #eef4fb; border: 1px solid #c8d7ec;"
                " border-radius: 8px; }")
            pv = QVBoxLayout(panel)
            pv.setContentsMargins(Spacing.CARD_PAD_H, Spacing.SM,
                                  Spacing.CARD_PAD_H, Spacing.SM)
            pv.setSpacing(Spacing.SM)
            self._walkin_head = eyebrow(t.gettext("s4.walkin_head"))
            self._walkin_head.setWordWrap(True)
            pv.addWidget(self._walkin_head)

            self._walkin_name = QLineEdit()
            self._walkin_name.setPlaceholderText(t.gettext("s4.walkin_name_ph"))
            self._walkin_phone = QLineEdit()
            self._walkin_address = QLineEdit()
            # Full-height labelled fields (NOT compact) with a sensible minimum
            # width each, then share the remaining width by stretch factor:
            # Address/Note widest, then Name, then Phone. No fixed pixel geometry.
            walkin_specs = [
                ("s4.walkin_name", self._walkin_name, FieldWidth.MD, 3),
                ("s4.walkin_phone", self._walkin_phone, FieldWidth.SM, 2),
                ("s4.walkin_address", self._walkin_address, FieldWidth.MD, 4),
            ]
            wrow = QHBoxLayout(); wrow.setSpacing(Spacing.LG)
            self._walkin_lfs: list[tuple[str, LabeledField]] = []
            for key, ctrl, minw, stretch in walkin_specs:
                ctrl.setMinimumWidth(int(minw))
                # An enforced minimum HEIGHT is what stops the inputs collapsing /
                # clipping when the panel is under vertical pressure.
                ctrl.setMinimumHeight(int(ControlSize.INPUT_HEIGHT))
                ctrl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                lf = LabeledField(t.gettext(key), ctrl)
                lf.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                self._walkin_lfs.append((key, lf))
                wrow.addWidget(lf, stretch)
            pv.addLayout(wrow)
            self._walkin_wrap = panel
            # The panel demands its full content height (sizeHint = minimum) so it
            # can never be squeezed/clipped by the greedy items table below.
            panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
            self._walkin_wrap.setVisible(False)
            self._walkin_name.returnPressed.connect(self._item_focus)
            card.body.addWidget(self._walkin_wrap)

        # Secondary metadata strip — quieter compact fields (Stage 01 §8 hierarchy).
        meta = QHBoxLayout(); meta.setSpacing(Spacing.LG)
        self._invoice_no = QLineEdit(t.gettext("s4.auto")); self._invoice_no.setReadOnly(True)
        self._date_edit = QLineEdit(self._ctx_today())
        self._wh_combo = QComboBox()
        self._currency_combo = QComboBox()
        self._rate_edit = QLineEdit("1")
        self._rate_edit.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._meta_fields: list[tuple[str, LabeledField]] = []
        specs = [
            ("si.invoice_no", self._invoice_no, FieldWidth.SM),
            ("si.date", self._date_edit, FieldWidth.SM),
            ("si.warehouse", self._wh_combo, FieldWidth.MD),
            ("si.currency", self._currency_combo, FieldWidth.SM),
            ("si.rate", self._rate_edit, FieldWidth.XS),
        ]
        for key, ctrl, width in specs:
            lf = LabeledField(t.gettext(key), ctrl, width=width, compact=True)
            self._meta_fields.append((key, lf))
            meta.addWidget(lf)
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

    def _item_focus(self) -> None:
        if hasattr(self, "_item_selector"):
            self._item_selector.focus()

    def _set_customer_mode(self, mode: str) -> None:
        """Toggle between a registered customer account and a walk-in customer."""
        if self._mode != "sale":
            return
        self._customer_mode = mode
        registered = mode == "registered"
        self._registered_wrap.setVisible(registered)
        self._chip_phone.setVisible(registered)
        self._chip_balance.setVisible(registered)
        self._walkin_wrap.setVisible(not registered)
        self._seg_registered.setProperty("variant", "accent" if registered else "plain")
        self._seg_walkin.setProperty("variant", "accent" if not registered else "plain")
        for b in (self._seg_registered, self._seg_walkin):
            b.style().unpolish(b); b.style().polish(b)
        # Never carry stale identity from the other mode into a posted sale.
        if registered:
            for e in (self._walkin_name, self._walkin_phone, self._walkin_address):
                e.clear()
        else:
            self._party_id = None
            self._party_selector.clear()
            self._set_chip(self._chip_phone, "—", "neutral")
            self._set_chip(self._chip_balance, "—", "neutral")
            self._walkin_name.setFocus()

    # ---- entry strip -----------------------------------------------------

    def _num_edit(self, ph: str) -> QLineEdit:
        e = QLineEdit(); e.setPlaceholderText(ph)
        e.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return e

    # ---- grid (entry row + committed lines) ------------------------------

    def _grid_headers(self) -> list[str]:
        return ["si.col_row", "si.col_item_code", "si.col_item_name", "si.col_unit",
                "si.col_qty", "si.col_price", "si.col_discount", "si.col_total",
                "si.col_warehouse"]

    def _build_entry_row(self) -> QHBoxLayout:
        """A single compact add-line row; the grid headers below are the guide."""
        row = QHBoxLayout(); row.setSpacing(Spacing.SM)
        self._item_selector = SearchSelector(
            self._ctx.item_search, placeholder=self._t.gettext("s4.item_search_ph"),
            display_index=1, panel_width=520)
        self._item_selector.rowSelected.connect(self._on_item_selected)
        row.addWidget(self._item_selector, 1)

        # Per-line Unit selector so the operator can confirm/replace the unit
        # (round 2 §6). Defaults to the item's base unit on selection.
        self._unit_combo = QComboBox(); self._unit_combo.setFixedWidth(int(FieldWidth.SM))
        row.addWidget(self._unit_combo)

        self._qty_edit = self._num_edit(self._t.gettext("si.col_qty"))
        self._price_edit = self._num_edit(self._t.gettext("si.col_price"))
        self._disc_edit = self._num_edit(self._t.gettext("si.col_discount"))
        for ctrl, width in ((self._qty_edit, FieldWidth.XS), (self._price_edit, FieldWidth.SM),
                            (self._disc_edit, FieldWidth.XS)):
            ctrl.setFixedWidth(int(width)); row.addWidget(ctrl)

        self._add_btn = secondary_button(self._t.gettext("s4.add_line"))
        self._add_btn.setProperty("variant", "accent")
        self._add_btn.setIcon(standard_icon("next"))
        self._add_btn.clicked.connect(self._commit_line)
        row.addWidget(self._add_btn)

        self._qty_edit.returnPressed.connect(self._price_edit.setFocus)
        self._price_edit.returnPressed.connect(self._disc_edit.setFocus)
        self._disc_edit.returnPressed.connect(self._commit_line)
        return row

    def _build_grid_card(self) -> QWidget:
        card = Card(role="section"); card.setProperty("accent", "brand"); apply_shadow(card)
        # The grid card must EXPAND to hold the dominant items table; a Preferred
        # policy would size to content and clip the table (round 2 §5).
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        card.body.setContentsMargins(Spacing.CARD_PAD_H, Spacing.XS, Spacing.CARD_PAD_H, Spacing.XS)
        card.body.setSpacing(Spacing.XS)
        # Edit/Delete buttons live on the single entry-strip row (no separate
        # toolbar row) so the items table keeps the maximum vertical space (§5).
        self._btn_edit = secondary_button(self._t.gettext("s4.edit_line"))
        self._btn_edit.setIcon(standard_icon("edit"))
        self._btn_edit.clicked.connect(self._edit_selected)
        self._btn_delete = secondary_button(self._t.gettext("s4.delete_line"))
        self._btn_delete.setProperty("variant", "danger")
        self._btn_delete.clicked.connect(self._delete_selected)
        # Retained (referenced by retranslate) but shown as a compact hint on the
        # search field rather than their own row.
        self._lines_title = QLabel(self._t.gettext("s4.add_item")); self._lines_title.setVisible(False)
        self._edit_hint = muted(self._t.gettext("s4.edit_hint")); self._edit_hint.setVisible(False)
        strip = self._build_entry_row()
        strip.addWidget(self._btn_edit)
        strip.addWidget(self._btn_delete)
        card.body.addLayout(strip)

        self._table = QTableWidget(0, 9)
        self._table.setHorizontalHeaderLabels([self._t.gettext(k) for k in self._grid_headers()])
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        # Qty / Price / Discount are editable in place (double-click or type); other
        # columns are read-only. Double-clicking an item cell reloads the whole line
        # into the entry strip so the item itself can be replaced (defect #3).
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed)
        self._table.itemChanged.connect(self._on_cell_changed)
        self._table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setDefaultSectionSize(ControlSize.TABLE_ROW_HEIGHT + 2)
        # The line grid is the DOMINANT central area of the invoice (round 2 §5):
        # a generous floor keeps ~7-8 rows visible even under the fixed header/totals
        # at 1024×768, and its root stretch lets it grow (with internal scrolling for
        # 10+ lines) so secondary controls never squeeze the invoice lines.
        # A modest floor keeps the table usable; the Expanding policy lets it grow
        # to dominate the screen at larger resolutions and scroll internally when
        # short. The floor is deliberately below the header's needs so the grid —
        # not the header — absorbs any vertical squeeze at 1366×768 (otherwise the
        # taller walk-in panel in the header gets clipped). The table stays the
        # dominant, growing area at every normal window size via the Expanding
        # policy; only its *floor* is modest.
        self._table.setMinimumHeight(100)
        self._table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        from PyQt6.QtWidgets import QHeaderView
        header = self._table.horizontalHeader()
        header.setHighlightSections(False)
        header.setSectionResizeMode(C_NAME, QHeaderView.ResizeMode.Stretch)
        widths = {C_NO: 40, C_CODE: 100, C_UNIT: 60, C_QTY: 80, C_PRICE: 110,
                  C_DISC: 90, C_TOTAL: 120, C_WH: 110}
        for col, w in widths.items():
            self._table.setColumnWidth(col, w)
        card.body.addWidget(self._table, 1)  # table takes the card's growth
        return card

    # ---- bottom totals strip (compact, always visible) ------------------

    def _inline(self, key: str) -> tuple[QLabel, QLabel, QWidget]:
        """An inline ``label: value`` metric (keeps the totals strip one row)."""
        lab = field_label(self._t.gettext(key))
        val = QLabel("—"); val.setProperty("role", "total-value")
        h = QHBoxLayout(); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(Spacing.XS)
        h.addWidget(lab); h.addWidget(val)
        holder = QWidget(); holder.setLayout(h); holder.setStyleSheet("background: transparent;")
        return lab, val, holder

    def _build_bottom_band(self) -> QHBoxLayout:
        """A compact two-row totals/payment/balance strip (reference lower area):
        row 1 = item totals + grand total, row 2 = payment + customer balance. Both
        stay visible while the dominant line grid keeps the vertical space."""
        t = self._t
        card = Card(role="section"); card.setProperty("accent", "brand"); apply_shadow(card)
        card.body.setContentsMargins(Spacing.CARD_PAD_H, Spacing.XS, Spacing.CARD_PAD_H, Spacing.XS)
        card.body.setSpacing(Spacing.XXS)
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        # -- row 1: item count, subtotal, discount, cash/credit, grand total --
        row = QHBoxLayout(); row.setSpacing(Spacing.XL)
        self._items_label, self._items_value, items_w = self._inline("s4.items")
        self._sub_label, self._sub_value, sub_w = self._inline("si.subtotal")
        self._disc_label, self._disc_value, disc_w = self._inline("si.discount")
        for w in (items_w, sub_w, disc_w):
            row.addWidget(w)
        row.addStretch(1)
        self._seg_cash = chip(t.gettext("si.pay_cash"), "success")
        self._seg_credit = chip(t.gettext("si.pay_credit"), "neutral")
        row.addWidget(self._seg_cash); row.addWidget(self._seg_credit)
        gt = QFrame(); gt.setProperty("role", "grand-total-strong")
        gtl = QHBoxLayout(gt); gtl.setContentsMargins(Spacing.LG, Spacing.XS, Spacing.LG, Spacing.XS)
        gtl.setSpacing(Spacing.MD)
        self._grand_label = QLabel(t.gettext("si.grand_total")); self._grand_label.setProperty("role", "gts-label")
        self._grand_value = QLabel("—"); self._grand_value.setProperty("role", "gts-value")
        gtl.addWidget(self._grand_label); gtl.addWidget(self._grand_value)
        row.addWidget(gt)
        card.body.addLayout(row)

        # -- row 2: previous balance, amount paid, remaining, updated balance --
        row2 = QHBoxLayout(); row2.setSpacing(Spacing.XL)
        self._prev_label, self._prev_value, prev_w = self._inline("si.prev_balance")
        row2.addWidget(prev_w)
        row2.addStretch(1)
        self._recv_label = QLabel(t.gettext("s4.amount_paid")); self._recv_label.setProperty("role", "total-label")
        self._recv_edit = self._num_edit("0.00"); self._recv_edit.setFixedWidth(int(FieldWidth.SM))
        self._recv_edit.textEdited.connect(self._recompute_totals)
        row2.addWidget(self._recv_label); row2.addWidget(self._recv_edit)
        self._rem_label = QLabel(t.gettext("si.remaining")); self._rem_label.setProperty("role", "total-label")
        self._rem_value = QLabel("—"); self._rem_value.setProperty("role", "total-value")
        self._rem_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row2.addWidget(self._rem_label); row2.addWidget(self._rem_value)
        self._upd_label, self._upd_value, upd_w = self._inline("si.updated_balance")
        row2.addWidget(upd_w)
        card.body.addLayout(row2)

        band = QHBoxLayout(); band.addWidget(card)
        return band

    # ---- action bar ------------------------------------------------------

    def _build_action_bar(self) -> QWidget:
        bar = QFrame(); bar.setProperty("role", "actionbar")
        apply_shadow(bar, blur=18, y=3, alpha=30)
        row = QHBoxLayout(bar)
        row.setContentsMargins(Spacing.LG, Spacing.SM, Spacing.LG, Spacing.SM)
        row.setSpacing(Spacing.SM)
        self._btn_new = secondary_button(self._t.gettext("s4.act_new"))
        self._btn_new.setIcon(standard_icon("new"))
        self._btn_new.clicked.connect(self.reset_form)
        self._btn_post = primary_button(self._t.gettext("s4.act_post"))
        self._btn_post.setIcon(standard_icon("save"))
        self._btn_post.clicked.connect(lambda: self._post(print_after=False))
        self._btn_post_print = secondary_button(self._t.gettext("s4.act_post_print"))
        self._btn_post_print.setIcon(standard_icon("print"))
        self._btn_post_print.clicked.connect(lambda: self._post(print_after=True))
        self._error = QLabel(""); self._error.setProperty("role", "error")
        self._error.setVisible(False)
        for b in (self._btn_new, self._btn_post, self._btn_post_print):
            row.addWidget(b)
        row.addSpacing(Spacing.MD)
        row.addWidget(self._error)
        row.addStretch(1)
        self._btn_close = secondary_button(self._t.gettext("s4.act_close"))
        self._btn_close.setIcon(standard_icon("close"))
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
        # Per-line unit choices (round 2 §6): label by symbol, fall back to name.
        cur_unit = self._unit_combo.currentData()
        self._unit_combo.clear()
        rtl = self._t.direction.name == "RTL" if hasattr(self._t, "direction") else False
        for u in self._ctx.units_repo.list_all():
            label = (u.get("name_fa") if rtl else u.get("name_en")) or u.get("symbol") or u["code"]
            self._unit_combo.addItem(label, u["id"])
        if cur_unit is not None:
            idx = self._unit_combo.findData(cur_unit)
            if idx >= 0:
                self._unit_combo.setCurrentIndex(idx)

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
            bal = self._ctx.purchase_documents.payable(self._party_id)
            positive = D(bal) > 0
            self._set_chip(self._chip_balance, format_money(bal),
                           "warning" if positive else "success")
        self._prev_balance = D(bal)
        self._recompute_totals()

    # ---- item / line entry ----------------------------------------------

    def _on_item_selected(self, row: SearchRow) -> None:
        p = row.payload
        self._pending_item = p
        if self._mode == "sale" and p.get("sale_price") is not None:
            self._price_edit.setText(format_money(p["sale_price"]).replace(",", ""))
        base_unit = p.get("base_unit_id")
        if base_unit is not None:
            idx = self._unit_combo.findData(base_unit)
            if idx >= 0:
                self._unit_combo.setCurrentIndex(idx)
        if not self._qty_edit.text():
            self._qty_edit.setText("1")
        self._qty_edit.setFocus(); self._qty_edit.selectAll()

    def _current_unit(self, fallback) -> tuple[int, str]:
        uid = self._unit_combo.currentData()
        if uid is None:
            return fallback, ""
        return uid, self._unit_combo.currentText()

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
        unit_id, unit_label = self._current_unit(payload.get("base_unit_id"))
        self._lines.append({
            "item_id": payload["item_id"], "unit_id": unit_id,
            "code": payload.get("item_code", ""), "name": payload.get("name", ""),
            "unit": unit_label or payload.get("unit_symbol") or "",
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

    _EDITABLE_COLS = {C_QTY, C_PRICE, C_DISC}

    def _render_lines(self) -> None:
        self._rendering = True  # suppress itemChanged during the programmatic fill
        try:
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
                    flags = item.flags()
                    if col in self._EDITABLE_COLS:
                        flags |= Qt.ItemFlag.ItemIsEditable
                    else:
                        flags &= ~Qt.ItemFlag.ItemIsEditable
                    item.setFlags(flags)
                    self._table.setItem(r, col, item)
        finally:
            self._rendering = False

    def _on_cell_changed(self, item: QTableWidgetItem) -> None:
        """Inline edit of qty/price/discount — recompute the line + all totals."""
        if self._rendering:
            return
        r, col = item.row(), item.column()
        if not (0 <= r < len(self._lines)) or col not in self._EDITABLE_COLS:
            return
        raw = (item.text() or "").replace(",", "").strip()
        ln = self._lines[r]
        try:
            c = compute_line(
                raw if col == C_QTY else ln["qty"],
                raw if col == C_PRICE else ln["price"],
                raw if col == C_DISC else ln["discount"])
        except ZenithError as exc:
            self._show_error(getattr(exc, "user_message", None) or str(exc))
            self._render_lines()  # revert to the last valid values
            return
        ln["qty"] = str(c.quantity); ln["price"] = str(c.unit_price)
        ln["discount"] = str(c.discount); ln["total"] = str(c.line_total)
        self.clear_error()
        self._render_lines()
        self._recompute_totals()

    def _on_cell_double_clicked(self, row: int, col: int) -> None:
        # Double-clicking a non-editable cell (e.g. the item name) reloads the whole
        # line into the entry strip so the item itself can be replaced.
        if col not in self._EDITABLE_COLS:
            self._edit_selected()

    def _edit_selected(self, *_a) -> None:
        r = self._table.currentRow()
        if not (0 <= r < len(self._lines)):
            return
        ln = self._lines[r]
        self._pending_item = {
            "item_id": ln["item_id"], "base_unit_id": ln["unit_id"],
            "item_code": ln["code"], "name": ln["name"], "unit_symbol": ln["unit"],
            "sale_price": ln["price"]}
        self._item_selector.set_text(ln["name"])
        idx = self._unit_combo.findData(ln["unit_id"])
        if idx >= 0:
            self._unit_combo.setCurrentIndex(idx)
        self._qty_edit.setText(ln["qty"]); self._price_edit.setText(ln["price"])
        self._disc_edit.setText(ln["discount"])
        self._lines.pop(r)  # re-committing the entry strip re-adds the edited line
        self._render_lines()
        self._recompute_totals()
        self._qty_edit.setFocus(); self._qty_edit.selectAll()

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
        self._items_value.setText(str(len(self._lines)))
        self._sub_value.setText(format_money(subtotal))
        self._disc_value.setText(format_money(discount))
        self._grand_value.setText(format_money(grand))
        try:
            paid = money(self._recv_edit.text() or "0")
        except Exception:
            paid = D(0)
        remaining = money(grand - paid)
        self._rem_value.setText(format_money(remaining))
        self._rem_value.setProperty("money", "negative" if remaining > 0 else "positive")
        self._rem_value.style().unpolish(self._rem_value)
        self._rem_value.style().polish(self._rem_value)
        # cash when fully settled, otherwise credit (mirrors the Stage 01 demo).
        cash = remaining <= 0 and grand > 0
        self._seg_cash.setProperty("chip", "success" if cash else "neutral")
        self._seg_credit.setProperty("chip", "neutral" if cash else "warning")
        for c in (self._seg_cash, self._seg_credit):
            c.style().unpolish(c); c.style().polish(c)
        # Previous balance and the balance this invoice would leave the customer
        # (round 2): the unpaid remainder adds to what they owe.
        self._prev_value.setText(format_money(self._prev_balance))
        self._upd_value.setText(format_money(self._prev_balance + remaining))

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
                walkin = self._customer_mode == "walkin"
                sale_kwargs = dict(
                    currency_code=currency_code, lines=lines,
                    party_id=None if walkin else self._party_id,
                    warehouse_id=wh_id, amount_paid=paid, exchange_rate=rate, sale_date=date,
                    walkin_name=self._walkin_name.text() if walkin else None,
                    walkin_phone=self._walkin_phone.text() if walkin else None,
                    walkin_address=self._walkin_address.text() if walkin else None)
                if self._correction_sale_id is not None:
                    # Safe correction of a posted invoice: voids the original and
                    # posts this replacement atomically (round 2 §9).
                    posted = self._ctx.sales_documents.correct_sale(
                        sale_id=self._correction_sale_id, **sale_kwargs)
                else:
                    posted = self._ctx.sales_documents.post_sale(**sale_kwargs)
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
        was_correction = self._correction_sale_id is not None
        self._status_msg.setText(self._t.gettext(
            "s4.msg_corrected" if was_correction else "s4.msg_posted").replace(
            "{no}", posted.document_no))
        self.reset_form()
        if print_after and self._on_print is not None:
            self._on_print(posted.id)

    def reset_form(self) -> None:
        self._lines = []
        self._party_id = None
        self._pending_item = None
        self._correction_sale_id = None
        self._prev_balance = D(0)
        self._render_lines()
        self._party_selector.clear()
        self._item_selector.clear()
        self._set_chip(self._chip_phone, "—", "neutral")
        self._set_chip(self._chip_balance, "—", "neutral")
        self._qty_edit.clear(); self._price_edit.clear(); self._disc_edit.clear()
        self._recv_edit.clear()
        self._date_edit.setText(self._ctx_today())
        self._title.setText(self._t.gettext(self._title_key()))
        if self._mode == "sale":
            self._set_customer_mode("registered")  # back to the default customer mode
        self._recompute_totals()

    # ---- load a posted sale for safe correction (round 2 §9) ------------

    def load_for_correction(self, sale_id: int) -> None:
        """Load a posted sale into the form so it can be corrected. Saving posts a
        replacement invoice and voids the original (see ``correct_sale``)."""
        sale = self._ctx.sales_repo.get(sale_id)
        if sale is None or sale.get("status") != "POSTED":
            self._show_error(self._t.gettext("s4.msg_correct_only_posted"))
            return
        self.reset_form()
        self._correction_sale_id = sale_id
        # currency / date / warehouse
        cur = self._ctx.currencies_repo.get(sale["currency_id"])
        if cur is not None:
            i = self._currency_combo.findData(cur["code"])
            if i >= 0:
                self._currency_combo.setCurrentIndex(i)
        self._date_edit.setText(sale["sale_date"])
        self._rate_edit.setText(str(sale.get("exchange_rate") or "1"))
        if sale.get("warehouse_id") is not None:
            i = self._wh_combo.findData(sale["warehouse_id"])
            if i >= 0:
                self._wh_combo.setCurrentIndex(i)
        # customer: registered vs walk-in snapshot
        if sale.get("party_id"):
            party = self._ctx.parties_repo.get(sale["party_id"])
            self._set_customer_mode("registered")
            self._party_id = sale["party_id"]
            if party is not None:
                self._party_selector.set_text(party.get("name") or "")
                self._set_chip(self._chip_phone, party.get("phone") or "—", "neutral")
                bal = self._ctx.sales_documents.receivable(self._party_id)
                self._prev_balance = D(bal)
                self._set_chip(self._chip_balance, format_money(bal),
                               "danger" if D(bal) > 0 else "success")
        elif sale.get("walkin_name"):
            self._set_customer_mode("walkin")
            self._walkin_name.setText(sale.get("walkin_name") or "")
            self._walkin_phone.setText(sale.get("walkin_phone") or "")
            self._walkin_address.setText(sale.get("walkin_address") or "")
        # lines
        unit_by_id = {u["id"]: u for u in self._ctx.units_repo.list_all()}
        for ln in self._ctx.sales_repo.lines_for(sale_id):
            item = self._ctx.items_repo.get(ln["item_id"]) or {}
            unit = unit_by_id.get(ln["unit_id"], {})
            self._lines.append({
                "item_id": ln["item_id"], "unit_id": ln["unit_id"],
                "code": item.get("item_code", ""), "name": item.get("name", ""),
                "unit": unit.get("symbol") or unit.get("name_en") or "",
                "qty": str(ln["quantity"]), "price": str(ln["unit_price"]),
                "discount": str(ln["discount"]), "total": str(ln["line_total"]),
                "wh_id": ln.get("warehouse_id"),
                "wh_name": self._wh_combo.currentText()})
        self._recv_edit.setText(str(sale.get("amount_paid") or "0"))
        self._render_lines()
        self._recompute_totals()
        self._title.setText(
            self._t.gettext("s4.correcting").replace("{no}", sale["document_no"]))

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
        self._party_eyebrow.setText(
            translator.gettext("s4.customer" if self._mode == "sale" else "s4.supplier"))
        self._party_selector.line_edit.setPlaceholderText(translator.gettext(
            "s4.customer_search_ph" if self._mode == "sale" else "s4.supplier_search_ph"))
        self._item_selector.line_edit.setPlaceholderText(translator.gettext("s4.item_search_ph"))
        self._qty_edit.setPlaceholderText(translator.gettext("si.col_qty"))
        self._price_edit.setPlaceholderText(translator.gettext("si.col_price"))
        self._disc_edit.setPlaceholderText(translator.gettext("si.col_discount"))
        self._table.setHorizontalHeaderLabels([translator.gettext(k) for k in self._grid_headers()])
        self._lines_title.setText(translator.gettext("s4.add_item"))
        self._edit_hint.setText(translator.gettext("s4.edit_hint"))
        self._btn_edit.setText(escape_amp(translator.gettext("s4.edit_line")))
        self._btn_delete.setText(escape_amp(translator.gettext("s4.delete_line")))
        self._step_customer.setText(translator.gettext(
            "s4.step_customer" if self._mode == "sale" else "s4.step_supplier"))
        if self._mode == "sale":
            self._seg_registered.setText(escape_amp(translator.gettext("s4.mode_registered")))
            self._seg_walkin.setText(escape_amp(translator.gettext("s4.mode_walkin")))
            self._walkin_head.setText(translator.gettext("s4.walkin_head"))
            self._walkin_name.setPlaceholderText(translator.gettext("s4.walkin_name_ph"))
            for key, lf in self._walkin_lfs:
                lf.set_label(translator.gettext(key))
        self._items_label.setText(translator.gettext("s4.items"))
        self._grand_label.setText(translator.gettext("si.grand_total"))
        self._sub_label.setText(translator.gettext("si.subtotal"))
        self._disc_label.setText(translator.gettext("si.discount"))
        self._recv_label.setText(translator.gettext("s4.amount_paid"))
        self._rem_label.setText(translator.gettext("si.remaining"))
        self._prev_label.setText(translator.gettext("si.prev_balance"))
        self._upd_label.setText(translator.gettext("si.updated_balance"))
        self._reload_meta_sources()  # unit labels follow language
        self._kbd_note.setText(translator.gettext("s4.keyboard_hint"))
        self._seg_cash.setText(translator.gettext("si.pay_cash"))
        self._seg_credit.setText(translator.gettext("si.pay_credit"))
        self._add_btn.setText(escape_amp(translator.gettext("s4.add_line")))
        self._btn_new.setText(escape_amp(translator.gettext("s4.act_new")))
        self._btn_post.setText(escape_amp(translator.gettext("s4.act_post")))
        self._btn_post_print.setText(escape_amp(translator.gettext("s4.act_post_print")))
        self._btn_close.setText(escape_amp(translator.gettext("s4.act_close")))
        for key, lf in self._meta_fields:
            lf.set_label(translator.gettext(key))
        for wrap in (self._chip_phone, self._chip_balance):
            wrap._label.setText(translator.gettext(wrap._label_key))  # type: ignore[attr-defined]
        self._invoice_no.setText(translator.gettext("s4.auto"))
        self._render_lines()
