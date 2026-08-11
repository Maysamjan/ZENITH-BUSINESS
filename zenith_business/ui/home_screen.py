"""Branded home / start screen (Prompt 01 §14, §33).

Layout concept (top navigation lives on the main window, not here):

    +--------------------------------------------------+
    |              [ Zenith Soft Logo ]                |
    |                ZENITH BUSINESS                   |
    |             Business Management System           |
    |                    v0.1.0                        |
    +--------------------------------------------------+

The logo is a replaceable placeholder container: if a real asset is dropped into
``resources/logo.png`` later, it is shown automatically without redesigning the
screen. No permanent logo is invented (Prompt 01 §14, §35).

Uses Qt layouts only (no absolute positioning) so it adapts to resizing and DPI
scaling (§17). A scroll area guards against very small windows.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from zenith_business.core.i18n import Translator
from zenith_business.core.identity import IDENTITY
from zenith_business.ui.design.tokens import Spacing


def _resources_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "resources"


class HomeScreen(QScrollArea):
    """Central branded workspace shown at startup."""

    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._t = translator
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        container = QWidget()
        self.setWidget(container)

        outer = QVBoxLayout(container)
        outer.setContentsMargins(
            Spacing.XXL, Spacing.XXL, Spacing.XXL, Spacing.XXL
        )
        outer.addStretch(1)

        # Logo placeholder / real asset.
        self._logo = QLabel()
        self._logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._apply_logo()
        outer.addWidget(self._logo, alignment=Qt.AlignmentFlag.AlignHCenter)

        outer.addSpacing(Spacing.XL)

        # Product name.
        self._title = QLabel(IDENTITY.product)
        self._title.setProperty("class", "brand-title")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self._title)

        # Tagline (localized).
        self._tagline = QLabel(self._t.gettext("app.tagline"))
        self._tagline.setProperty("class", "brand-tagline")
        self._tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self._tagline)

        outer.addSpacing(Spacing.SM)

        # Version + company (from central identity).
        self._version = QLabel(f"v{IDENTITY.version} · {IDENTITY.company}")
        self._version.setProperty("class", "muted")
        self._version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self._version)

        outer.addSpacing(Spacing.XL)

        # Hint that modules appear as enabled (no fake business features).
        self._hint = QLabel(self._t.gettext("home.placeholder_hint"))
        self._hint.setProperty("class", "muted")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint.setWordWrap(True)
        outer.addWidget(self._hint)

        outer.addStretch(2)

    def _apply_logo(self) -> None:
        """Show the real logo if present, else a clean placeholder container."""
        logo_path = _resources_dir() / "logo.png"
        size = 140
        self._logo.setFixedSize(size, size)
        if logo_path.exists():
            pixmap = QPixmap(str(logo_path))
            if not pixmap.isNull():
                self._logo.setPixmap(
                    pixmap.scaled(
                        size,
                        size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                self._logo.setProperty("class", None)
                return
        # Placeholder container (replaceable later without redesign).
        self._logo.setProperty("class", "logo-placeholder")
        self._logo.setText(IDENTITY.company)
        self._logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def retranslate(self, translator: Translator) -> None:
        """Update localized strings after a language change."""
        self._t = translator
        self._tagline.setText(self._t.gettext("app.tagline"))
        self._hint.setText(self._t.gettext("home.placeholder_hint"))
