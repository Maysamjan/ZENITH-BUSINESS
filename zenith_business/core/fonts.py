"""Centralized application typography loading (Prompt 01G-follow-up §B, §E).

Zenith Business bundles **Vazirmatn** (SIL OFL 1.1) — a high-quality
Persian/Dari + Latin typeface with Regular/Medium/SemiBold/Bold weights, proper
Arabic glyph shaping, and clear numerals. Bundling (rather than relying on a
system font) means Dari renders identically and professionally on every Windows
customer machine.

This is the single place fonts are registered. All screens, dialogs, tables,
buttons, the dashboard, the Sales Invoice and the printed documents inherit the
same family via :data:`FONT_FAMILY` / :data:`FONT_STACK`, so future Stage 02+
modules get correct typography automatically — no per-screen font choices.
"""

from __future__ import annotations

from pathlib import Path

#: Preferred UI family (bundled). Falls back to good system faces if unavailable.
FONT_FAMILY = "Vazirmatn"

#: CSS/QSS font stack. Vazirmatn covers Persian, Latin and Western digits with a
#: single, consistent baseline, so mixed Persian/English/number content aligns
#: cleanly. System faces are fallbacks only.
FONT_STACK = '"Vazirmatn", "Segoe UI", "Tahoma", "Noto Naskh Arabic", sans-serif'

_FONT_DIR = Path(__file__).resolve().parent.parent / "resources" / "fonts"

_loaded = False
_families: set[str] = set()


def load_application_fonts() -> set[str]:
    """Register the bundled fonts with Qt (idempotent). Returns loaded families.

    Safe to call before styling. Requires a live QApplication. If PyQt6 or the
    font files are unavailable, it degrades to system fallbacks silently.
    """
    global _loaded
    if _loaded:
        return set(_families)
    try:
        from PyQt6.QtGui import QFontDatabase
    except Exception:  # pragma: no cover - PyQt6 not installed
        _loaded = True
        return set()

    if _FONT_DIR.is_dir():
        for ttf in sorted(_FONT_DIR.glob("*.ttf")):
            font_id = QFontDatabase.addApplicationFont(str(ttf))
            if font_id != -1:
                for fam in QFontDatabase.applicationFontFamilies(font_id):
                    _families.add(fam)
    _loaded = True
    return set(_families)


def apply_base_font(app) -> None:
    """Set the application's default font to the bundled family at a base size."""
    try:
        from PyQt6.QtGui import QFont
    except Exception:  # pragma: no cover
        return
    load_application_fonts()
    family = FONT_FAMILY if FONT_FAMILY in _families else app.font().family()
    base = QFont(family, 10)
    base.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(base)


def is_bundled_available() -> bool:
    return FONT_FAMILY in _families
