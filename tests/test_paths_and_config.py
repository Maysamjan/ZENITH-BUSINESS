"""Paths + configuration loading (Prompt 01 §5, §30, §32)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from zenith_business.core.config import DEFAULT_LANGUAGE, AppConfig, load_config
from zenith_business.core.exceptions import ConfigurationError
from zenith_business.core.paths import resolve_paths


def test_paths_are_separated_and_created(app_paths) -> None:
    # Business data, logs, backups, config, license live in distinct dirs (§30).
    dirs = {
        app_paths.config_dir,
        app_paths.data_dir,
        app_paths.logs_dir,
        app_paths.backups_dir,
        app_paths.license_dir,
    }
    assert len(dirs) == 5  # all distinct
    for directory in dirs:
        assert directory.exists()


def test_data_not_inside_config(app_paths) -> None:
    # Business data must not live under the config (roaming) tree.
    assert app_paths.config_dir not in app_paths.data_dir.parents


def test_load_config_creates_defaults(data_home: Path) -> None:
    paths = resolve_paths().ensure()
    assert not paths.config_file.exists()
    cfg = load_config(paths)
    assert isinstance(cfg, AppConfig)
    assert cfg.ui.language == DEFAULT_LANGUAGE
    # First run persists defaults.
    assert paths.config_file.exists()


def test_load_config_roundtrip(data_home: Path) -> None:
    paths = resolve_paths().ensure()
    cfg = load_config(paths)
    cfg.ui.language = "en"
    cfg.logging.level = "DEBUG"
    cfg.save()

    reloaded = load_config(paths)
    assert reloaded.ui.language == "en"
    assert reloaded.logging.level == "DEBUG"


def test_corrupt_config_raises(data_home: Path) -> None:
    paths = resolve_paths().ensure()
    paths.config_file.write_text("{ not valid json", encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_config(paths)


def test_unknown_language_falls_back(data_home: Path) -> None:
    paths = resolve_paths().ensure()
    paths.config_file.write_text(
        json.dumps({"ui": {"language": "zz"}}), encoding="utf-8"
    )
    cfg = load_config(paths)
    assert cfg.ui.language == DEFAULT_LANGUAGE
