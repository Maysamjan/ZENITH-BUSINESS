"""Application bootstrap and entry point (Prompt 01 §4).

Startup responsibilities are clearly separated into small steps so future stages
can extend them (license verification, richer localization, splash, etc.) at
well-defined extension points. Stage 01 does NOT implement production licensing.

Startup order:
    1. resolve + create data directories
    2. load configuration
    3. initialize logging
    4. install global exception handler
    5. initialize database infrastructure (no business tables)
    6. [extension point] license verification  -> dev provider only
    7. [extension point] localization           -> Translator
    8. create QApplication + apply theme
    9. create + show MainWindow
"""

from __future__ import annotations

import sys

from zenith_business.core.config import AppConfig, load_config
from zenith_business.core.error_handler import install_global_exception_handler
from zenith_business.core.identity import IDENTITY
from zenith_business.core.logging_setup import get_logger, setup_logging
from zenith_business.core.paths import resolve_paths
from zenith_business.database import Database, check_health
from zenith_business.security.licensing import DevelopmentLicenseProvider


class Bootstrap:
    """Headless startup steps, separated from Qt so they are unit-testable.

    Running the GUI is a thin wrapper around this (see :func:`run`). Tests can
    drive :meth:`initialize` without creating a QApplication.
    """

    def __init__(self) -> None:
        self.config: AppConfig | None = None
        self.database: Database | None = None
        self.license_provider = DevelopmentLicenseProvider()

    def initialize(self) -> AppConfig:
        """Perform non-GUI startup steps and return the loaded config."""
        # 1. data directories
        paths = resolve_paths().ensure()

        # 2. configuration
        self.config = load_config(paths)

        # 3. logging
        setup_logging(paths.logs_dir, self.config.logging)
        logger = get_logger("app")
        logger.info(
            "Starting %s (%s build) — config=%s",
            IDENTITY.full_title,
            IDENTITY.channel,
            paths.config_file,
        )

        # 4. global exception handling
        install_global_exception_handler()

        # 5. database infrastructure (connection + safety pragmas; no tables)
        self.database = Database(paths.database_file)
        health = check_health(self.database)
        if health.ok:
            logger.info("Database infrastructure ready (SQLite %s)", health.sqlite_version)
        else:
            # Not fatal for the shell, but must be visible — never silent.
            logger.error("Database infrastructure degraded: %s", health.message)

        # 6. license verification — extension point (dev provider only in Stage 01)
        logger.info("License state: %s", self.license_provider.current_state().summary)

        return self.config

    def shutdown(self) -> None:
        """Release resources acquired during startup."""
        logger = get_logger("app")
        if self.database is not None:
            self.database.close()
        logger.info("%s shut down cleanly", IDENTITY.product)


def run(argv: list[str] | None = None) -> int:
    """Create the Qt application and show the main window. Returns exit code."""
    from PyQt6.QtWidgets import QApplication

    from zenith_business.ui.design.theme import build_stylesheet
    from zenith_business.ui.main_window import MainWindow

    boot = Bootstrap()
    config = boot.initialize()

    from zenith_business.core.fonts import apply_base_font

    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(IDENTITY.product)
    app.setApplicationDisplayName(IDENTITY.product)
    app.setApplicationVersion(IDENTITY.version)
    app.setOrganizationName(IDENTITY.company)
    apply_base_font(app)  # bundled Vazirmatn — consistent EN + Dari typography
    app.setStyleSheet(build_stylesheet())

    window = MainWindow(
        config,
        database=boot.database,
        license_provider=boot.license_provider,
    )
    if config.ui.start_maximized:
        window.showMaximized()
    else:
        window.show()

    try:
        return app.exec()
    finally:
        boot.shutdown()


def main() -> None:
    """Console-script entry point."""
    raise SystemExit(run())


if __name__ == "__main__":
    main()
