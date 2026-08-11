"""Centralized configuration (Prompt 01 §5).

A single, typed configuration object drives the whole application. Values come
from sensible defaults, overlaid by an optional JSON file in the user's config
directory. Configuration is *never* scattered as constants across modules, and
absolute paths are never hard-coded — path values are resolved via
:mod:`zenith_business.core.paths`.

Only foundation-relevant settings exist today. Future stages extend
:class:`AppConfig` (application identity is separate; see ``core.identity``).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from zenith_business.core.exceptions import ConfigurationError
from zenith_business.core.paths import AppPaths, resolve_paths

# Supported UI languages (foundation demonstrates two; see core.i18n).
LANG_DARI = "fa_AF"  # Dari (Afghan Persian) — Right-to-Left
LANG_ENGLISH = "en"  # English — Left-to-Right
SUPPORTED_LANGUAGES = (LANG_DARI, LANG_ENGLISH)
DEFAULT_LANGUAGE = LANG_DARI


@dataclass
class LoggingConfig:
    """Logging-related settings."""

    level: str = "INFO"
    max_bytes: int = 1_048_576  # 1 MiB per log file before rotation
    backup_count: int = 5


@dataclass
class UIConfig:
    """User-interface settings (foundation subset)."""

    language: str = DEFAULT_LANGUAGE
    # 'auto' derives direction from language; may be forced to 'rtl'/'ltr'.
    direction: str = "auto"
    start_maximized: bool = True


@dataclass
class AppConfig:
    """Root configuration object.

    ``paths`` is computed at load time and is not serialized (it depends on the
    host machine, not on user preference).
    """

    environment: str = "development"
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    ui: UIConfig = field(default_factory=UIConfig)

    # Non-serialized runtime attachments.
    paths: AppPaths = field(default_factory=resolve_paths, compare=False)

    # ---- serialization helpers -------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize user-preference fields (excludes host-specific paths)."""
        data = asdict(self)
        data.pop("paths", None)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, paths: AppPaths) -> "AppConfig":
        """Build a config from a dict, tolerating missing/extra keys."""
        try:
            logging_data = data.get("logging", {}) or {}
            ui_data = data.get("ui", {}) or {}
            cfg = cls(
                environment=str(data.get("environment", "development")),
                logging=LoggingConfig(
                    level=str(logging_data.get("level", "INFO")).upper(),
                    max_bytes=int(logging_data.get("max_bytes", 1_048_576)),
                    backup_count=int(logging_data.get("backup_count", 5)),
                ),
                ui=UIConfig(
                    language=_coerce_language(ui_data.get("language", DEFAULT_LANGUAGE)),
                    direction=str(ui_data.get("direction", "auto")),
                    start_maximized=bool(ui_data.get("start_maximized", True)),
                ),
                paths=paths,
            )
            return cfg
        except (TypeError, ValueError) as exc:
            raise ConfigurationError(f"Invalid configuration values: {exc}") from exc

    def save(self) -> None:
        """Persist user-preference fields to the config file (atomic write)."""
        target = self.paths.config_file
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        try:
            tmp.write_text(
                json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            tmp.replace(target)
        except OSError as exc:
            raise ConfigurationError(
                f"Could not write configuration to {target}: {exc}"
            ) from exc


def _coerce_language(value: Any) -> str:
    """Return a supported language code, falling back to the default."""
    text = str(value)
    return text if text in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def load_config(paths: AppPaths | None = None) -> AppConfig:
    """Load configuration, creating defaults when no file exists.

    Missing file  -> defaults are used (and written on first run).
    Corrupt file  -> :class:`ConfigurationError` (never silently ignored).
    """
    resolved = paths or resolve_paths()
    config_file: Path = resolved.config_file

    if not config_file.exists():
        cfg = AppConfig(paths=resolved)
        # Best-effort first-run write; failure here is non-fatal for startup
        # but must not be silently swallowed — surface as configuration error.
        cfg.save()
        return cfg

    try:
        raw = config_file.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigurationError(
            f"Could not read configuration file {config_file}: {exc}"
        ) from exc

    try:
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as exc:
        raise ConfigurationError(
            f"Configuration file {config_file} is not valid JSON: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise ConfigurationError(
            f"Configuration file {config_file} must contain a JSON object."
        )

    return AppConfig.from_dict(data, paths=resolved)
