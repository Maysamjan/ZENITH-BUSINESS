"""Resolving what a typed document reference means.

An operator looking up an invoice types whatever is shortest for them — ``2``,
``000002`` or the full ``SALE-000002``. All three name the SAME document, so a
lookup must resolve the *number*, not match a substring: ``LIKE '%2%'`` also hits
SALE-000012 and SALE-000020, which is why a bare number could never identify one
invoice.

This module turns a typed term into the exact document numbers it could mean,
using the live numbering scheme (prefix + zero padding) so it stays correct if
the numbering is ever reconfigured.
"""

from __future__ import annotations


def candidates(term: str, prefix: str, padding: int) -> list[str]:
    """Upper-cased document numbers ``term`` could refer to, best guess first.

    ``SALE-000002``, ``sale-2``, ``000002`` and ``2`` all yield ``SALE-000002``
    for prefix ``SALE-`` / padding 6. A term with no digits (someone searching by
    customer name) yields only itself, so the caller can fall back to a search.
    """
    text = (term or "").strip()
    if not text:
        return []
    out = [text.upper()]
    digits = "".join(ch for ch in text if ch.isdigit())
    if digits:
        number = int(digits)
        # Canonical form for the configured padding, plus the digits exactly as
        # typed (covers a document numbered before a padding change).
        out.append(f"{prefix}{number:0{max(1, int(padding))}d}".upper())
        out.append(f"{prefix}{digits}".upper())
    # Preserve order, drop duplicates.
    return list(dict.fromkeys(out))
