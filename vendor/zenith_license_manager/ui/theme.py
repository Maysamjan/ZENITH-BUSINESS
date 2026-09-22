"""Styling for the vendor tool — deliberately its OWN look.

Zenith Business has a locked design system; this application does not share it
and should not. Two reasons, and the second is the real one:

* it is a different product with a different audience of exactly one; and
* **it must never be mistaken for the customer application in a screenshot.**
  A vendor tool that looks like the customer's program is one careless screen
  share away from a customer seeing where licences come from.

So: a teal accent instead of Zenith Business's navy, a permanent red
confidentiality banner, and the system font rather than the bundled Vazirmatn —
this window is English-only and never shows Dari.
"""

from __future__ import annotations

STYLESHEET = """
QMainWindow, QWidget { background: #F4F7FA; color: #16212F; font-size: 10pt; }

QWidget#Header { background: #FFFFFF; border-bottom: 1px solid #D7DEE7; }
QLabel#HeaderTitle { font-size: 15pt; font-weight: 700; color: #0E7C6B; }

QLabel#KeyState { padding: 4px 10px; border-radius: 4px; font-weight: 600; }
QLabel#KeyState[state="ok"]      { color: #0E7C6B; background: #E3F5F1; }
QLabel#KeyState[state="locked"]  { color: #8A6100; background: #FFF4DC; }
QLabel#KeyState[state="missing"] { color: #A32A2A; background: #FCE8E8; }

QLabel#Warning {
    background: #FCE8E8; color: #A32A2A; border: 1px solid #F3C9C9;
    padding: 8px 20px; font-weight: 600;
}

QTabWidget::pane { border: none; }
QTabBar::tab {
    background: transparent; padding: 10px 18px; color: #5A6B7F; font-weight: 600;
}
QTabBar::tab:selected { color: #0E7C6B; border-bottom: 3px solid #0E7C6B; }

QGroupBox {
    background: #FFFFFF; border: 1px solid #D7DEE7; border-radius: 8px;
    margin-top: 14px; padding: 14px 14px 12px 14px; font-weight: 700;
    color: #0E7C6B;
}
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }

QLineEdit, QPlainTextEdit, QComboBox, QSpinBox {
    background: #FFFFFF; border: 1px solid #C8D3DF; border-radius: 6px;
    padding: 6px 8px; color: #16212F; selection-background-color: #0E7C6B;
}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 1px solid #0E7C6B;
}
QPlainTextEdit[readOnly="true"] { background: #F7FAFC; }

QPushButton {
    background: #FFFFFF; border: 1px solid #C8D3DF; border-radius: 6px;
    padding: 7px 14px; color: #16212F;
}
QPushButton:hover { border-color: #0E7C6B; color: #0E7C6B; }
QPushButton:disabled { color: #9AA8B8; border-color: #E2E8EF; }
QPushButton#GenerateButton {
    background: #0E7C6B; color: #FFFFFF; border: none; font-size: 11pt;
    font-weight: 700;
}
QPushButton#GenerateButton:hover { background: #0B6557; }
QPushButton#GenerateButton:disabled { background: #B7CFCA; }

QLabel[role="hint"] { color: #6B7A8C; font-size: 9pt; }
QLabel[role="summary"] { color: #16212F; font-weight: 600; }
QLabel[role="preview"] { color: #0E7C6B; font-weight: 700; }

QTableWidget {
    background: #FFFFFF; border: 1px solid #D7DEE7; border-radius: 6px;
    gridline-color: transparent;
}
QHeaderView::section {
    background: #EEF3F8; border: none; border-bottom: 1px solid #D7DEE7;
    padding: 7px; font-weight: 700; color: #5A6B7F;
}
QTableWidget::item:selected { background: #E3F5F1; color: #16212F; }
"""
