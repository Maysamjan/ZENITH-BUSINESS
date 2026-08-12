"""Reusable UI components — the shared design vocabulary (Prompt 01B §18-§23).

Factories and small widgets that encode the design system so every future
module composes screens from the same parts instead of restyling widgets
locally. Nothing here contains business logic or touches the database.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from zenith_business.ui.design.tokens import Color, ControlSize, FieldWidth, Spacing, Typography


# ---- primitives ---------------------------------------------------------


def page_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "page-title")
    return label


def page_subtitle(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "page-subtitle")
    label.setWordWrap(True)
    return label


def section_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "section-title")
    return label


def field_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "field-label")
    return label


def eyebrow(text: str) -> QLabel:
    """Small accented section marker (e.g. a prominent 'Customer' label)."""
    label = QLabel(text)
    label.setProperty("role", "eyebrow")
    return label


def muted(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "muted")
    return label


def secondary(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "secondary")
    return label


def error_label(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "error")
    label.setWordWrap(True)
    return label


def chip(text: str, kind: str = "neutral") -> QLabel:
    """A pill status chip. ``kind`` in {info, success, warning, danger, neutral}."""
    label = QLabel(text)
    label.setProperty("chip", kind)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    return label


def standard_icon(name: str) -> QIcon:
    """Return a platform-style icon by short name (Prompt 01D §6).

    Uses Qt's built-in style icons so no third-party/unlicensed assets are
    bundled. Unknown names return a null icon (button still shows its text).
    """
    mapping = {
        "new": QStyle.StandardPixmap.SP_FileIcon,
        "save": QStyle.StandardPixmap.SP_DialogSaveButton,
        "print": QStyle.StandardPixmap.SP_FileDialogDetailedView,
        "receive": QStyle.StandardPixmap.SP_DialogApplyButton,
        "close": QStyle.StandardPixmap.SP_DialogCloseButton,
        "delete": QStyle.StandardPixmap.SP_TrashIcon,
        "next": QStyle.StandardPixmap.SP_ArrowForward,
    }
    pixmap = mapping.get(name)
    app = QApplication.instance()
    if pixmap is None or app is None:
        return QIcon()
    return app.style().standardIcon(pixmap)


def escape_amp(text: str) -> str:
    """Escape ``&`` for Qt button/menu labels so it renders literally.

    Qt treats a single ``&`` as a mnemonic marker; escape it (e.g. 'Save & Print')
    until deliberate Alt-mnemonics are assigned per module. Use this whenever a
    label is set on a QPushButton, including in ``retranslate``.
    """
    return text.replace("&", "&&")


def primary_button(text: str) -> QPushButton:
    btn = QPushButton(escape_amp(text))
    btn.setProperty("variant", "primary")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


def secondary_button(text: str) -> QPushButton:
    btn = QPushButton(escape_amp(text))
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


def ghost_button(text: str) -> QPushButton:
    btn = QPushButton(escape_amp(text))
    btn.setProperty("variant", "ghost")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


def horizontal_divider() -> QFrame:
    line = QFrame()
    line.setProperty("role", "divider")
    line.setFixedHeight(1)
    line.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return line


def vertical_line() -> QFrame:
    line = QFrame()
    line.setProperty("role", "vline")
    line.setFixedWidth(1)
    return line


def apply_field_width(widget: QWidget, width: FieldWidth) -> QWidget:
    """Apply a semantic minimum field width (§13). Returns the widget."""
    widget.setMinimumWidth(int(width))
    widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    return widget


def apply_shadow(
    widget: QWidget, *, blur: int = 24, y: int = 4, alpha: int = 38
) -> QWidget:
    """Attach a soft drop shadow to a card/panel for subtle depth (§6).

    Kept restrained (low alpha, tight offset) so the UI reads premium, not noisy.
    """
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setXOffset(0)
    effect.setYOffset(y)
    effect.setColor(QColor(20, 38, 61, alpha))
    widget.setGraphicsEffect(effect)
    return widget


# ---- composite widgets --------------------------------------------------


class Card(QFrame):
    """A surface panel with padding; children go in :attr:`body` layout."""

    def __init__(self, *, role: str = "card", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("role", role)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(
            Spacing.CARD_PAD_H, Spacing.CARD_PAD_V,
            Spacing.CARD_PAD_H, Spacing.CARD_PAD_V,
        )
        self.body.setSpacing(Spacing.SM)


class StatTile(QFrame):
    """Compact labelled metric tile (label + value) for operational info (§3).

    Values shown in prototypes are clearly demonstration data, not live figures.
    """

    def __init__(
        self,
        label: str,
        value: str = "—",
        *,
        accent: str = "neutral",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("role", "stat")
        self.setProperty("accent", accent)  # colored left border for scannability
        self.setMinimumHeight(ControlSize.STAT_TILE_HEIGHT)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.MD, Spacing.SM, Spacing.MD, Spacing.SM)
        layout.setSpacing(Spacing.XXS)

        self._label = QLabel(label)
        self._label.setProperty("role", "stat-label")
        self._value = QLabel(value)
        self._value.setProperty("role", "stat-value")
        self._value.setProperty("accent", accent)
        layout.addWidget(self._label)
        layout.addWidget(self._value)

    def set_value(self, value: str) -> None:
        self._value.setText(value)

    def set_label(self, label: str) -> None:
        self._label.setText(label)

    def set_accent(self, accent: str) -> None:
        self._value.setProperty("accent", accent)
        self._value.style().unpolish(self._value)
        self._value.style().polish(self._value)


class LabeledField(QWidget):
    """A field label stacked above its control — compact and grid-friendly (§9).

    Ideal for dense multi-column business headers where label-beside-field would
    waste width. The control keeps its semantic width; the label never squeezes
    the input.
    """

    def __init__(
        self,
        label: str,
        control: QWidget,
        *,
        width: FieldWidth | None = None,
        compact: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(Spacing.XXS)
        # Secondary/metadata fields are visually quieter (Prompt 01G §8): a
        # smaller muted label and a compact, lighter input.
        self._label = QLabel(label)
        self._label.setProperty("role", "field-label-sm" if compact else "field-label")
        col.addWidget(self._label)
        if compact:
            control.setProperty("size", "compact")
        if width is not None:
            apply_field_width(control, width)
        col.addWidget(control)
        self.control = control

    def set_label(self, label: str) -> None:
        self._label.setText(label)


class PageHeader(QWidget):
    """Standard page header: title + optional subtitle, with a trailing slot."""

    def __init__(
        self,
        title: str,
        subtitle: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(Spacing.MD)

        text_col = QVBoxLayout()
        text_col.setSpacing(Spacing.XXS)
        text_col.addWidget(page_title(title))
        if subtitle:
            text_col.addWidget(page_subtitle(subtitle))
        row.addLayout(text_col)
        row.addStretch(1)

        self._trailing = QHBoxLayout()
        self._trailing.setSpacing(Spacing.SM)
        row.addLayout(self._trailing)

    def add_trailing(self, widget: QWidget) -> None:
        self._trailing.addWidget(widget)


class EmptyState(QWidget):
    """Reusable empty / unavailable / loading state (Prompt 01B §23).

    Used, for example, when a not-yet-built module is selected — a truthful
    "feature unavailable" panel rather than a blank window or fake content.
    """

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        glyph: str = "▧",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.XXL, Spacing.XXL, Spacing.XXL, Spacing.XXL)
        layout.addStretch(1)

        self._glyph = QLabel(glyph)
        self._glyph.setProperty("role", "empty-glyph")
        self._glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._glyph)

        layout.addSpacing(Spacing.MD)

        self._title = QLabel(title)
        self._title.setProperty("role", "empty-title")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._title)

        self._subtitle = QLabel(subtitle)
        self._subtitle.setProperty("role", "empty-subtitle")
        self._subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._subtitle.setWordWrap(True)
        layout.addWidget(self._subtitle)

        layout.addStretch(2)

    def set_text(self, title: str, subtitle: str = "") -> None:
        self._title.setText(title)
        self._subtitle.setText(subtitle)
