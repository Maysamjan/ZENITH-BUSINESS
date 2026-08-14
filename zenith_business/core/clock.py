"""Canonical date/time storage (Stage 02 §35).

Business timestamps are stored as canonical, machine-readable **UTC ISO-8601**
strings; business dates as ``YYYY-MM-DD``. Jalali/Gregorian formatting is a
display concern handled in the UI, never in storage. This keeps the database
locale-independent and sortable.
"""

from __future__ import annotations

from datetime import date, datetime, timezone


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    """Current UTC instant as ``YYYY-MM-DDTHH:MM:SSZ``."""
    return now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")


def today_iso() -> str:
    """Today's date as ``YYYY-MM-DD`` (UTC)."""
    return now_utc().strftime("%Y-%m-%d")


def parse_iso(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None


def to_date(text: str | None) -> date | None:
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None
