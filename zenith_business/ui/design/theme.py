"""Application stylesheet (QSS), generated from design tokens.

Centralizing the stylesheet here (Prompt 01B §9-§12) means every module inherits
consistent chrome, controls, borders, and colors without restyling widgets
locally. Apply once to the QApplication; all widgets follow.

Selector conventions (so screens stay declarative):
    * object names:   #HeaderBar #PrimaryNav #ContextBar #BrandWordmark ...
    * properties:     QPushButton[variant="primary"] , QPushButton[nav="true"]
                      QLabel[role="page-title"] , QLabel[chip="success"] , ...
    * state property: setProperty("selected", True) on nav buttons

Everything derives from :mod:`.tokens` — no hard-coded colors or sizes are
duplicated here in literal form.
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
    t = Typography
    return f"""
    /* ==== base ========================================================== */
    QWidget {{
        background-color: {c.BACKGROUND};
        color: {c.TEXT_PRIMARY};
        font-family: {t.FAMILY};
        font-size: {t.SIZE_BODY}pt;
    }}
    /* Labels are transparent by default so text sits cleanly on any surface;
       chips/marks re-declare their own background where needed. */
    QLabel {{ background: transparent; }}
    QToolTip {{
        background-color: {c.HEADER_BG};
        color: {c.HEADER_TEXT};
        border: 1px solid {c.HEADER_BORDER};
        padding: {Spacing.XS}px {Spacing.SM}px;
        border-radius: {Radius.SM}px;
    }}

    /* ==== brand header ================================================== */
    QFrame#HeaderBar {{
        background-color: {c.HEADER_BG};
        border: none;
        border-bottom: 1px solid {c.HEADER_BORDER};
    }}
    QFrame#HeaderBar QLabel {{ background: transparent; color: {c.HEADER_TEXT}; }}
    QLabel#BrandWordmark {{
        color: {c.HEADER_TEXT};
        font-size: {t.SIZE_BRAND_HEADER}pt;
        font-weight: {t.WEIGHT_BOLD};
        letter-spacing: 1px;
    }}
    QLabel#BrandSub {{
        color: {c.HEADER_TEXT_MUTED};
        font-size: {t.SIZE_SECONDARY}pt;
    }}
    QLabel#BrandMark {{
        background-color: {c.PRIMARY};
        color: {c.TEXT_ON_PRIMARY};
        font-size: {t.SIZE_BRAND_HEADER}pt;
        font-weight: {t.WEIGHT_BOLD};
        border-radius: {Radius.MD}px;
    }}
    QFrame#HeaderBar QLabel[role="header-muted"] {{ color: {c.HEADER_TEXT_MUTED}; }}

    /* header segmented language control */
    QPushButton[segment="true"] {{
        background-color: transparent;
        color: {c.HEADER_TEXT_MUTED};
        border: 1px solid {c.HEADER_BG_ALT};
        padding: {Spacing.XXS}px {Spacing.MD}px;
        min-height: {ControlSize.TOOLBAR_BUTTON_HEIGHT}px;
    }}
    QPushButton[segment="true"]:hover {{ color: {c.HEADER_TEXT}; }}
    QPushButton[segment="true"][selected="true"] {{
        background-color: {c.PRIMARY};
        color: {c.TEXT_ON_PRIMARY};
        border: 1px solid {c.PRIMARY};
    }}

    /* ==== primary navigation ============================================ */
    QFrame#PrimaryNav {{
        background-color: {c.NAV_BG};
        border: none;
        border-bottom: 1px solid {c.NAV_BORDER};
    }}
    QPushButton[nav="true"] {{
        background-color: transparent;
        color: {c.TEXT_SECONDARY};
        border: none;
        border-bottom: 2px solid transparent;
        padding: {Spacing.SM}px {Spacing.LG}px;
        min-height: {ControlSize.NAV_BUTTON_HEIGHT}px;
        font-size: {t.SIZE_NAV}pt;
        font-weight: {t.WEIGHT_MEDIUM};
    }}
    QPushButton[nav="true"]:hover {{
        color: {c.PRIMARY};
        background-color: {c.PRIMARY_SOFT};
    }}
    QPushButton[nav="true"][selected="true"] {{
        color: {c.PRIMARY};
        border-bottom: 2px solid {c.PRIMARY};
        font-weight: {t.WEIGHT_SEMIBOLD};
    }}

    /* ==== contextual command bar ======================================== */
    QFrame#ContextBar {{
        background-color: {c.CONTEXT_BG};
        border: none;
        border-bottom: 1px solid {c.CONTEXT_BORDER};
    }}
    QLabel#ContextTitle {{
        color: {c.TEXT_MUTED};
        font-size: {t.SIZE_SECONDARY}pt;
        font-weight: {t.WEIGHT_SEMIBOLD};
    }}
    QPushButton[toolbar="true"] {{
        background-color: {c.SURFACE};
        color: {c.TEXT_PRIMARY};
        border: 1px solid {c.BORDER};
        border-radius: {Radius.SM}px;
        padding: {Spacing.XS}px {Spacing.MD}px;
        min-height: {ControlSize.TOOLBAR_BUTTON_HEIGHT}px;
    }}
    QPushButton[toolbar="true"]:hover {{
        border-color: {c.PRIMARY};
        color: {c.PRIMARY};
    }}
    QPushButton[toolbar="true"]:disabled {{
        color: {c.TEXT_DISABLED};
        background-color: {c.SURFACE_ALT};
        border-color: {c.BORDER};
    }}

    /* ==== inputs ======================================================== */
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
    QLineEdit[state="error"], QComboBox[state="error"],
    QDoubleSpinBox[state="error"], QDateEdit[state="error"] {{
        border: 1px solid {c.DANGER};
        background-color: {c.DANGER_SOFT};
    }}
    QComboBox::drop-down {{ border: none; width: 22px; }}
    QComboBox QAbstractItemView {{
        background-color: {c.SURFACE};
        border: 1px solid {c.BORDER};
        selection-background-color: {c.PRIMARY_SOFT};
        selection-color: {c.TEXT_PRIMARY};
        outline: none;
    }}

    /* ==== buttons ======================================================= */
    QPushButton {{
        background-color: {c.SURFACE};
        color: {c.TEXT_PRIMARY};
        border: 1px solid {c.BORDER_STRONG};
        border-radius: {Radius.SM}px;
        padding: {Spacing.XS}px {Spacing.LG}px;
        min-height: {ControlSize.BUTTON_HEIGHT}px;
    }}
    QPushButton:hover {{ border-color: {c.PRIMARY}; color: {c.PRIMARY}; }}
    QPushButton:disabled {{ color: {c.TEXT_DISABLED}; border-color: {c.BORDER}; }}
    QPushButton[variant="primary"] {{
        background-color: {c.PRIMARY};
        color: {c.TEXT_ON_PRIMARY};
        border: 1px solid {c.PRIMARY};
        font-weight: {t.WEIGHT_MEDIUM};
    }}
    QPushButton[variant="primary"]:hover {{
        background-color: {c.PRIMARY_HOVER}; color: {c.TEXT_ON_PRIMARY};
    }}
    QPushButton[variant="primary"]:pressed {{ background-color: {c.PRIMARY_PRESSED}; }}
    QPushButton[variant="ghost"] {{
        background-color: transparent; border: 1px solid transparent;
        color: {c.TEXT_SECONDARY};
    }}
    QPushButton[variant="ghost"]:hover {{ color: {c.PRIMARY}; background-color: {c.PRIMARY_SOFT}; }}

    /* ==== tables ======================================================== */
    QTableView, QTableWidget {{
        background-color: {c.SURFACE};
        alternate-background-color: {c.SURFACE_ALT};
        gridline-color: {c.BORDER};
        border: 1px solid {c.BORDER};
        border-radius: {Radius.SM}px;
        selection-background-color: {c.SELECTED_BG};
        selection-color: {c.TEXT_PRIMARY};
        outline: none;
    }}
    QTableView::item, QTableWidget::item {{
        padding: {Spacing.XS}px {Spacing.SM}px;
        border: none;
    }}
    QTableView::item:selected, QTableWidget::item:selected {{
        background-color: {c.SELECTED_BG};
        color: {c.TEXT_PRIMARY};
    }}
    QHeaderView::section {{
        background-color: {c.SURFACE_SUNKEN};
        color: {c.TEXT_SECONDARY};
        padding: {Spacing.XS}px {Spacing.SM}px;
        border: none;
        border-right: 1px solid {c.BORDER};
        border-bottom: 1px solid {c.BORDER_STRONG};
        min-height: {ControlSize.TABLE_HEADER_HEIGHT}px;
        font-size: {t.SIZE_TABLE_HEADER}pt;
        font-weight: {t.WEIGHT_SEMIBOLD};
    }}
    QTableCornerButton::section {{
        background-color: {c.SURFACE_SUNKEN};
        border: none;
        border-bottom: 1px solid {c.BORDER_STRONG};
    }}

    /* ==== scrollbars (subtle, modern) =================================== */
    QScrollBar:vertical {{ background: transparent; width: 12px; margin: 0; }}
    QScrollBar::handle:vertical {{
        background: {c.BORDER_STRONG}; border-radius: 6px; min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {c.TEXT_MUTED}; }}
    QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 0; }}
    QScrollBar::handle:horizontal {{
        background: {c.BORDER_STRONG}; border-radius: 6px; min-width: 30px;
    }}
    QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

    /* ==== status bar ==================================================== */
    QStatusBar {{
        background-color: {c.STATUSBAR_BG};
        border-top: 1px solid {c.STATUSBAR_BORDER};
        color: {c.STATUSBAR_TEXT};
        min-height: {ControlSize.STATUSBAR_HEIGHT}px;
    }}
    QStatusBar::item {{ border: none; }}
    QStatusBar QLabel {{
        background: transparent; color: {c.STATUSBAR_TEXT};
        font-size: {t.SIZE_STATUS}pt;
    }}
    QLabel[role="status-strong"] {{ color: {c.HEADER_TEXT}; font-weight: {t.WEIGHT_MEDIUM}; }}

    /* ==== design-system helper classes ================================== */
    QLabel[role="page-title"] {{
        font-size: {t.SIZE_PAGE_TITLE}pt; font-weight: {t.WEIGHT_BOLD};
        color: {c.TEXT_PRIMARY};
    }}
    QLabel[role="page-subtitle"] {{ color: {c.TEXT_SECONDARY}; font-size: {t.SIZE_BODY}pt; }}
    QLabel[role="section-title"] {{
        font-size: {t.SIZE_SECTION_TITLE}pt; font-weight: {t.WEIGHT_SEMIBOLD};
        color: {c.TEXT_PRIMARY};
    }}
    QLabel[role="field-label"] {{ color: {c.TEXT_SECONDARY}; font-size: {t.SIZE_LABEL}pt; }}
    QLabel[role="muted"] {{ color: {c.TEXT_MUTED}; }}
    QLabel[role="secondary"] {{ color: {c.TEXT_SECONDARY}; font-size: {t.SIZE_SECONDARY}pt; }}
    QLabel[role="error"] {{ color: {c.DANGER}; font-size: {t.SIZE_SECONDARY}pt; }}
    QLabel[role="brand-title"] {{
        font-size: {t.SIZE_BRAND_HOME}pt; font-weight: {t.WEIGHT_BOLD};
        color: {c.TEXT_PRIMARY}; letter-spacing: 1px;
    }}
    QLabel[role="brand-tagline"] {{ font-size: {t.SIZE_TAGLINE}pt; color: {c.TEXT_SECONDARY}; }}

    QFrame[role="card"] {{
        background-color: {c.SURFACE};
        border: 1px solid {c.BORDER};
        border-radius: {Radius.LG}px;
    }}
    QFrame[role="section"] {{
        background-color: {c.SURFACE};
        border: 1px solid {c.BORDER};
        border-radius: {Radius.MD}px;
    }}
    QFrame[role="divider"] {{ background-color: {c.BORDER}; max-height: 1px; min-height: 1px; }}
    QFrame[role="vline"] {{ background-color: {c.HEADER_BG_ALT}; max-width: 1px; min-width: 1px; }}
    QFrame[role="logo-placeholder"] {{
        background-color: {c.SURFACE_ALT};
        border: 2px dashed {c.BORDER_STRONG};
        border-radius: {Radius.LG}px;
    }}
    QLabel[role="logo-mark"] {{
        color: {c.PRIMARY}; font-size: 34pt; font-weight: {t.WEIGHT_BOLD};
        background: transparent;
    }}

    /* status chips */
    QLabel[chip="info"] {{
        background-color: {c.INFO_SOFT}; color: {c.INFO};
        border-radius: {Radius.PILL}px; padding: {Spacing.XXS}px {Spacing.MD}px;
        font-size: {t.SIZE_SECONDARY}pt; font-weight: {t.WEIGHT_MEDIUM};
    }}
    QLabel[chip="success"] {{
        background-color: {c.SUCCESS_SOFT}; color: {c.SUCCESS};
        border-radius: {Radius.PILL}px; padding: {Spacing.XXS}px {Spacing.MD}px;
        font-size: {t.SIZE_SECONDARY}pt; font-weight: {t.WEIGHT_MEDIUM};
    }}
    QLabel[chip="warning"] {{
        background-color: {c.WARNING_SOFT}; color: {c.WARNING};
        border-radius: {Radius.PILL}px; padding: {Spacing.XXS}px {Spacing.MD}px;
        font-size: {t.SIZE_SECONDARY}pt; font-weight: {t.WEIGHT_MEDIUM};
    }}
    QLabel[chip="danger"] {{
        background-color: {c.DANGER_SOFT}; color: {c.DANGER};
        border-radius: {Radius.PILL}px; padding: {Spacing.XXS}px {Spacing.MD}px;
        font-size: {t.SIZE_SECONDARY}pt; font-weight: {t.WEIGHT_MEDIUM};
    }}
    QLabel[chip="neutral"] {{
        background-color: {c.SURFACE_ALT}; color: {c.TEXT_SECONDARY};
        border-radius: {Radius.PILL}px; padding: {Spacing.XXS}px {Spacing.MD}px;
        font-size: {t.SIZE_SECONDARY}pt; font-weight: {t.WEIGHT_MEDIUM};
    }}

    /* empty / unavailable state */
    QLabel[role="empty-glyph"] {{
        color: {c.BORDER_STRONG}; font-size: 40pt; background: transparent;
    }}
    QLabel[role="empty-title"] {{
        color: {c.TEXT_SECONDARY}; font-size: {t.SIZE_SECTION_TITLE}pt;
        font-weight: {t.WEIGHT_SEMIBOLD};
    }}
    QLabel[role="empty-subtitle"] {{ color: {c.TEXT_MUTED}; font-size: {t.SIZE_BODY}pt; }}

    /* ==== stat / KPI tiles ============================================== */
    QFrame[role="stat"] {{
        background-color: {c.SURFACE};
        border: 1px solid {c.BORDER};
        border-left: 3px solid {c.BORDER_STRONG};
        border-radius: {Radius.MD}px;
    }}
    QFrame[role="stat"][accent="info"] {{ border-left: 3px solid {c.PRIMARY}; }}
    QFrame[role="stat"][accent="success"] {{ border-left: 3px solid {c.SUCCESS}; }}
    QFrame[role="stat"][accent="warning"] {{ border-left: 3px solid {c.WARNING}; }}
    QFrame[role="stat"][accent="danger"] {{ border-left: 3px solid {c.DANGER}; }}
    QFrame[role="stat"][accent="neutral"] {{ border-left: 3px solid {c.TEXT_MUTED}; }}
    QLabel[role="stat-label"] {{
        color: {c.TEXT_MUTED}; font-size: {t.SIZE_STAT_LABEL}pt;
    }}
    QLabel[role="stat-value"] {{
        color: {c.TEXT_PRIMARY}; font-size: {t.SIZE_STAT_VALUE}pt;
        font-weight: {t.WEIGHT_SEMIBOLD};
    }}
    QLabel[role="stat-value"][accent="success"] {{ color: {c.SUCCESS}; }}
    QLabel[role="stat-value"][accent="danger"] {{ color: {c.DANGER}; }}
    QLabel[role="stat-value"][accent="warning"] {{ color: {c.WARNING}; }}
    QLabel[role="stat-value"][accent="info"] {{ color: {c.PRIMARY}; }}

    /* ==== totals / summary ============================================== */
    QLabel[role="total-label"] {{ color: {c.TEXT_SECONDARY}; font-size: {t.SIZE_BODY}pt; }}
    QLabel[role="total-value"] {{
        color: {c.TEXT_PRIMARY}; font-size: {t.SIZE_BODY}pt;
        font-weight: {t.WEIGHT_MEDIUM};
    }}
    QFrame[role="grand-total"] {{
        background-color: {c.PRIMARY_SOFT};
        border: 1px solid {c.PRIMARY};
        border-radius: {Radius.MD}px;
    }}
    QLabel[role="grand-total-label"] {{
        color: {c.PRIMARY_PRESSED}; font-size: {t.SIZE_SECTION_TITLE}pt;
        font-weight: {t.WEIGHT_SEMIBOLD};
    }}
    QLabel[role="grand-total-value"] {{
        color: {c.PRIMARY_PRESSED}; font-size: {t.SIZE_TOTAL}pt;
        font-weight: {t.WEIGHT_BOLD};
    }}

    /* ==== bottom action bar ============================================= */
    QFrame[role="actionbar"] {{
        background-color: {c.SURFACE};
        border: 1px solid {c.BORDER};
        border-radius: {Radius.MD}px;
    }}
    QLabel[role="shortcut"] {{
        color: {c.TEXT_MUTED}; font-size: {t.SIZE_CAPTION}pt;
    }}

    /* ==== section header strip (card titles with underline) ============= */
    QLabel[role="card-title"] {{
        color: {c.TEXT_PRIMARY}; font-size: {t.SIZE_SECTION_TITLE}pt;
        font-weight: {t.WEIGHT_SEMIBOLD};
        padding-bottom: {Spacing.XS}px;
    }}

    /* ==== workspace depth (subtle tinted gradient behind cards) ========= */
    QWidget[role="workspace"] {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {c.WORKSPACE_TOP}, stop:1 {c.WORKSPACE_BOTTOM});
    }}

    /* ==== accent-topped section cards (Prompt 01E §15) ================== */
    QFrame[role="section"][accent="brand"] {{ border-top: 2px solid {c.PRIMARY}; }}
    QFrame[role="section"][accent="teal"] {{ border-top: 2px solid {c.ACCENT}; }}
    QFrame[role="section"][accent="navy"] {{ border-top: 2px solid {c.HEADER_BG}; }}
    QLabel[role="card-title"][accent="teal"] {{ color: {c.ACCENT_TEXT}; }}
    QLabel[role="card-title"][accent="brand"] {{ color: {c.PRIMARY_PRESSED}; }}

    /* ==== destructive button ============================================ */
    QPushButton[variant="danger"] {{
        background-color: {c.SURFACE}; color: {c.DANGER};
        border: 1px solid #E4B4AE;
    }}
    QPushButton[variant="danger"]:hover {{
        background-color: {c.DANGER_SOFT}; border-color: {c.DANGER}; color: {c.DANGER};
    }}
    QPushButton[variant="accent"] {{
        background-color: {c.ACCENT}; color: {c.TEXT_ON_PRIMARY};
        border: 1px solid {c.ACCENT}; font-weight: {t.WEIGHT_MEDIUM};
    }}
    QPushButton[variant="accent"]:hover {{ background-color: {c.ACCENT_HOVER}; }}

    /* ==== strong filled grand total (brand emphasis) =================== */
    QFrame[role="grand-total-strong"] {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 {c.PRIMARY}, stop:1 {c.PRIMARY_PRESSED});
        border: none; border-radius: {Radius.MD}px;
    }}
    QLabel[role="gts-label"] {{
        color: {c.TEXT_ON_PRIMARY}; font-size: {t.SIZE_SECTION_TITLE}pt;
        font-weight: {t.WEIGHT_SEMIBOLD};
    }}
    QLabel[role="gts-value"] {{
        color: {c.TEXT_ON_PRIMARY}; font-size: {t.SIZE_PAGE_TITLE}pt;
        font-weight: {t.WEIGHT_BOLD};
    }}

    /* ==== financial value colors ======================================= */
    QLabel[money="positive"] {{ color: {c.POSITIVE}; font-weight: {t.WEIGHT_SEMIBOLD}; }}
    QLabel[money="negative"] {{ color: {c.NEGATIVE}; font-weight: {t.WEIGHT_SEMIBOLD}; }}

    /* ==== menus (used by combo popups / context menus) ================== */
    QMenu {{
        background-color: {c.SURFACE}; border: 1px solid {c.BORDER};
        padding: {Spacing.XS}px;
    }}
    QMenu::item {{ padding: {Spacing.SM}px {Spacing.XL}px; border-radius: {Radius.SM}px; }}
    QMenu::item:selected {{ background-color: {c.PRIMARY_SOFT}; color: {c.PRIMARY}; }}
    QMenu::item:disabled {{ color: {c.TEXT_DISABLED}; }}
    QMenu::separator {{ height: 1px; background: {c.BORDER}; margin: {Spacing.XS}px 0; }}

    /* ==== dialogs ======================================================= */
    QDialog {{ background-color: {c.BACKGROUND}; }}
    QMessageBox {{ background-color: {c.SURFACE}; }}
    """ + _selector_styles()


def _selector_styles() -> str:
    """Search-selector chrome, kept in its widget module (lazy import)."""
    from zenith_business.ui.widgets.search_selector import selector_styles

    return selector_styles()
