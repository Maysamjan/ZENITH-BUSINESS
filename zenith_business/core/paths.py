"""Windows-safe application data locations (Prompt 01 §5, §30).

Design rules:
    * Separate APPLICATION CODE from USER/BUSINESS DATA.
    * Never store writable business data inside the installed application dir.
    * Never hard-code absolute paths.
    * Keep the directory strategy documented and reliably locatable for backup.

Directory strategy
------------------
On Windows the roaming/local application-data roots are used:

    <APPDATA>\\ZenithSoft\\ZenithBusiness\\        (roaming: config, license)
    <LOCALAPPDATA>\\ZenithSoft\\ZenithBusiness\\    (local:   database, logs, backups)

We deliberately split *roaming* (small, user-portable settings and license
state) from *local* (large, machine-specific data such as the SQLite database,
logs, and backups). This mirrors standard Windows guidance and keeps business
data out of any roaming-profile sync.

On non-Windows platforms (developer machines / CI) equivalent locations under
the user's home directory are used so the code is testable everywhere. The
``ZENITH_DATA_HOME`` environment variable overrides everything, which is what
the test-suite uses to obtain an isolated sandbox.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from zenith_business.core.identity import COMPANY_NAME, PRODUCT_NAME

# Vendor/product folder segments (no spaces, registry/path friendly).
_VENDOR_DIR = "ZenithSoft"
_PRODUCT_DIR = "ZenithBusiness"

#: Environment variable that, when set, overrides all data roots with a single
#: base directory. Primarily for tests and portable/dev installs.
DATA_HOME_ENV = "ZENITH_DATA_HOME"


def _roaming_root() -> Path:
    """Base directory for small, roaming user data (config, license state)."""
    override = os.environ.get(DATA_HOME_ENV)
    if override:
        return Path(override) / "roaming"
    if os.name == "nt":
        base = os.environ.get("APPDATA")
        if base:
            return Path(base)
    # Non-Windows / fallback: ~/.config
    xdg = os.environ.get("XDG_CONFIG_HOME")
    return Path(xdg) if xdg else Path.home() / ".config"


def _local_root() -> Path:
    """Base directory for large, machine-local data (db, logs, backups)."""
    override = os.environ.get(DATA_HOME_ENV)
    if override:
        return Path(override) / "local"
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base)
    xdg = os.environ.get("XDG_DATA_HOME")
    return Path(xdg) if xdg else Path.home() / ".local" / "share"


@dataclass(frozen=True)
class AppPaths:
    """Resolved application directories.

    Instances are cheap value objects. Call :meth:`ensure` once at startup to
    create the directories on disk.
    """

    config_dir: Path
    data_dir: Path
    logs_dir: Path
    backups_dir: Path
    license_dir: Path

    @property
    def config_file(self) -> Path:
        """Primary configuration file path."""
        return self.config_dir / "config.json"

    @property
    def database_file(self) -> Path:
        """Primary business database path (created by a future stage)."""
        return self.data_dir / "zenith_business.db"

    def ensure(self) -> "AppPaths":
        """Create all directories if missing. Returns self for chaining."""
        for directory in (
            self.config_dir,
            self.data_dir,
            self.logs_dir,
            self.backups_dir,
            self.license_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        return self


def resolve_paths() -> AppPaths:
    """Compute the application's data locations without creating them."""
    roaming = _roaming_root() / _VENDOR_DIR / _PRODUCT_DIR
    local = _local_root() / _VENDOR_DIR / _PRODUCT_DIR
    return AppPaths(
        config_dir=roaming / "config",
        data_dir=local / "data",
        logs_dir=local / "logs",
        backups_dir=local / "backups",
        license_dir=roaming / "license",
    )
