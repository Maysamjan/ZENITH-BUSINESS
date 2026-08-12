"""Centralized typography system (Prompt 01G-follow-up §B, §E)."""

from __future__ import annotations

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from zenith_business.core.fonts import (  # noqa: E402
    FONT_FAMILY,
    FONT_STACK,
    load_application_fonts,
)
from zenith_business.ui.design.tokens import Typography  # noqa: E402


@pytest.fixture(autouse=True)
def _qt(qapp):
    return qapp


def test_bundled_vazirmatn_loads() -> None:
    families = load_application_fonts()
    # The bundled Persian/Latin family registers with Qt.
    assert FONT_FAMILY in families


def test_font_stack_is_centralized() -> None:
    # A single family stack drives both the app theme and the printed documents.
    assert "Vazirmatn" in FONT_STACK
    assert "Vazirmatn" in Typography.FAMILY
