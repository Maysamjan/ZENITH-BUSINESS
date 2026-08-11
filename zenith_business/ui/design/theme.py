"""Application stylesheet (QSS) generated from design tokens.

Centralizing the stylesheet here (Prompt 01 §15, §34) means every future module
inherits consistent control heights, spacing, borders, and colors without
restyling widgets locally. Apply once to the QApplication; all widgets follow.

The QSS is built from :mod:`.tokens` so there is a single source of truth — no
hard-coded colors or sizes are duplicated in string form.
"""

from __future__ import annotations

from zenith_business.ui.design.tokens import (
    Color,
    ControlSize,
    Radius,
    Spacing,
    Typography,
)


def build_stylesheet() -> str:
    """Return the global application stylesheet."""
    c = Color
    return f"""
    /* ---- base ---------------------------------------------------------- */
    QWidget {{
        background-color: {c.BACKGROUND};
        color: {c.TEXT};
        font-family: {Typography.FAMILY};
        font-size: {Typography.SIZE_BODY}pt;
    }}

    /* ---- menu bar (TOP navigation) ------------------------------------- */
    QMenuBar {{
        background-color: {c.MENUBAR_BG};
        border-bottom: 1px solid {c.BORDER};
        padding: {Spacing.XS}px {Spacing.SM}px;
        min-height: {ControlSize.MENUBAR_HEIGHT}px;
    }}
    QMenuBar::item {{
        background: transparent;
        padding: {Spacing.SM}px {Spacing.LG}px;
        margin: 0px {Spacing.XS}px;
        border-radius: {Radius.SM}px;
        font-size: {Typography.SIZE_CONTROL}pt;
    }}
    QMenuBar::item:selected {{
        background-color: {c.SURFACE_ALT};
        color: {c.PRIMARY};
    }}
    QMenuBar::item:disabled {{ color: {c.TEXT_DISABLED}; }}

    QMenu {{
        background-color: {c.SURFACE};
        border: 1px solid {c.BORDER};
        padding: {Spacing.XS}px;
    }}
    QMenu::item {{
        padding: {Spacing.SM}px {Spacing.XL}px;
        border-radius: {Radius.SM}px;
    }}
    QMenu::item:selected {{ background-color: {c.SURFACE_ALT}; color: {c.PRIMARY}; }}
    QMenu::item:disabled {{ color: {c.TEXT_DISABLED}; }}
    QMenu::separator {{ height: 1px; background: {c.BORDER}; margin: {Spacing.XS}px 0; }}

    /* ---- inputs -------------------------------------------------------- */
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QPlainTextEdit,
    QTextEdit {{
        background-color: {c.SURFACE};
        border: 1px solid {c.BORDER};
        border-radius: {Radius.SM}px;
        padding: {Spacing.XS}px {Spacing.SM}px;
        min-height: {ControlSize.INPUT_HEIGHT}px;
        selection-background-color: {c.PRIMARY};
        selection-color: {c.TEXT_ON_PRIMARY};
    }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,
    QDateEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{
        border: 1px solid {c.PRIMARY};
    }}
    QLineEdit:disabled, QComboBox:disabled {{
        background-color: {c.SURFACE_ALT};
        color: {c.TEXT_DISABLED};
    }}
    /* Validation state hook: set property state='error' on a widget. */
    QLineEdit[state="error"], QComboBox[state="error"] {{
        border: 1px solid {c.ERROR};
    }}

    /* ---- buttons ------------------------------------------------------- */
    QPushButton {{
        background-color: {c.SURFACE};
        color: {c.TEXT};
        border: 1px solid {c.BORDER_STRONG};
        border-radius: {Radius.SM}px;
        padding: {Spacing.XS}px {Spacing.LG}px;
        min-height: {ControlSize.BUTTON_HEIGHT}px;
    }}
    QPushButton:hover {{ border-color: {c.PRIMARY}; }}
    QPushButton:disabled {{ color: {c.TEXT_DISABLED}; border-color: {c.BORDER}; }}
    /* Primary action: set property variant='primary'. */
    QPushButton[variant="primary"] {{
        background-color: {c.PRIMARY};
        color: {c.TEXT_ON_PRIMARY};
        border: 1px solid {c.PRIMARY};
        font-weight: {Typography.WEIGHT_MEDIUM};
    }}
    QPushButton[variant="primary"]:hover {{ background-color: {c.PRIMARY_HOVER}; }}
    QPushButton[variant="primary"]:pressed {{ background-color: {c.PRIMARY_PRESSED}; }}

    /* ---- tables -------------------------------------------------------- */
    QTableView, QTableWidget {{
        background-color: {c.SURFACE};
        alternate-background-color: {c.SURFACE_ALT};
        gridline-color: {c.BORDER};
        border: 1px solid {c.BORDER};
        border-radius: {Radius.SM}px;
        selection-background-color: {c.PRIMARY};
        selection-color: {c.TEXT_ON_PRIMARY};
    }}
    QHeaderView::section {{
        background-color: {c.SURFACE_ALT};
        color: {c.TEXT_MUTED};
        padding: {Spacing.XS}px {Spacing.SM}px;
        border: none;
        border-right: 1px solid {c.BORDER};
        border-bottom: 1px solid {c.BORDER};
        min-height: {ControlSize.TABLE_HEADER_HEIGHT}px;
        font-weight: {Typography.WEIGHT_MEDIUM};
    }}

    /* ---- status bar ---------------------------------------------------- */
    QStatusBar {{
        background-color: {c.STATUSBAR_BG};
        border-top: 1px solid {c.BORDER};
        color: {c.TEXT_MUTED};
        min-height: {ControlSize.STATUSBAR_HEIGHT}px;
    }}
    QStatusBar QLabel {{ background: transparent; color: {c.TEXT_MUTED}; }}

    /* ---- design-system helper classes (set via setProperty('class', ...)) */
    QLabel[class="page-title"] {{
        font-size: {Typography.SIZE_PAGE}pt;
        font-weight: {Typography.WEIGHT_BOLD};
        color: {c.TEXT};
    }}
    QLabel[class="section-title"] {{
        font-size: {Typography.SIZE_SECTION}pt;
        font-weight: {Typography.WEIGHT_MEDIUM};
        color: {c.TEXT};
    }}
    QLabel[class="muted"] {{ color: {c.TEXT_MUTED}; }}
    QLabel[class="brand-title"] {{
        font-size: {Typography.SIZE_BRAND}pt;
        font-weight: {Typography.WEIGHT_BOLD};
        color: {c.TEXT};
    }}
    QLabel[class="brand-tagline"] {{
        font-size: {Typography.SIZE_BRAND_TAGLINE}pt;
        color: {c.TEXT_MUTED};
    }}
    QFrame[class="card"] {{
        background-color: {c.SURFACE};
        border: 1px solid {c.BORDER};
        border-radius: {Radius.LG}px;
    }}
    QFrame[class="logo-placeholder"] {{
        background-color: {c.SURFACE_ALT};
        border: 1px dashed {c.BORDER_STRONG};
        border-radius: {Radius.LG}px;
        color: {c.TEXT_MUTED};
    }}
    """
