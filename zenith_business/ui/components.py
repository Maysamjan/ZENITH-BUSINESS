"""Reusable UI components — the shared design vocabulary (Prompt 01B §18-§23).

Factories and small widgets that encode the design system so every future
module composes screens from the same parts instead of restyling widgets
locally. Nothing here contains business logic or touches the database.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from zenith_business.ui.design.tokens import FieldWidth, Spacing


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


def primary_button(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setProperty("variant", "primary")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


def secondary_button(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


def ghost_button(text: str) -> QPushButton:
    btn = QPushButton(text)
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


# ---- composite widgets --------------------------------------------------


class Card(QFrame):
    """A surface panel with padding; children go in :attr:`body` layout."""

    def __init__(self, *, role: str = "card", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("role", role)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(
            Spacing.XL, Spacing.LG, Spacing.XL, Spacing.LG
        )
        self.body.setSpacing(Spacing.MD)


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
