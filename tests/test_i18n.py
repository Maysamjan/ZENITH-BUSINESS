"""Localization + RTL/LTR direction foundation (Prompt 01 §19, §20, §32)."""

from __future__ import annotations

from zenith_business.core.config import LANG_DARI, LANG_ENGLISH
from zenith_business.core.i18n import (
    Direction,
    Translator,
    direction_for_language,
    resolve_direction,
)


def test_dari_is_rtl_english_is_ltr() -> None:
    assert direction_for_language(LANG_DARI) == Direction.RTL
    assert direction_for_language(LANG_ENGLISH) == Direction.LTR


def test_resolve_direction_override() -> None:
    # Config can force a direction regardless of language.
    assert resolve_direction(LANG_ENGLISH, "rtl") == Direction.RTL
    assert resolve_direction(LANG_DARI, "ltr") == Direction.LTR
    # 'auto' derives from language.
    assert resolve_direction(LANG_DARI, "auto") == Direction.RTL


def test_translator_switches_language() -> None:
    t = Translator(LANG_ENGLISH)
    assert t.gettext("menu.base_data") == "Base Data"
    t.set_language(LANG_DARI)
    assert t.direction == Direction.RTL
    assert t.gettext("menu.base_data") == "اطلاعات پایه"


def test_missing_key_returns_key() -> None:
    t = Translator(LANG_ENGLISH)
    assert t.gettext("does.not.exist") == "does.not.exist"


def test_unknown_language_defaults_to_dari() -> None:
    t = Translator("zz")
    assert t.language == LANG_DARI
