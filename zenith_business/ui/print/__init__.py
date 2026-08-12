"""Printed-document architecture (Prompt 01E §16-§19).

Customer-facing print layouts, separate from the on-screen application chrome.
The A4 Sales Invoice document renders the same demonstration transaction shown
in the app. Ink-friendly (light background, restrained brand accents) and
direction-aware (English LTR / Dari RTL).
"""

from zenith_business.ui.print.invoice_document import (
    A4,
    A5,
    PAPERS,
    A4InvoiceDocument,
    InvoicePrintDocument,
    PaperSize,
    paginate,
)

__all__ = [
    "A4", "A5", "PAPERS", "A4InvoiceDocument", "InvoicePrintDocument",
    "PaperSize", "paginate",
]
