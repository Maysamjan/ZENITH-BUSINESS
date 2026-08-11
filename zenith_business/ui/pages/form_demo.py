"""Form layout demonstration (Prompt 01B §18).

Proves that future Sales, Purchase, Person, and Product screens can share one
coherent form design language: page header, grouped sections, semantic field
widths, aligned labels/controls, validation message, primary/secondary actions.

NOT a business module — generic placeholders only; nothing is saved.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from zenith_business.core.i18n import Translator
from zenith_business.ui.components import (
    Card,
    PageHeader,
    apply_field_width,
    error_label,
    field_label,
    primary_button,
    secondary_button,
    section_title,
)
from zenith_business.ui.design.tokens import FieldWidth, Spacing


class FormDemoPage(QScrollArea):
    """Scrollable form demonstration page."""

    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._t = translator
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)

        root = QWidget()
        self.setWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(
            Spacing.PAGE_MARGIN, Spacing.PAGE_MARGIN,
            Spacing.PAGE_MARGIN, Spacing.PAGE_MARGIN,
        )
        layout.setSpacing(Spacing.SECTION_GAP)

        self._header = PageHeader(
            self._t.gettext("formdemo.title"),
            self._t.gettext("formdemo.subtitle"),
        )
        layout.addWidget(self._header)

        layout.addWidget(self._build_general_section())
        layout.addWidget(self._build_details_section())
        layout.addLayout(self._build_actions())
        layout.addStretch(1)

    # ---- sections --------------------------------------------------------

    def _form(self) -> QFormLayout:
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(Spacing.FIELD_HGAP)
        form.setVerticalSpacing(Spacing.FIELD_VGAP)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        return form

    def _build_general_section(self) -> QWidget:
        card = Card(role="section")
        card.body.addWidget(section_title(self._t.gettext("formdemo.section_general")))
        form = self._form()

        # Short code (XS)
        code = apply_field_width(QLineEdit(), FieldWidth.XS)
        form.addRow(field_label(self._t.gettext("formdemo.code")), code)

        # Date (SM)
        date = QDateEdit()
        date.setCalendarPopup(True)
        date.setDisplayFormat("yyyy/MM/dd")
        apply_field_width(date, FieldWidth.SM)
        form.addRow(field_label(self._t.gettext("formdemo.date")), date)

        # Name (LG) with a validation error demonstration
        name = apply_field_width(QLineEdit(), FieldWidth.LG)
        name.setProperty("state", "error")
        name_col = QVBoxLayout()
        name_col.setSpacing(Spacing.XXS)
        name_col.addWidget(name)
        name_col.addWidget(error_label(self._t.gettext("formdemo.validation")))
        name_wrap = QWidget()
        name_wrap.setStyleSheet("background: transparent;")  # sit cleanly on the card
        name_wrap.setLayout(name_col)
        form.addRow(field_label(self._t.gettext("formdemo.name")), name_wrap)

        # Category (combo, MD)
        category = QComboBox()
        category.addItem(self._t.gettext("formdemo.combo_placeholder"))
        category.addItems(["A", "B", "C"])
        apply_field_width(category, FieldWidth.MD)
        form.addRow(field_label(self._t.gettext("formdemo.category")), category)

        card.body.addLayout(form)
        self._name = name
        return card

    def _build_details_section(self) -> QWidget:
        card = Card(role="section")
        card.body.addWidget(section_title(self._t.gettext("formdemo.section_details")))
        form = self._form()

        # Quantity (numeric, SM, right-aligned)
        qty = QSpinBox()
        qty.setMaximum(1_000_000)
        qty.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        apply_field_width(qty, FieldWidth.SM)
        form.addRow(field_label(self._t.gettext("formdemo.quantity")), qty)

        # Amount (numeric, MD, right-aligned, thousands)
        amount = QDoubleSpinBox()
        amount.setMaximum(1_000_000_000)
        amount.setDecimals(2)
        amount.setGroupSeparatorShown(True)
        amount.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        apply_field_width(amount, FieldWidth.MD)
        form.addRow(field_label(self._t.gettext("formdemo.amount")), amount)

        # Description (XL, multi-line)
        desc = QTextEdit()
        desc.setMinimumWidth(int(FieldWidth.XL))
        desc.setFixedHeight(80)
        form.addRow(field_label(self._t.gettext("formdemo.description")), desc)

        card.body.addLayout(form)
        return card

    def _build_actions(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch(1)
        self._cancel = secondary_button(self._t.gettext("action.cancel"))
        self._save = primary_button(self._t.gettext("action.save"))
        row.addWidget(self._cancel)
        row.addWidget(self._save)
        return row

    # ---- i18n ------------------------------------------------------------

    def retranslate(self, translator: Translator) -> None:
        self._t = translator
        # Simplest robust path: rebuild would be heavy; update key texts.
        self._save.setText(translator.gettext("action.save"))
        self._cancel.setText(translator.gettext("action.cancel"))
