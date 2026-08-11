"""Branded home / workspace screen (Prompt 01B §7, §8).

A professionally composed brand screen — not a logo floating in an empty window.
Composition: a central hero (logo + identity + version), a "System Readiness"
card that shows only truthful state, and a reserved "Quick Access" area for
future modules. No fake financial numbers (§8).

Layouts only (no absolute positioning) with a max-width content column that
stays well-proportioned when the window is maximized (§17). A scroll area guards
small windows (§16).
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from zenith_business.core.i18n import Translator
from zenith_business.core.identity import IDENTITY
from zenith_business.ui.components import Card, apply_shadow, chip, muted, section_title
from zenith_business.ui.design.tokens import ControlSize, FieldWidth, Spacing


def _resources_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "resources"


class HomeScreen(QScrollArea):
    """Central branded workspace shown at startup / when Home is selected."""

    CONTENT_MAX_WIDTH = 940

    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._t = translator
        self._db_ok = False
        self._license_summary = ""

        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        outer = QWidget()
        self.setWidget(outer)
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(
            Spacing.XXL, Spacing.XL, Spacing.XXL, Spacing.XL
        )
        outer_layout.addStretch(2)

        # Centered, max-width content column.
        center_row = QHBoxLayout()
        center_row.addStretch(1)
        self._column = QWidget()
        self._column.setMaximumWidth(self.CONTENT_MAX_WIDTH)
        center_row.addWidget(self._column, stretch=0)
        center_row.addStretch(1)
        outer_layout.addLayout(center_row)
        outer_layout.addStretch(3)

        col = QVBoxLayout(self._column)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(Spacing.LG)

        col.addWidget(self._build_hero())

        cards_row = QHBoxLayout()
        cards_row.setSpacing(Spacing.XL)
        cards_row.addWidget(self._build_readiness_card(), stretch=1)
        cards_row.addWidget(self._build_quick_access_card(), stretch=1)
        col.addLayout(cards_row)

        self._get_started = muted(self._t.gettext("home.get_started"))
        self._get_started.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.addWidget(self._get_started)

    # ---- hero ------------------------------------------------------------

    def _build_hero(self) -> QWidget:
        hero = Card()
        apply_shadow(hero, blur=32, y=6, alpha=34)
        hero.body.setContentsMargins(Spacing.XXL, Spacing.XL, Spacing.XXL, Spacing.XL)
        hero.body.setSpacing(Spacing.SM)

        self._logo = QLabel()
        self._logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._apply_logo()
        hero.body.addWidget(self._logo, alignment=Qt.AlignmentFlag.AlignHCenter)

        title = QLabel(IDENTITY.product)
        title.setProperty("role", "brand-title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero.body.addWidget(title)

        self._tagline = QLabel(self._t.gettext("home.system_full"))
        self._tagline.setProperty("role", "brand-tagline")
        self._tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero.body.addWidget(self._tagline)

        version_row = QHBoxLayout()
        version_row.addStretch(1)
        self._version_chip = chip(f"v{IDENTITY.version}", "info")
        version_row.addWidget(self._version_chip)
        self._company = muted(IDENTITY.company)
        version_row.addWidget(self._company)
        version_row.addStretch(1)
        hero.body.addSpacing(Spacing.XS)
        hero.body.addLayout(version_row)

        return hero

    def _apply_logo(self) -> None:
        """Show the real logo if present, else a refined placeholder (§7)."""
        from PyQt6.QtGui import QPixmap

        logo_path = _resources_dir() / "logo.png"
        size = 128
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
                self._logo.setProperty("role", None)
                return
        # Neutral placeholder with the brand initial (replaceable later).
        self._logo.setProperty("role", "logo-placeholder")
        mark = QLabel(IDENTITY.product[:1], self._logo)
        mark.setProperty("role", "logo-mark")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setGeometry(0, 0, size, size)

    # ---- readiness card --------------------------------------------------

    def _build_readiness_card(self) -> QWidget:
        card = Card()
        apply_shadow(card)
        card.body.addWidget(section_title(self._t.gettext("home.readiness")))

        self._readiness_grid = QGridLayout()
        self._readiness_grid.setHorizontalSpacing(Spacing.LG)
        self._readiness_grid.setVerticalSpacing(Spacing.MD)
        self._readiness_grid.setColumnStretch(1, 1)
        card.body.addLayout(self._readiness_grid)
        card.body.addStretch(1)

        self._readiness_rows: dict[str, tuple[QLabel, QLabel]] = {}
        for row_key in ("home.ready.database", "home.ready.language",
                        "home.ready.license", "home.ready.version"):
            name = muted("")
            value = chip("", "neutral")
            r = self._readiness_grid.rowCount()
            self._readiness_grid.addWidget(name, r, 0, Qt.AlignmentFlag.AlignLeft)
            self._readiness_grid.addWidget(value, r, 1, Qt.AlignmentFlag.AlignLeft)
            self._readiness_rows[row_key] = (name, value)

        self._refresh_readiness()
        return card

    def _refresh_readiness(self) -> None:
        t = self._t
        db_name, db_val = self._readiness_rows["home.ready.database"]
        db_name.setText(t.gettext("home.ready.database"))
        db_val.setText(
            t.gettext("status.db_ok") if self._db_ok
            else t.gettext("status.db_unavailable")
        )
        db_val.setProperty("chip", "success" if self._db_ok else "danger")

        lang_name, lang_val = self._readiness_rows["home.ready.language"]
        lang_name.setText(t.gettext("home.ready.language"))
        lang_val.setText(
            t.gettext("menu.language.dari") if t.language == "fa_AF"
            else t.gettext("menu.language.english")
        )
        lang_val.setProperty("chip", "neutral")

        lic_name, lic_val = self._readiness_rows["home.ready.license"]
        lic_name.setText(t.gettext("home.ready.license"))
        lic_val.setText(t.gettext("header.channel_dev"))
        lic_val.setProperty("chip", "warning")

        ver_name, ver_val = self._readiness_rows["home.ready.version"]
        ver_name.setText(t.gettext("home.ready.version"))
        ver_val.setText(f"v{IDENTITY.version}")
        ver_val.setProperty("chip", "info")

        for _, val in self._readiness_rows.values():
            val.style().unpolish(val)
            val.style().polish(val)

    # ---- quick access (reserved) ----------------------------------------

    def _build_quick_access_card(self) -> QWidget:
        card = Card()
        apply_shadow(card)
        card.body.addWidget(section_title(self._t.gettext("home.quick_access")))

        grid = QGridLayout()
        grid.setSpacing(Spacing.MD)
        for i in range(4):
            tile = QFrame()
            tile.setProperty("role", "logo-placeholder")
            tile.setMinimumHeight(56)
            tile.setMinimumWidth(int(FieldWidth.SM))
            grid.addWidget(tile, i // 2, i % 2)
        card.body.addLayout(grid)

        self._quick_note = muted(self._t.gettext("home.quick_reserved"))
        self._quick_note.setWordWrap(True)
        card.body.addWidget(self._quick_note)
        card.body.addStretch(1)
        return card

    # ---- public API ------------------------------------------------------

    def set_readiness(self, *, db_ok: bool, license_summary: str) -> None:
        self._db_ok = db_ok
        self._license_summary = license_summary
        self._refresh_readiness()

    def retranslate(self, translator: Translator) -> None:
        self._t = translator
        self._tagline.setText(translator.gettext("home.system_full"))
        self._get_started.setText(translator.gettext("home.get_started"))
        self._quick_note.setText(translator.gettext("home.quick_reserved"))
        self._refresh_readiness()
