"""Core importability (Prompt 01 §32)."""

from __future__ import annotations

import importlib

import pytest

CORE_MODULES = [
    "zenith_business",
    "zenith_business.app",
    "zenith_business.core.identity",
    "zenith_business.core.paths",
    "zenith_business.core.config",
    "zenith_business.core.exceptions",
    "zenith_business.core.logging_setup",
    "zenith_business.core.i18n",
    "zenith_business.core.error_handler",
    "zenith_business.database",
    "zenith_business.database.connection",
    "zenith_business.database.health",
    "zenith_business.security.passwords",
    "zenith_business.security.licensing",
    "zenith_business.ui.design.tokens",
    "zenith_business.ui.design.theme",
]


@pytest.mark.parametrize("module_name", CORE_MODULES)
def test_module_imports(module_name: str) -> None:
    assert importlib.import_module(module_name) is not None
